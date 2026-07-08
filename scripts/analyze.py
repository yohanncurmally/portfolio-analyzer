"""End-to-end analysis driver: pull -> (tag) -> enrich -> dashboard + JSON.

Stages (--stage):
  pull    fetch the book and write outputs/snapshot_<ts>.json, then print any tickers
          that still need a thesis tag. This is where Claude fills in tags.json.
  render  read the newest snapshot, enrich, and write the dashboard + analysis JSON.
  all     pull then render in one shot (default; the classic one-command behaviour).

Splitting pull from render is what lets Claude tag the holdings *between* the two:
run `--stage pull`, classify anything new into tags.json, then `--stage render`.

Emits:
  outputs/snapshot_<ts>.json     raw normalized holdings (re-render or --cached later)
  outputs/dashboard_<ts>.png     visual dashboard
  outputs/dashboard_<ts>.html    interactive dashboard
  outputs/analysis_<ts>.json     enriched, flattened data for narrative analysis
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
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.models import Account, EquityPosition, OptionPosition, PortfolioSnapshot
from analysis.portfolio import report
from analysis.enrich import enrich
from analysis import viz, dashboard_html
from shared import tagging


def _snapshot_from_dict(d: dict) -> PortfolioSnapshot:
    accts = [
        Account(
            id=a["id"], name=a["name"], account_type=a["account_type"],
            institution=a["institution"], cash=a["cash"],
            equities=[EquityPosition(**e) for e in a["equities"]],
            options=[OptionPosition(**o) for o in a["options"]],
        )
        for a in d["accounts"]
    ]
    return PortfolioSnapshot(timestamp=d["timestamp"], accounts=accts, source=d.get("source", "snaptrade"))


def _latest_snapshot() -> PortfolioSnapshot:
    files = glob.glob("outputs/snapshot_*.json")
    if not files:
        raise SystemExit("No saved snapshot found; run --stage pull (or --stage all) first.")
    latest = max(files, key=os.path.getmtime)
    print(f"(loaded snapshot {latest})")
    return _snapshot_from_dict(json.load(open(latest)))


def _all_symbols(snap: PortfolioSnapshot) -> list[str]:
    syms = [e.symbol for a in snap.accounts for e in a.equities]
    syms += [o.symbol for a in snap.accounts for o in a.options]
    return syms


def _pull(source: str, debug: bool) -> tuple[PortfolioSnapshot, Optional[dict]]:
    spots = None
    if source == "demo":
        from data_sources.demo.portfolio import fetch_snapshot, SPOTS
        snap = fetch_snapshot(debug=debug)
        spots = SPOTS
        print("\n*** DEMO MODE: fabricated sample data. No broker is connected and nothing "
              "is fetched from the network. Numbers are illustrative, not advice. ***")
    elif source == "ibkr":
        from data_sources.ibkr.portfolio import fetch_snapshot
        snap = fetch_snapshot(debug=debug)
    else:
        from data_sources.snaptrade.portfolio import fetch_snapshot
        snap = fetch_snapshot(debug=debug)
    return snap, spots


def _write_snapshot(snap: PortfolioSnapshot, ts: str) -> str:
    os.makedirs("outputs", exist_ok=True)
    path = f"outputs/snapshot_{ts}.json"
    with open(path, "w") as f:
        json.dump(snap.to_dict(), f, indent=2, default=str)
    return path


def _report_untagged(snap: PortfolioSnapshot) -> list[str]:
    tagging.reload()  # pick up any hand/Claude edits made this session
    todo = tagging.needs_tagging(_all_symbols(snap))
    if todo:
        print("\nNEEDS TAGGING (not yet in tags.json; will fall back to 'Other'):")
        print("  " + ", ".join(todo))
        print("  -> classify each into a taxonomy bucket in tags.json, then re-run --stage render.")
    else:
        print("\nAll holdings are tagged.")
    return todo


def _render(snap: PortfolioSnapshot, spots: Optional[dict], ts: str) -> None:
    tagging.reload()  # honour edits to tags.json before enriching
    if spots is None and snap.source == "demo":
        from data_sources.demo.portfolio import SPOTS
        spots = SPOTS

    report(snap)
    es = enrich(snap, spots=spots)

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
        "taxonomy": es.taxonomy,
        "notional_by_bucket": es.notional_by_bucket,
        "exposure_by_bucket": es.exposure_by_bucket,
        "exposure_by_symbol": es.exposure_by_symbol,
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
    print("Delta-$ by thesis bucket:")
    for b, v in es.notional_by_bucket.items():
        print(f"  {tagging.label(b):<28} ${v:,.0f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["pull", "render", "all"], default="all",
                    help="pull (fetch + save + list untagged), render (enrich + dashboard "
                         "from newest snapshot), or all (default).")
    ap.add_argument("--cached", action="store_true",
                    help="alias for --stage render: reuse the newest saved snapshot.")
    ap.add_argument("--source", choices=["snaptrade", "ibkr", "demo"], default="snaptrade",
                    help="data source (default: snaptrade). 'demo' uses fabricated sample "
                         "data with no broker or network. ibkr needs IB Gateway/TWS running.")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    stage = "render" if args.cached else args.stage
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if stage == "pull":
        snap, _ = _pull(args.source, args.debug)
        report(snap)
        path = _write_snapshot(snap, ts)
        print(f"\nSnapshot   -> {path}")
        _report_untagged(snap)
        return

    if stage == "render":
        snap = _latest_snapshot()
        _render(snap, None, ts)
        return

    # all: pull, save, report untagged (so Claude can tag before the read), then render.
    snap, spots = _pull(args.source, args.debug)
    _write_snapshot(snap, ts)
    _report_untagged(snap)
    _render(snap, spots, ts)


if __name__ == "__main__":
    main()
