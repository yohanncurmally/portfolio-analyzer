"""Broker-agnostic portfolio data models.

Both SnapTrade (now) and IBKR (future) normalize into these, so analysis code
never depends on a specific broker's response shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class EquityPosition:
    symbol: str
    quantity: float
    price: float
    avg_cost: Optional[float]  # None when broker doesn't supply cost basis
    market_value: float

    @property
    def cost_basis(self) -> Optional[float]:
        if self.avg_cost is None:
            return None
        return self.avg_cost * self.quantity

    @property
    def unrealized_pl(self) -> Optional[float]:
        cb = self.cost_basis
        return None if cb is None else self.market_value - cb


@dataclass
class OptionPosition:
    symbol: str  # underlying ticker
    option_type: str  # 'call' | 'put'
    strike: float
    expiration: str  # YYYY-MM-DD
    side: str  # 'long' | 'short'
    quantity: float  # number of contracts
    mark: float  # per-share mark
    avg_price: Optional[float]  # per-contract avg paid; None if broker omits it
    market_value: float
    multiplier: float = 100.0

    @property
    def cost_basis(self) -> Optional[float]:
        if self.avg_price is None:
            return None
        sign = 1 if self.side == "long" else -1
        return self.avg_price * self.quantity * sign

    @property
    def unrealized_pl(self) -> Optional[float]:
        cb = self.cost_basis
        return None if cb is None else self.market_value - cb


@dataclass
class Account:
    id: str
    name: str
    account_type: str  # e.g. 'individual', 'ira', 'roth_ira'
    institution: str
    cash: float = 0.0
    equities: list[EquityPosition] = field(default_factory=list)
    options: list[OptionPosition] = field(default_factory=list)

    @property
    def equity_value(self) -> float:
        return sum(p.market_value for p in self.equities)

    @property
    def options_value(self) -> float:
        return sum(p.market_value for p in self.options)

    @property
    def total_value(self) -> float:
        return self.equity_value + self.options_value + self.cash


@dataclass
class PortfolioSnapshot:
    timestamp: str
    accounts: list[Account] = field(default_factory=list)
    source: str = "snaptrade"

    @classmethod
    def now(cls, source: str = "snaptrade") -> "PortfolioSnapshot":
        return cls(timestamp=datetime.now().isoformat(), source=source)

    @property
    def total_value(self) -> float:
        return sum(a.total_value for a in self.accounts)

    @property
    def cash(self) -> float:
        return sum(a.cash for a in self.accounts)

    @property
    def equity_value(self) -> float:
        return sum(a.equity_value for a in self.accounts)

    @property
    def options_value(self) -> float:
        return sum(a.options_value for a in self.accounts)

    def to_dict(self) -> dict:
        return asdict(self)
