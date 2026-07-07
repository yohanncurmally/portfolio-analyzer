# Contributing

Thanks for taking a look. This is a small, local-first tool; contributions that keep it
simple, read-only, and dependency-light are very welcome.

## Dev setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # runtime deps + pytest + ruff
```

## Run the checks

```bash
.venv/bin/pytest                      # unit tests (pure-stdlib math, fast)
.venv/bin/ruff check .                # lint
.venv/bin/ruff format .               # format
python -m compileall analysis data_sources scripts shared   # syntax check
```

CI runs the syntax check + test suite on Python 3.10–3.12 (see
`.github/workflows/ci.yml`). Please keep it green.

## Project layout

```
shared/          canonical models + Black-Scholes math (single source of truth)
data_sources/    read-only broker connectors, each returning a PortfolioSnapshot
  snaptrade/       SnapTrade path (Robinhood, IBKR, 20+ brokers)
  ibkr/            direct IB Gateway/TWS path
analysis/        enrich (greeks, carry, cycle buckets) + PNG + HTML dashboards
scripts/         entrypoints (analyze.py is the driver)
claude-skill/    the Claude Code skill that orchestrates the flow
docs/            optional per-user thesis (target_portfolio.md)
```

## Adding a new data source

The analyzer is broker-agnostic because every connector normalizes into
`shared.models`. To add one:

1. Create `data_sources/<broker>/portfolio.py` exposing
   `fetch_snapshot(debug: bool = False) -> PortfolioSnapshot`.
2. Map the broker's positions onto `EquityPosition` / `OptionPosition` and populate
   `Account` / `PortfolioSnapshot(source="<broker>")`. Mirror `data_sources/ibkr/portfolio.py`.
3. Wire it into `scripts/analyze.py` under the `--source` flag.

Everything downstream (enrich, dashboards, the skill) then works unchanged.

## Ground rules

- **Stay read-only.** No connector or script should ever place an order or move money.
- **No secrets in git.** Never commit `.env` or real holdings.
- **One implementation of the math.** All pricing/greeks/IV go through
  `shared/blackscholes.py` (it is put-correct — don't reintroduce a call-only solver).
- Keep new runtime dependencies to a minimum and explain why in the PR.
