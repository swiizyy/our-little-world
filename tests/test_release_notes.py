import subprocess
import unittest
from unittest import mock

from scripts.generate_release_notes import generate_release_notes


def git_result(stdout=""):
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


class ReleaseNotesTests(unittest.TestCase):
    @mock.patch("scripts.generate_release_notes.subprocess.run")
    def test_lists_commit_subjects_since_previous_tag(self, run):
        run.side_effect = [
            git_result("v0.1.0-beta.1"),
            git_result("Add resource packs\nUpdate Xaero settings\n"),
        ]

        self.assertEqual(
            generate_release_notes("HEAD"),
            "## Changes\n\n- Add resource packs\n- Update Xaero settings\n",
        )
        self.assertEqual(run.call_args_list[1].args[0][-1], "v0.1.0-beta.1..HEAD")

    @mock.patch("scripts.generate_release_notes.subprocess.run")
    def test_uses_all_commits_when_no_previous_tag_exists(self, run):
        run.side_effect = [
            subprocess.CalledProcessError(128, ["git", "describe"]),
            git_result("Initial pack\nAdd gameplay mods\n"),
        ]

        self.assertEqual(
            generate_release_notes("HEAD"),
            "## Changes\n\n- Initial pack\n- Add gameplay mods\n",
        )

    @mock.patch("scripts.generate_release_notes.subprocess.run")
    def test_describes_empty_range(self, run):
        run.side_effect = [git_result("v0.1.0-beta.1"), git_result()]

        self.assertEqual(
            generate_release_notes("HEAD"),
            "## Changes\n\n- No code changes since the previous release.\n",
        )


if __name__ == "__main__":
    unittest.main()
