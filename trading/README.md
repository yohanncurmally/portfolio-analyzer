# Trading / execution (future)

Placeholder for the order-execution layer. **Not active** — the current setup is
read-only.

SnapTrade's Robinhood integration is read-only, so live trading here will wait
until accounts move to a broker with an official trading API (e.g. IBKR). When
built, this layer will consume signals from `analysis/` and route orders through
a broker connector in `data_sources/`.
