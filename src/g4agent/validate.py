"""Validate a submission bundle the same way the competition harness will.

Runs the real ``adk_submission`` compiler (with stub tools and a dummy model endpoint),
then layers extra lint checks for failure modes the compiler does not catch but which
break or silently degrade an evaluation run:

* ADK state placeholders (``{name}``) in instructions that are not in session state
  raise ``KeyError`` at the first model call.
* Skill scripts with syntax errors only fail when the agent calls them.
* LoRA ranks above the vLLM ``max_lora_rank`` fail at server start.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from collections.abc import Iterator
from pathlib import Path

import yaml

ALLOWED_MODEL = "gemma-4-31b-it-qat-w4a16-ct"
MAX_LORA_RANK = 128
# Keys the harness puts into session.state (swegemma agent_runner). `hints` is only present
# when the task has hints, so it must be referenced as `{hints?}`.
SESSION_STATE_KEYS = {"problem_description"}
OPTIONAL_STATE_KEYS = {"hints"}
PLACEHOLDER_RE = re.compile(r"{+[^{}]*}+")  # identical to google.adk.utils.instructions_utils
# eval_config `timeout_seconds` is also the timeout of the scoring pytest run
# (swegemma config.py -> harness.command_timeout_seconds -> harness/verification.py).
DEFAULT_VERIFICATION_TIMEOUT = 300  # harness default for timeout_seconds
MIN_VERIFICATION_TIMEOUT = 240
MAX_MODEL_LEN = 32768  # scorer's vLLM max_model_len
MAX_SAFE_OUTPUT_TOKENS = 8192
# The scorer runs ~120 tasks one after another; its 12 h include sandbox setup, not grading.
SCORER_TASKS = 120
SCORER_WALL_CLOCK_HOURS = 12
SETUP_MINUTES_PER_TASK = 1.0


@dataclass
class ValidationReport:
    bundle: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def format(self) -> str:
        lines = [f"Bundle: {self.bundle}", "Status: " + ("OK" if self.ok else "FAILED")]
        lines += [f"  ERROR   {e}" for e in self.errors]
        lines += [f"  WARNING {w}" for w in self.warnings]
        return "\n".join(lines)


def _stub_tools() -> dict:
    """Stubs with the harness tool names and signatures (swegemma.tools.create_tools)."""

    def run_command(command: str) -> str:
        """Execute a shell command."""
        return ""

    def read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Read a file."""
        return ""

    def write_file(filepath: str, content: str) -> str:
        """Write a file."""
        return ""

    def edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str:
        """Edit a file."""
        return ""

    def submit_patch() -> str:
        """Submit the patch."""
        return ""

    def get_status() -> str:
        """Budget status."""
        return ""

    def get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str:
        """Graph neighbors."""
        return ""

    def search_similar_code(query: str, k: int = 10) -> str:
        """Embedding search."""
        return ""

    def get_code_subgraph(nodes: list[str]) -> str:
        """Induced subgraph."""
        return ""

    return {f.__name__: f for f in (run_command, read_file, write_file, edit_file, submit_patch,
                                    get_status, get_code_neighbors, search_similar_code, get_code_subgraph)}


def _compile(bundle: Path, report: ValidationReport) -> None:
    from adk_submission import compile_submission, discover_adapters
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS, build_submission_limits
    from swegemma.models.discovery import validate_single_declared_model
    from swegemma.models.registry import setup_gemma_model_registry

    try:
        model = validate_single_declared_model(bundle)
    except Exception as e:  # noqa: BLE001 - surface any harness validation error verbatim
        report.errors.append(f"model declaration: {e}")
        return
    if model != ALLOWED_MODEL:
        report.errors.append(f"declared model {model!r} is not the competition model {ALLOWED_MODEL!r}")

    limits, gen_constraints = build_submission_limits()
    try:
        adapters = discover_adapters(str(bundle), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
        models = setup_gemma_model_registry(api_base="http://127.0.0.1:9/v1", adapter_manifest=adapters)
        compile_submission(
            submission_dir=bundle,
            tool_registry=_stub_tools(),
            model_registry=models,
            limits=limits,
            generation_constraints=gen_constraints,
            adapter_manifest=adapters,
        )
    except Exception as e:  # noqa: BLE001
        report.errors.append(f"compile_submission: {type(e).__name__}: {e}")


def _lint_placeholders(bundle: Path, report: ValidationReport) -> None:
    for md in sorted(bundle.rglob("*.md")):
        if "skills" in md.relative_to(bundle).parts:
            continue  # SKILL.md is not templated
        text = md.read_text(encoding="utf-8")
        for m in PLACEHOLDER_RE.finditer(text):
            name = m.group().strip("{}").strip()
            optional = name.endswith("?")
            name = name.removesuffix("?")
            if not name.isidentifier():
                continue  # ADK leaves non-identifier braces untouched
            rel = md.relative_to(bundle)
            if name in SESSION_STATE_KEYS:
                continue
            if name in OPTIONAL_STATE_KEYS and not optional:
                report.errors.append(f"{rel}: '{{{name}}}' crashes on tasks without it; use '{{{name}?}}'")
            elif name not in OPTIONAL_STATE_KEYS:
                report.errors.append(f"{rel}: ADK state placeholder {m.group()!r} is not in session state "
                                     "(raises KeyError). Rephrase without braces.")


def _lint_skills(bundle: Path, report: ValidationReport) -> None:
    for skill_md in sorted(bundle.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        head = skill_md.read_text(encoding="utf-8")
        if not head.startswith("---"):
            report.errors.append(f"{skill_md.relative_to(bundle)}: missing YAML frontmatter")
            continue
        meta = yaml.safe_load(head.split("---", 2)[1]) or {}
        if meta.get("name") != skill_dir.name:
            report.errors.append(f"{skill_md.relative_to(bundle)}: frontmatter name {meta.get('name')!r} "
                                 f"!= directory name {skill_dir.name!r}")
        for script in sorted((skill_dir / "scripts").rglob("*.py")):
            try:
                compile(script.read_text(encoding="utf-8"), str(script), "exec")
            except SyntaxError as e:
                report.errors.append(f"{script.relative_to(bundle)}: syntax error line {e.lineno}: {e.msg}")


def _lint_adapters(bundle: Path, report: ValidationReport) -> None:
    for cfg in sorted((bundle / "adapters").glob("*/adapter_config.json")):
        data = json.loads(cfg.read_text(encoding="utf-8"))
        rank = max([data.get("r", 0), *data.get("rank_pattern", {}).values()] or [0])
        if rank > MAX_LORA_RANK:
            report.errors.append(f"{cfg.relative_to(bundle)}: rank {rank} > vLLM max_lora_rank {MAX_LORA_RANK}")
        if not (cfg.parent / "adapter_model.safetensors").is_file():
            report.errors.append(f"{cfg.parent.relative_to(bundle)}: missing adapter_model.safetensors")


class _IncludeAsNullLoader(yaml.SafeLoader):
    """Reads one YAML file on its own; included files are linted when the scan reaches them."""


_IncludeAsNullLoader.add_constructor("!include", lambda loader, node: None)


def _mappings(node: object) -> Iterator[dict]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _mappings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _mappings(value)


def _lint_sampling(bundle: Path, report: ValidationReport) -> None:
    for path in sorted(bundle.rglob("*.y*ml")):
        if path.name == "eval_config.yaml" or "skills" in path.relative_to(bundle).parts:
            continue
        rel = path.relative_to(bundle)
        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=_IncludeAsNullLoader)
        except yaml.YAMLError as e:
            report.errors.append(f"{rel}: unreadable YAML: {e}".splitlines()[0])
            continue
        for m in _mappings(data):
            max_out = m.get("max_output_tokens")
            if isinstance(max_out, int) and max_out > MAX_SAFE_OUTPUT_TOKENS:
                report.warnings.append(f"{rel}: max_output_tokens={max_out}: vLLM rejects requests whose prompt "
                                       f"+ max output exceed {MAX_MODEL_LEN} tokens; use <= {MAX_SAFE_OUTPUT_TOKENS}")
            thinking = m.get("thinking_config")
            if isinstance(thinking, dict) and thinking.get("include_thoughts") is False \
                    and (thinking.get("thinking_budget") or 0) > 0:
                report.warnings.append(f"{rel}: include_thoughts: false disables reasoning in the ADK bridge, "
                                       "so thinking_budget is ignored")


def _lint_eval_config(bundle: Path, report: ValidationReport) -> None:
    path = bundle / "eval_config.yaml"
    if not path.is_file():
        report.warnings.append("no eval_config.yaml: harness defaults apply (60 min/task, 100 tool calls)")
        return
    section = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("evaluation", {})
    try:
        timeout = int(section.get("timeout_seconds", DEFAULT_VERIFICATION_TIMEOUT))
        minutes = float(section.get("max_time_minutes", 60.0))
    except (TypeError, ValueError) as e:
        report.errors.append(f"eval_config.yaml: timeout_seconds and max_time_minutes must be numbers ({e})")
        return
    if timeout < MIN_VERIFICATION_TIMEOUT:
        report.warnings.append(f"timeout_seconds={timeout}: it also caps the scoring pytest run on the hidden "
                               f"test files, so slow files fail correct patches; use >= {MIN_VERIFICATION_TIMEOUT}")
    worst_hours = SCORER_TASKS * (minutes + SETUP_MINUTES_PER_TASK) / 60
    if worst_hours > SCORER_WALL_CLOCK_HOURS:
        report.warnings.append(f"max_time_minutes={minutes}: if every task hits the cap, {SCORER_TASKS} serial tasks "
                               f"plus sandbox setup take {worst_hours:.1f} h; over {SCORER_WALL_CLOCK_HOURS} h the whole submission errors")


def validate_bundle(bundle: str | Path) -> ValidationReport:
    bundle = Path(bundle).resolve()
    report = ValidationReport(bundle=bundle)
    if not bundle.is_dir():
        report.errors.append("bundle directory does not exist")
        return report
    _compile(bundle, report)
    _lint_placeholders(bundle, report)
    _lint_skills(bundle, report)
    _lint_adapters(bundle, report)
    _lint_sampling(bundle, report)
    _lint_eval_config(bundle, report)
    return report
