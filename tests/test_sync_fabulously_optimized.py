import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "sync_fabulously_optimized", ROOT / "scripts" / "sync_fabulously_optimized.py"
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def mod(project, version, checksum):
    return (
        f'name = "{project}"\nfilename = "{project}.jar"\n'
        f'[download]\nhash-format = "sha512"\nhash = "{checksum}"\n'
        f'[update.modrinth]\nmod-id = "{project}"\nversion = "{version}"\n'
    )


def archive(loader, mods):
    manifest = {
        "dependencies": {"minecraft": "26.3", "fabric-loader": loader},
        "files": [
            {
                "path": f"mods/{project}.jar",
                "downloads": [f"https://cdn.modrinth.com/data/{project}/versions/{version}/file.jar"],
                "hashes": {"sha512": checksum},
            }
            for project, version, checksum in mods
        ],
    }
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as file:
        file.writestr("modrinth.index.json", json.dumps(manifest))
    return data.getvalue()


class UpstreamTests(unittest.TestCase):
    def test_selects_latest_matching_fabric_and_ignores_resource_packs(self):
        wrong = archive("0.21", [("wrong", "v1", "hash")])
        correct = archive("0.20", [("project", "v2", "hash")])
        releases = [
            {
                "id": name,
                "version_number": name,
                "date_published": date,
                "files": [{
                    "primary": True,
                    "filename": name + ".mrpack",
                    "url": name,
                    "hashes": {"sha512": hashlib.sha512(data).hexdigest()},
                }],
            }
            for name, date, data in [
                ("old", "2026-01-01", correct),
                ("new", "2026-02-01", wrong),
            ]
        ]

        def fetch(url):
            return {"new": wrong, "old": correct}.get(url, json.dumps(releases).encode())

        with mock.patch.object(sync, "fetch", side_effect=fetch):
            release, mods = sync.upstream_mods({"versions": {"minecraft": "26.3", "fabric": "0.20"}})
        self.assertEqual(release["id"], "old")
        self.assertEqual(mods, {"project": ("v2", "hash")})

    def test_rejects_bad_checksum(self):
        release = {
            "version_number": "bad",
            "date_published": "2026-01-01",
            "files": [{"primary": True, "filename": "pack.mrpack", "url": "pack",
                       "hashes": {"sha512": "incorrect"}}],
        }
        with mock.patch.object(sync, "fetch", side_effect=[json.dumps([release]).encode(), b"invalid"]):
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                sync.upstream_mods({"versions": {"minecraft": "26.3", "fabric": "0.20"}})


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "mods").mkdir()
        (self.root / "pack.toml").write_text('[versions]\nminecraft = "26.3"\nfabric = "0.20"\n')
        (self.root / "index.toml").write_text('hash-format = "sha256"\n')
        (self.root / "mods" / "upstream.pw.toml").write_text(mod("upstream", "v1", "old"))
        (self.root / "mods" / "local.pw.toml").write_text(mod("local", "v1", "localhash"))
        self.wanted = {"upstream": ("v2", "new"), "added": ("v1", "addedhash")}

    def packwiz(self, directory, *arguments):
        if arguments[0] == "modrinth":
            project = arguments[arguments.index("--project-id") + 1]
            version, checksum = self.wanted[project]
            (directory / "mods" / f"{project}.pw.toml").write_text(mod(project, version, checksum))
        return ""

    def test_updates_and_adds_without_removing_local_mods(self):
        with mock.patch.object(sync, "ROOT", self.root), \
             mock.patch.object(sync.shutil, "which", return_value="/usr/bin/packwiz"), \
             mock.patch.object(sync, "upstream_mods", return_value=({"version_number": "1", "id": "id"}, self.wanted)), \
             mock.patch.object(sync, "run_packwiz", side_effect=self.packwiz):
            sync.sync()
        mods = sync.read_mods(self.root / "mods")
        self.assertEqual(set(mods), {"upstream", "added", "local"})
        self.assertEqual(mods["upstream"][1]["update"]["modrinth"]["version"], "v2")
        self.assertEqual(mods["local"][1]["update"]["modrinth"]["version"], "v1")

    def test_refresh_failure_restores_original_files(self):
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

        def fail_on_final_refresh(directory, *arguments):
            if directory == self.root:
                raise RuntimeError("refresh failed")
            return self.packwiz(directory, *arguments)

        with mock.patch.object(sync, "ROOT", self.root), \
             mock.patch.object(sync.shutil, "which", return_value="/usr/bin/packwiz"), \
             mock.patch.object(sync, "upstream_mods", return_value=({"version_number": "1", "id": "id"}, self.wanted)), \
             mock.patch.object(sync, "run_packwiz", side_effect=fail_on_final_refresh):
            with self.assertRaisesRegex(RuntimeError, "refresh failed"):
                sync.sync()
        after = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
