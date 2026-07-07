"""Tests for the canonical Black-Scholes primitives.

These lock in the put-awareness that the module was created to fix: puts must be
priced with the put formula, put delta must be negative, and implied_vol must solve
against the correct pricer (a call-only solver returned ~0.478 for a put whose true
vol was 0.55; see shared/blackscholes.py docstring).

Pure stdlib math, no network, no third-party deps; fast and deterministic.
"""

from __future__ import annotations

import math

from shared.blackscholes import (
    R,
    bs_call,
    bs_delta,
    bs_price,
    bs_put,
    implied_vol,
)

S, K, T, SIG = 100.0, 100.0, 1.0, 0.25


def test_put_call_parity():
    # C - P == S - K*e^{-rT}
    c = bs_price(S, K, T, SIG, R, "call")
    p = bs_price(S, K, T, SIG, R, "put")
    assert math.isclose(c - p, S - K * math.exp(-R * T), abs_tol=1e-9)


def test_aliases_match_typed_pricer():
    assert math.isclose(bs_call(S, K, T, SIG), bs_price(S, K, T, SIG, R, "call"))
    assert math.isclose(bs_put(S, K, T, SIG), bs_price(S, K, T, SIG, R, "put"))


def test_call_delta_bounds():
    d = bs_delta(S, K, T, SIG, R, "call")
    assert 0.0 <= d <= 1.0
    # deep ITM call ~ +1, deep OTM call ~ 0
    assert bs_delta(200.0, K, T, SIG, R, "call") > 0.95
    assert bs_delta(50.0, K, T, SIG, R, "call") < 0.05


def test_put_delta_is_negative():
    # The core historical bug: puts reported positive delta. Must be in [-1, 0].
    d = bs_delta(S, K, T, SIG, R, "put")
    assert -1.0 <= d <= 0.0
    assert bs_delta(50.0, K, T, SIG, R, "put") < -0.95   # deep ITM put ~ -1
    assert bs_delta(200.0, K, T, SIG, R, "put") > -0.05  # deep OTM put ~ 0


def test_delta_relationship():
    # put_delta == call_delta - 1  (no dividends)
    cd = bs_delta(S, K, T, SIG, R, "call")
    pd = bs_delta(S, K, T, SIG, R, "put")
    assert math.isclose(pd, cd - 1.0, abs_tol=1e-9)


def test_implied_vol_roundtrip_call():
    price = bs_price(S, K, T, 0.42, R, "call")
    iv = implied_vol(price, S, K, T, R, "call")
    assert math.isclose(iv, 0.42, abs_tol=1e-3)


def test_implied_vol_roundtrip_put():
    # Regression guard: a put priced at true vol 0.55 must solve back to ~0.55,
    # NOT the ~0.478 an old call-only solver produced.
    true_vol = 0.55
    price = bs_price(S, K, T, true_vol, R, "put")
    iv = implied_vol(price, S, K, T, R, "put")
    assert math.isclose(iv, true_vol, abs_tol=1e-3)
    assert iv > 0.5  # would have failed under the call-only bug


def test_degenerate_inputs_dont_raise():
    # Expired / zero-vol return intrinsic; bad IV inputs return a tiny vol.
    assert bs_price(S, K, 0.0, SIG, R, "call") == max(0.0, S - K)
    assert bs_price(S, K, T, 0.0, R, "put") == max(0.0, K - S)
    assert implied_vol(0.0, S, K, T, R, "call") == 1e-4
    assert implied_vol(5.0, S, K, 0.0, R, "put") == 1e-4
