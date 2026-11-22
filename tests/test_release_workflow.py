import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(sys.platform == "win32" or not shutil.which("bash") or not shutil.which("jq"),
                 "Release workflow requires bash and jq")
class ReleaseWorkflowTests(unittest.TestCase):
    def run_advance(self, *, channel="release", latest="v1.2.3", status="ahead",
                    release_tree="tree", stable_tree="tree", patch_result=0, compare_result=0):
        workflow = (ROOT / ".github/workflows/release-pack.yml").read_text(encoding="utf-8")
        step = workflow.split("      - name: Advance the stable Packwiz branch\n", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dist").mkdir()
            (root / "dist/pack-manifest.json").write_text(
                json.dumps({"channel": channel, "commit": "releasecommit"}), encoding="utf-8")
            gh = root / "gh"
            gh.write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                echo "$*" >> "$GH_LOG"
                case "$*" in
                  *"--method PATCH"*) exit "$PATCH_RESULT" ;;
                  *"/releases/latest"*) echo "$LATEST" ;;
                  *"/git/ref/heads/stable"*) echo stablecommit ;;
                  *"/compare/"*) echo "$STATUS"; exit "$COMPARE_RESULT" ;;
                  *"/git/commits/releasecommit"*) echo "$RELEASE_TREE" ;;
                  *"/git/commits/stablecommit"*) echo "$STABLE_TREE" ;;
                  *) exit 1 ;;
                esac
                """), encoding="utf-8")
            gh.chmod(0o755)
            env = dict(os.environ, PATH=f"{root}{os.pathsep}{os.environ['PATH']}",
                       GH_LOG=str(root / "calls"), GITHUB_REPOSITORY="owner/repo",
                       GITHUB_REF_NAME="v1.2.3", LATEST=latest, STATUS=status,
                       RELEASE_TREE=release_tree, STABLE_TREE=stable_tree,
                       PATCH_RESULT=str(patch_result), COMPARE_RESULT=str(compare_result))
            result = subprocess.run(["bash", "-e", "-c", script], cwd=root, env=env,
                                    capture_output=True, text=True)
            calls = (root / "calls").read_text(encoding="utf-8") if (root / "calls").exists() else ""
            return result, calls

    def test_descendant_with_release_tree_is_already_published(self):
        result, calls = self.run_advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already contains the release tree", result.stdout)
        self.assertNotIn("--method PATCH", calls)

    def test_different_or_missing_tree_does_not_hide_non_fast_forward(self):
        for tree in ("different", "null", ""):
            with self.subTest(tree=tree):
                result, calls = self.run_advance(release_tree=tree, stable_tree=tree if tree != "different" else "other",
                                                 patch_result=1)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("-F force=false", calls)

    def test_unrelated_equal_tree_still_requires_fast_forward(self):
        result, calls = self.run_advance(status="diverged", patch_result=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("-F force=false", calls)

    def test_fast_forward_updates_stable(self):
        result, calls = self.run_advance(status="behind")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-f sha=releasecommit -F force=false", calls)

    def test_comparison_error_fails_without_updating_stable(self):
        result, calls = self.run_advance(compare_result=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("--method PATCH", calls)

    def test_preview_and_old_release_do_not_update_stable(self):
        for options in ({"channel": "beta"}, {"latest": "v1.2.4"}):
            with self.subTest(options=options):
                result, calls = self.run_advance(**options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("--method PATCH", calls)
                self.assertNotIn("/compare/", calls)
