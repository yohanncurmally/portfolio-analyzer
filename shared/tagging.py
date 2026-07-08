"""Portfolio tagging: thesis-aware thematic buckets, resolved from an editable cache.

This replaces the old hardcoded AI-cycle dict with a two-layer system that works for
any portfolio and any thesis:

  1. A *taxonomy* of buckets (id, label, color, desc). It is data, not code, so it
     adapts to the user's actual strategy (AI capital cycle, dividend income, sector
     rotation, whatever). Keep it small (aim <=8 buckets) so the exposure chart splits
     cleanly, and it always carries an "other" catch-all so nothing is force-fit.

  2. A per-holding map (ticker -> bucket id) that Claude fills in during the skill run,
     grounded by what each name actually is and how the portfolio expresses it.

Granularity matches the instrument: a single name gets a leaf bucket (e.g. AI picks &
shovels vs debt-funded infra); a basket ETF gets the parent theme only, because you
cannot honestly split a mixed ETF into a leaf sub-bucket without look-through.

Resolution order for a ticker: manual override > cached tag > "other".
The math (greeks, carry, exposure) never depends on this; only the *labels* do.

Storage: `tags.json` at the repo root (gitignored, holds your real book), falling back
to `tags.example.json` (shipped template), then a generic sector taxonomy baked in here.
Override the path with the PORTFOLIO_TAGS env var.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[1]
_TAGS_PATH = Path(os.environ.get("PORTFOLIO_TAGS") or (_ROOT / "tags.json"))
_EXAMPLE_PATH = _ROOT / "tags.example.json"

OTHER_ID = "other"

# Baked-in fallback taxonomy: a generic, thesis-agnostic sector/asset-class split so a
# brand-new user with no tags.json still gets a clean read. A personalized run replaces
# this via tags.json.
_GENERIC_TAXONOMY = [
    {"id": "broad-market", "label": "Broad market", "color": "#6e9e63",
     "desc": "Diversified index ETFs (VOO, VTI, VT). Read as diversification, not concentration."},
    {"id": "technology", "label": "Technology", "color": "#58a6ff",
     "desc": "Tech single names."},
    {"id": "financials", "label": "Financials", "color": "#bc8cff",
     "desc": "Banks, payments, insurers."},
    {"id": "healthcare", "label": "Healthcare", "color": "#3fb0ac",
     "desc": "Pharma, biotech, medical devices."},
    {"id": "consumer", "label": "Consumer", "color": "#e3934f",
     "desc": "Retail, staples, discretionary."},
    {"id": "energy-industrials", "label": "Energy & industrials", "color": "#d29922",
     "desc": "Energy, materials, industrials."},
    {"id": "crypto", "label": "Crypto", "color": "#f0883e",
     "desc": "Digital assets."},
    {"id": OTHER_ID, "label": "Other", "color": "#8b949e",
     "desc": "Doesn't fit the thesis, or not yet classified."},
]


def _tag_id(entry) -> Optional[str]:
    """A holding entry may be a bare string id or a dict {tag, asset_class, ...}."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("tag")
    return None


class Tagger:
    """Loaded view over a tags file. Cheap to construct; hold one per process."""

    def __init__(self, data: Optional[dict] = None):
        data = data or {}
        tax = data.get("taxonomy") or _GENERIC_TAXONOMY
        # Guarantee an "other" bucket exists so resolution never returns a dead id.
        if not any(t.get("id") == OTHER_ID for t in tax):
            tax = list(tax) + [{"id": OTHER_ID, "label": "Other", "color": "#8b949e",
                                "desc": "Doesn't fit the thesis, or not yet classified."}]
        self.version = data.get("version", 1)
        self.thesis_hash = data.get("thesis_hash")
        self.taxonomy: list[dict] = tax
        self._by_id: dict[str, dict] = {t["id"]: t for t in tax}
        self._holdings: dict[str, dict] = {k.upper(): v for k, v in (data.get("holdings") or {}).items()}
        self._overrides: dict[str, dict] = {k.upper(): v for k, v in (data.get("overrides") or {}).items()}

    # --- resolution -----------------------------------------------------------
    def resolve(self, symbol: Optional[str]) -> str:
        """Return the bucket id for a ticker. Override > cached tag > 'other'."""
        if not symbol:
            return OTHER_ID
        s = symbol.upper()
        for src in (self._overrides, self._holdings):
            tid = _tag_id(src.get(s))
            if tid and tid in self._by_id:
                return tid
        return OTHER_ID

    def is_explicit(self, symbol: Optional[str]) -> bool:
        """True if the ticker was deliberately tagged (not just falling through to other)."""
        if not symbol:
            return False
        s = symbol.upper()
        return _tag_id(self._overrides.get(s)) in self._by_id or _tag_id(self._holdings.get(s)) in self._by_id

    def needs_tagging(self, symbols) -> list[str]:
        """Tickers with no deliberate tag yet, so Claude knows what to classify."""
        seen: dict[str, None] = {}
        for s in symbols:
            if s and not self.is_explicit(s):
                seen[s.upper()] = None
        return sorted(seen)

    # --- taxonomy accessors ---------------------------------------------------
    def label(self, tag_id: str) -> str:
        t = self._by_id.get(tag_id)
        return t["label"] if t else tag_id

    def color(self, tag_id: str) -> str:
        t = self._by_id.get(tag_id)
        return t.get("color", "#8b949e") if t else "#8b949e"

    def desc(self, tag_id: str) -> str:
        t = self._by_id.get(tag_id)
        return t.get("desc", "") if t else ""

    def taxonomy_map(self) -> dict[str, dict]:
        """id -> {label, color, desc}, for the dashboard to render labels from data."""
        return {t["id"]: {"label": t["label"], "color": t.get("color", "#8b949e"),
                          "desc": t.get("desc", "")} for t in self.taxonomy}


def _load_data() -> dict:
    for path in (_TAGS_PATH, _EXAMPLE_PATH):
        try:
            if path.exists():
                return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
    return {}


# Module-level singleton, lazily loaded so importing is cheap and tests can reload().
_TAGGER: Optional[Tagger] = None


def tagger() -> Tagger:
    global _TAGGER
    if _TAGGER is None:
        _TAGGER = Tagger(_load_data())
    return _TAGGER


def reload() -> Tagger:
    """Force a re-read of the tags file (after Claude edits it mid-run, or in tests)."""
    global _TAGGER
    _TAGGER = Tagger(_load_data())
    return _TAGGER


# --- module-level convenience API (what callers import) -----------------------
def resolve(symbol: Optional[str]) -> str:
    return tagger().resolve(symbol)


def label(tag_id: str) -> str:
    return tagger().label(tag_id)


def color(tag_id: str) -> str:
    return tagger().color(tag_id)


def desc(tag_id: str) -> str:
    return tagger().desc(tag_id)


def taxonomy() -> list[dict]:
    return tagger().taxonomy


def taxonomy_map() -> dict[str, dict]:
    return tagger().taxonomy_map()


def needs_tagging(symbols) -> list[str]:
    return tagger().needs_tagging(symbols)
