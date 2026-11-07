"""Regression checks for files that define the distributable pack."""

import re
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


class PackMetadataTests(unittest.TestCase):
    def test_index_includes_every_mod_metadata_file(self):
        with (ROOT / "index.toml").open("rb") as index_file:
            index = tomllib.load(index_file)

        indexed = {entry["file"] for entry in index["files"]}
        metadata = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "mods").glob("*.pw.toml")
        }

        self.assertEqual(metadata, indexed & {path for path in indexed if path.startswith("mods/")})

    def test_credits_count_matches_mod_metadata(self):
        credits = (ROOT / "CREDITS.txt").read_text()
        match = re.search(r"The (\d+) mods below", credits)

        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), len(list((ROOT / "mods").glob("*.pw.toml"))))

    def test_e4mc_voice_chat_path_is_complete(self):
        required = {
            "e4mc.pw.toml": "qANg5Jrr",
            "simple-voice-chat.pw.toml": "9eGKb6K1",
            "voice-bridge-for-e4mc.pw.toml": "nLkVETsG",
        }

        for filename, project_id in required.items():
            with (ROOT / "mods" / filename).open("rb") as metadata_file:
                metadata = tomllib.load(metadata_file)
            self.assertEqual(metadata["update"]["modrinth"]["mod-id"], project_id)

        with (ROOT / "mods" / "voice-bridge-for-e4mc.pw.toml").open("rb") as bridge_file:
            bridge = tomllib.load(bridge_file)
        self.assertEqual(bridge["side"], "both")


if __name__ == "__main__":
    unittest.main()
