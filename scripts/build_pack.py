"""Export and verify the Modrinth archive and write release artifacts."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import unquote
import zipfile

from generate_release_notes import git_output, generate_release_notes
from validate_pack import RESOURCE_PACK_DEFAULTS, load_pack, applicable, safe_path


VERSION_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-((?:alpha|beta)(?:\.[0-9A-Za-z-]+)*))?")


def release_channel(tag, version):
    if not tag:
        return "development"
    match = VERSION_TAG.fullmatch(tag)
    if not match or tag != f"v{version}":
        raise ValueError(f"Tag {tag} must match pack.toml version {version} (stable, alpha or beta)")
    prerelease = match.group(4)
    return prerelease.split(".")[0] if prerelease else "release"


def export_pack(root, output, pack, items):
    with tempfile.TemporaryDirectory() as temporary:
        exported = Path(temporary) / "export.mrpack"
        subprocess.run(
            ["packwiz", "modrinth", "export", "--restrictDomains=false", "--output", str(exported)],
            check=True, cwd=root,
        )
        with zipfile.ZipFile(exported) as source:
            if source.testzip() is not None:
                raise ValueError("Packwiz produced a corrupt archive")
            members = set(source.namelist())
            allowed = {"modrinth.index.json", "overrides/", "overrides/CREDITS.txt",
                       "overrides/LICENSE-Ore-Borders.txt", f"overrides/{RESOURCE_PACK_DEFAULTS}"}
            if members - allowed:
                raise ValueError(f"Unexpected bundled files: {sorted(members - allowed)}")
            index = json.loads(source.read("modrinth.index.json"))
            expected_versions = {"minecraft": pack["versions"]["minecraft"],
                                 "fabric-loader": pack["versions"]["fabric"]}
            if index["dependencies"] != expected_versions or index["versionId"] != pack["version"]:
                raise ValueError("Exported Minecraft, Fabric or pack version differs from pack.toml")
            expected = {f"{Path(name).parent.as_posix()}/{item['filename']}": item
                        for name, item in items.items()}
            for entry in index["files"]:
                item = expected.pop(entry["path"])
                download = item["download"]
                sides = {side: "required" if applicable(item, side) else "unsupported"
                         for side in ("client", "server")}
                if (entry["env"] != sides or entry["fileSize"] <= 0 or
                        list(map(unquote, entry["downloads"])) != [unquote(download["url"])] or
                        not all(re.fullmatch(pattern, entry["hashes"].get(algorithm, ""))
                                for algorithm, pattern in (("sha1", "[0-9a-f]{40}"), ("sha512", "[0-9a-f]{128}"))) or
                        (download["hash-format"] == "sha512" and entry["hashes"]["sha512"] != download["hash"])):
                    raise ValueError(f"Invalid exported record: {entry['path']}")
            if expected:
                raise ValueError(f"Export is missing files: {', '.join(expected)}")
            defaults = subprocess.check_output(["git", "ls-files", "-z", "--", "config/", "defaultconfigs/"],
                                               cwd=root).decode().split("\0")
            with (zipfile.ZipFile(output / "our-little-world.mrpack", "w", zipfile.ZIP_DEFLATED) as archive,
                  zipfile.ZipFile(output / "client-defaults.zip", "w", zipfile.ZIP_DEFLATED) as client):
                for entry in source.infolist():
                    if entry.filename != f"overrides/{RESOURCE_PACK_DEFAULTS}":
                        archive.writestr(entry, source.read(entry))
                for name in filter(None, defaults):
                    file = root / safe_path(name)
                    contents = file.read_bytes().replace(b"\r\n", b"\n")
                    archive.writestr(f"client-overrides/{name}", contents)
                    client.writestr(name, contents)


def mod_changes(base, items):
    old_paths = git_output("ls-tree", "-r", "--name-only", base, "--", "mods/").splitlines() if base else []
    old = {path for path in old_paths if path.endswith(".pw.toml")}
    current = {path for path in items if path.startswith("mods/")}
    updated = []
    for path in sorted(current & old):
        if subprocess.check_output(["git", "show", f"{base}:{path}"]) != Path(path).read_bytes():
            updated.append(path)
    return {"added": sorted(current - old), "removed": sorted(old - current), "updated": updated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--tag", default="")
    parser.add_argument("--base")
    parser.add_argument("--export-only", action="store_true", help="Skip upstream metadata recheck; verify the export")
    args = parser.parse_args()
    root = Path.cwd()
    pack, items = load_pack(root)
    channel = release_channel(args.tag, pack["version"])
    if not args.export_only:
        from validate_pack import verify_online
        errors = verify_online(pack, items)
        if errors:
            raise SystemExit("Pack validation failed:\n- " + "\n- ".join(errors))
    args.output.mkdir(parents=True, exist_ok=True)
    export_pack(root, args.output, pack, items)
    commit = git_output("rev-parse", "HEAD")
    pack_url = f"https://raw.githubusercontent.com/swiizyy/our-little-world/{commit}/pack.toml"
    if args.tag and subprocess.check_output(["git", "show", "HEAD:pack.toml"]) != (root / "pack.toml").read_bytes():
        raise ValueError("Release pack.toml must be committed")
    base = args.base
    if base is None:
        previous = subprocess.run(["git", "describe", "--tags", "--abbrev=0", "HEAD^"], capture_output=True, text=True)
        base = previous.stdout.strip()
    changes = mod_changes(base, items)
    manifest = {
        "version": pack["version"], "versions": pack["versions"], "tag": args.tag,
        "channel": channel, "commit": commit, "packwiz_url": pack_url,
        "packwiz_sha256": hashlib.sha256((root / "pack.toml").read_bytes()).hexdigest(),
        "client_defaults_sha256": hashlib.sha256((args.output / "client-defaults.zip").read_bytes()).hexdigest(),
        "locked_files": len(items), "mods": changes,
    }
    (args.output / "pack-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    notes = generate_release_notes(commit) + "\n## Mod changes\n\n"
    for label, paths in changes.items():
        notes += f"- {label.capitalize()} — {', '.join(Path(path).name.removesuffix('.pw.toml') for path in paths) or 'none'}\n"
    notes += (f"\n## Install or update\n\n"
              f"- Minecraft {pack['versions']['minecraft']} · Fabric {pack['versions']['fabric']}\n"
              f"- [Packwiz for this commit]({pack_url})\n"
              f"- [Windows and Docker guides / Guides Windows et Docker]"
              f"(https://github.com/swiizyy/our-little-world/tree/{commit}/docs)\n")
    (args.output / "release-notes.md").write_text(notes, encoding="utf-8")


if __name__ == "__main__":
    main()
