#!/usr/bin/env python3
"""Generate release notes from commits since the previous reachable tag."""

import subprocess
import sys


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def generate_release_notes(commit: str) -> str:
    try:
        previous_tag = git_output(
            "describe", "--tags", "--abbrev=0", f"{commit}^"
        )
    except subprocess.CalledProcessError:
        commits = git_output(
            "log", "--reverse", "--no-merges", "--format=%s", commit
        ).splitlines()
    else:
        commits = git_output(
            "log",
            "--reverse",
            "--no-merges",
            "--format=%s",
            f"{previous_tag}..{commit}",
        ).splitlines()

    changes = "\n".join(f"- {subject}" for subject in commits)
    if not changes:
        changes = "- No code changes since the previous release."
    return f"## Changes\n\n{changes}\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: generate_release_notes.py <commit>")
    print(generate_release_notes(sys.argv[1]), end="")
