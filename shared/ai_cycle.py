"""Deprecated compatibility shim.

The old hardcoded AI-cycle dict has been replaced by the thesis-aware, editable
tagging system in `shared/tagging.py` (buckets live in `tags.json`). This module is
kept only so older imports keep working. New code should import from `shared.tagging`.
"""

from __future__ import annotations

from shared.tagging import resolve as bucket, taxonomy as _taxonomy  # noqa: F401


def _labels() -> dict[str, str]:
    return {t["id"]: t["label"] for t in _taxonomy()}


# Back-compat: some callers did `from shared.ai_cycle import LABELS`.
LABELS = _labels()
