"""A fabricated sample portfolio so anyone can see the output with no broker account.

Everything here is invented. It is NOT a real portfolio and not a recommendation.
The point is to let someone run the full pipeline (enrich -> dashboard -> written
analysis) and see exactly what the tool produces before deciding to connect a broker.

It is deliberately offline and evergreen:

- No network. `SPOTS` below supplies the underlying prices, so `enrich(snap, spots=SPOTS)`
  never needs yfinance. Option greeks, carry, and moneyness are still computed for real
  by the Black-Scholes engine from these prices, strikes, and marks.
- Option expirations are stored as day-offsets from today and resolved at call time, so
  the sample never drifts into "expired" and the days-to-expiry always look sensible.

The book is a mixed one on purpose: a base of stocks and ETFs plus an options overlay
that is tilted toward the AI buildout, with a short put to show the premium-selling read.
Use it with:

    python scripts/analyze.py --source demo
"""

from __future__ import annotations

from datetime import date, timedelta

from shared.models import Account, EquityPosition, OptionPosition, PortfolioSnapshot

# Underlying / equity prices for the sample. enrich() uses these instead of yfinance.
SPOTS: dict[str, float] = {
    # equities held outright
    "NVDA": 178.0, "VOO": 560.0, "AAPL": 235.0, "COST": 985.0,
    "AMZN": 235.0, "SCHD": 29.0, "MSFT": 505.0,
    # option underlyings
    "AMD": 214.0, "MU": 148.0, "ORCL": 208.0, "TSM": 246.0, "CRWD": 392.0,
    "DELL": 156.0, "HOOD": 96.0, "TSLA": 312.0, "MRVL": 96.0, "IREN": 23.0,
    "SMCI": 47.0, "NET": 184.0, "PANW": 196.0,
}

# equities: (account, symbol, quantity, avg_cost)  -- price comes from SPOTS
_EQUITIES = [
    ("Individual", "NVDA", 120, 92.0),
    ("Individual", "VOO", 60, 430.0),
    ("Individual", "AAPL", 90, 170.0),
    ("Individual", "COST", 15, 720.0),
    ("Roth IRA", "AMZN", 80, 150.0),
    ("Roth IRA", "MSFT", 25, 330.0),
    ("Roth IRA", "SCHD", 200, 26.0),
]

# options: (account, underlying, type, side, strike, days_to_exp, contracts, mark, avg_per_share)
# avg_per_share is the per-share entry price; it is stored per-contract (x100) to match
# how market_value and cost basis are denominated in shared.models.OptionPosition.
_OPTIONS = [
    ("Individual", "AMD",  "call", "long", 180.0, 353, 6,  58.0, 41.0),
    ("Individual", "MU",   "call", "long", 120.0, 353, 5,  41.0, 26.0),
    ("Individual", "ORCL", "call", "long", 175.0, 353, 3,  49.0, 32.0),
    ("Individual", "TSM",  "call", "long", 220.0, 171, 4,  42.0, 33.0),
    ("Roth IRA",   "CRWD", "call", "long", 340.0, 171, 2,  79.0, 61.0),
    ("Individual", "DELL", "call", "long", 140.0, 143, 4,  27.0, 19.0),
    ("Roth IRA",   "HOOD", "call", "long", 80.0,  143, 3,  23.0, 15.0),
    ("Roth IRA",   "TSLA", "call", "long", 300.0, 80,  2,  39.0, 44.0),
    ("Individual", "MRVL", "call", "long", 95.0,  52,  8,  10.0, 7.4),
    ("Individual", "IREN", "call", "long", 25.0,  52,  20, 2.3,  1.5),
    ("Individual", "SMCI", "call", "long", 55.0,  24,  15, 3.6,  5.6),
    ("Individual", "NET",  "call", "long", 205.0, 14,  6,  4.2,  9.1),
    ("Individual", "PANW", "put",  "short", 175.0, 52, 5,  3.9,  3.9),
]

_CASH = {"Individual": 9000.0, "Roth IRA": 7000.0}
_META = {
    "Individual": ("acct-demo-1", "individual", "Demo Brokerage"),
    "Roth IRA": ("acct-demo-2", "roth_ira", "Demo Brokerage"),
}


def _equity(symbol: str, qty: float, avg: float) -> EquityPosition:
    price = SPOTS[symbol]
    return EquityPosition(symbol=symbol, quantity=qty, price=price, avg_cost=avg,
                          market_value=round(qty * price, 2))


def _option(underlying, otype, side, strike, days, qty, mark, avg_ps, today) -> OptionPosition:
    sign = 1 if side == "long" else -1
    mv = round(sign * mark * 100 * qty, 2)
    exp = (today + timedelta(days=days)).isoformat()
    return OptionPosition(symbol=underlying, option_type=otype, strike=strike,
                          expiration=exp, side=side, quantity=qty, mark=mark,
                          avg_price=round(avg_ps * 100, 2), market_value=mv)


def fetch_snapshot(debug: bool = False) -> PortfolioSnapshot:
    """Build the fabricated sample snapshot (offline, evergreen)."""
    today = date.today()
    names = ["Individual", "Roth IRA"]
    accounts = []
    for name in names:
        acct_id, acct_type, inst = _META[name]
        eqs = [_equity(sym, q, avg) for a, sym, q, avg in _EQUITIES if a == name]
        opts = [_option(u, t, s, k, d, q, m, avg, today)
                for a, u, t, s, k, d, q, m, avg in _OPTIONS if a == name]
        accounts.append(Account(id=acct_id, name=name, account_type=acct_type,
                                institution=inst, cash=_CASH[name],
                                equities=eqs, options=opts))
    if debug:
        print(f"[demo] built {len(accounts)} accounts, "
              f"{sum(len(a.options) for a in accounts)} option legs")
    return PortfolioSnapshot(timestamp=today.isoformat() + "T16:00:00",
                             accounts=accounts, source="demo")
