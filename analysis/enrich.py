"""Enrich a PortfolioSnapshot with live spot prices and derived option analytics.

Adds the things a raw broker pull lacks: underlying spot, moneyness, intrinsic vs.
extrinsic (time) value, controlled notional, days-to-expiry, and risk flags. Spot
prices come from yfinance; everything else is computed locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from shared.models import PortfolioSnapshot
from shared.blackscholes import bs_delta, implied_vol
from shared.ai_cycle import bucket as cycle_bucket


def fetch_spots(symbols: list[str]) -> dict[str, float]:
    """Map ticker -> last price via yfinance. Missing/failed tickers are omitted."""
    import yfinance as yf

    out: dict[str, float] = {}
    uniq = sorted({s for s in symbols if s})
    for s in uniq:
        try:
            fi = yf.Ticker(s).fast_info
            px = fi.get("last_price") or fi.get("lastPrice") or fi.get("previous_close")
            if px:
                out[s] = float(px)
        except Exception:
            continue
    return out


def _dte(expiration: str) -> Optional[int]:
    try:
        return (datetime.strptime(expiration[:10], "%Y-%m-%d").date() - date.today()).days
    except (ValueError, TypeError):
        return None


@dataclass
class OptionAnalytics:
    symbol: str
    option_type: str
    side: str
    strike: float
    expiration: str
    quantity: float
    mark: float                 # per-share
    market_value: float
    avg_price: Optional[float]  # per-contract paid
    unrealized_pl: Optional[float]
    spot: Optional[float]
    dte: Optional[int]
    moneyness: Optional[float]      # spot/strike for calls; strike/spot for puts (>1 = ITM)
    pct_to_strike: Optional[float]  # how far spot must move to reach strike, signed %
    intrinsic_per_share: float
    extrinsic_per_share: float      # time value at risk to decay
    extrinsic_value: float          # extrinsic_per_share * 100 * qty
    notional: float                 # spot * 100 * qty (delta-1 controlled exposure)
    iv: Optional[float] = None              # implied vol backed out of the mark (put-correct)
    delta: Optional[float] = None           # per-share, signed for long/short (+call/-put)
    delta_notional: Optional[float] = None  # delta-adjusted $ exposure (true directional risk)
    carry_pct_yr: Optional[float] = None    # annualized cost of the leverage; low=cheap ITM, high=expensive OTM
    cycle_bucket: str = "UNTAGGED"          # AI capital-cycle role (see shared/ai_cycle.py)
    flags: list[str] = field(default_factory=list)


def enrich_option(o, spot: Optional[float]) -> OptionAnalytics:
    dte = _dte(o.expiration)
    is_call = o.option_type == "call"

    intrinsic = 0.0
    moneyness = pct_to_strike = None
    if spot:
        if is_call:
            intrinsic = max(0.0, spot - o.strike)
            moneyness = spot / o.strike if o.strike else None
            pct_to_strike = (o.strike - spot) / spot * 100  # >0 = OTM, must rise
        else:
            intrinsic = max(0.0, o.strike - spot)
            moneyness = o.strike / spot if spot else None
            pct_to_strike = (spot - o.strike) / spot * 100  # >0 = OTM, must fall

    extrinsic = max(0.0, o.mark - intrinsic)
    qty = o.quantity
    extrinsic_value = extrinsic * 100 * qty
    notional = (spot or 0.0) * 100 * qty

    # --- Greeks & leverage economics (put-correct via shared BS) --------------
    iv = delta = delta_notional = carry_pct_yr = None
    side_sign = 1.0 if o.side == "long" else -1.0
    T = (dte / 365.0) if dte else None
    if spot and T and T > 0 and o.mark and o.mark > 0:
        iv = implied_vol(o.mark, spot, o.strike, T, option_type=o.option_type)
        d = bs_delta(spot, o.strike, T, iv, option_type=o.option_type)  # long delta
        delta = side_sign * d                                          # position delta
        delta_notional = delta * 100 * qty * spot                      # true directional $
        # carry/yr: annualized % the underlying must move in the option's favor to
        # break even. Low = cheap leverage (ITM/LEAP); high = expensive (deep OTM).
        if is_call:
            carry_pct_yr = ((o.strike + o.mark) / spot - 1.0) / T * 100
        else:
            carry_pct_yr = (1.0 - (o.strike - o.mark) / spot) / T * 100

    flags: list[str] = []
    if dte is not None and dte <= 30:
        flags.append("SHORT_DATED")
    if dte is not None and dte >= 270:
        flags.append("LEAP")
    if moneyness is not None:
        if is_call and moneyness < 0.90:
            flags.append("OTM")
        if is_call and moneyness >= 1.05:
            flags.append("ITM")
    # time-value-at-risk: extrinsic as a share of position MV
    if o.market_value and extrinsic_value / abs(o.market_value) > 0.6 and (dte or 999) < 120:
        flags.append("HIGH_THETA")
    if moneyness is not None and is_call and moneyness < 0.80 and (dte or 999) < 60:
        flags.append("LOTTERY")  # deep OTM + short dated
    if carry_pct_yr is not None and carry_pct_yr >= 40:
        flags.append("EXPENSIVE_CARRY")  # paying a lot per year for this leverage

    return OptionAnalytics(
        symbol=o.symbol, option_type=o.option_type, side=o.side, strike=o.strike,
        expiration=o.expiration, quantity=qty, mark=o.mark, market_value=o.market_value,
        avg_price=o.avg_price, unrealized_pl=o.unrealized_pl, spot=spot, dte=dte,
        moneyness=moneyness, pct_to_strike=pct_to_strike,
        intrinsic_per_share=intrinsic, extrinsic_per_share=extrinsic,
        extrinsic_value=extrinsic_value, notional=notional,
        iv=iv, delta=delta, delta_notional=delta_notional,
        carry_pct_yr=carry_pct_yr, cycle_bucket=cycle_bucket(o.symbol),
        flags=flags,
    )


@dataclass
class EnrichedSnapshot:
    snap: PortfolioSnapshot
    spots: dict[str, float]
    options: list[OptionAnalytics]          # flat, across all accounts
    options_by_account: dict[str, list[OptionAnalytics]]

    @property
    def total_notional(self) -> float:
        return sum(o.notional for o in self.options)

    @property
    def total_extrinsic(self) -> float:
        return sum(o.extrinsic_value for o in self.options)

    @property
    def net_delta_notional(self) -> float:
        """Delta-adjusted net directional $ exposure, the honest leverage number
        (raw controlled notional overstates it for OTM/short-dated legs)."""
        return sum(o.delta_notional or 0.0 for o in self.options)

    @property
    def notional_by_bucket(self) -> dict[str, float]:
        """Delta-adjusted exposure grouped by AI capital-cycle bucket."""
        out: dict[str, float] = {}
        for o in self.options:
            out[o.cycle_bucket] = out.get(o.cycle_bucket, 0.0) + (o.delta_notional or 0.0)
        return dict(sorted(out.items(), key=lambda kv: -abs(kv[1])))


def enrich(snap: PortfolioSnapshot) -> EnrichedSnapshot:
    underlyings = [o.symbol for a in snap.accounts for o in a.options]
    equities = [e.symbol for a in snap.accounts for e in a.equities]
    spots = fetch_spots(underlyings + equities)

    flat: list[OptionAnalytics] = []
    by_acct: dict[str, list[OptionAnalytics]] = {}
    for a in snap.accounts:
        rows = [enrich_option(o, spots.get(o.symbol)) for o in a.options]
        by_acct[a.name] = rows
        flat.extend(rows)
    return EnrichedSnapshot(snap=snap, spots=spots, options=flat, options_by_account=by_acct)
