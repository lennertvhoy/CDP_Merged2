from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KBO_ZIP_FILENAME = "KboOpenData_0285_2026_02_27_Full.zip"
KBO_ZIP_GLOB = "KboOpenData_*_Full.zip"


def resolve_kbo_zip_path(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the KBO archive path from env or the active repo checkout."""
    source = os.environ if env is None else env

    configured = source.get("KBO_ZIP_PATH")
    if configured:
        return Path(configured).expanduser()

    repo_default = PROJECT_ROOT / DEFAULT_KBO_ZIP_FILENAME
    if repo_default.exists():
        return repo_default

    matches = sorted(PROJECT_ROOT.glob(KBO_ZIP_GLOB))
    if matches:
        return matches[-1]

    return repo_default
