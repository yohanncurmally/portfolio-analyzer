"""Render a portfolio dashboard PNG from an enriched snapshot.

Six panels: asset-class allocation, per-account allocation, options moneyness vs.
days-to-expiry, controlled notional by underlying, time-value by expiry month, and
thematic-bucket exposure vs. the target model in docs/target_portfolio.md.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.enrich import EnrichedSnapshot

# Underlying -> thematic bucket, aligned to docs/target_portfolio.md.
THEME = {
    # Bucket 1: AI software recovery
    "NOW": "AI Software", "HUBS": "AI Software", "ADBE": "AI Software",
    "WDAY": "AI Software", "TEAM": "AI Software", "MNDY": "AI Software",
    "RBRK": "AI Software", "SHOP": "AI Software", "ZS": "AI Software",
    "FIG": "AI Software", "MDB": "AI Software", "CRM": "AI Software",
    # Bucket 2: mega-cap AI
    "GOOGL": "Mega-cap AI", "MSFT": "Mega-cap AI", "ORCL": "Mega-cap AI",
    # Bucket 3: AI power infrastructure
    "GEV": "Power Infra", "CEG": "Power Infra", "VST": "Power Infra",
    "PWR": "Power Infra", "BE": "Power Infra", "FIX": "Power Infra",
    # Bucket 4: miners / power compute
    "RIOT": "Miners/Compute", "CLSK": "Miners/Compute", "IREN": "Miners/Compute",
    "CORZ": "Miners/Compute", "APLD": "Miners/Compute",
    # Bucket 5: nuclear supply & special situations
    "CCJ": "Nuclear/Special", "VRT": "Nuclear/Special", "DAL": "Nuclear/Special",
    "COHR": "Nuclear/Special", "ASPI": "Nuclear/Special",
    # China tech
    "BIDU": "China Tech", "TCEHY": "China Tech", "MPNGY": "China Tech",
}
# Target model weights from docs/target_portfolio.md (the 5 buckets).
TARGET_WEIGHTS = {
    "AI Software": 35, "Mega-cap AI": 20, "Power Infra": 25,
    "Miners/Compute": 12, "Nuclear/Special": 8,
}


def _theme(sym: str) -> str:
    return THEME.get(sym, "Other")


def render(es: EnrichedSnapshot, path: str) -> str:
    snap = es.snap
    fig, axes = plt.subplots(3, 2, figsize=(16, 18))
    fig.suptitle(
        f"Portfolio Dashboard  |  {snap.timestamp[:10]}  |  "
        f"Total ${snap.total_value:,.0f}  |  Controlled notional ${es.total_notional:,.0f}  "
        f"({es.total_notional / snap.total_value:.1f}x)",
        fontsize=15, fontweight="bold",
    )

    # 1) Asset-class allocation
    ax = axes[0][0]
    vals = [snap.equity_value, snap.options_value, snap.cash]
    labels = [f"Equities\n${snap.equity_value:,.0f}", f"Options\n${snap.options_value:,.0f}",
              f"Cash\n${snap.cash:,.0f}"]
    ax.pie(vals, labels=labels, autopct="%1.0f%%", colors=["#4C72B0", "#DD8452", "#55A868"],
           startangle=90, wedgeprops=dict(width=0.42))
    ax.set_title("Asset-class allocation", fontweight="bold")

    # 2) Per-account total
    ax = axes[0][1]
    names = [a.name.replace("Robinhood ", "") for a in snap.accounts]
    eq = [a.equity_value for a in snap.accounts]
    op = [a.options_value for a in snap.accounts]
    csh = [a.cash for a in snap.accounts]
    ax.bar(names, eq, label="Equities", color="#4C72B0")
    ax.bar(names, op, bottom=eq, label="Options", color="#DD8452")
    ax.bar(names, csh, bottom=[e + o for e, o in zip(eq, op)], label="Cash", color="#55A868")
    ax.set_title("Value by account", fontweight="bold")
    ax.set_ylabel("USD")
    ax.legend()
    for i, a in enumerate(snap.accounts):
        ax.text(i, a.total_value, f"${a.total_value:,.0f}", ha="center", va="bottom", fontsize=9)

    # 3) Moneyness vs DTE scatter (size = notional)
    ax = axes[1][0]
    for o in es.options:
        if o.moneyness is None or o.dte is None:
            continue
        color = "#55A868" if o.moneyness >= 1.0 else ("#DD8452" if o.moneyness >= 0.85 else "#C44E52")
        ax.scatter(o.dte, o.moneyness, s=max(20, o.notional / 1500), color=color, alpha=0.6,
                   edgecolors="black", linewidths=0.5)
        ax.annotate(o.symbol, (o.dte, o.moneyness), fontsize=7, alpha=0.8)
    ax.axhline(1.0, color="black", lw=1, ls="--", alpha=0.6)
    ax.axhline(0.85, color="#C44E52", lw=0.8, ls=":", alpha=0.5)
    ax.set_xlabel("Days to expiry")
    ax.set_ylabel("Moneyness (spot/strike; >1 = ITM)")
    ax.set_title("Option moneyness vs. time (bubble = notional)", fontweight="bold")

    # 4) Controlled notional by underlying (top 15)
    ax = axes[1][1]
    notional = defaultdict(float)
    for o in es.options:
        notional[o.symbol] += o.notional
    top = sorted(notional.items(), key=lambda x: x[1], reverse=True)[:15]
    syms = [t[0] for t in top][::-1]
    nvals = [t[1] for t in top][::-1]
    ax.barh(syms, nvals, color="#8172B3")
    ax.set_title("Controlled notional by underlying (top 15)", fontweight="bold")
    ax.set_xlabel("USD notional (spot x 100 x contracts)")
    for i, v in enumerate(nvals):
        ax.text(v, i, f" ${v/1000:,.0f}k", va="center", fontsize=8)

    # 5) Time value (extrinsic) by expiry month, stacked on intrinsic
    ax = axes[2][0]
    by_month_ext = defaultdict(float)
    by_month_int = defaultdict(float)
    for o in es.options:
        try:
            m = datetime.strptime(o.expiration[:10], "%Y-%m-%d").strftime("%Y-%m")
        except (ValueError, TypeError):
            continue
        by_month_ext[m] += o.extrinsic_value
        by_month_int[m] += o.intrinsic_per_share * 100 * o.quantity
    months = sorted(set(by_month_ext) | set(by_month_int))
    intr = [by_month_int[m] for m in months]
    extr = [by_month_ext[m] for m in months]
    ax.bar(months, intr, label="Intrinsic (real)", color="#4C72B0")
    ax.bar(months, extr, bottom=intr, label="Extrinsic (time value at risk)", color="#C44E52")
    ax.set_title("Option value by expiry month: real vs. decaying", fontweight="bold")
    ax.set_ylabel("USD")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()

    # 6) Thematic bucket exposure vs target
    ax = axes[2][1]
    bucket_exposure = defaultdict(float)  # by controlled notional + equity MV
    for a in snap.accounts:
        for e in a.equities:
            bucket_exposure[_theme(e.symbol)] += e.market_value
    for o in es.options:
        bucket_exposure[_theme(o.symbol)] += o.notional
    buckets = list(TARGET_WEIGHTS.keys()) + ["China Tech", "Other"]
    total_exp = sum(bucket_exposure.values()) or 1.0
    actual_pct = [bucket_exposure.get(b, 0.0) / total_exp * 100 for b in buckets]
    target_pct = [TARGET_WEIGHTS.get(b, 0) for b in buckets]
    x = range(len(buckets))
    ax.bar([i - 0.2 for i in x], actual_pct, width=0.4, label="Actual (exposure-wt)", color="#DD8452")
    ax.bar([i + 0.2 for i in x], target_pct, width=0.4, label="Target", color="#4C72B0")
    ax.set_xticks(list(x))
    ax.set_xticklabels(buckets, rotation=30, ha="right")
    ax.set_ylabel("% of thematic exposure")
    ax.set_title("Thematic buckets: actual vs. target model", fontweight="bold")
    ax.legend()

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path
