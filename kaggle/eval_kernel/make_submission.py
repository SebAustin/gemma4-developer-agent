"""CPU kernel whose only job is to emit submission.zip for a code-competition submission.

Rendered by `g4 submission-kernel`; the packaged bundle is embedded as base64. Submit with
`kaggle competitions submit gemma-4-developer-agent -k <kernel> -f submission.zip -v <version>`.
"""

import base64
import hashlib
from pathlib import Path

BUNDLE_ZIP_B64 = "__G4_BUNDLE_B64__"
BUNDLE_HASH = "__G4_BUNDLE_HASH__"

payload = base64.b64decode(BUNDLE_ZIP_B64)
Path("/kaggle/working/submission.zip").write_bytes(payload)
print(f"wrote submission.zip ({len(payload)} bytes, bundle {BUNDLE_HASH}, sha256 {hashlib.sha256(payload).hexdigest()[:12]})")
