#!/usr/bin/env python3
"""Synchronize Modrinth mod versions with a compatible Fabulously Optimized release."""

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        sys.exit("Python 3.11+ or `python3 -m pip install -r scripts/requirements.txt` is required.")

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.modrinth.com/v2"
USER_AGENT = "swiizyy/our-little-world sync-fabulously-optimized"
PROJECT = "fabulously-optimized"
MODRINTH_URL = re.compile(
    r"^https://cdn\.modrinth\.com/data/([A-Za-z0-9]+)/versions/([A-Za-z0-9]+)/"
)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def load_toml(path):
    with path.open("rb") as file:
        return tomllib.load(file)


def upstream_mods(pack):
    versions = pack["versions"]
    query = urllib.parse.urlencode({
        "game_versions": json.dumps([versions["minecraft"]]),
        "loaders": json.dumps(["fabric"]),
        "include_changelog": "false",
    })
    releases = json.loads(fetch(f"{API}/project/{PROJECT}/version?{query}"))
    releases.sort(key=lambda version: version["date_published"], reverse=True)
    if not releases:
        raise ValueError(f"No Fabulously Optimized release for Minecraft {versions['minecraft']} and Fabric")

    for release in releases:
        primary = [file for file in release["files"] if file["primary"]]
        if len(primary) != 1 or not primary[0]["filename"].endswith(".mrpack"):
            raise ValueError(f"Release {release['version_number']} has no unique primary .mrpack")
        file = primary[0]
        data = fetch(file["url"])
        if hashlib.sha512(data).hexdigest() != file["hashes"]["sha512"]:
            raise ValueError(f"Checksum mismatch for Fabulously Optimized {release['version_number']}")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("modrinth.index.json"))
        dependencies = manifest["dependencies"]
        if (dependencies.get("minecraft") != versions["minecraft"]
                or dependencies.get("fabric-loader") != versions["fabric"]):
            continue
        mods = {}
        for item in manifest["files"]:
            if not item["path"].startswith("mods/") or not item["path"].endswith(".jar"):
                continue
            matches = [MODRINTH_URL.match(url) for url in item["downloads"]]
            matches = [match for match in matches if match]
            if not matches or len({match.groups() for match in matches}) != 1:
                raise ValueError(f"Unsupported or ambiguous mod downloads: {item['path']}")
            project_id, version_id = matches[0].groups()
            if project_id in mods:
                raise ValueError(f"Duplicate Modrinth project in upstream pack: {project_id}")
            mods[project_id] = (version_id, item["hashes"]["sha512"])
        if not mods:
            raise ValueError("Upstream pack contains no indexed mods")
        return release, mods
    raise ValueError(
        f"No Fabulously Optimized release matches Minecraft {versions['minecraft']} "
        f"and Fabric {versions['fabric']}"
    )


def read_mods(directory):
    mods = {}
    for path in sorted(directory.glob("*.pw.toml")):
        metadata = load_toml(path)
        modrinth = metadata.get("update", {}).get("modrinth")
        if modrinth is None:
            continue
        project_id = modrinth["mod-id"]
        if project_id in mods:
            raise ValueError(f"Duplicate Modrinth project {project_id}: {path}")
        mods[project_id] = (path, metadata)
    return mods


def run_packwiz(directory, *arguments):
    result = subprocess.run(
        ["packwiz", *arguments],
        cwd=directory,
        input="n\n" * 100,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"packwiz {' '.join(arguments)} failed:\n{result.stdout}")
    return result.stdout


def sync():
    if shutil.which("packwiz") is None:
        raise RuntimeError("Packwiz is not installed or is not in PATH")
    pack = load_toml(ROOT / "pack.toml")
    if "fabric" not in pack["versions"]:
        raise ValueError("The pack must use Fabric")
    release, wanted = upstream_mods(pack)
    original = read_mods(ROOT / "mods")
    print(f"Fabulously Optimized {release['version_number']} ({release['id']})")
    changes = {}
    for project, (version, checksum) in wanted.items():
        existing = original.get(project)
        if existing:
            metadata = existing[1]
            if (metadata["update"]["modrinth"]["version"] == version
                    and metadata["download"]["hash-format"] == "sha512"
                    and metadata["download"]["hash"] == checksum):
                continue
        changes[project] = (version, checksum)
    retained = sorted(set(original) - set(wanted))
    if retained:
        print(f"Keeping {len(retained)} local Modrinth mod(s) not present upstream.")
    if not changes:
        print(f"All {len(wanted)} upstream mods are already synchronized.")
        return

    print(f"Preparing {len(changes)} mod addition(s) or update(s).")
    with tempfile.TemporaryDirectory(prefix="packwiz-fo-sync-") as tmp:
        stage = Path(tmp)
        shutil.copy2(ROOT / "pack.toml", stage / "pack.toml")
        shutil.copy2(ROOT / "index.toml", stage / "index.toml")
        shutil.copytree(ROOT / "mods", stage / "mods")
        run_packwiz(stage, "refresh")
        for project, (version, _) in changes.items():
            print(f"  {project}: {version}", flush=True)
            run_packwiz(stage, "modrinth", "install", "--project-id", project, "--version-id", version)
        staged = read_mods(stage / "mods")
        for project, (version, checksum) in wanted.items():
            if project not in staged:
                raise ValueError(f"Packwiz did not install project {project}")
            metadata = staged[project][1]
            if (metadata["update"]["modrinth"]["version"] != version
                    or metadata["download"]["hash-format"] != "sha512"
                    or metadata["download"]["hash"] != checksum):
                raise ValueError(f"Packwiz metadata does not match upstream for project {project}")
        for project in set(original) - set(changes):
            path, _ = original[project]
            staged_path = stage / "mods" / path.name
            if not staged_path.is_file() or staged_path.read_bytes() != path.read_bytes():
                raise ValueError(f"Packwiz unexpectedly modified local mod {path.name}")
        if set(staged) != set(original) | set(wanted):
            raise ValueError("Packwiz unexpectedly added or removed Modrinth projects")

        updates = {}
        removals = set()
        for project in changes:
            new_path = staged[project][0]
            destination = ROOT / "mods" / new_path.name
            old_path = original[project][0] if project in original else None
            if destination.exists() and destination != old_path:
                raise ValueError(f"Refusing to overwrite existing file: {destination}")
            if destination in updates:
                raise ValueError(f"Multiple projects would write to {destination}")
            updates[destination] = new_path.read_bytes()
            if old_path and old_path != destination:
                removals.add(old_path)
        touched = set(updates) | removals | {ROOT / "pack.toml", ROOT / "index.toml"}
        backups = {path: path.read_bytes() if path.exists() else None for path in touched}
        try:
            for path, data in updates.items():
                path.write_bytes(data)
            for path in removals:
                path.unlink()
            run_packwiz(ROOT, "refresh")
        except Exception:
            for path, data in backups.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(data)
            raise
    print(f"Synchronized {len(wanted)} upstream mods; local-only mods were retained.")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        sync()
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            zipfile.BadZipFile, urllib.error.URLError, RuntimeError) as error:
        sys.exit(f"Synchronization failed: {error}")


if __name__ == "__main__":
    main()
