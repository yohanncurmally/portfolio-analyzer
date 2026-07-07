"""Broker-agnostic portfolio analysis + console report.

Takes a PortfolioSnapshot (from any data source) and prints a combined,
cross-account breakdown: allocation, positions, options with days-to-expiry,
and unrealized P/L.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.models import PortfolioSnapshot


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _pl(x: float | None) -> str:
    return "n/a" if x is None else _money(x)


def _dte(expiration: str) -> int | None:
    try:
        return (datetime.strptime(expiration[:10], "%Y-%m-%d").date() - date.today()).days
    except (ValueError, TypeError):
        return None


def _pct(part: float, whole: float) -> float:
    return (part / whole * 100) if whole else 0.0


def report(snap: PortfolioSnapshot) -> None:
    total = snap.total_value
    line = "=" * 78

    print("\n" + line)
    print(f"PORTFOLIO ANALYSIS  —  {snap.timestamp[:19]}  (source: {snap.source})")
    print(line)

    print(f"\nCOMBINED — {_money(total)} across {len(snap.accounts)} account(s)")
    print("-" * 78)
    print(f"  Equities: {_money(snap.equity_value):>15}  ({_pct(snap.equity_value, total):.1f}%)")
    print(f"  Options:  {_money(snap.options_value):>15}  ({_pct(snap.options_value, total):.1f}%)")
    print(f"  Cash:     {_money(snap.cash):>15}  ({_pct(snap.cash, total):.1f}%)")

    for acct in snap.accounts:
        print("\n" + line)
        print(f"ACCOUNT: {acct.name}  [{acct.account_type}] @ {acct.institution}")
        print(f"  Total {_money(acct.total_value)}  "
              f"({_pct(acct.total_value, total):.1f}% of portfolio)")
        print(line)

        if acct.equities:
            print(f"\n  EQUITIES ({len(acct.equities)}) — {_money(acct.equity_value)}")
            print("  " + "-" * 76)
            print(f"  {'SYM':<8}{'QTY':>10}{'PRICE':>11}{'AVG':>11}"
                  f"{'MKT VAL':>14}{'U_P/L':>13}{'%PORT':>7}")
            for p in sorted(acct.equities, key=lambda x: x.market_value, reverse=True):
                avg_s = f"{p.avg_cost:>11.2f}" if p.avg_cost is not None else f"{'n/a':>11}"
                pl_s = f"{p.unrealized_pl:>13,.2f}" if p.unrealized_pl is not None else f"{'n/a':>13}"
                print(f"  {p.symbol:<8}{p.quantity:>10.2f}{p.price:>11.2f}{avg_s}"
                      f"{p.market_value:>14,.2f}{pl_s}"
                      f"{_pct(p.market_value, total):>6.1f}%")

        if acct.options:
            print(f"\n  OPTIONS ({len(acct.options)}) — {_money(acct.options_value)}")
            print("  " + "-" * 76)
            for o in sorted(acct.options, key=lambda x: abs(x.market_value), reverse=True):
                dte = _dte(o.expiration)
                dte_s = f"{dte}d" if dte is not None else "?"
                print(f"  {o.symbol:<6}{o.side:<6}{o.option_type:<5}"
                      f"${o.strike:>8.1f} {o.expiration[:10]} {dte_s:>6}  x{o.quantity:>4.0f}  "
                      f"MV {_money(o.market_value):>14}  P/L {_pl(o.unrealized_pl):>13}")

    print("\n" + line)
    eq_pl = sum(p.unrealized_pl for a in snap.accounts for p in a.equities
                if p.unrealized_pl is not None)
    opt_pl_vals = [o.unrealized_pl for a in snap.accounts for o in a.options
                   if o.unrealized_pl is not None]
    opt_pl = sum(opt_pl_vals)
    opt_note = "" if opt_pl_vals else " (options cost basis not provided by Robinhood via SnapTrade)"
    print(f"TOTAL UNREALIZED P/L (known): {_money(eq_pl + opt_pl)}  "
          f"(equities {_money(eq_pl)}, options {_money(opt_pl)}){opt_note}")
    print(line + "\n")
