"""The ship-check command in v3_guard's prompt, run on a scratch git repo.

The harness never reverts the agent's test edits (docs/diagnosis/test-patch-conflicts.md), so the
prompt's ship check must revert every test and config edit and keep every source edit.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROMPT = Path(__file__).resolve().parents[1] / "submissions" / "v3_guard" / "prompts" / "system.md"
EDITED = {"tests/test_a.py": False, "src/pkg/test_helpers.py": False, "pkg/thing_test.py": False,
          "conftest.py": False, "pyproject.toml": False, "setup.cfg": False,
          "src/pkg/core.py": True, "docs_src/tutorial001.py": True}


def ship_check_command() -> str:
    match = re.search(r"Ship check:.*?\n```\n(.+?)\n```", PROMPT.read_text(), re.S)
    assert match, "ship check code block missing from the prompt"
    return match.group(1)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_ship_check_reverts_test_and_config_edits_and_keeps_source_edits(tmp_path):
    for rel in EDITED:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("original\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "baseline")
    for rel in EDITED:
        (tmp_path / rel).write_text("agent edit\n")

    subprocess.run(ship_check_command(), shell=True, cwd=tmp_path, check=True, capture_output=True)

    still_changed = set(_git(tmp_path, "diff", "--name-only").split())
    assert still_changed == {rel for rel, kept in EDITED.items() if kept}
