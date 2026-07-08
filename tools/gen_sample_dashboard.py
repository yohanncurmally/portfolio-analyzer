"""Regenerate the sample dashboard image used in the README.

This is a DEV/DOCS utility, not part of the read-only product surface. Every
ticker, weight, and dollar figure below is fabricated; it is not a real
portfolio. The point is to render the real dashboard template (analysis.
dashboard_html._TEMPLATE) with realistic-but-fake data so the README can show
what the output looks like without exposing anyone's holdings.

Two steps:

  1. Emit the HTML (this script):
       python tools/gen_sample_dashboard.py
     Writes docs/sample-dashboard.html (gitignored) and prints the screenshot
     command.

  2. Screenshot it to PNG with any Chromium-based browser (Chrome, Brave, Edge,
     Chromium). Example:
       "<browser>" --headless=new --disable-gpu --hide-scrollbars \
         --force-device-scale-factor=2 --window-size=1440,2560 \
         --screenshot=docs/sample-dashboard.png \
         "file://$PWD/docs/sample-dashboard.html"

Only docs/sample-dashboard.png is committed. Regenerate it after any change to
the dashboard layout so the README stays in sync.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from analysis.dashboard_html import _TEMPLATE, _verdict  # noqa: E402
from shared.ai_cycle import LABELS as BUCKET_LABELS  # noqa: E402

SNAP = "2026-06-30T16:00:00"

# expiration -> days-to-expiry as of the (fabricated) snapshot date
EXP = {
    "2027-06-18": 353, "2026-12-18": 171, "2026-11-20": 143,
    "2026-09-18": 80, "2026-08-21": 52, "2026-07-31": 31, "2026-07-17": 17,
}

# base inputs: symbol, bucket, type, side, spot, strike, exp, qty, mark, avg, iv, delta
RAW = [
    ("AMD",  "G3A", "call", "long", 214.0, 180.0, "2027-06-18", 6,  58.0, 41.0, 0.47, 0.71),
    ("MU",   "G3A", "call", "long", 148.0, 120.0, "2027-06-18", 5,  41.0, 26.0, 0.44, 0.73),
    ("ORCL", "G2",  "call", "long", 208.0, 175.0, "2027-06-18", 3,  49.0, 32.0, 0.39, 0.72),
    ("TSM",  "G3A", "call", "long", 246.0, 220.0, "2026-12-18", 4,  42.0, 33.0, 0.42, 0.68),
    ("CRWD", "G1",  "call", "long", 392.0, 340.0, "2026-12-18", 2,  79.0, 61.0, 0.45, 0.67),
    ("DELL", "G3A", "call", "long", 156.0, 140.0, "2026-11-20", 4,  27.0, 19.0, 0.46, 0.64),
    ("HOOD", "NON", "call", "long", 96.0,  80.0,  "2026-11-20", 3,  23.0, 15.0, 0.55, 0.69),
    ("TSLA", "G2",  "call", "long", 312.0, 300.0, "2026-09-18", 2,  39.0, 44.0, 0.52, 0.55),
    ("MRVL", "G3A", "call", "long", 96.0,  95.0,  "2026-08-21", 8,  10.0, 7.4,  0.51, 0.53),
    ("IREN", "G3B", "call", "long", 23.0,  25.0,  "2026-08-21", 20, 2.3,  1.5,  0.78, 0.36),
    ("SMCI", "G3A", "call", "long", 47.0,  55.0,  "2026-07-31", 15, 3.6,  5.6,  0.63, 0.33),
    ("NET",  "G1",  "call", "long", 184.0, 205.0, "2026-07-17", 6,  4.2,  9.1,  0.55, 0.24),
    ("PANW", "G1",  "put",  "short", 196.0, 175.0, "2026-08-21", 5, 3.9,  3.9,  0.34, 0.27),
]


def build_data() -> dict:
    positions = []
    for sym, bkt, typ, side, spot, strike, exp, qty, mark, avg, iv, delta in RAW:
        dte = EXP[exp]
        sign = 1 if side == "long" else -1
        shares = qty * 100
        if typ == "call":
            intrinsic = max(0.0, spot - strike)
            moneyness = spot / strike
        else:
            intrinsic = max(0.0, strike - spot)
            moneyness = strike / spot
        ext_ps = max(0.0, mark - intrinsic)
        mv = sign * mark * shares
        extrinsic_value = sign * ext_ps * shares
        notional = sign * spot * shares
        if typ == "put" and side == "long":
            delta_signed = -abs(delta)
        elif typ == "put" and side == "short":
            delta_signed = abs(delta)
        else:
            delta_signed = delta
        delta_notional = delta_signed * shares * spot
        unrealized_pl = sign * (mark - avg) * shares
        ext_pct_mv = (extrinsic_value / abs(mv)) if mv else 0.0
        yrs = dte / 365.0
        carry_pct_yr = round((ext_ps / spot) / yrs * 100, 1) if yrs > 0 else None
        pct_to_strike = round((strike - spot) / spot * 100, 1)

        itm = moneyness >= 1.0
        flags = ["ITM" if itm else "OTM"]
        if dte > 300:
            flags.append("LEAP")
        if 0 <= dte < 30:
            flags.append("SHORT_DATED")
        if carry_pct_yr and carry_pct_yr > 40 and side == "long":
            flags.append("EXPENSIVE_CARRY")
        if ext_pct_mv > 0.5 and 0 < dte < 120 and "LEAP" not in flags and side == "long":
            flags.append("HIGH_THETA")
        if (not itm) and dte < 30 and delta < 0.35 and side == "long":
            flags.append("LOTTERY")

        o = SimpleNamespace(flags=flags, dte=dte, extrinsic_value=extrinsic_value,
                            market_value=mv, carry_pct_yr=carry_pct_yr, moneyness=moneyness)
        tag, why = _verdict(o)

        positions.append({
            "symbol": sym, "type": typ, "side": side, "strike": strike,
            "expiration": exp, "dte": dte, "qty": qty, "mark": mark, "mv": round(mv),
            "avg_price": avg, "unrealized_pl": round(unrealized_pl), "spot": spot,
            "moneyness": round(moneyness, 4), "pct_to_strike": pct_to_strike,
            "intrinsic": round(intrinsic, 2), "extrinsic_ps": round(ext_ps, 2),
            "extrinsic_value": round(extrinsic_value), "extrinsic_pct_mv": round(ext_pct_mv, 4),
            "notional": round(notional), "iv": iv, "delta": round(delta_signed, 3),
            "delta_notional": round(delta_notional), "carry_pct_yr": carry_pct_yr,
            "cycle_bucket": bkt, "flags": flags, "verdict": tag, "why": why,
        })

    positions.sort(key=lambda p: -(p["mv"] or 0))

    options_value = sum(p["mv"] for p in positions)
    opt_pl = sum(p["unrealized_pl"] for p in positions)
    total_extrinsic = sum(p["extrinsic_value"] for p in positions if p["extrinsic_value"] > 0)
    total_notional = sum(abs(p["notional"]) for p in positions)
    net_delta_notional = sum(p["delta_notional"] for p in positions)

    equity_value, eq_pl, cash = 118000, 24600, 16000
    total = equity_value + options_value + cash

    bmap: dict[str, float] = {}
    for p in positions:
        bmap[p["cycle_bucket"]] = bmap.get(p["cycle_bucket"], 0) + p["delta_notional"]
    order = ["G3A", "G2", "G1", "G3B", "NON"]
    buckets = [{"code": c, "label": BUCKET_LABELS.get(c, c),
                "delta_notional": round(bmap[c]), "pct": round(bmap[c] / total * 100, 1)}
               for c in order if c in bmap]

    usym: dict[str, float] = {}
    for p in positions:
        usym[p["symbol"]] = usym.get(p["symbol"], 0) + p["delta_notional"]
    underlyings = [{"symbol": s, "delta_notional": round(v)}
                   for s, v in sorted(usym.items(), key=lambda kv: -abs(kv[1]))]

    em, im, cm = {}, {}, {}
    for p in positions:
        m = p["expiration"][:7]
        em[m] = em.get(m, 0) + p["extrinsic_value"]
        im[m] = im.get(m, 0) + p["intrinsic"] * 100 * p["qty"] * (1 if p["side"] == "long" else -1)
        cm[m] = cm.get(m, 0) + 1
    expiry = [{"month": m, "intrinsic": round(im[m]), "extrinsic": round(em[m]), "count": cm[m]}
              for m in sorted(set(em) | set(im))]

    actions = []
    sd = sorted({p["symbol"] for p in positions if "SHORT_DATED" in p["flags"]})
    lot = sorted({p["symbol"] for p in positions if "LOTTERY" in p["flags"]})
    expc = sorted({p["symbol"] for p in positions if "EXPENSIVE_CARRY" in p["flags"]})
    if sd:
        actions.append(["THIS WEEK", f"Expiring <30d, hold/roll/close decision: {', '.join(sd)}"])
    if lot:
        actions.append(["DE-RISK", f"Deep-OTM lottery tickets to exit/roll ITM: {', '.join(lot)}"])
    if expc:
        actions.append(["DE-RISK", f"Expensive carry (>40%/yr), roll down-and-out: {', '.join(expc)}"])
    top = underlyings[0]
    if abs(top["delta_notional"]) / total > 0.35:
        actions.append(["CONCENTRATION",
                        f"{top['symbol']} is {abs(top['delta_notional'])/total:.2f}x NAV of delta-$"
                        ", single-name concentration risk."])
    dlev = net_delta_notional / total
    if dlev > 2.5:
        actions.append(["LEVERAGE", f"Delta-adjusted exposure {dlev:.2f}x NAV, directional risk is high."])

    return {
        "meta": {"timestamp": SNAP, "source": "snaptrade",
                 "generated": datetime.now().strftime("%Y-%m-%d %H:%M")},
        "totals": {
            "total_value": round(total), "equity_value": round(equity_value),
            "options_value": round(options_value), "cash": round(cash),
            "cash_pct": round(cash / total * 100, 1),
            "controlled_notional": round(total_notional),
            "net_delta_notional": round(net_delta_notional),
            "leverage_x": round(total_notional / total, 2),
            "delta_leverage_x": round(net_delta_notional / total, 2),
            "extrinsic_at_risk": round(total_extrinsic),
            "extrinsic_pct_nav": round(total_extrinsic / total * 100, 1),
            "opt_pl": round(opt_pl), "eq_pl": round(eq_pl),
        },
        "accounts": [
            {"name": "Individual", "type": "taxable", "total": round(total * 0.62),
             "cash": 9000, "equity_value": 70000, "options_value": round(options_value * 0.6)},
            {"name": "Roth IRA", "type": "retirement", "total": round(total * 0.38),
             "cash": 7000, "equity_value": 48000, "options_value": round(options_value * 0.4)},
        ],
        "buckets": buckets, "underlyings": underlyings, "expiry": expiry,
        "positions": positions, "actions": actions,
    }


def main() -> None:
    data = build_data()
    html = _TEMPLATE.replace("/*__DATA__*/", json.dumps(data))
    out_html = _ROOT / "docs" / "sample-dashboard.html"
    out_png = _ROOT / "docs" / "sample-dashboard.png"
    out_html.write_text(html)
    print(f"wrote {out_html.relative_to(_ROOT)}")
    print("\nNow screenshot it with any Chromium-based browser, e.g.:\n")
    print(f'  "<browser>" --headless=new --disable-gpu --hide-scrollbars \\\n'
          f'    --force-device-scale-factor=2 --window-size=1440,2560 \\\n'
          f'    --screenshot={out_png.relative_to(_ROOT)} \\\n'
          f'    "file://{out_html}"\n')


if __name__ == "__main__":
    main()
