"""Check or deploy a stable GitHub release from the Docker host."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
RELEASES = "https://github.com/swiizyy/our-little-world/releases"
RAW = "https://raw.githubusercontent.com/swiizyy/our-little-world"
STABLE_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)+")
DATA = ROOT / "data"
PACK_ENV = ROOT / ".pack.env"
BACKUPS = ROOT / "backups"


def fetch(url):
    with urlopen(url, timeout=60) as response:
        return response.read()


def stable_manifest(tag=None):
    if tag and not STABLE_TAG.fullmatch(tag):
        raise ValueError("Select a stable vMAJOR.MINOR.PATCH tag")
    assets = f"download/{tag}" if tag else "latest/download"
    manifest = json.loads(fetch(f"{RELEASES}/{assets}/pack-manifest.json"))
    release_tag = manifest["tag"]
    if (manifest["channel"] != "release" or not STABLE_TAG.fullmatch(release_tag) or
            (tag and release_tag != tag) or release_tag != f"v{manifest['version']}" or
            not re.fullmatch(r"[0-9a-f]{40}", manifest["commit"])):
        raise ValueError("Unexpected stable release manifest")
    url = f"{RAW}/{manifest['commit']}/pack.toml"
    if manifest["packwiz_url"] != url:
        raise ValueError("Packwiz URL must point to the release commit")
    content = fetch(url)
    if hashlib.sha256(content).hexdigest() != manifest["packwiz_sha256"]:
        raise ValueError("Packwiz descriptor failed SHA-256 verification")
    pack = tomllib.loads(content.decode())
    if pack["version"] != manifest["version"] or pack["versions"] != manifest["versions"]:
        raise ValueError("Packwiz descriptor disagrees with the release manifest")
    if not all(VERSION.fullmatch(pack["versions"][key]) for key in ("minecraft", "fabric")):
        raise ValueError("Unexpected Minecraft or Fabric version")
    return manifest


def compose(*args, overrides=None):
    env = os.environ.copy()
    for key in ("PACKWIZ_URL", "MINECRAFT_VERSION", "FABRIC_LOADER_VERSION", "DATA_DIRECTORY"):
        env.pop(key, None)
    config = ["--env-file", ".env"]
    if PACK_ENV.exists():
        config += ["--env-file", PACK_ENV.name]
    env["DATA_DIRECTORY"] = str(DATA)
    env.update(overrides or {})
    return subprocess.run(["docker", "compose", *config, *args], cwd=ROOT, env=env,
                          check=True, stdout=subprocess.PIPE if args[0] == "ps" else None, text=True)


def require_stopped():
    # Supply a placeholder for project discovery before the first deployment.
    output = compose("ps", "--all", "--format", "json",
                     overrides={"PACKWIZ_URL": f"{RAW}/dev/pack.toml"}).stdout.strip()
    containers = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.splitlines()]
    if any(container["State"] not in ("created", "exited", "dead") for container in containers):
        raise ValueError("Server is running. Schedule a maintenance window and stop it before applying or restoring.")


def snapshot():
    BACKUPS.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="snapshot-", dir=BACKUPS))
    if DATA.exists():
        shutil.copytree(DATA, backup / "data", symlinks=True)
    if PACK_ENV.exists():
        shutil.copy2(PACK_ENV, backup / PACK_ENV.name)
    (backup / "complete").touch()
    print(f"Snapshot: {backup}", flush=True)
    return backup


def restore(backup):
    if not (backup / "complete").is_file():
        raise ValueError("Select a complete snapshot")
    # Prepare a copy before moving the live data. Keep the snapshot for retries.
    recovery = Path(tempfile.mkdtemp(prefix="recovery-", dir=BACKUPS))
    if (backup / "data").exists():
        shutil.copytree(backup / "data", recovery / "restored", symlinks=True)
    if DATA.exists():
        DATA.rename(recovery / "previous-data")
    if (recovery / "restored").exists():
        (recovery / "restored").rename(DATA)
    if PACK_ENV.exists():
        PACK_ENV.rename(recovery / PACK_ENV.name)
    if (backup / PACK_ENV.name).exists():
        shutil.copy2(backup / PACK_ENV.name, PACK_ENV)
    print(f"Restored {backup}. Previous data retained in {recovery}.", flush=True)


def deploy(manifest):
    releases = {"PACKWIZ_URL": manifest["packwiz_url"],
                "MINECRAFT_VERSION": manifest["versions"]["minecraft"],
                "FABRIC_LOADER_VERSION": manifest["versions"]["fabric"]}
    content = "".join(f"{key}={value}\n" for key, value in releases.items())
    if PACK_ENV.exists() and PACK_ENV.read_text() == content:
        print(f"{manifest['tag']} is already selected.")
        return
    require_stopped()
    if DATA.is_symlink() or (DATA / "mods").is_symlink():
        raise ValueError("Use a local data directory and a local mods directory")
    if (DATA / "mods").exists() and any((DATA / "mods").iterdir()) and not (DATA / "packwiz.json").is_file():
        raise ValueError("Migrate the existing unmanaged mods directory before deploying")
    compose("config", "--quiet", overrides=releases)
    backup = snapshot()
    with tempfile.TemporaryDirectory(prefix="preflight-", dir=BACKUPS) as scratch:
        # One-off containers have no published gameplay ports or access to live data.
        compose("run", "--rm", "--no-deps", "-T", "-e", "SETUP_ONLY=TRUE", "minecraft",
                overrides={**releases, "DATA_DIRECTORY": scratch})
    try:
        compose("up", "-d", "--wait", "--wait-timeout", "600", overrides=releases)
        pending = PACK_ENV.with_suffix(".env.next")
        pending.write_text(content, encoding="ascii")
        pending.replace(PACK_ENV)
    except (OSError, subprocess.CalledProcessError, KeyboardInterrupt):
        compose("stop", overrides=releases)
        restore(backup)
        if PACK_ENV.exists():
            compose("up", "-d", "--wait", "--wait-timeout", "600")
        raise
    print(f"Deployed {manifest['tag']}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "apply"):
        commands.add_parser(command).add_argument("--tag")
    commands.add_parser("restore").add_argument("snapshot", type=Path)
    args = parser.parse_args()
    if args.command == "check":
        release = stable_manifest(args.tag)
        print(f"{release['tag']} {release['packwiz_url']}")
        return
    lock = ROOT / ".deploy-lock"
    lock.mkdir()
    try:
        if args.command == "apply":
            deploy(stable_manifest(args.tag))
        else:
            require_stopped()
            backup = args.snapshot.resolve()
            if backup.parent != BACKUPS or not backup.name.startswith("snapshot-"):
                raise ValueError("Select a snapshot in server/backups/")
            restore(backup)
    finally:
        lock.rmdir()


if __name__ == "__main__":
    try:
        main()
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Deployment stopped: {error}") from None
