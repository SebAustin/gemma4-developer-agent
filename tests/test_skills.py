"""Skill scripts run through the same wrapper the harness uses, against a synthetic git repo."""

import subprocess
import sys
from pathlib import Path

import pytest

from g4agent.skill_runner import run_skill_script

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "submissions" / "v1_scaffold" / "skills" / "swe"

PKG = '''\
"""Tiny package used by skill tests."""

DEFAULT_TIMEOUT = 5


class Client:
    """HTTP-ish client."""

    def send(self, request, timeout=DEFAULT_TIMEOUT):
        """Send a request."""
        return build_response(request)

    async def asend(self, request):
        return build_response(request)


def build_response(request):
    if request is None:
        raise ValueError("request must not be None")
    return {"ok": True}
'''

TEST = '''\
from minipkg.client import Client, build_response


def test_send():
    assert Client().send("x") == {"ok": True}


def test_none():
    assert build_response("y")["ok"]
'''


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "workspace"
    (repo / "minipkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "minipkg" / "__init__.py").write_text("")
    (repo / "minipkg" / "client.py").write_text(PKG)
    (repo / "tests" / "test_client.py").write_text(TEST)
    (repo / "pytest.ini").write_text("[pytest]\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline")
    return repo


def run(repo: Path, script: str, *args: str):
    res = run_skill_script(SKILL, f"scripts/{script}", list(args), repo)
    # Nothing may leak into the workspace (the wrapper file is removed by the runner).
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert status == "" or script == "check_patch.py", status
    return res


def test_locate_ranks_defining_file_first(repo):
    res = run(repo, "locate.py", "Client.send raises ValueError when request is None")
    assert res.returncode == 0, res.stderr
    ranked = [ln for ln in res.stdout.splitlines() if ln.strip()[:1].isdigit()]
    assert "minipkg/client.py" in ranked[0]


def test_locate_excludes_tests_by_default(repo):
    res = run(repo, "locate.py", "test_send build_response")
    assert "tests/test_client.py" not in res.stdout
    res = run(repo, "locate.py", "test_send build_response", "--tests")
    assert "tests/test_client.py" in res.stdout


def test_symbol_finds_method_and_references(repo):
    res = run(repo, "symbol.py", "Client.send")
    assert res.returncode == 0, res.stderr
    assert "minipkg/client.py:9" in res.stdout
    assert "references in tests" in res.stdout and "tests/test_client.py" in res.stdout


def test_outline_and_symbol_source(repo):
    res = run(repo, "outline.py", "minipkg/client.py")
    assert "class Client" in res.stdout and "def Client.asend" in res.stdout
    res = run(repo, "outline.py", "/workspace/minipkg/client.py", "--symbol", "build_response")
    assert "raise ValueError" in res.stdout and res.stdout.splitlines()[1].strip().startswith("17")


def test_grep_regex_and_fixed(repo):
    res = run(repo, "grep.py", r"def \w*send", "--no-tests")
    assert "2 matches in 1 files" in res.stdout
    res = run(repo, "grep.py", "request must not be None", "--fixed")
    assert "minipkg/client.py" in res.stdout


def test_tests_find_and_run(repo):
    res = run(repo, "tests.py", "find", "minipkg/client.py")
    assert "tests/test_client.py" in res.stdout
    res = run(repo, "tests.py", "run", "tests/test_client.py")
    assert "2 passed" in res.stdout, res.stdout + res.stderr


def test_tests_run_refuses_whole_suite(repo):
    res = run(repo, "tests.py", "run", ".")
    assert res.returncode != 0 and "whole suite" in res.stderr


def test_tests_run_reports_failure(repo):
    (repo / "minipkg" / "client.py").write_text(PKG.replace('{"ok": True}', '{"ok": False}'))
    res = run_skill_script(SKILL, "scripts/tests.py", ["run", "tests/test_client.py::test_send"], repo)
    assert "1 failed" in res.stdout and "FAILED" in res.stdout


def test_check_patch_empty_is_blocking(repo):
    res = run(repo, "check_patch.py")
    assert res.returncode != 0 and "EMPTY PATCH" in res.stdout


def test_check_patch_flags_scratch_syntax_and_tests(repo):
    (repo / "repro.py").write_text("print(1)\n")
    (repo / "minipkg" / "client.py").write_text(PKG + "\ndef broken(:\n")
    (repo / "tests" / "test_client.py").write_text(TEST + "\n# edited\n")
    res = run(repo, "check_patch.py")
    out = res.stdout
    assert res.returncode != 0
    assert "repro.py: looks like a scratch file" in out
    assert "SYNTAX ERROR" in out
    assert "tests/test_client.py: test files are reset" in out


def test_check_patch_ok_for_clean_source_change(repo):
    (repo / "minipkg" / "client.py").write_text(PKG.replace("DEFAULT_TIMEOUT = 5", "DEFAULT_TIMEOUT = 10"))
    res = run(repo, "check_patch.py")
    assert res.returncode == 0 and "OK: no blocking problems" in res.stdout
    assert "+DEFAULT_TIMEOUT = 10" in res.stdout


def test_outputs_stay_compact(repo):
    for i in range(300):
        (repo / "minipkg" / f"mod_{i}.py").write_text("def send():\n    pass\n" * 5)
    res = run_skill_script(SKILL, "scripts/grep.py", ["send"], repo)
    assert len(res.stdout) < 4200 and "truncated" in res.stdout
