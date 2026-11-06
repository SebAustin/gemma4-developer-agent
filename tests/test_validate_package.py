import zipfile

import pytest

from g4agent.package import PackagingError, bundle_hash, package_bundle
from g4agent.validate import validate_bundle


def test_minimal_bundle_is_valid(bundle):
    report = validate_bundle(bundle)
    assert report.ok, report.format()


def test_unknown_state_placeholder_is_rejected(bundle):
    (bundle / "prompts" / "system.md").write_text("Edit {filename} carefully.\n")
    report = validate_bundle(bundle)
    assert any("filename" in e for e in report.errors)


def test_json_braces_are_allowed(bundle):
    (bundle / "prompts" / "system.md").write_text('Return {"status": "ok"} and {x: 1}.\n')
    assert validate_bundle(bundle).ok


def test_required_hints_placeholder_is_rejected_but_optional_ok(bundle):
    prompt = bundle / "prompts" / "system.md"
    prompt.write_text("Hints: {hints}\n")
    assert not validate_bundle(bundle).ok
    prompt.write_text("Hints: {hints?}\n")
    assert validate_bundle(bundle).ok


def test_wrong_model_is_rejected(bundle):
    agent = bundle / "agent.yaml"
    agent.write_text(agent.read_text().replace("gemma-4-31b-it-qat-w4a16-ct", "gemma-4-e4b-it"))
    assert not validate_bundle(bundle).ok


def test_unknown_tool_is_rejected(bundle):
    agent = bundle / "agent.yaml"
    agent.write_text(agent.read_text().replace("  - submit_patch\n", "  - submit_patch\n  - grep_repo\n"))
    report = validate_bundle(bundle)
    assert any("compile_submission" in e for e in report.errors)


def test_skill_script_syntax_error_is_reported(bundle):
    (bundle / "skills" / "demo" / "scripts" / "hello.py").write_text("def broken(:\n")
    report = validate_bundle(bundle)
    assert any("syntax error" in e for e in report.errors)


def test_skill_name_must_match_directory(bundle):
    skill = bundle / "skills" / "demo" / "SKILL.md"
    skill.write_text(skill.read_text().replace("name: demo", "name: other"))
    assert not validate_bundle(bundle).ok


def test_long_time_budget_warns(bundle):
    (bundle / "eval_config.yaml").write_text("evaluation:\n  max_time_minutes: 30\n")
    report = validate_bundle(bundle)
    assert report.ok and any("12 h" in w for w in report.warnings)


def test_serial_projection_counts_sandbox_setup(bundle):
    (bundle / "eval_config.yaml").write_text("evaluation:\n  max_time_minutes: 6\n")
    report = validate_bundle(bundle)
    assert any("14.0 h" in w for w in report.warnings), report.format()
    (bundle / "eval_config.yaml").write_text("evaluation:\n  max_time_minutes: 5\n")
    assert not validate_bundle(bundle).warnings


def test_short_command_timeout_no_longer_warns_since_scoring_has_its_own_timeout(bundle):
    (bundle / "eval_config.yaml").write_text("evaluation:\n  max_time_minutes: 5\n  timeout_seconds: 60\n")

    report = validate_bundle(bundle)

    assert report.ok and not report.warnings, report.format()


def test_large_max_output_tokens_warns_about_the_32k_request_limit(bundle):
    agent = bundle / "agent.yaml"
    agent.write_text(agent.read_text().replace("max_output_tokens: 8192", "max_output_tokens: 16384"))
    report = validate_bundle(bundle)
    assert report.ok and any("max_output_tokens=16384" in w for w in report.warnings)


def test_hidden_thoughts_with_a_thinking_budget_are_valid_in_an_included_config(bundle):
    agent = bundle / "agent.yaml"
    sampling = "generate_content_config:\n  temperature: 0.2\n  max_output_tokens: 8192\n"
    agent.write_text(agent.read_text().replace(sampling, "generate_content_config: !include configs/sampling.yaml\n"))
    (bundle / "configs").mkdir()
    (bundle / "configs" / "sampling.yaml").write_text(
        "temperature: 0.2\nthinking_config:\n  thinking_budget: 4096\n  include_thoughts: false\n")

    report = validate_bundle(bundle)

    assert report.ok and not report.warnings, report.format()


def test_null_thinking_budget_does_not_crash_validation(bundle):
    (bundle / "configs").mkdir()
    (bundle / "configs" / "sampling.yaml").write_text("thinking_config:\n  thinking_budget:\n  include_thoughts: false\n")

    report = validate_bundle(bundle)

    assert report.ok, report.format()


@pytest.mark.parametrize(("name", "text"), [("broken.yaml", "a: [1,\n"), ("tagged.yaml", "x: !secret value\n")])
def test_unreadable_yaml_is_a_report_error_not_a_crash(bundle, name, text):
    (bundle / name).write_text(text)

    report = validate_bundle(bundle)

    assert any(name in e for e in report.errors)


def test_non_numeric_timeout_is_a_report_error(bundle):
    (bundle / "eval_config.yaml").write_text("evaluation:\n  timeout_seconds: soon\n")

    report = validate_bundle(bundle)

    assert any("timeout_seconds" in e for e in report.errors)


def test_package_is_deterministic_with_root_agent_yaml(bundle, tmp_path):
    z1 = package_bundle(bundle, tmp_path / "a.zip")
    z2 = package_bundle(bundle, tmp_path / "b.zip")
    assert z1.read_bytes() == z2.read_bytes()
    with zipfile.ZipFile(z1) as zf:
        assert "agent.yaml" in zf.namelist()


def test_package_rejects_disallowed_extension(bundle, tmp_path):
    (bundle / "notes.sh").write_text("echo hi\n")
    with pytest.raises(PackagingError):
        package_bundle(bundle, tmp_path / "x.zip", validate=False)


def test_bundle_hash_changes_with_content(bundle):
    before = bundle_hash(bundle)
    (bundle / "prompts" / "system.md").write_text("Different prompt.\n")
    assert bundle_hash(bundle) != before
