"""Per-task wheel sets that make local Docker verification faithful to scoring.

The harness injects the *highest* version of every wheel in the wheels dir into site-packages.
With the public wheel set that breaks two ways:
1. The repo's own package (e.g. `rich`) is injected and shadows the patched /workspace copy.
   At scoring time the repos are private, so no such wheel exists; we drop it.
2. Newest versions violate the snapshot's pins (starlette 1.x vs old fastapi). We keep only
   versions that satisfy the constraints declared in the snapshot's pyproject.toml.

The harness caches unpacked wheels under ``tempfile.gettempdir()/swegemma_sp_cache_v8`` keyed
by a fixed name, so each wheel set also gets its own temp dir (see ``activate``).
"""

from __future__ import annotations

import hashlib
import io
import re
import tarfile
import tempfile
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


def _read_member(snapshot: Path, name: str) -> str | None:
    with tarfile.open(snapshot) as tf:
        for candidate in (f"./{name}", name):
            try:
                member = tf.extractfile(candidate)
            except KeyError:
                continue
            if member is not None:
                return io.TextIOWrapper(member, encoding="utf-8", errors="replace").read()
    return None


def snapshot_requirements(snapshot: Path) -> tuple[str | None, list[Requirement]]:
    """(own distribution name, declared requirements) from the snapshot's packaging metadata."""
    reqs: list[str] = []
    own = None
    pyproject = _read_member(snapshot, "pyproject.toml")
    if pyproject:
        data = tomllib.loads(pyproject)
        project = data.get("project", {})
        own = project.get("name") or data.get("tool", {}).get("poetry", {}).get("name")
        reqs += project.get("dependencies", [])
        for extra in project.get("optional-dependencies", {}).values():
            reqs += extra
        for group in data.get("dependency-groups", {}).values():
            reqs += [r for r in group if isinstance(r, str)]
    setup_py = _read_member(snapshot, "setup.py") or ""
    if own is None:
        m = re.search(r"name\s*=\s*['\"]([\w.-]+)['\"]", setup_py)
        own = m.group(1) if m else None
    reqs += re.findall(r"['\"]([A-Za-z][\w.-]*\s*(?:\[[^\]]*\])?\s*[<>=!~][^'\"]*)['\"]", setup_py)
    parsed = []
    for r in reqs:
        try:
            parsed.append(Requirement(r))
        except InvalidRequirement:
            continue
    return own, parsed


def _wheel_name_version(path: Path) -> tuple[str, Version] | None:
    parts = path.name[:-4].split("-")
    if len(parts) < 5:
        return None
    try:
        return canonicalize_name(parts[0]), Version(parts[1])
    except InvalidVersion:
        return None


def build_task_wheels(snapshot: Path, source: Path, cache_root: Path) -> Path:
    own, reqs = snapshot_requirements(snapshot)
    own_norm = canonicalize_name(own) if own else None
    specs: dict[str, list] = {}
    for r in reqs:
        specs.setdefault(canonicalize_name(r.name), []).append(r.specifier)

    selected = []
    for whl in sorted(source.glob("*.whl")):
        nv = _wheel_name_version(whl)
        if nv is None:
            continue
        name, version = nv
        if name == own_norm:
            continue
        if any(not spec.contains(version, prereleases=True) for spec in specs.get(name, []) if str(spec)):
            continue
        selected.append(whl)

    key = hashlib.sha256("\n".join(w.name for w in selected).encode()).hexdigest()[:12]
    out = cache_root / f"wheels_{key}"
    if not out.exists():
        tmp = cache_root / f".tmp_{key}"
        tmp.mkdir(parents=True, exist_ok=True)
        for whl in selected:
            target = tmp / whl.name
            if not target.exists():
                target.hardlink_to(whl)
        tmp.rename(out)
    return out


def activate(wheels_dir: Path) -> None:
    """Point the harness's unpacked-wheel cache at a directory unique to this wheel set."""
    tmp = wheels_dir.parent / f"tmp_{wheels_dir.name}"
    tmp.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(tmp)
