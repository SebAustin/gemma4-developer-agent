import io
import tarfile
from pathlib import Path

from g4agent.local_env import build_task_wheels, snapshot_requirements

PYPROJECT = """\
[project]
name = "fastapi"
dependencies = ["starlette>=0.40.0,<0.49.0", "pydantic>=2.0"]

[dependency-groups]
tests = ["dirty-equals >=0.9.0", { include-group = "docs" }]
"""


def _snapshot(tmp_path: Path, files: dict[str, str]) -> Path:
    path = tmp_path / "snap.tgz"
    with tarfile.open(path, "w:gz") as tf:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"./{name}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def _wheels(tmp_path: Path, names: list[str]) -> Path:
    d = tmp_path / "wheels"
    d.mkdir()
    for n in names:
        (d / n).write_bytes(b"")
    return d


def test_requirements_from_pyproject(tmp_path):
    own, reqs = snapshot_requirements(_snapshot(tmp_path, {"pyproject.toml": PYPROJECT}))
    assert own == "fastapi"
    assert {r.name for r in reqs} == {"starlette", "pydantic", "dirty-equals"}


def test_requirements_from_setup_py(tmp_path):
    setup = "setup(name='requests', install_requires=['urllib3>=1.21.1,<3', 'idna>=2.5'])"
    own, reqs = snapshot_requirements(_snapshot(tmp_path, {"setup.py": setup}))
    assert own == "requests" and {r.name for r in reqs} == {"urllib3", "idna"}


def test_task_wheels_drop_own_package_and_respect_pins(tmp_path):
    snap = _snapshot(tmp_path, {"pyproject.toml": PYPROJECT})
    src = _wheels(tmp_path, [
        "fastapi-0.110.0-py3-none-any.whl",
        "starlette-0.38.0-py3-none-any.whl",
        "starlette-0.48.0-py3-none-any.whl",
        "starlette-1.6.0-py3-none-any.whl",
        "pydantic-2.13.4-py3-none-any.whl",
        "rich-14.0.0-py3-none-any.whl",
    ])
    out = build_task_wheels(snap, src, tmp_path / "cache")
    names = sorted(p.name for p in out.glob("*.whl"))
    assert names == ["pydantic-2.13.4-py3-none-any.whl", "rich-14.0.0-py3-none-any.whl",
                     "starlette-0.48.0-py3-none-any.whl"]
    assert build_task_wheels(snap, src, tmp_path / "cache") == out  # cached by content
