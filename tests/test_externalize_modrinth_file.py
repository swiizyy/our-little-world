import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "externalize_modrinth_file", ROOT / "scripts" / "externalize_modrinth_file.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalizeModrinthFileTests(unittest.TestCase):
    def test_replaces_bundled_mod_with_official_download(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metadata = root / "mod.pw.toml"
            metadata.write_text(
                'name = "Example"\n'
                'filename = "example.jar"\n'
                'side = "both"\n\n'
                '[download]\n'
                'url = "https://example.test/example.jar"\n'
                'hash-format = "sha512"\n'
                'hash = "abc"\n'
            )
            archive = root / "pack.mrpack"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("overrides/mods/example.jar", b"mod contents")
                package.writestr(
                    "modrinth.index.json",
                    json.dumps({"formatVersion": 1, "files": []}),
                )

            MODULE.externalize(archive, metadata)

            with zipfile.ZipFile(archive) as package:
                self.assertNotIn("overrides/mods/example.jar", package.namelist())
                manifest = json.loads(package.read("modrinth.index.json"))

            self.assertEqual(
                manifest["files"],
                [
                    {
                        "path": "mods/example.jar",
                        "hashes": {"sha512": "abc"},
                        "env": {"client": "required", "server": "required"},
                        "downloads": ["https://example.test/example.jar"],
                        "fileSize": 12,
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
