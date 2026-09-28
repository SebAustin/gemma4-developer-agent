"""Run a bundle's skill script locally exactly the way the harness does.

ADK's ``_SkillScriptCodeExecutor`` builds a self-extracting wrapper (skill files are written
to a temp dir, cwd is switched there, the script runs via ``runpy``). swegemma's
``AdkSandboxCodeExecutor`` writes that wrapper into the workspace and runs
``python3 <workspace>/.adk_exec_<id>.py`` with cwd = workspace. We reproduce both steps so
tests exercise the real materialization path, including repo-root discovery.
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillRun:
    stdout: str
    stderr: str
    returncode: int


def build_wrapper(skill_dir: Path, file_path: str, args: list[str]) -> str:
    from google.adk.skills import load_skill_from_dir
    from google.adk.tools.skill_toolset import _SkillScriptCodeExecutor

    skill = load_skill_from_dir(skill_dir)
    code = _SkillScriptCodeExecutor(base_executor=None, script_timeout=300)._build_wrapper_code(
        skill, file_path, args
    )
    if code is None:
        raise ValueError(f"unsupported script type: {file_path}")
    return code


def run_skill_script(skill_dir: str | Path, file_path: str, args: list[str], workspace: str | Path,
                     *, python: str = sys.executable, timeout: int = 300) -> SkillRun:
    workspace = Path(workspace)
    wrapper = workspace / f".adk_exec_{uuid.uuid4().hex[:8]}.py"
    wrapper.write_text(build_wrapper(Path(skill_dir), file_path, args), encoding="utf-8")
    try:
        proc = subprocess.run([python, str(wrapper)], cwd=workspace, capture_output=True, text=True,
                              timeout=timeout)
    finally:
        wrapper.unlink(missing_ok=True)
    return SkillRun(proc.stdout, proc.stderr, proc.returncode)
