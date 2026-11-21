import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_pack import release_channel
from validate_pack import RESOURCE_PACK_DEFAULTS, check_dependencies, check_fabric_sides, load_pack

spec = importlib.util.spec_from_file_location("deploy", ROOT / "server/deploy.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DistributionTests(unittest.TestCase):
    def test_checkout_has_a_valid_index_and_no_unsided_configs(self):
        pack, items = load_pack(ROOT)
        self.assertEqual(pack["versions"]["fabric"], "0.20.1")
        self.assertEqual(items["mods/zoomify.pw.toml"]["side"], "client")
        self.assertTrue(all(not name.startswith("config/") for name in items))

    def test_resource_packs_are_seeded_in_priority_order(self):
        _, items = load_pack(ROOT)
        self.assertEqual(items["mods/default-options.pw.toml"]["side"], "client")
        index = tomllib.loads((ROOT / "index.toml").read_text(encoding="utf-8"))
        self.assertIn(RESOURCE_PACK_DEFAULTS, [entry["file"] for entry in index["files"]])
        options = dict(line.split(":", 1) for line in
                       (ROOT / RESOURCE_PACK_DEFAULTS).read_text(encoding="utf-8").splitlines())
        self.assertEqual(set(options), {"version", "resourcePacks"})
        expected = ["vanilla", "fabric"]
        for pack in ("faithful-64x", "ore-borders-64x", "faithful-64x-clear-glass",
                     "visual-waxed-copper-items-64x"):
            expected.append(f"file/{items[f'resourcepacks/{pack}.pw.toml']['filename']}")
        self.assertEqual(json.loads(options["resourcePacks"]), expected)

    def test_release_requires_the_exact_committed_version(self):
        self.assertEqual(release_channel("v1.2.3", "1.2.3"), "release")
        self.assertEqual(release_channel("v1.2.3-beta.1", "1.2.3-beta.1"), "beta")
        with self.assertRaises(ValueError):
            release_channel("v1.2.3", "1.2.2")

    def test_required_modrinth_dependency_must_be_on_the_same_side(self):
        requires = {"id": "test", "dependencies": [
            {"dependency_type": "required", "project_id": "library", "version_id": None},
        ]}
        projects = {"library": {"side": "client", "update": {"modrinth": {"version": "1"}}}}
        errors = check_dependencies("mod", {"side": "both"}, requires, projects, {})
        self.assertEqual(len(errors), 1)
        self.assertIn("server", errors[0])

    def test_fabric_counts_embedded_dependencies(self):
        items = {"example": {"side": "both"}}
        records = {"example": [{"id": "example", "depends": {"library": "*"}},
                               {"id": "library", "environment": "client"}]}
        self.assertEqual(check_fabric_sides(items, records),
                         ["example: missing Fabric dependency library on server"])

    def test_deploy_manifest_verifies_pack_hash_before_accepting_tree(self):
        content = b'version = "1.2.3"\n[versions]\nminecraft = "26.3"\nfabric = "0.20.1"\n'
        commit = "a" * 40
        manifest = {"channel": "release", "tag": "v1.2.3", "version": "1.2.3", "commit": commit,
                    "packwiz_url": f"{deploy.RAW}/{commit}/pack.toml",
                    "versions": {"minecraft": "26.3", "fabric": "0.20.1"},
                    "packwiz_sha256": hashlib.sha256(content).hexdigest()}
        with patch.object(deploy, "fetch", side_effect=[json.dumps(manifest), content]):
            self.assertEqual(deploy.stable_manifest(), manifest)
        with patch.object(deploy, "fetch", side_effect=[json.dumps(manifest), content + b"\n"]):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                deploy.stable_manifest()

    def test_restore_retains_current_world_and_recovers_the_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (patch.object(deploy, "BACKUPS", root / "backups"),
                  patch.object(deploy, "DATA", root / "data"),
                  patch.object(deploy, "PACK_ENV", root / ".pack.env")):
                deploy.DATA.mkdir()
                world = deploy.DATA / "level.dat"
                world.write_text("old world")
                deploy.PACK_ENV.write_text("old pack")
                backup = deploy.snapshot()
                world.write_text("new world")
                deploy.PACK_ENV.write_text("new pack")
                deploy.restore(backup)
                self.assertEqual(world.read_text(), "old world")
                self.assertEqual(deploy.PACK_ENV.read_text(), "old pack")
                retained, = deploy.BACKUPS.glob("recovery-*/previous-data/level.dat")
                self.assertEqual(retained.read_text(), "new world")
