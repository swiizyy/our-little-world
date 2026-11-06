import configparser
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VisualOverridesTest(unittest.TestCase):
    def test_inventory_hud_is_compact_and_subtle(self):
        config = json.loads((ROOT / "config/inventoryhud.json").read_text())

        self.assertEqual(config["invMini"], True)
        self.assertEqual(config["invAlpha"], 45)
        self.assertEqual(config["invHideBG"], True)

    def test_jei_lists_use_compact_pack_defaults(self):
        config = configparser.ConfigParser()
        with (ROOT / "config/jei/client/default/jei-client.ini").open() as file:
            config.read_file(file)

        self.assertEqual(config.getint("ingredientList", "maxColumns"), 6)
        self.assertEqual(config.getint("bookmarkList", "maxColumns"), 6)


if __name__ == "__main__":
    unittest.main()
