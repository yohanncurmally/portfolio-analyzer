"""Canonical Black-Scholes primitives: the single source of truth for pricing,
delta, and implied vol across the repo.

Every function is PUT-AWARE. Historically the BS helpers lived in scripts/scenario.py
and were call-only: implied_vol() solved against bs_call regardless of option type,
and delta returned N(d1) for puts too. That silently mispriced puts and reported a
positive delta for a long put (should be negative), which zeroed out hedge P/L in the
scenario model. This module fixes that; scenario.py and analysis/enrich.py both import
from here so there is exactly one implementation.
"""

from __future__ import annotations

import math

R = 0.04  # risk-free, ~Fed funds


def _N(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _n(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(S, K, T, sig, r=R):
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    return d1, d1 - sig * math.sqrt(T)


def bs_price(S, K, T, sig, r=R, option_type: str = "call") -> float:
    """Black-Scholes price for a call or put."""
    is_put = option_type == "put"
    if T <= 0 or sig <= 0:  # intrinsic at expiry / degenerate vol
        return max(0.0, (K - S) if is_put else (S - K))
    d1, d2 = _d1_d2(S, K, T, sig, r)
    if is_put:
        return K * math.exp(-r * T) * _N(-d2) - S * _N(-d1)
    return S * _N(d1) - K * math.exp(-r * T) * _N(d2)


def bs_delta(S, K, T, sig, r=R, option_type: str = "call") -> float:
    """Position-agnostic (long) delta. Call in [0,1]; put in [-1,0]."""
    is_put = option_type == "put"
    if T <= 0 or sig <= 0:
        if is_put:
            return -1.0 if S < K else 0.0
        return 1.0 if S > K else 0.0
    d1, _ = _d1_d2(S, K, T, sig, r)
    return _N(d1) - 1.0 if is_put else _N(d1)


def implied_vol(mark, S, K, T, r=R, option_type: str = "call") -> float:
    """Back out IV from a mark by bisection, using the CORRECT (call/put) pricer.

    Returns a tiny vol for expired/degenerate inputs rather than raising.
    """
    if T <= 0 or mark <= 0 or S <= 0 or K <= 0:
        return 1e-4
    lo, hi = 1e-4, 5.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if bs_price(S, K, T, mid, r, option_type) > mark:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


# Backwards-compatible alias: callers that only ever priced calls.
def bs_call(S, K, T, sig, r=R) -> float:
    return bs_price(S, K, T, sig, r, "call")


def bs_put(S, K, T, sig, r=R) -> float:
    return bs_price(S, K, T, sig, r, "put")
