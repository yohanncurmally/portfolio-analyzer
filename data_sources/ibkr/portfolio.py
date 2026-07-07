"""Pull a normalized PortfolioSnapshot from Interactive Brokers.

Connects (read-only) to a running IB Gateway or Trader Workstation (TWS) that has
the API enabled, reads every position across all accounts under the login, and
normalizes into shared.models, so analysis/, enrich, and the dashboards work
unchanged, exactly like the SnapTrade connector.

Requires the `ib_async` package and a running Gateway/TWS. See
data_sources/ibkr/README.md and SETUP_FOR_CLAUDE.md for the one-time setup.

Env (all optional, sensible defaults):
  IBKR_HOST       default 127.0.0.1
  IBKR_PORT       default 4001  (IB Gateway live=4001/paper=4002; TWS live=7496/paper=7497)
  IBKR_CLIENT_ID  default 17    (any unused integer)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.models import Account, EquityPosition, OptionPosition, PortfolioSnapshot


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _iso_expiry(yyyymmdd: str) -> str:
    s = str(yyyymmdd or "")
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _account_type(values_by_tag: dict) -> str:
    """Best-effort classification from IB account values."""
    at = (values_by_tag.get("AccountType", "") or "").upper()
    if "ROTH" in at:
        return "roth_ira"
    if "IRA" in at or "RETIREMENT" in at:
        return "ira"
    return "individual"


def fetch_snapshot(debug: bool = False) -> PortfolioSnapshot:
    try:
        from ib_async import IB
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "IBKR support needs the 'ib_async' package. Install it with:\n"
            "  .venv/bin/pip install ib_async\n"
            "and make sure IB Gateway or TWS is running with the API enabled."
        ) from e

    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "4001"))
    client_id = int(os.getenv("IBKR_CLIENT_ID", "17"))

    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id, readonly=True, timeout=15)
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            f"Could not connect to IBKR at {host}:{port}. Is IB Gateway/TWS running "
            f"with the API enabled and this port allowed?\n  ({e})"
        ) from e

    snap = PortfolioSnapshot.now(source="ibkr")
    try:
        managed = [a for a in ib.managedAccounts() if a]
        if debug:
            print(f"=== IBKR managed accounts: {managed} ===")

        for acct in managed:
            # account-level values (cash, type)
            vals = ib.accountValues(acct)
            by_tag: dict[str, str] = {}
            cash = 0.0
            for v in vals:
                # prefer USD / BASE currency lines
                if v.tag == "TotalCashValue" and v.currency in ("USD", "BASE", ""):
                    cash = _f(v.value)
                if v.tag not in by_tag or v.currency in ("USD", "BASE"):
                    by_tag[v.tag] = v.value

            equities: list[EquityPosition] = []
            options: list[OptionPosition] = []
            for item in ib.portfolio(acct):
                c = item.contract
                qty = _f(item.position)
                if qty == 0:
                    continue
                sec = getattr(c, "secType", "")
                if sec in ("STK", "ETF"):
                    equities.append(EquityPosition(
                        symbol=c.symbol,
                        quantity=qty,
                        price=_f(item.marketPrice),
                        avg_cost=_f(item.averageCost) or None,
                        market_value=_f(item.marketValue),
                    ))
                elif sec == "OPT":
                    mult = _f(c.multiplier, 100.0) or 100.0
                    side = "long" if qty > 0 else "short"
                    options.append(OptionPosition(
                        symbol=c.symbol,
                        option_type="put" if (c.right or "").upper().startswith("P") else "call",
                        strike=_f(c.strike),
                        expiration=_iso_expiry(c.lastTradeDateOrContractMonth),
                        side=side,
                        quantity=abs(qty),
                        mark=_f(item.marketPrice),          # per-share
                        avg_price=_f(item.averageCost) or None,  # per-contract (incl. multiplier)
                        market_value=_f(item.marketValue),
                        multiplier=mult,
                    ))
                elif debug:
                    print(f"  (skipped {sec} {c.symbol})")

            if debug:
                print(f"=== {acct}: cash={cash} eq={len(equities)} opt={len(options)} ===")

            snap.accounts.append(Account(
                id=acct,
                name=f"IBKR {acct}",
                account_type=_account_type(by_tag),
                institution="Interactive Brokers",
                cash=cash,
                equities=equities,
                options=options,
            ))
    finally:
        ib.disconnect()

    return snap
