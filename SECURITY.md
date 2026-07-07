# Security Policy

## Design posture

This tool is built to minimize what it can touch:

- **Read-only broker access.** Both connection paths (SnapTrade and direct Interactive
  Brokers) authenticate read-only. The tool cannot place trades, withdraw, or move money.
  The IBKR connector passes `readonly=True`; SnapTrade access is granted read-only at the
  broker's OAuth screen.
- **Credentials never leave your machine.** API keys and user secrets live in a local
  `.env` file, which is `.gitignore`d. The tool talks directly to SnapTrade / IBKR from
  your computer. There is **no hosted backend and no telemetry**; nothing is uploaded to
  the project authors or anyone else.
- **Your holdings stay local.** Snapshots and dashboards are written to `outputs/`, which
  is also `.gitignore`d.

## Your responsibilities as a user

- **Never commit `.env`** or paste its contents anywhere. Only `.env.example` (a blank
  template) belongs in git.
- If you fill in `docs/target_portfolio.md` with real holdings and don't want them public,
  uncomment the relevant line in `.gitignore` before committing.
- Revoke access any time: disconnect the broker in the SnapTrade dashboard, or turn off
  the API in IBKR Gateway/TWS settings.

## Reporting a vulnerability

If you find a security issue (e.g. a path where credentials could leak, or where a write
operation could occur), please **do not open a public issue**. Instead, use GitHub's
**private vulnerability reporting** (the *Security* tab → *Report a vulnerability*) so it
can be addressed before disclosure.

## Not financial advice

This is an analysis/education tool, not investment advice, and its authors are not your
broker, adviser, or fiduciary. See the [LICENSE](LICENSE) and README for the full notice.
