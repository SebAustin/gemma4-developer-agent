"""Build a deterministic ``submission.zip`` with ``agent.yaml`` at the archive root."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from .validate import validate_bundle

ALLOWED_EXTENSIONS = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
MAX_TOTAL_BYTES = 3 * 1024**3
_FIXED_DATE = (2026, 1, 1, 0, 0, 0)  # constant mtime -> byte-identical zips for identical bundles
_SKIP_PARTS = {"__pycache__", ".DS_Store", ".pytest_cache"}


class PackagingError(RuntimeError):
    pass


def _bundle_files(bundle: Path) -> list[Path]:
    files = []
    for p in sorted(bundle.rglob("*")):
        rel = p.relative_to(bundle)
        if any(part in _SKIP_PARTS for part in rel.parts) or p.is_dir():
            continue
        if p.is_symlink():
            raise PackagingError(f"symlinks are rejected by the harness: {rel}")
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise PackagingError(f"disallowed file extension: {rel}")
        files.append(p)
    return files


def bundle_hash(bundle: str | Path) -> str:
    """Content hash of a bundle; used as the experiment config id."""
    bundle = Path(bundle)
    h = hashlib.sha256()
    for p in _bundle_files(bundle):
        h.update(p.relative_to(bundle).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def package_bundle(bundle: str | Path, out_zip: str | Path, *, validate: bool = True) -> Path:
    bundle, out_zip = Path(bundle).resolve(), Path(out_zip).resolve()
    if validate:
        report = validate_bundle(bundle)
        if not report.ok:
            raise PackagingError("bundle failed validation:\n" + report.format())
    files = _bundle_files(bundle)
    total = sum(p.stat().st_size for p in files)
    if total > MAX_TOTAL_BYTES:
        raise PackagingError(f"unpacked size {total:,} B exceeds the 3 GiB limit")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            info = zipfile.ZipInfo(p.relative_to(bundle).as_posix(), date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_STORED if p.suffix == ".safetensors" else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, p.read_bytes())
    return out_zip
