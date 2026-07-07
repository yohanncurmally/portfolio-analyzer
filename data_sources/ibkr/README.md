# IBKR connector

Read-only Interactive Brokers integration. Pulls every position across all accounts
under an IBKR login and normalizes into `shared.models`, so `analysis/` and the
dashboards work identically to the SnapTrade path.

## How it works

`portfolio.py` connects with [`ib_async`](https://github.com/ib-api-reloaded/ib_async)
to a running **IB Gateway** or **Trader Workstation (TWS)** that has the API enabled,
reads `ib.portfolio()` + `ib.accountValues()` for each managed account, and builds a
`PortfolioSnapshot(source="ibkr")`.

## Run it

1. Install the extra dependency (already in `requirements.txt`):
   ```bash
   .venv/bin/pip install ib_async
   ```
2. Start **IB Gateway** (lighter) or **TWS**, log in, and enable the API:
   *Configure → Settings → API → Settings* → check **Enable ActiveX and Socket Clients**,
   check **Read-Only API**, and note the socket port.
3. Run the analysis against IBKR:
   ```bash
   .venv/bin/python scripts/analyze.py --source ibkr
   ```

## Ports (set `IBKR_PORT` if yours differ)

| App          | Live | Paper |
|--------------|------|-------|
| IB Gateway   | 4001 | 4002  |
| TWS          | 7496 | 7497  |

Optional env: `IBKR_HOST` (default `127.0.0.1`), `IBKR_PORT` (default `4001`),
`IBKR_CLIENT_ID` (default `17` — any unused integer).

## Notes

- **Read-only by design** here (the connect call passes `readonly=True`). IBKR *does*
  support programmatic trading if you later want it — that would live in `trading/`.
- Unlike Robinhood, IBKR exposes option average cost directly, so P/L is available
  without reconstructing it from a transaction feed.
- The simplest alternative is to connect IBKR through **SnapTrade** instead (SnapTrade
  supports Interactive Brokers) — then no Gateway/TWS is needed and you use the default
  `--source snaptrade` path. See `SETUP_FOR_CLAUDE.md` for both options.
