"""A scripted stand-in for Gemma that drives the real harness without a GPU.

Each model turn returns the next tool call from a fixed plan. The oracle plan exercises every
part of the pipeline our bundle relies on: skill scripts in the real sandbox, a source edit
(the reference patch applied through run_command), the pre-submit check, submit_patch and
Phase-2 verification. If oracle runs resolve, the local harness setup and the skill tooling
work end to end, and failures of real runs can be attributed to the model.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def oracle_plan(task) -> list[tuple[str, dict]]:
    """Tool calls for one task: navigate with the skill, apply the gold patch, check, submit."""
    patch_cmd = f"cd /workspace && git apply --whitespace=nowarn <<'G4PATCH'\n{task.patch}\nG4PATCH"
    return [
        ("run_skill_script", {"skill_name": "swe", "file_path": "scripts/locate.py",
                              "args": [task.problem_statement[:2000], "--top", "5"]}),
        ("run_skill_script", {"skill_name": "swe", "file_path": "scripts/check_patch.py", "args": []}),
        ("run_command", {"command": patch_cmd}),
        ("run_skill_script", {"skill_name": "swe", "file_path": "scripts/check_patch.py", "args": []}),
        ("submit_patch", {}),
    ]


class ScriptedLlm(BaseLlm):
    """Plays back ``plan`` one tool call per turn, then a final text message."""

    plan: list = []
    step: int = 0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if self.step < len(self.plan):
            name, args = self.plan[self.step]
            self.step += 1
            call = types.FunctionCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, args=args)
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))
            return
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Done: patch submitted.")]))

