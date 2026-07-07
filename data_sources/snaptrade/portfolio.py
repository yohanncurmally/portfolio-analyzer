"""Pull a normalized PortfolioSnapshot from SnapTrade (all connected accounts).

SnapTrade response shapes vary slightly by broker; parsing here is defensive.
Field names are based on the documented API but may need a small tweak once
real Robinhood data flows; run scripts/pull_snapshot.py --debug to dump raw bodies.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.models import Account, EquityPosition, OptionPosition, PortfolioSnapshot
from .client import get_client, get_user_creds
from .transactions import option_cost_basis


def _g(obj, *path, default=None):
    """Walk nested dict/list-of-one safely."""
    cur = obj
    for key in path:
        if cur is None:
            return default
        if isinstance(cur, list):
            cur = cur[0] if cur else None
            if cur is None:
                return default
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur if cur is not None else default


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _opt_f(x):
    """Float or None (preserve 'unknown' for missing cost basis)."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _ticker(sym_obj) -> str:
    # UniversalSymbol: {"symbol": {"symbol": "AAPL", ...}} or {"symbol": "AAPL"}
    inner = _g(sym_obj, "symbol")
    if isinstance(inner, dict):
        return inner.get("raw_symbol") or inner.get("symbol") or ""
    return inner or _g(sym_obj, "raw_symbol", default="") or ""


def _infer_account_type(name: str, raw: dict) -> str:
    meta_type = (_g(raw, "meta", "type", default="") or _g(raw, "raw_type", default="")).upper()
    if "ROTH" in meta_type:
        return "roth_ira"
    if "IRA" in meta_type or "RETIREMENT" in meta_type:
        return "ira"
    if "DIGITAL" in meta_type or "CRYPTO" in meta_type:
        return "crypto"
    return "individual"


def _parse_equities(positions) -> list[EquityPosition]:
    out = []
    for p in positions or []:
        qty = _f(_g(p, "units")) or _f(_g(p, "fractional_units"))
        if qty == 0:
            continue
        price = _f(_g(p, "price"))
        out.append(
            EquityPosition(
                symbol=_ticker(_g(p, "symbol")),
                quantity=qty,
                price=price,
                avg_cost=_opt_f(_g(p, "average_purchase_price")),
                market_value=price * qty,
            )
        )
    return out


def _parse_options(holdings, cost_basis=None) -> list[OptionPosition]:
    cost_basis = cost_basis or {}
    out = []
    for h in holdings or []:
        units = _f(_g(h, "units"))
        if units == 0:
            continue
        opt = _g(h, "symbol", "option_symbol") or _g(h, "option_symbol")
        occ_ticker = _g(opt, "ticker")
        otype = (_g(opt, "option_type", default="") or "").lower()  # CALL/PUT -> call/put
        strike = _f(_g(opt, "strike_price"))
        expiry = _g(opt, "expiration_date", default="")
        underlying = _ticker(_g(opt, "underlying_symbol")) or _g(opt, "ticker", default="")
        # SnapTrade 'price' is the per-contract dollar value (already x100 multiplier).
        price = _f(_g(h, "price"))
        mult = 100.0
        side = "long" if units > 0 else "short"
        out.append(
            OptionPosition(
                symbol=underlying,
                option_type=otype or "call",
                strike=strike,
                expiration=expiry,
                side=side,
                quantity=abs(units),
                mark=price / mult,  # per-share
                avg_price=_opt_f(_g(h, "average_purchase_price")) or cost_basis.get(occ_ticker),
                market_value=price * abs(units) * (1 if side == "long" else -1),
                multiplier=mult,
            )
        )
    return out


def _cash(balances) -> float:
    total = 0.0
    for b in balances or []:
        total += _f(_g(b, "cash"))
    return total


def fetch_snapshot(debug: bool = False) -> PortfolioSnapshot:
    client = get_client()
    user_id, user_secret = get_user_creds()
    snap = PortfolioSnapshot.now(source="snaptrade")

    accounts = client.account_information.list_user_accounts(
        user_id=user_id, user_secret=user_secret
    ).body

    if debug:
        import json
        print("=== RAW list_user_accounts ===")
        print(json.dumps(accounts, indent=2, default=str)[:4000])

    for raw in accounts or []:
        acct_id = _g(raw, "id")
        name = _g(raw, "name", default="") or _g(raw, "number", default="")
        inst = _g(raw, "institution_name", default="")

        balances = client.account_information.get_user_account_balance(
            user_id=user_id, user_secret=user_secret, account_id=acct_id
        ).body
        positions = client.account_information.get_user_account_positions(
            user_id=user_id, user_secret=user_secret, account_id=acct_id
        ).body
        options = client.options.list_option_holdings(
            user_id=user_id, user_secret=user_secret, account_id=acct_id
        ).body
        try:
            cost_basis = option_cost_basis(acct_id)
        except Exception as e:
            cost_basis = {}
            if debug:
                print(f"  (cost-basis reconstruction failed for {name}: {e})")

        if debug:
            import json
            print(f"=== RAW balances ({name}) ===")
            print(json.dumps(balances, indent=2, default=str)[:2000])
            print(f"=== RAW positions ({name}) ===")
            print(json.dumps(positions, indent=2, default=str)[:2000])
            print(f"=== RAW options ({name}) ===")
            print(json.dumps(options, indent=2, default=str)[:2000])

        snap.accounts.append(
            Account(
                id=str(acct_id),
                name=name,
                account_type=_infer_account_type(name, raw if isinstance(raw, dict) else {}),
                institution=inst,
                cash=_cash(balances),
                equities=_parse_equities(positions),
                options=_parse_options(options, cost_basis),
            )
        )

    return snap
