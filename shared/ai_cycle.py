"""AI capital-cycle bucket classifier.

Tags each underlying to where it sits in the AI buildout so the portfolio report can
show concentration by *thematic role*, not just by ticker. This encodes the 3-group /
Bucket-A-vs-B framework we built:

  G1  Beaten-down / re-rating SaaS applying AI to an existing book of business.
      Cheap-ish, earnings risk is execution not a capex cliff.
  G2  Megacap spenders / hyperscalers funding the buildout from cash flow. Already
      de-rated off 2024-25 highs; downside is earnings risk, not a multiple crash.
  G3A Picks-and-shovels, SELF-FUNDED (semis/power/infra incumbents). Cyclical; the
      "unloved rotation" crowded here — carries the bust risk if capex blinks.
  G3B Picks-and-shovels, DEBT-FUNDED pure-plays (neoclouds, single-customer infra).
      Highest torque up, first to be wiped out if financing tightens (Bucket A).
  NON Not an AI-cycle name (crypto, unrelated).

This is a judgment map, not gospel — update it as the thesis evolves. Unknown tickers
return "UNTAGGED" so they surface for manual classification rather than hiding.
"""

from __future__ import annotations

_BUCKETS: dict[str, str] = {
    # G1 — beaten-down / re-rating application SaaS
    "NOW": "G1", "CRM": "G1", "WDAY": "G1", "ADBE": "G1", "HUBS": "G1",
    "MNDY": "G1", "SHOP": "G1", "ZS": "G1", "DDOG": "G1", "SNOW": "G1",
    "CRWD": "G1", "TEAM": "G1", "NET": "G1", "RBRK": "G1", "PATH": "G1",
    "TWLO": "G1", "OKTA": "G1", "PANW": "G1",
    # G2 — megacap spenders / hyperscalers (self-funded from cash flow)
    "MSFT": "G2", "META": "G2", "AMZN": "G2", "GOOG": "G2", "GOOGL": "G2",
    "AAPL": "G2", "ORCL": "G2", "TSLA": "G2",
    # G3A — picks-and-shovels, self-funded incumbents (semis / power / infra)
    "AVGO": "G3A", "MU": "G3A", "NVDA": "G3A", "AMD": "G3A", "TSM": "G3A",
    "VRT": "G3A", "CLS": "G3A", "COHR": "G3A", "GEV": "G3A", "CEG": "G3A",
    "FIX": "G3A", "ANET": "G3A", "MRVL": "G3A", "LRCX": "G3A", "KLAC": "G3A",
    "ASML": "G3A", "SMCI": "G3A", "DELL": "G3A", "PWR": "G3A", "ETN": "G3A",
    # G3B — debt-funded pure-play infra (neoclouds / miners pivoting to HPC hosting)
    "NBIS": "G3B", "CRWV": "G3B", "IREN": "G3B", "APLD": "G3B", "CIFR": "G3B",
    "RIOT": "G3B", "WULF": "G3B", "CORZ": "G3B", "CLSK": "G3B",
    # NON — not an AI-cycle capex name
    "BTC": "NON", "ETH": "NON", "DOGE": "NON",
    "HOOD": "NON",   # broker/fintech momentum, not AI capex
    "ASPI": "NON",   # isotope enrichment — adjacent at best, not core AI cycle
    "NFLX": "NON",   # consumer streaming; AI-assisted but not a capex-cycle name
    "KRE": "NON",    # regional-bank ETF (hedge/short leg)
    "VYX": "NON",    # NCR Voyix — payments/retail tech
}

LABELS = {
    "G1": "G1 beaten SaaS (re-rating, execution risk)",
    "G2": "G2 megacap spender (de-rated, earnings risk)",
    "G3A": "G3A picks&shovels self-funded (crowded, capex-blink risk)",
    "G3B": "G3B debt-funded pure-play (highest torque / first to break)",
    "NON": "Non-AI-cycle",
    "UNTAGGED": "Untagged — classify manually",
}


def bucket(symbol: str) -> str:
    """Return the AI-cycle bucket code for an underlying ticker."""
    if not symbol:
        return "UNTAGGED"
    return _BUCKETS.get(symbol.upper(), "UNTAGGED")
