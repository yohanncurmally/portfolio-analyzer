"""Interactive, self-contained HTML dashboard for an enriched snapshot.

Emits a single .html file (no external CDNs; inline data + SVG charts + vanilla JS,
so it opens offline). It adapts to the shape of the book: an equities-only portfolio,
an options-heavy one, or any mix all render cleanly with no blank panels. Options-only
panels (moneyness/DTE scatter, expiry wall, options table, the delta-leverage KPIs) only
appear when there are options; an equities table appears when there are equities; and the
AI-cycle bucket chart only shows when the book actually tilts into those buckets.

Reads only from EnrichedSnapshot (same object viz.render uses), so PNG and HTML stay
in lockstep. Per-position greeks/carry/bucket/flags come straight from analysis.enrich.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime

from analysis.enrich import EnrichedSnapshot
from shared.tagging import resolve as cycle_bucket, taxonomy_map, label as tag_label, \
    color as tag_color, desc as tag_desc, OTHER_ID

# Chart-only auto-collapse threshold: a thesis bucket holding less than this share of
# total exposure rolls into "Other" ON THE CHART (donut/bars/footer) so slivers don't
# clutter the read. Holdings keep their precise tag in the tables. 4% of exposure.
BUCKET_COLLAPSE_PCT = 0.04

# Column header tooltips for the positions tables (native title= hover, works offline).
OPT_COL_HELP = {
    "symbol": "Underlying ticker. C/P marks call or put; ·S marks a short (written) leg.",
    "strike": "Strike price of the option.",
    "expiration": "Expiration date.",
    "dte": "Days to expiry (calendar days from today).",
    "qty": "Number of contracts. Each contract controls 100 shares.",
    "mark": "Current option price, per share.",
    "mv": "Market value = mark × 100 × contracts. Negative for short legs.",
    "moneyness": "Moneyness. Calls: spot/strike; puts: strike/spot. Above 1 = in the money.",
    "delta": "Delta per share, signed for your side (long call +, long put −, shorts flip). Roughly the odds of finishing in the money.",
    "delta_notional": "Delta-adjusted dollar exposure (delta × 100 × contracts × spot). The honest directional risk; raw notional overstates it for OTM/short-dated legs.",
    "carry_pct_yr": "Annualized % the underlying must move in your favor just to break even on the leverage. Low = cheap (ITM/LEAP); high = expensive (deep OTM).",
    "extrinsic_value": "Time value at risk ($). This portion of the mark decays to zero by expiry if the underlying doesn't move.",
    "unrealized_pl": "Unrealized profit or loss versus your entry price.",
    "cycle_bucket": "Thesis bucket this name sits in. See the legend under the exposure-by-bucket chart above.",
    "verdict": "The tool's candid call for this leg, from the flags and economics.",
}
EQ_COL_HELP = {
    "symbol": "Ticker.",
    "account": "Which account holds it.",
    "qty": "Shares held.",
    "price": "Current price per share.",
    "avg_cost": "Average cost basis per share.",
    "mv": "Market value = shares × price.",
    "weight_pct": "Position size as a percent of total portfolio value.",
    "unrealized_pl": "Unrealized profit or loss versus cost basis.",
    "cycle_bucket": "Thesis bucket this name sits in. See the legend under the exposure-by-bucket chart above.",
}

# Tooltips for each field in the per-option drilldown panel (keyed by the on-screen label).
DRILL_HELP = {
    "Spot": "Current price of the underlying stock/ETF.",
    "Strike / DTE": "Strike price, and days to expiry (calendar days from today).",
    "Moneyness": "Spot/strike for calls (strike/spot for puts). Above 1.0 = in the money.",
    "% to strike": "How far the underlying must move to reach the strike. Negative means it's already past it (ITM).",
    "Implied vol": "The volatility the option's price implies. Higher = pricier option and bigger expected swings.",
    "Delta": "Per-share price sensitivity to the underlying, signed for your side. Also roughly the odds of finishing in the money.",
    "Delta-$ (directional)": "Delta × 100 × contracts × spot. Your true dollar directional exposure through this leg.",
    "Carry / yr": "Annualized % the underlying must move in your favor just to break even on the leverage. Low = cheap (ITM/LEAP); high = expensive (deep OTM).",
    "Mark / Avg": "Current option price versus your average entry price, per share.",
    "Market value": "Current dollar value of the position (mark × 100 × contracts). Negative for short legs.",
    "Intrinsic / sh": "The in-the-money portion per share (real value if exercised now).",
    "Extrinsic / sh": "The time-value portion per share. Decays to zero by expiry if the underlying doesn't move.",
    "Extrinsic $ (at risk)": "Total time value in dollars that decays to zero absent a move in the underlying.",
    "Extrinsic % of MV": "What share of this position's value is time value, i.e. the part at risk to decay.",
    "Controlled notional": "Shares controlled × spot (100 × contracts × spot). Gross exposure, before delta-adjustment.",
    "Unrealized P/L": "Mark-to-market gain or loss versus your entry price.",
}


# Broad-market ETFs that track a wide index. A large position in one of these is
# diversification, not single-name risk, so it doesn't trip the concentration flag.
# Conservative allowlist: anything not here is still treated as a concentrated bet.
BROAD_MARKET_ETFS = {
    # US total market / S&P 500 / large cap (incl. common mutual-fund equivalents)
    "VOO", "VTI", "SPY", "IVV", "ITOT", "SCHB", "SCHX", "VV", "SPLG", "SPTM",
    "IWB", "IWV", "FXAIX", "FZROX", "FSKAX", "FNILX", "SWPPX", "VFIAX", "VTSAX",
    # Nasdaq / broad
    "QQQ", "QQQM", "ONEQ",
    # mid / small broad
    "VO", "VB", "IJH", "IJR", "VXF", "SCHM", "SCHA", "MDY",
    # world / developed / emerging broad
    "VT", "VXUS", "VEU", "VEA", "VWO", "IXUS", "ACWI", "IEFA", "IEMG",
    "SCHF", "SCHE", "SPDW", "SPEM", "VEU",
    # broad dividend
    "SCHD", "VYM", "VIG", "DGRO", "DVY", "HDV", "NOBL",
    # broad bond aggregate
    "BND", "AGG", "BNDX", "SCHZ", "SPAB", "GOVT", "VCIT", "VCSH", "IUSB", "FXNAX",
}


def _is_broad_etf(sym: str) -> bool:
    return bool(sym) and sym.upper() in BROAD_MARKET_ETFS


def _verdict(o) -> tuple[str, str]:
    """Return (tag, one-line rationale): the candid per-position call."""
    f = set(o.flags)
    dte = o.dte if o.dte is not None else 999
    ext_pct = (o.extrinsic_value / abs(o.market_value)) if o.market_value else 0.0
    if dte < 0:
        return ("EXPIRED?", "Past expiration in the feed; verify it actually settled/closed.")
    if "LOTTERY" in f:
        return ("CLOSE / ROLL", "Deep-OTM + short-dated lottery ticket, the exact profile to exit. "
                "Bank it or roll into an ITM/LEAP with real delta.")
    if "EXPENSIVE_CARRY" in f:
        return ("DE-RISK", f"Carry {o.carry_pct_yr:.0f}%/yr; you're renting expensive leverage. "
                "Roll down-and-out (lower strike, more time) to cut the annualized cost.")
    if "SHORT_DATED" in f and ext_pct > 0.5:
        return ("DECIDE NOW", f"{dte}d left and {ext_pct*100:.0f}% of value is decaying time; "
                "roll out or take it off before theta does.")
    if "SHORT_DATED" in f:
        return ("DECIDE NOW", f"{dte}d to expiry; needs a hold/roll/close call this week.")
    if "HIGH_THETA" in f:
        return ("TRIM / ROLL", f"{ext_pct*100:.0f}% of MV is time value under 120d; heavy theta bleed.")
    if "LEAP" in f and (o.carry_pct_yr or 99) < 25:
        return ("CORE HOLD", "Long-dated, cheap carry; this is the kind of leverage to keep.")
    if o.moneyness is not None and o.moneyness >= 1.05:
        return ("HOLD", "ITM with real intrinsic; lower-risk leg, let it work.")
    return ("HOLD", "No acute flag; monitor against thesis and expiry.")


def _num(x):
    return None if x is None else round(float(x), 4)


# Per-holding narrative write-ups: the judgment layer on top of the algorithmic verdict.
# Authored by Claude during the skill run and keyed by underlying symbol. Optional; an
# absent file just hides the section. Each entry may carry: call (headline recommendation),
# one_liner, thesis, bull/base/bear (scenario cases), rationale (why the call follows), and
# invalidation (what would change the call). Only fields that are present get rendered.
_WRITEUPS_PATH = os.environ.get("PORTFOLIO_WRITEUPS", "writeups.json")
_WRITEUPS_EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "writeups.example.json")


def _load_writeups(source: str) -> dict:
    """Load writeups.json (env PORTFOLIO_WRITEUPS overrides the path). For the demo book we
    fall back to the shipped writeups.example.json so a fresh clone renders the section out of
    the box; for a real book only the user's own file is used (absent -> section hidden)."""
    path = _WRITEUPS_PATH
    if not os.path.exists(path) and source == "demo" and os.path.exists(_WRITEUPS_EXAMPLE):
        path = _WRITEUPS_EXAMPLE
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    wu = data.get("writeups", data)
    return wu if isinstance(wu, dict) else {}


def _build_data(es: EnrichedSnapshot) -> dict:
    snap = es.snap
    total = snap.total_value or 1.0

    opt_pl = sum(o.unrealized_pl for o in es.options if o.unrealized_pl is not None)
    eq_pl = sum(e.unrealized_pl for a in snap.accounts for e in a.equities
                if e.unrealized_pl is not None)

    # ---- equities (present for most books; the options-only view simply omits this) ----
    equities = []
    for a in snap.accounts:
        for e in a.equities:
            equities.append({
                "symbol": e.symbol, "account": a.name, "qty": e.quantity,
                "price": _num(e.price), "avg_cost": _num(e.avg_cost),
                "mv": _num(e.market_value),
                "weight_pct": round((e.market_value or 0.0) / total * 100, 1),
                "unrealized_pl": _num(e.unrealized_pl),
                "cycle_bucket": cycle_bucket(e.symbol),
            })
    equities.sort(key=lambda x: -(x["mv"] or 0))

    # ---- options ----
    positions = []
    for o in es.options:
        tag, why = _verdict(o)
        ext_pct_mv = (o.extrinsic_value / abs(o.market_value)) if o.market_value else None
        positions.append({
            "symbol": o.symbol, "type": o.option_type, "side": o.side,
            "strike": o.strike, "expiration": o.expiration[:10] if o.expiration else None,
            "dte": o.dte, "qty": o.quantity, "mark": _num(o.mark),
            "mv": _num(o.market_value), "avg_price": _num(o.avg_price),
            "unrealized_pl": _num(o.unrealized_pl), "spot": _num(o.spot),
            "moneyness": _num(o.moneyness), "pct_to_strike": _num(o.pct_to_strike),
            "intrinsic": _num(o.intrinsic_per_share), "extrinsic_ps": _num(o.extrinsic_per_share),
            "extrinsic_value": _num(o.extrinsic_value), "extrinsic_pct_mv": _num(ext_pct_mv),
            "notional": _num(o.notional), "iv": _num(o.iv), "delta": _num(o.delta),
            "delta_notional": _num(o.delta_notional), "carry_pct_yr": _num(o.carry_pct_yr),
            "cycle_bucket": o.cycle_bucket, "flags": o.flags,
            "verdict": tag, "why": why,
        })
    positions.sort(key=lambda p: -(p["mv"] or 0))

    has_options = bool(positions)
    has_equities = bool(equities)

    # ---- deep-dive write-ups (Claude-authored narrative, keyed by underlying symbol) ----
    # We only surface a write-up for a symbol the book actually holds, and order them by
    # the name's weight in the book (equity MV + option delta-$) so the biggest bets lead.
    book_weight: dict[str, float] = defaultdict(float)
    for e in equities:
        book_weight[e["symbol"]] += abs(e["mv"] or 0.0)
    for p in positions:
        book_weight[p["symbol"]] += abs(p["delta_notional"] or p["mv"] or 0.0)
    writeups = []
    for sym, w in _load_writeups(snap.source).items():
        if sym not in book_weight or not isinstance(w, dict):
            continue
        writeups.append({
            "symbol": sym,
            "weight": round(book_weight[sym]),
            "bucket": cycle_bucket(sym),
            "call": w.get("call") or w.get("verdict") or "",
            "one_liner": w.get("one_liner") or w.get("summary") or "",
            "thesis": w.get("thesis") or "",
            "bull": w.get("bull") or w.get("bull_case") or "",
            "base": w.get("base") or w.get("base_case") or "",
            "bear": w.get("bear") or w.get("bear_case") or "",
            "rationale": w.get("rationale") or w.get("why") or "",
            "invalidation": w.get("invalidation") or w.get("what_would_change") or "",
            "updated": w.get("updated") or "",
        })
    writeups.sort(key=lambda x: -x["weight"])
    has_writeups = bool(writeups)

    # ---- whole-book exposure (equity MV + option delta-$), portfolio-agnostic ----
    # pct is each bucket's SHARE OF TOTAL EXPOSURE (so the buckets compose to ~100%),
    # not delta-$/NAV (which is a leverage ratio and can exceed 100% on a levered book).
    bucket_dv = es.exposure_by_bucket
    total_exposure = sum(abs(v) for v in bucket_dv.values()) or 1.0
    # Chart-only auto-collapse: any bucket below this share of total exposure is a
    # sliver that clutters the donut/bars without changing the read, so it rolls into
    # "Other" FOR THE CHART ONLY. Each holding keeps its precise tag in the tables
    # below; this only affects the exposure-by-bucket visual and its footer summary.
    collapsed = defaultdict(float)
    for tid, dv in bucket_dv.items():
        keep = tid if (tid == OTHER_ID or abs(dv) / total_exposure >= BUCKET_COLLAPSE_PCT) else OTHER_ID
        collapsed[keep] += dv
    buckets = [{"id": tid, "label": tag_label(tid), "color": tag_color(tid),
                "desc": tag_desc(tid), "delta_notional": round(dv),
                "pct": round(abs(dv) / total_exposure * 100, 1)} for tid, dv in collapsed.items()]
    # sort by weight, keep "Other" last so the catch-all reads as the tail of the chart
    buckets.sort(key=lambda b: (b["id"] == OTHER_ID, -abs(b["delta_notional"])))
    # Show the bucket chart once a meaningful share of the book is in thesis buckets
    # (i.e. not everything sitting in the "other" catch-all).
    tagged_weight = sum(abs(v) for c, v in bucket_dv.items() if c != OTHER_ID)
    show_buckets = (tagged_weight / total) > 0.05

    exposure = [{"symbol": s, "delta_notional": round(v)}
                for s, v in es.exposure_by_symbol.items()]

    # ---- expiry wall (options only) ----
    ext_m, int_m, cnt_m = defaultdict(float), defaultdict(float), defaultdict(int)
    for o in es.options:
        try:
            m = datetime.strptime(o.expiration[:10], "%Y-%m-%d").strftime("%Y-%m")
        except (ValueError, TypeError):
            continue
        ext_m[m] += o.extrinsic_value
        int_m[m] += o.intrinsic_per_share * 100 * o.quantity
        cnt_m[m] += 1
    expiry = [{"month": m, "intrinsic": round(int_m[m]), "extrinsic": round(ext_m[m]),
               "count": cnt_m[m]} for m in sorted(set(ext_m) | set(int_m))]

    # ---- prioritized actions (shape-aware) ----
    actions = []
    if has_options:
        sd = sorted({p["symbol"] for p in positions if "SHORT_DATED" in p["flags"]})
        lot = sorted({p["symbol"] for p in positions if "LOTTERY" in p["flags"]})
        exp = sorted({p["symbol"] for p in positions if "EXPENSIVE_CARRY" in p["flags"]})
        if sd:
            actions.append(("THIS WEEK", f"Expiring <30d, hold/roll/close decision: {', '.join(sd)}"))
        if lot:
            actions.append(("DE-RISK", f"Deep-OTM lottery tickets to exit/roll ITM: {', '.join(lot)}"))
        if exp:
            actions.append(("DE-RISK", f"Expensive carry (>40%/yr), roll down-and-out: {', '.join(exp)}"))
        dlev = es.net_delta_notional / total
        if dlev > 2.5:
            actions.append(("LEVERAGE", f"Delta-adjusted exposure {dlev:.2f}x NAV, directional risk is high."))
    # single-name concentration: skip broad-market ETFs (a big index position is
    # diversification, not a concentrated bet)
    top_single = next((e for e in exposure if not _is_broad_etf(e["symbol"])), None)
    if top_single:
        conc = abs(top_single["delta_notional"]) / total
        if conc > 0.35:
            actions.append(("CONCENTRATION",
                            f"{top_single['symbol']} is {conc*100:.0f}% of NAV, your largest "
                            "single-name position. Confirm that concentration is intended."))
    if snap.cash / total < 0.10:
        actions.append(("LIQUIDITY", f"Cash is {snap.cash/total*100:.0f}% of NAV, thin dry powder."))

    # ---- KPIs for the top row of the book summary (concentration / diversification) ----
    top_holding = None
    if exposure:
        t = exposure[0]
        top_holding = {"symbol": t["symbol"],
                       "pct": round(abs(t["delta_notional"]) / total * 100, 1),
                       "broad": _is_broad_etf(t["symbol"])}
    n_holdings = len({e["symbol"] for e in equities}) + len({p["symbol"] for p in positions})

    return {
        "meta": {"timestamp": snap.timestamp, "source": snap.source,
                 "generated": datetime.now().strftime("%Y-%m-%d %H:%M")},
        "shape": {"has_options": has_options, "has_equities": has_equities,
                  "show_buckets": show_buckets, "has_writeups": has_writeups},
        "totals": {
            "total_value": round(total), "equity_value": round(snap.equity_value),
            "options_value": round(snap.options_value), "cash": round(snap.cash),
            "cash_pct": round(snap.cash / total * 100, 1),
            "invested_value": round(total - snap.cash),
            "invested_pct": round((total - snap.cash) / total * 100, 1),
            "controlled_notional": round(es.total_notional),
            "net_delta_notional": round(es.net_delta_notional),
            "leverage_x": round(es.total_notional / total, 2),
            "delta_leverage_x": round(es.net_delta_notional / total, 2),
            "extrinsic_at_risk": round(es.total_extrinsic),
            "extrinsic_pct_nav": round(es.total_extrinsic / total * 100, 1),
            "opt_pl": round(opt_pl), "eq_pl": round(eq_pl),
            "top_holding": top_holding, "n_holdings": n_holdings,
        },
        "accounts": [{"name": a.name, "type": a.account_type, "total": round(a.total_value),
                      "cash": round(a.cash), "equity_value": round(a.equity_value),
                      "options_value": round(a.options_value)} for a in snap.accounts],
        "taxonomy": taxonomy_map(),
        "buckets": buckets, "exposure": exposure, "expiry": expiry,
        "equities": equities, "positions": positions, "actions": actions,
        "writeups": writeups,
    }


def render(es: EnrichedSnapshot, path: str) -> str:
    data = _build_data(es)
    html = _TEMPLATE.replace("/*__DATA__*/", json.dumps(data))
    with open(path, "w") as f:
        f.write(html)
    return path


# --------------------------------------------------------------------------------------
# Single-file template. Data is injected in place of the /*__DATA__*/ token. All charts
# are hand-drawn SVG (no CDN) so the file is fully portable/offline. The JS reads
# D.shape to decide which KPIs/charts/tables to render, so blank panels never appear.
# --------------------------------------------------------------------------------------
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portfolio Dashboard</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2230;--line:#2a323d;--tx:#e6edf3;--mut:#8b949e;
--grn:#3fb950;--red:#f85149;--org:#e3934f;--blu:#58a6ff;--pur:#bc8cff;--yel:#e3b341;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial}
.wrap{max-width:1360px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 2px}
.sub{color:var(--mut);font-size:13px;margin-bottom:20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:22px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .l{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.kpi .v{font-size:22px;font-weight:700;margin-top:4px}
.kpi .h{font-size:11px;margin-top:3px;color:var(--mut)}
.pos{color:var(--grn)}.neg{color:var(--red)}.warn{color:var(--org)}.blu{color:var(--blu)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{margin:0 0 12px;font-size:13px;font-weight:600;color:var(--tx)}
.full{grid-column:1/-1}
.actions{list-style:none;padding:0;margin:0}
.actions li{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line)}
.actions li:last-child{border:0}
.badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;white-space:nowrap;text-transform:uppercase;letter-spacing:.4px}
.b-week{background:#5a2a00;color:#ffb972}.b-derisk{background:#5a1717;color:#ff9d97}
.b-conc{background:#2a2350;color:#c4b5ff}.b-liq{background:#003a4d;color:#8fd6ff}.b-lev{background:#4d0033;color:#ff9de0}
.b-ok{background:#123a1a;color:#7ee29a}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.controls input{background:var(--panel2);border:1px solid var(--line);color:var(--tx);border-radius:8px;padding:7px 10px;font-size:13px;min-width:180px}
.chip{cursor:pointer;font-size:11px;padding:4px 10px;border-radius:20px;border:1px solid var(--line);background:var(--panel2);color:var(--mut);user-select:none}
.chip.on{background:var(--blu);color:#001a33;border-color:var(--blu);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 9px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--mut);font-weight:600;cursor:pointer;position:sticky;top:0;background:var(--panel);user-select:none}
th:first-child,td:first-child{text-align:left}th.a-l{text-align:left}
th[data-tip]{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:var(--mut);cursor:pointer}
[data-tip]{cursor:help}
.stat .l[data-tip]{text-decoration:underline dotted;text-underline-offset:2px;text-decoration-color:var(--line)}
.kpi .l[data-tip]{text-decoration:underline dotted;text-underline-offset:2px;text-decoration-color:var(--line)}
#tt{position:fixed;z-index:200;max-width:290px;background:#0b0f14;border:1px solid var(--blu);
color:var(--tx);padding:9px 11px;border-radius:8px;font-size:11.5px;line-height:1.5;
box-shadow:0 8px 24px rgba(0,0,0,.55);pointer-events:none;display:none}
tr.row{cursor:pointer}tr.row:hover td{background:var(--panel2)}
.tag{font-size:10px;font-weight:700;padding:2px 6px;border-radius:5px}
.t-close,.t-derisk{background:#5a1717;color:#ff9d97}.t-now,.t-trim{background:#5a2a00;color:#ffb972}
.t-hold{background:#123a1a;color:#7ee29a}.t-core{background:#0d2a4d;color:#8fc4ff}
.fl{font-size:9px;padding:1px 5px;border-radius:4px;background:var(--panel2);color:var(--mut);margin-left:3px}
.drill{background:var(--panel2)}
.drill td{padding:0}
.dwrap{padding:16px 18px}
.why{background:#0d1117;border-left:3px solid var(--org);padding:10px 14px;border-radius:6px;margin-bottom:14px;color:var(--tx)}
.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 11px}
.stat .l{color:var(--mut);font-size:10px;text-transform:uppercase}.stat .v{font-size:15px;font-weight:600;margin-top:2px}
.muted{color:var(--mut)} svg{display:block;width:100%}
.lgd{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--mut);margin-top:8px}
.lgd span{display:inline-flex;align-items:center;gap:5px}.dot{width:9px;height:9px;border-radius:2px;display:inline-block}
.blgd{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;font-size:11.5px;color:var(--mut)}
.blgd div{display:flex;gap:8px;padding:3px 0;align-items:flex-start}
.blgd .code{font-weight:700;min-width:150px;flex:none}
.wu{border:1px solid var(--line);border-radius:10px;margin-bottom:10px;overflow:hidden;background:var(--panel2)}
.wu-h{display:flex;gap:12px;align-items:center;padding:12px 14px;cursor:pointer;user-select:none}
.wu-h:hover{background:var(--panel)}
.wu-h .sym{font-weight:700;font-size:15px;min-width:74px;display:inline-flex;gap:6px;align-items:center}
.wu-h .ol{color:var(--mut);font-size:12.5px;flex:1;white-space:normal}
.wu-h .wt{color:var(--mut);font-size:11px;white-space:nowrap;text-align:right}
.wu-h .car{font-size:16px;color:var(--mut);transition:transform .15s}
.wu-h.open .car{transform:rotate(90deg)}
.wu-b{padding:0 16px 16px;display:none}.wu-b.open{display:block}
.wu-thesis{color:var(--tx);line-height:1.6;margin:8px 0 14px;white-space:normal}
.cases{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:14px}
.case{border-radius:8px;padding:10px 12px;border:1px solid var(--line);background:var(--panel);white-space:normal;line-height:1.55;font-size:12.5px}
.case .cl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px}
.case.bull{border-top:2px solid var(--grn)}.case.bull .cl{color:var(--grn)}
.case.base{border-top:2px solid var(--blu)}.case.base .cl{color:var(--blu)}
.case.bear{border-top:2px solid var(--red)}.case.bear .cl{color:var(--red)}
.wu-note{border-left:3px solid var(--org);background:#0d1117;padding:10px 14px;border-radius:6px;margin-bottom:10px;line-height:1.6;white-space:normal}
.wu-note.inval{border-left-color:var(--pur)}
.wu-note .nl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--mut);margin-bottom:4px}
</style></head><body><div id="tt"></div><div class="wrap">
<h1>Portfolio Dashboard</h1><div class="sub" id="sub"></div>
<div class="kpis" id="kpis"></div>
<div class="card full" style="margin-bottom:22px"><h3>Prioritized actions</h3><ul class="actions" id="actions"></ul></div>
<div class="grid">
  <div class="card" id="card-alloc"><h3>Asset allocation</h3><div id="alloc"></div><div class="lgd" id="alloc-lgd"></div></div>
  <div class="card" id="card-buckets"><h3>Exposure by thesis bucket <span class="muted">(whole book: equity + option delta-$)</span></h3><div id="buckets"></div><div class="blgd" id="buckets-lgd"></div></div>
  <div class="card" id="card-scatter"><h3>Moneyness vs. days-to-expiry <span class="muted">(bubble = delta-$)</span></h3><div id="scatter"></div></div>
  <div class="card" id="card-exposure"><h3>Exposure by holding <span class="muted">(equity value + option delta-$, top 14)</span></h3><div id="exposure"></div></div>
  <div class="card full" id="card-expiry"><h3>Expiry wall: intrinsic (real) vs. extrinsic (decaying)</h3><div id="expiry"></div>
    <div class="lgd"><span><i class="dot" style="background:var(--blu)"></i>Intrinsic</span><span><i class="dot" style="background:var(--red)"></i>Extrinsic (time value at risk)</span></div></div>
</div>

<div class="card full" id="card-equities" style="margin-bottom:22px">
  <h3>Equities &amp; ETFs <span class="muted">(click a column to sort)</span></h3>
  <div style="overflow:auto;max-height:520px"><table id="eqtbl"><thead><tr id="eqhead"></tr></thead><tbody id="eqtb"></tbody></table></div>
</div>

<div class="card full" id="card-options">
  <h3>Options (click any row to drill down)</h3>
  <div class="controls">
    <input id="search" placeholder="Filter by ticker…" oninput="applyFilter()">
    <span class="chip" data-f="ITM">ITM</span><span class="chip" data-f="OTM">OTM</span>
    <span class="chip" data-f="SHORT_DATED">&lt;30d</span><span class="chip" data-f="LEAP">LEAP</span>
    <span class="chip" data-f="LOTTERY">Lottery</span><span class="chip" data-f="EXPENSIVE_CARRY">Expensive carry</span>
    <span class="chip" data-f="HIGH_THETA">High theta</span>
  </div>
  <div style="overflow:auto;max-height:640px"><table id="tbl"><thead><tr id="opthead"></tr></thead><tbody id="tb"></tbody></table></div>
</div>

<div class="card full" id="card-writeups" style="margin-top:22px">
  <h3>Deep-dive write-ups <span class="muted">(the in-depth read: click a name for the full thesis, bull / base / bear cases, and the rationale behind the call)</span></h3>
  <div id="writeups"></div>
</div>
<div class="sub" id="foot" style="margin-top:18px"></div>
</div>
<script>
const D=/*__DATA__*/;
function money(n){if(n==null)return '—';const s=n<0?'-':'';return s+'$'+Math.abs(Math.round(n)).toLocaleString();}
function k(n){if(n==null)return '—';const s=n<0?'-':'';const a=Math.abs(n);return s+'$'+(a>=1000?(a/1000).toFixed(0)+'k':Math.round(a));}
function pct(n,d){return n==null?'—':(n).toFixed(d==null?1:d)+'%';}
function num(n,d){return n==null?'—':n.toFixed(d==null?2:d);}
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
const clr=v=>v>0?'pos':v<0?'neg':'';
const hide=id=>{const e=document.getElementById(id);if(e)e.style.display='none';};
// Bucket labels/colors come from the taxonomy in the data payload (thesis-driven,
// editable in tags.json), not hardcoded codes.
const TAX=D.taxonomy||{};
const tlabel=id=>(TAX[id]&&TAX[id].label)||id;
const tcolor=id=>(TAX[id]&&TAX[id].color)||'#8b949e';
const DTIP=/*__DRILLHELP__*/;
const S=D.shape,T=D.totals;

// ---- visible hover tooltips (native title= is too subtle) ----
(function(){const TT=document.getElementById('tt');
 const esc=s=>(s==null?'':String(s));
 document.addEventListener('mouseover',e=>{const t=e.target.closest('[data-tip]');
  if(!t||!t.getAttribute('data-tip')){return;}TT.textContent=t.getAttribute('data-tip');TT.style.display='block';});
 document.addEventListener('mousemove',e=>{if(TT.style.display!=='block')return;
  let x=e.clientX+14,y=e.clientY+16;const w=TT.offsetWidth,h=TT.offsetHeight;
  if(x+w+8>innerWidth)x=e.clientX-w-14;if(y+h+8>innerHeight)y=e.clientY-h-14;
  TT.style.left=Math.max(4,x)+'px';TT.style.top=Math.max(4,y)+'px';});
 document.addEventListener('mouseout',e=>{if(e.target.closest('[data-tip]'))TT.style.display='none';});
})();

// ---- header / KPIs ----
document.getElementById('sub').innerHTML=`Snapshot ${D.meta.timestamp?D.meta.timestamp.slice(0,16):''} · source ${D.meta.source||'—'} · generated ${D.meta.generated}`;
const plHint=(S.has_options?`Opt ${money(T.opt_pl)} · `:'')+`Eq ${money(T.eq_pl)}`;
const allocHint=`Cash ${T.cash_pct}% · Eq ${money(T.equity_value)}`+(S.has_options?` · Opt ${money(T.options_value)}`:'');
let kpis=[['Total value',money(T.total_value),allocHint,'','']];
if(S.has_options){
 kpis.push(['Delta-adj leverage',T.delta_leverage_x+'x',`Gross notional ${T.leverage_x}x (${money(T.controlled_notional)})`,T.delta_leverage_x>2.5?'warn':'','Net delta-adjusted directional exposure divided by net worth. The honest leverage number.']);
 kpis.push(['Net directional Δ-$',money(T.net_delta_notional),'Options directional exposure','','Sum of every option leg’s delta-adjusted dollar exposure. What you’re really long/short through options.']);
 kpis.push(['Time value at risk',money(T.extrinsic_at_risk),`${T.extrinsic_pct_nav}% of NAV decays absent a move`,T.extrinsic_pct_nav>40?'warn':'','Total extrinsic (time) value across all options. This decays to zero by expiry if the underlyings don’t move.']);
}else{
 kpis.push(['Invested',money(T.invested_value),`${T.invested_pct}% of NAV at work`,'','Portfolio value excluding cash.']);
 if(T.top_holding){const th=T.top_holding;const broad=th.broad;
  const hint=broad?'largest position (broad ETF)':(th.pct>25?'single-name concentration':'largest position');
  kpis.push(['Top holding',th.symbol+' '+th.pct+'%',hint,(!broad&&th.pct>30)?'warn':'','Largest single position as a percent of net worth. Broad-market ETFs are treated as diversified, not concentration.']);}
 kpis.push(['Holdings',String(T.n_holdings),'distinct positions','','Number of distinct tickers held.']);
}
kpis.push(['Unrealized P/L',money(T.opt_pl+T.eq_pl),plHint,clr(T.opt_pl+T.eq_pl),'Mark-to-market gain/loss versus cost across the whole book.']);
kpis.push(['Cash',money(T.cash),`${T.cash_pct}% dry powder`,T.cash_pct<10?'warn':'','Uninvested cash across all accounts.']);
document.getElementById('kpis').innerHTML=kpis.map(x=>`<div class="kpi"><div class="l" data-tip="${x[4]||''}">${x[0]}</div><div class="v ${x[3]}">${x[1]}</div><div class="h">${x[2]}</div></div>`).join('');

// ---- actions ----
const bmap={'THIS WEEK':'b-week','DE-RISK':'b-derisk','CONCENTRATION':'b-conc','LIQUIDITY':'b-liq','LEVERAGE':'b-lev','OK':'b-ok'};
document.getElementById('actions').innerHTML=(D.actions.length?D.actions:[['OK','No acute flags; book is within tolerances.']])
 .map(a=>`<li><span class="badge ${bmap[a[0]]||''}">${a[0]}</span><span>${a[1]}</span></li>`).join('');

// ---- SVG helpers ----
const NS='http://www.w3.org/2000/svg';
function svg(w,h){const s=document.createElementNS(NS,'svg');s.setAttribute('viewBox',`0 0 ${w} ${h}`);s.setAttribute('width','100%');return s;}
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e;}
function txt(x,y,s,a,p,cls){const t=el('text',{x,y,fill:cls||'#8b949e','font-size':a&&a.fs||11,'text-anchor':a&&a.anchor||'start'},p);t.textContent=s;return t;}

// donut allocation (zero slices dropped so equities-only books show cleanly)
(function(){const raw=[['Equities',T.equity_value,'#58a6ff'],['Options',T.options_value,'#e3934f'],['Cash',T.cash,'#3fb950']];
 const items=raw.filter(i=>i[1]>0);const tot=items.reduce((s,i)=>s+i[1],0)||1;const W=280,H=180,cx=90,cy=90,r=70,rin=42;let a0=-Math.PI/2;
 const s=svg(W,H);for(const it of items){const frac=it[1]/tot,a1=a0+frac*2*Math.PI;
  const x0=cx+r*Math.cos(a0),y0=cy+r*Math.sin(a0),x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1);
  const xi1=cx+rin*Math.cos(a1),yi1=cy+rin*Math.sin(a1),xi0=cx+rin*Math.cos(a0),yi0=cy+rin*Math.sin(a0);
  const big=frac>0.5?1:0;
  el('path',{d:`M${x0},${y0} A${r},${r} 0 ${big} 1 ${x1},${y1} L${xi1},${yi1} A${rin},${rin} 0 ${big} 0 ${xi0},${yi0} Z`,fill:it[2]},s);a0=a1;}
 txt(cx,cy+4,money(tot),{anchor:'middle',fs:15},s,'#e6edf3');
 document.getElementById('alloc').appendChild(s);
 document.getElementById('alloc-lgd').innerHTML=items.map(i=>`<span><i class="dot" style="background:${i[2]}"></i>${i[0]} ${((i[1]/tot)*100).toFixed(0)}%</span>`).join('');
})();

// horizontal bars generic
function hbars(elid,rows,fmt,lblW){lblW=lblW||52;const W=560,rowH=26,H=Math.max(rowH+14,rows.length*rowH+14);const s=svg(W,H);
 const max=Math.max(1,...rows.map(r=>Math.abs(r.v)));const x0=lblW+6,bw=W-x0-70;
 rows.forEach((r,i)=>{const y=i*rowH+8;txt(lblW,y+13,r.label,{anchor:'end',fs:11},s,'#e6edf3');
  const w=Math.abs(r.v)/max*bw;el('rect',{x:x0,y:y+3,width:w,height:16,rx:3,fill:r.color||'#8172b3'},s);
  txt(x0+w+5,y+15,fmt(r.v),{fs:10},s,'#8b949e');});
 document.getElementById(elid).appendChild(s);}

// bucket chart + on-page legend (only when the book actually tilts into AI-cycle buckets)
if(S.show_buckets&&D.buckets.length){
 hbars('buckets',D.buckets.map(b=>({label:b.label,v:b.delta_notional,color:b.color||'#8172b3'})),v=>k(v)+'',128);
 document.getElementById('buckets-lgd').innerHTML=D.buckets.map(b=>
  `<div><span class="code" style="color:${b.color||'#8b949e'}">${b.label} <span class="muted">(${b.pct}%)</span></span><span>${b.desc||b.label}</span></div>`).join('');
}else{hide('card-buckets');}

// exposure by holding (equity value + option delta-$), meaningful for any book
if(D.exposure.length){
 hbars('exposure',D.exposure.slice(0,14).map(u=>({label:u.symbol,v:u.delta_notional,color:u.delta_notional<0?'#f85149':'#8172b3'})),v=>k(v));
}else{hide('card-exposure');}

// scatter moneyness vs dte (options only)
if(S.has_options){(function(){const P=D.positions.filter(p=>p.moneyness!=null&&p.dte!=null);
 if(!P.length){hide('card-scatter');return;}
 const W=560,H=300,ml=44,mb=30,mt=10,mr=12;
 const xs=P.map(p=>p.dte),ys=P.map(p=>p.moneyness);const xmax=Math.max(60,...xs),ymin=Math.min(0.7,...ys),ymax=Math.max(1.3,...ys);
 const px=d=>ml+(d/xmax)*(W-ml-mr),py=m=>mt+(1-(m-ymin)/(ymax-ymin))*(H-mt-mb);const s=svg(W,H);
 el('line',{x1:ml,y1:py(1),x2:W-mr,y2:py(1),stroke:'#2a323d','stroke-dasharray':'4 3'},s);txt(W-mr,py(1)-3,'ATM',{anchor:'end',fs:9},s,'#8b949e');
 [0,30,60,90,180,270].filter(d=>d<=xmax).forEach(d=>{el('line',{x1:px(d),y1:mt,x2:px(d),y2:H-mb,stroke:'#1c2230'},s);txt(px(d),H-mb+13,d+'d',{anchor:'middle',fs:9},s);});
 [0.8,1.0,1.2].forEach(m=>txt(ml-6,py(m)+3,m.toFixed(1),{anchor:'end',fs:9},s));
 const dmax=Math.max(1,...P.map(p=>Math.abs(p.delta_notional||0)));
 P.forEach(p=>{const r=6+Math.sqrt(Math.abs(p.delta_notional||0)/dmax)*22;
  const c=p.moneyness>=1?'#3fb950':p.moneyness>=0.85?'#e3934f':'#f85149';
  const g=el('g',{},s);const cir=el('circle',{cx:px(p.dte),cy:py(p.moneyness),r:r,fill:c,'fill-opacity':.45,stroke:c},g);
  cir.appendChild(el('title',{},cir)).textContent=`${p.symbol} ${p.strike}${p.type[0]} ${p.expiration} · Δ-$ ${k(p.delta_notional)}`;
  txt(px(p.dte),py(p.moneyness)+3,p.symbol,{anchor:'middle',fs:8},g,'#e6edf3');});
 document.getElementById('scatter').appendChild(s);})();}else{hide('card-scatter');}

// expiry wall stacked (options only)
if(S.has_options&&D.expiry.length){(function(){const E=D.expiry;
 const W=1280,H=220,ml=54,mb=34,mt=10;const max=Math.max(1,...E.map(m=>m.intrinsic+m.extrinsic));
 const bw=(W-ml-10)/E.length,pw=Math.min(70,bw*0.6);const s=svg(W,H);const H0=H-mb;
 E.forEach((m,i)=>{const x=ml+i*bw+(bw-pw)/2;const hi=m.intrinsic/max*(H0-mt),he=m.extrinsic/max*(H0-mt);
  el('rect',{x,y:H0-hi,width:pw,height:hi,fill:'#58a6ff'},s);
  el('rect',{x,y:H0-hi-he,width:pw,height:he,fill:'#f85149'},s);
  txt(x+pw/2,H0+13,m.month,{anchor:'middle',fs:10},s);
  txt(x+pw/2,H0-hi-he-4,k(m.intrinsic+m.extrinsic),{anchor:'middle',fs:9},s,'#e6edf3');
  txt(x+pw/2,H0+25,m.count+' legs',{anchor:'middle',fs:8},s);});
 document.getElementById('expiry').appendChild(s);})();}else{hide('card-expiry');}

// ---- deep-dive write-ups ----
if(S.has_writeups&&D.writeups.length){
 const wc=document.getElementById('writeups');
 const callCls=v=>{v=(v||'').toUpperCase();
  return /CLOSE|DE-?RISK|EXIT|SELL|CUT/.test(v)?'t-close'
   :/TRIM|DECIDE|ROLL|REDUCE/.test(v)?'t-now'
   :/CORE|ADD|BUY|ACCUMULATE/.test(v)?'t-core':'t-hold';};
 const caseBox=(cls,label,txt)=>txt?`<div class="case ${cls}"><div class="cl">${label}</div>${esc(txt)}</div>`:'';
 const noteBox=(cls,label,txt)=>txt?`<div class="wu-note ${cls}"><div class="nl">${label}</div>${esc(txt)}</div>`:'';
 wc.innerHTML=D.writeups.map((w,i)=>{
  const tag=w.call?`<span class="tag ${callCls(w.call)}">${esc(w.call)}</span>`:'';
  const cases=[caseBox('bull','Bull case',w.bull),caseBox('base','Base case',w.base),caseBox('bear','Bear case',w.bear)].join('');
  const ol=w.one_liner||(w.thesis.length>140?w.thesis.slice(0,140)+'…':w.thesis);
  return `<div class="wu">
   <div class="wu-h" data-i="${i}">
     <span class="sym"><span style="color:${tcolor(w.bucket)}">●</span>${esc(w.symbol)}</span>
     ${tag}<span class="ol">${esc(ol)}</span>
     <span class="wt">${k(w.weight)}${w.updated?' · '+esc(w.updated):''}</span>
     <span class="car">›</span>
   </div>
   <div class="wu-b" id="wu-${i}">
     ${w.thesis?`<div class="wu-thesis">${esc(w.thesis)}</div>`:''}
     ${cases?`<div class="cases">${cases}</div>`:''}
     ${noteBox('','Why this call',w.rationale)}
     ${noteBox('inval','What would change this',w.invalidation)}
   </div></div>`;}).join('');
 wc.querySelectorAll('.wu-h').forEach(h=>h.onclick=()=>{
   const b=document.getElementById('wu-'+h.dataset.i);b.classList.toggle('open');h.classList.toggle('open');});
}else{hide('card-writeups');}

// ---- equities table ----
const EQH=/*__EQHELP__*/;
if(S.has_equities&&D.equities.length){
 const cols=[['symbol','Ticker','a-l'],['account','Account','a-l'],['qty','Qty',''],['price','Price',''],
  ['avg_cost','Avg cost',''],['mv','Market value',''],['weight_pct','Weight',''],['unrealized_pl','P/L',''],['cycle_bucket','Bucket','a-l']];
 document.getElementById('eqhead').innerHTML=cols.map(c=>`<th class="${c[2]}" data-k="${c[0]}" data-tip="${EQH[c[0]]||''}">${c[1]}</th>`).join('');
 let EQSORT={k:'mv',dir:-1};
 const eqtb=document.getElementById('eqtb');
 function eqRender(){const rows=D.equities.slice().sort((a,b)=>{let x=a[EQSORT.k],y=b[EQSORT.k];if(x==null)x=-Infinity;if(y==null)y=-Infinity;
   if(typeof x==='string')return EQSORT.dir*x.localeCompare(y);return EQSORT.dir*(x-y);});
  eqtb.innerHTML=rows.map(e=>`<tr>
   <td class="a-l"><b>${e.symbol}</b></td><td class="a-l muted">${e.account}</td>
   <td>${e.qty}</td><td>${money(e.price)}</td><td>${e.avg_cost==null?'n/a':money(e.avg_cost)}</td>
   <td>${money(e.mv)}</td><td>${e.weight_pct}%</td>
   <td class="${clr(e.unrealized_pl)}">${e.unrealized_pl==null?'n/a':money(e.unrealized_pl)}</td>
   <td class="a-l"><span style="color:${tcolor(e.cycle_bucket)}">●</span> ${tlabel(e.cycle_bucket)}</td></tr>`).join('');}
 document.querySelectorAll('#eqtbl th[data-k]').forEach(th=>th.onclick=()=>{const key=th.dataset.k;EQSORT.dir=EQSORT.k===key?-EQSORT.dir:-1;EQSORT.k=key;eqRender();});
 eqRender();
}else{hide('card-equities');}

// ---- options table ----
const OPTH=/*__OPTHELP__*/;
if(S.has_options&&D.positions.length){
 const ocols=[['symbol','Ticker','a-l'],['strike','Strike',''],['expiration','Exp','a-l'],['dte','DTE',''],['qty','Qty',''],
  ['mark','Mark',''],['mv','MV',''],['moneyness','Mny',''],['delta','Δ',''],['delta_notional','Δ-$',''],
  ['carry_pct_yr','Carry/yr',''],['extrinsic_value','Extrinsic',''],['unrealized_pl','P/L',''],['cycle_bucket','Bucket','a-l'],['verdict','Verdict','a-l']];
 document.getElementById('opthead').innerHTML=ocols.map(c=>`<th class="${c[2]}" data-k="${c[0]}" data-tip="${OPTH[c[0]]||''}">${c[1]}</th>`).join('');
 let SORT={k:'mv',dir:-1},FILTERS=new Set(),Q='';
 const tb=document.getElementById('tb');
 function verdictCls(v){return v==='CLOSE / ROLL'||v==='DE-RISK'?'t-close':v==='DECIDE NOW'||v==='TRIM / ROLL'?'t-now':v==='CORE HOLD'?'t-core':'t-hold';}
 function rowHtml(p,i){
  const fl=p.flags.map(f=>`<span class="fl">${f}</span>`).join('');
  return `<tr class="row" data-i="${i}">
   <td class="a-l"><b>${p.symbol}</b> <span class="muted">${p.type[0].toUpperCase()}${p.side==='short'?'·S':''}</span></td>
   <td>${p.strike}</td><td class="a-l">${p.expiration||'—'}</td><td>${p.dte==null?'—':p.dte}</td>
   <td>${p.qty}</td><td>${num(p.mark)}</td><td>${k(p.mv)}</td>
   <td>${num(p.moneyness)}</td><td>${num(p.delta)}</td><td>${k(p.delta_notional)}</td>
   <td class="${(p.carry_pct_yr||0)>40?'warn':''}">${p.carry_pct_yr==null?'—':p.carry_pct_yr.toFixed(0)+'%'}</td>
   <td>${k(p.extrinsic_value)}</td><td class="${clr(p.unrealized_pl)}">${p.unrealized_pl==null?'n/a':k(p.unrealized_pl)}</td>
   <td class="a-l"><span style="color:${tcolor(p.cycle_bucket)}">●</span> ${tlabel(p.cycle_bucket)}</td>
   <td class="a-l"><span class="tag ${verdictCls(p.verdict)}">${p.verdict}</span></td></tr>
   <tr class="drill" id="dr-${i}" style="display:none"><td colspan="15"><div class="dwrap">
    <div class="why"><b>${p.verdict}.</b> ${p.why} ${fl}</div>
    <div class="dgrid">
     ${stat('Spot',num(p.spot))}${stat('Strike / DTE',p.strike+' · '+(p.dte==null?'—':p.dte+'d'))}
     ${stat('Moneyness',num(p.moneyness))}${stat('% to strike',pct(p.pct_to_strike))}
     ${stat('Implied vol',p.iv==null?'—':(p.iv*100).toFixed(0)+'%')}${stat('Delta',num(p.delta))}
     ${stat('Delta-$ (directional)',money(p.delta_notional))}${stat('Carry / yr',p.carry_pct_yr==null?'—':p.carry_pct_yr.toFixed(0)+'%')}
     ${stat('Mark / Avg',num(p.mark)+' / '+(p.avg_price==null?'n/a':num(p.avg_price)))}${stat('Market value',money(p.mv))}
     ${stat('Intrinsic / sh',num(p.intrinsic))}${stat('Extrinsic / sh',num(p.extrinsic_ps))}
     ${stat('Extrinsic $ (at risk)',money(p.extrinsic_value))}${stat('Extrinsic % of MV',pct(p.extrinsic_pct_mv==null?null:p.extrinsic_pct_mv*100))}
     ${stat('Controlled notional',money(p.notional))}${stat('Unrealized P/L',p.unrealized_pl==null?'n/a':money(p.unrealized_pl))}
    </div></div></td></tr>`;}
 function stat(l,v){const tip=(DTIP[l]||'').replace(/"/g,'&quot;');return `<div class="stat"><div class="l" data-tip="${tip}">${l}</div><div class="v">${v}</div></div>`;}
 function render(){
  let rows=D.positions.map((p,i)=>[p,i]);
  if(Q)rows=rows.filter(([p])=>p.symbol.toLowerCase().includes(Q));
  if(FILTERS.size)rows=rows.filter(([p])=>[...FILTERS].every(f=>p.flags.includes(f)));
  rows.sort((a,b)=>{let x=a[0][SORT.k],y=b[0][SORT.k];if(x==null)x=-Infinity;if(y==null)y=-Infinity;
   if(typeof x==='string')return SORT.dir*x.localeCompare(y);return SORT.dir*(x-y);});
  tb.innerHTML=rows.map(([p,i])=>rowHtml(p,i)).join('');
  tb.querySelectorAll('tr.row').forEach(tr=>tr.onclick=()=>{const d=document.getElementById('dr-'+tr.dataset.i);d.style.display=d.style.display==='none'?'':'none';});
 }
 window.applyFilter=function(){Q=document.getElementById('search').value.trim().toLowerCase();render();};
 document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{const f=c.dataset.f;if(FILTERS.has(f)){FILTERS.delete(f);c.classList.remove('on');}else{FILTERS.add(f);c.classList.add('on');}render();});
 document.querySelectorAll('#tbl th[data-k]').forEach(th=>th.onclick=()=>{const key=th.dataset.k;SORT.dir=SORT.k===key?-SORT.dir:-1;SORT.k=key;render();});
 render();
}else{hide('card-options');window.applyFilter=function(){};}

// ---- footer ----
const nEq=new Set(D.equities.map(e=>e.symbol)).size,nOpt=D.positions.length;
let footParts=[];
if(nEq)footParts.push(`${nEq} equit${nEq===1?'y':'ies'}`);
if(nOpt)footParts.push(`${nOpt} option leg${nOpt===1?'':'s'}`);
if(S.show_buckets&&D.buckets.length)footParts.push('buckets: '+D.buckets.map(b=>`${b.label} ${b.pct}%`).join(' · '));
document.getElementById('foot').textContent=footParts.join(' · ');
</script></body></html>"""

_TEMPLATE = (_TEMPLATE
             .replace("/*__EQHELP__*/", json.dumps(EQ_COL_HELP))
             .replace("/*__OPTHELP__*/", json.dumps(OPT_COL_HELP))
             .replace("/*__DRILLHELP__*/", json.dumps(DRILL_HELP)))
