"""Replace a bundled Packwiz file with its authorized external download."""

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def externalize(archive_path: Path, metadata_path: Path) -> None:
    """Move one bundled mod out of an MRPACK and into its index manifest."""
    with metadata_path.open("rb") as metadata_file:
        metadata = tomllib.load(metadata_file)

    download = metadata["download"]
    filename = metadata["filename"]
    archive_member = f"overrides/mods/{filename}"
    manifest_path = f"mods/{filename}"
    side = metadata["side"]
    environment = {
        "client": "required" if side in {"client", "both"} else "unsupported",
        "server": "required" if side in {"server", "both"} else "unsupported",
    }

    with zipfile.ZipFile(archive_path) as source:
        try:
            bundled_file = source.getinfo(archive_member)
        except KeyError as error:
            raise ValueError(f"Expected bundled file {archive_member!r}") from error

        manifest = json.loads(source.read("modrinth.index.json"))
        if any(file["path"] == manifest_path for file in manifest["files"]):
            raise ValueError(f"Manifest already contains {manifest_path!r}")

        manifest["files"].append(
            {
                "path": manifest_path,
                "hashes": {download["hash-format"]: download["hash"]},
                "env": environment,
                "downloads": [download["url"]],
                "fileSize": bundled_file.file_size,
            }
        )

        with tempfile.NamedTemporaryFile(
            suffix=".mrpack", dir=archive_path.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        try:
            with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    if entry.filename == archive_member:
                        continue
                    if entry.filename == "modrinth.index.json":
                        target.writestr(
                            entry,
                            json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n",
                        )
                    else:
                        target.writestr(entry, source.read(entry.filename))
            shutil.move(temporary_path, archive_path)
        finally:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("metadata", type=Path)
    arguments = parser.parse_args()
    externalize(arguments.archive, arguments.metadata)


if __name__ == "__main__":
    main()
