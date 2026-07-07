"""Reconstruct option cost basis from SnapTrade activity history.

Robinhood does not expose option `average_purchase_price` via SnapTrade, but the
full transaction feed includes every option fill with its execution price. We
reconstruct the weighted-average open cost of the currently-held contracts by
replaying buys/sells (FIFO against closes), keyed by the OCC option ticker.
"""

from __future__ import annotations

from collections import defaultdict, deque

from .client import get_client


def _page_activities(client, user_id, user_secret, account_id, page=1000):
    """Yield all activity dicts for an account, following pagination."""
    offset = 0
    while True:
        resp = client.account_information.get_account_activities(
            account_id=account_id, user_id=user_id, user_secret=user_secret,
            offset=offset, limit=page,
        ).body
        data = resp.get("data", []) if isinstance(resp, dict) else (resp or [])
        if not data:
            break
        for row in data:
            yield row
        if len(data) < page:
            break
        offset += page


def _is_open(description: str) -> bool:
    return "to open" in (description or "").lower()


def option_cost_basis(account_id: str) -> dict[str, float]:
    """Return {occ_ticker: average cost per contract (USD)} for open positions."""
    client = get_client()
    import os
    user_id = os.getenv("SNAPTRADE_USER_ID")
    user_secret = os.getenv("SNAPTRADE_USER_SECRET")

    fills = defaultdict(list)  # occ_ticker -> list of (trade_date, units, price, is_open)
    for a in _page_activities(client, user_id, user_secret, account_id):
        if not isinstance(a, dict):
            continue
        opt = a.get("option_symbol")
        if not opt:
            continue
        ticker = opt.get("ticker")
        try:
            units = float(a.get("units"))
            price = float(a.get("price"))  # per share
        except (TypeError, ValueError):
            continue
        fills[ticker].append(
            (a.get("trade_date") or "", units, price, _is_open(a.get("description")))
        )

    basis = {}
    for ticker, rows in fills.items():
        rows.sort(key=lambda r: r[0])  # chronological
        lots: deque = deque()  # [signed_qty, price_per_share]
        for _, units, price, is_open in rows:
            if is_open:
                lots.append([units, price])
            else:
                # closing: reduce opposite-direction lots FIFO
                close_qty = abs(units)
                while close_qty > 1e-9 and lots:
                    lot = lots[0]
                    take = min(close_qty, abs(lot[0]))
                    lot[0] -= take * (1 if lot[0] > 0 else -1)
                    close_qty -= take
                    if abs(lot[0]) < 1e-9:
                        lots.popleft()
        net_qty = sum(q for q, _ in lots)
        if abs(net_qty) < 1e-9:
            continue
        wavg_per_share = sum(q * p for q, p in lots) / net_qty
        basis[ticker] = round(wavg_per_share * 100, 2)  # per contract
    return basis
