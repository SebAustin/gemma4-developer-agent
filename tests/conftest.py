from pathlib import Path

import pytest

MINIMAL_AGENT = """\
name: test_agent
model: gemma-4-31b-it-qat-w4a16-ct
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - submit_patch
skills:
  - skills/demo
generate_content_config:
  temperature: 0.2
  max_output_tokens: 8192
"""

SKILL_MD = """\
---
name: demo
description: Demo skill for tests.
---
Run `scripts/hello.py`.
"""


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    (root / "prompts").mkdir(parents=True)
    (root / "skills" / "demo" / "scripts").mkdir(parents=True)
    (root / "agent.yaml").write_text(MINIMAL_AGENT)
    (root / "prompts" / "system.md").write_text("Fix the issue. Problem: {problem_description}\n")
    (root / "skills" / "demo" / "SKILL.md").write_text(SKILL_MD)
    (root / "skills" / "demo" / "scripts" / "hello.py").write_text("print('hi')\n")
    (root / "eval_config.yaml").write_text("evaluation:\n  max_time_minutes: 5\n")
    return root
