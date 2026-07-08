"""End-to-end analysis driver: pull -> enrich -> dashboard + machine-readable JSON.

Run live (default) or against the most recent cached snapshot (--cached). Emits:
  outputs/dashboard_<ts>.png     visual dashboard
  outputs/analysis_<ts>.json     enriched, flattened data for narrative analysis
and prints the console report.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.models import Account, EquityPosition, OptionPosition, PortfolioSnapshot
from analysis.portfolio import report
from analysis.enrich import enrich
from analysis import viz, dashboard_html


def _load_cached() -> PortfolioSnapshot:
    files = glob.glob("outputs/snapshot_*.json")
    if not files:
        raise SystemExit("No cached snapshot found; run without --cached to pull live.")
    latest = max(files, key=os.path.getmtime)
    d = json.load(open(latest))
    accts = [
        Account(
            id=a["id"], name=a["name"], account_type=a["account_type"],
            institution=a["institution"], cash=a["cash"],
            equities=[EquityPosition(**e) for e in a["equities"]],
            options=[OptionPosition(**o) for o in a["options"]],
        )
        for a in d["accounts"]
    ]
    print(f"(loaded cached snapshot {latest})")
    return PortfolioSnapshot(timestamp=d["timestamp"], accounts=accts, source=d["source"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true", help="use most recent cached snapshot")
    ap.add_argument("--source", choices=["snaptrade", "ibkr", "demo"], default="snaptrade",
                    help="data source (default: snaptrade). 'demo' uses fabricated sample "
                         "data with no broker or network. ibkr needs IB Gateway/TWS running.")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    spots = None
    if args.cached:
        snap = _load_cached()
    elif args.source == "demo":
        from data_sources.demo.portfolio import fetch_snapshot, SPOTS
        snap = fetch_snapshot(debug=args.debug)
        spots = SPOTS
        print("\n*** DEMO MODE: fabricated sample data. No broker is connected and nothing "
              "is fetched from the network. Numbers are illustrative, not advice. ***")
    elif args.source == "ibkr":
        from data_sources.ibkr.portfolio import fetch_snapshot
        snap = fetch_snapshot(debug=args.debug)
    else:
        from data_sources.snaptrade.portfolio import fetch_snapshot
        snap = fetch_snapshot(debug=args.debug)

    report(snap)
    es = enrich(snap, spots=spots)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("outputs", exist_ok=True)
    png = viz.render(es, f"outputs/dashboard_{ts}.png")
    html = dashboard_html.render(es, f"outputs/dashboard_{ts}.html")

    payload = {
        "timestamp": snap.timestamp,
        "source": snap.source,
        "totals": {
            "total_value": snap.total_value,
            "equity_value": snap.equity_value,
            "options_value": snap.options_value,
            "cash": snap.cash,
            "controlled_notional": es.total_notional,
            "net_delta_notional": es.net_delta_notional,
            "extrinsic_at_risk": es.total_extrinsic,
            "leverage_x": es.total_notional / snap.total_value if snap.total_value else 0,
            "delta_leverage_x": es.net_delta_notional / snap.total_value if snap.total_value else 0,
        },
        "notional_by_bucket": es.notional_by_bucket,
        "spots": es.spots,
        "accounts": [
            {
                "name": a.name, "type": a.account_type, "total": a.total_value,
                "cash": a.cash, "equity_value": a.equity_value, "options_value": a.options_value,
                "equities": [asdict(e) | {"unrealized_pl": e.unrealized_pl, "spot": es.spots.get(e.symbol)}
                             for e in a.equities],
            }
            for a in snap.accounts
        ],
        "options": [asdict(o) for o in es.options],
    }
    apath = f"outputs/analysis_{ts}.json"
    with open(apath, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\nDashboard  -> {png}")
    print(f"Interactive-> {html}")
    print(f"Analysis   -> {apath}")
    print(f"Leverage   -> {payload['totals']['leverage_x']:.1f}x controlled notional"
          f"  |  {payload['totals']['delta_leverage_x']:.2f}x delta-adjusted (net directional)")
    print(f"Time value at risk (extrinsic) -> ${es.total_extrinsic:,.0f}")
    print("Delta-$ by AI-cycle bucket:")
    from shared.ai_cycle import LABELS
    for b, v in es.notional_by_bucket.items():
        print(f"  {LABELS.get(b, b):<48} ${v:,.0f}")


if __name__ == "__main__":
    main()
