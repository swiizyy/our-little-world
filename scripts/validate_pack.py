"""Validate the locked Packwiz index and optionally verify upstream files."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import zipfile


DIRECTORIES = ("mods", "resourcepacks", "shaderpacks")
RESOURCE_PACK_DEFAULTS = "config/defaultoptions/options.txt"
HASHES = {"sha256": 64, "sha512": 128}
USER_AGENT = "swiizyy/our-little-world (Packwiz validation)"
# Exceptions are scoped to the exact upstream releases examined in docs/audit.md.
DEPENDENCY_EXCEPTIONS = {
    ("wORq9rW6", "AANobbMI", "aFVpk3tG", "v7Lw0h1m", "client"),
    ("vTN4NRGW", "AANobbMI", "bAZQdGpg", "v7Lw0h1m", "client"),
    ("okecULrz", "mOgUt4GM", None, None, "server"),
    ("RUBpNu00", "1vrSzlao", None, None, "client"),
}
GAME_VERSION_EXCEPTIONS = {("j3SeQVjR", "26.3")}


def read_toml(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def safe_path(name):
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts) or re.search(r'[\\:<>|?*"\x00-\x1f]', name):
        raise ValueError(f"Invalid pack path: {name!r}")
    return PurePosixPath(name)


def check_hash(data, algorithm, expected, label):
    if algorithm not in HASHES or not re.fullmatch(r"[0-9a-f]+", expected) or len(expected) != HASHES[algorithm]:
        raise ValueError(f"{label}: invalid {algorithm} digest")
    if data is not None and hashlib.new(algorithm, data).hexdigest() != expected:
        raise ValueError(f"{label}: {algorithm} hash mismatch")


def load_pack(root):
    pack_path = root / "pack.toml"
    pack = read_toml(pack_path)
    for key in ("minecraft", "fabric"):
        if not pack["versions"][key]:
            raise ValueError(f"Missing {key} version")
    index = pack["index"]
    index_path = root / safe_path(index["file"])
    check_hash(index_path.read_bytes(), index["hash-format"], index["hash"], index_path.name)
    contents = read_toml(index_path)
    indexed, installed, projects, mods = set(), set(), set(), {}
    for entry in contents["files"]:
        name = entry["file"]
        path = safe_path(name)
        if name.casefold() in indexed:
            raise ValueError(f"Duplicate index path: {name}")
        indexed.add(name.casefold())
        file = root / path
        check_hash(file.read_bytes(), entry.get("hash-format", contents["hash-format"]), entry["hash"], name)
        if name in ("CREDITS.txt", RESOURCE_PACK_DEFAULTS) and not entry.get("metafile"):
            continue
        if path.parts[0] not in DIRECTORIES or len(path.parts) != 2 or not entry.get("metafile") or not name.endswith(".pw.toml"):
            raise ValueError(f"{name}: expected a sided Packwiz metafile in {DIRECTORIES}")
        item = read_toml(file)
        filename = safe_path(item["filename"])
        if len(filename.parts) != 1 or item["side"] not in ("client", "server", "both"):
            raise ValueError(f"{name}: invalid filename or side")
        if path.parts[0] != "mods" and item["side"] != "client":
            raise ValueError(f"{name}: visual assets must be client-side")
        target = str(path.parent / filename)
        if target.casefold() in installed:
            raise ValueError(f"Duplicate installation path: {target}")
        installed.add(target.casefold())
        download = item["download"]
        url = urlsplit(download["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError(f"{name}: an HTTPS download URL is required")
        check_hash(None, download["hash-format"], download["hash"], name)
        for provider, metadata in item.get("update", {}).items():
            if provider == "modrinth":
                project, version = (metadata[key] for key in ("mod-id", "version"))
                if not all(isinstance(value, str) and re.fullmatch(r"[\da-zA-Z]{8}", value) for value in (project, version)):
                    raise ValueError(f"{name}: invalid Modrinth IDs")
            elif provider == "curseforge":
                project, version = (metadata[key] for key in ("project-id", "file-id"))
                if not all(type(value) is int and value > 0 for value in (project, version)):
                    raise ValueError(f"{name}: invalid CurseForge IDs")
            else:
                raise ValueError(f"{name}: unsupported update provider {provider}")
            identity = (provider, project)
            if identity in projects:
                raise ValueError(f"{name}: duplicate project {identity}")
            projects.add(identity)
        mods[name] = item
    on_disk = {file.relative_to(root).as_posix().casefold()
               for directory in DIRECTORIES for file in (root / directory).rglob("*")
               if file.is_file()}
    indexed = {name for name in indexed if name.split("/")[0] in DIRECTORIES}
    if on_disk != indexed:
        raise ValueError(f"Unindexed paths: {', '.join(sorted(on_disk - indexed))}")
    return pack, mods


def request(url):
    response = urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60)
    if urlsplit(response.url).scheme != "https":
        response.close()
        raise ValueError(f"Download redirected away from HTTPS: {url}")
    return response


def applicable(item, side):
    return item["side"] in ("both", side)


def check_dependencies(name, item, version, projects, version_projects):
    errors = []
    for dependency in version["dependencies"]:
        kind = dependency["dependency_type"]
        version_id = dependency["version_id"]
        project_id = dependency["project_id"] or version_projects.get(version_id)
        if kind not in ("required", "incompatible") or not project_id:
            continue
        target = projects.get(project_id)
        for side in ("client", "server"):
            if not applicable(item, side):
                continue
            present = target and applicable(target, side)
            locked = target["update"]["modrinth"]["version"] if present else None
            if (version["id"], project_id, version_id, locked, side) in DEPENDENCY_EXCEPTIONS:
                continue
            same_version = present and (not version_id or locked == version_id)
            if (kind == "required" and not same_version) or (kind == "incompatible" and same_version):
                errors.append(f"{name}: {side} has unsatisfied {kind} dependency {project_id} ({version_id or 'any version'})")
    return errors


def fabric_metadata(jar):
    with zipfile.ZipFile(jar) as archive:
        if "fabric.mod.json" not in archive.namelist():
            return []
        # Fabric accepts literal control characters within strings in some manifests.
        metadata = json.loads(archive.read("fabric.mod.json"), strict=False)
        embedded = [child for entry in metadata.get("jars", [])
                    for child in fabric_metadata(io.BytesIO(archive.read(entry["file"])))]
        return [metadata, *embedded]


def check_fabric_sides(items, fabric):
    errors = []
    for name, records in fabric.items():
        environment = records[0].get("environment", "*")
        for side in ("client", "server"):
            if applicable(items[name], side) and environment not in ("*", side):
                errors.append(f"{name}: Fabric declares {environment}, but Packwiz installs it on {side}")
    for side in ("client", "server"):
        selected = {name: records for name, records in fabric.items() if applicable(items[name], side)}
        top_level = [records[0]["id"] for records in selected.values()]
        if len(set(top_level)) != len(top_level):
            errors.append(f"Duplicate top-level Fabric mod ID on {side}")
        provided = {"java", "minecraft", "fabricloader"}
        for records in selected.values():
            for record in records:
                if record.get("environment", "*") in ("*", side):
                    provided.update([record["id"], *record.get("provides", [])])
        for name, records in selected.items():
            for dependency in sorted(records[0].get("depends", {}).keys() - provided):
                errors.append(f"{name}: missing Fabric dependency {dependency} on {side}")
    return errors


def verify_online(pack, items):
    projects = {item["update"]["modrinth"]["mod-id"]: item for item in items.values()
                if "modrinth" in item.get("update", {})}
    version_ids = [item["update"]["modrinth"]["version"] for item in projects.values()]
    with request("https://api.modrinth.com/v2/versions?" + urlencode({"ids": json.dumps(version_ids)})) as response:
        versions = {version["id"]: version for version in json.load(response)}
    version_projects = {key: version["project_id"] for key, version in versions.items()}
    unresolved = {dep["version_id"] for version in versions.values() for dep in version["dependencies"]
                  if dep["version_id"] and not dep["project_id"] and dep["version_id"] not in version_projects}
    if unresolved:
        with request("https://api.modrinth.com/v2/versions?" + urlencode({"ids": json.dumps(sorted(unresolved))})) as response:
            version_projects.update({version["id"]: version["project_id"] for version in json.load(response)})

    def verify(entry):
        name, item = entry
        download = item["download"]
        try:
            modrinth = item.get("update", {}).get("modrinth")
            errors = []
            if modrinth:
                version = versions[modrinth["version"]]
                compatible_game = (pack["versions"]["minecraft"] in version["game_versions"] or
                                   (version["id"], pack["versions"]["minecraft"]) in GAME_VERSION_EXCEPTIONS)
                if (version["project_id"] != modrinth["mod-id"] or not compatible_game or
                        (name.startswith("mods/") and "fabric" not in version["loaders"])):
                    errors.append(f"{name}: Modrinth project, Minecraft version or loader mismatch")
                if not any(file["url"] == download["url"] and file["filename"] == item["filename"]
                           and file["hashes"].get(download["hash-format"]) == download["hash"]
                           for file in version["files"]):
                    errors.append(f"{name}: locked file differs from Modrinth metadata")
                errors.extend(check_dependencies(name, item, version, projects, version_projects))
            with request(download["url"]) as response:
                if name.startswith("mods/"):
                    jar = response.read()
                    check_hash(jar, download["hash-format"], download["hash"], name)
                    records = fabric_metadata(io.BytesIO(jar))
                    if not records:
                        errors.append(f"{name}: no fabric.mod.json in mod archive")
                    return errors, records
                digest = hashlib.file_digest(response, download["hash-format"]).hexdigest()
                if digest != download["hash"]:
                    errors.append(f"{name}: downloaded file hash mismatch")
            return errors, []
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
            return [f"{name}: {error}"], []

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(verify, items.items()))
    fabric = {name: records for name, (_, records) in zip(items, results) if records}
    return [error for errors, _ in results for error in errors] + check_fabric_sides(items, fabric)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    try:
        pack, items = load_pack(Path.cwd())
        errors = verify_online(pack, items) if args.online else []
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Pack validation failed: {error}") from None
    if errors:
        raise SystemExit("Pack validation failed:\n- " + "\n- ".join(errors))
    print(f"Validated {len(items)} locked files for Minecraft {pack['versions']['minecraft']}, "
          f"Fabric {pack['versions']['fabric']} ({'online' if args.online else 'local'}).")


if __name__ == "__main__":
    main()
