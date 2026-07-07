# Portfolio Analyzer

[![CI](https://github.com/yohanncurmally/portfolio-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/yohanncurmally/portfolio-analyzer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Read-only](https://img.shields.io/badge/broker%20access-read--only-brightgreen.svg)](#security--privacy)

A **local, read-only** tool that connects to your brokerage, pulls your holdings, and
produces an **interactive dashboard** plus a **candid, position-by-position analysis** —
tailored to your own strategy, thesis, and how you invest (equities or options, passive
or active, your risk tolerance).

It runs entirely on **your own computer**, under **your own broker login**. Nothing is
hosted, nothing is uploaded, and it can **never place a trade or move money**.

> ## ⚠️ Not financial advice
> This is a personal analysis and educational tool. It is **not** investment, financial,
> tax, or legal advice, and its authors are **not** your broker, adviser, or fiduciary.
> Nothing it outputs is a recommendation to buy, sell, or hold any security. Markets are
> risky and you can lose money. **You** are solely responsible for your own decisions.
> The software is provided **"as is," without warranty of any kind** (see [LICENSE](LICENSE)).
> Verify every number against your broker before acting on anything.

---

## What you get

- **Interactive dashboard** (opens in your browser, works offline): total value,
  leverage/risk, allocation, exposure by holding, an expiry wall for options, and a
  sortable/filterable positions table where every row expands into a full drilldown.
- **Written deep dive**: position by position — what's working, what's risky, and the
  tradeoffs — plus a portfolio-level synthesis. Framed around *your* stated strategy.
- For options traders: put-correct greeks, delta-adjusted exposure, and a
  cheap-vs-expensive-leverage (carry/yr) screen. For premium sellers, the read flips to
  premium captured / assignment odds / collateral.

## How it works

You drive it through **[Claude Code](https://claude.com/claude-code)** (or the Claude
desktop app's coding mode). It connects to your broker **read-only** via
**[SnapTrade](https://snaptrade.com)** (works for Robinhood, Interactive Brokers, and
20+ brokers) or a **direct Interactive Brokers** connection. Your credentials stay in a
local `.env` file that is gitignored and never leaves your machine.

## Quick start

You do **not** need to be technical. Claude sets it up for you.

1. Install [Claude Code](https://claude.com/claude-code).
2. Get this repo onto your computer — either:
   - **Download ZIP**: green **Code** button above → **Download ZIP** → unzip, or
   - **Clone**: `git clone https://github.com/yohanncurmally/portfolio-analyzer.git`
3. Open the folder in Claude Code and say:

   > **Read SETUP_FOR_CLAUDE.md and set me up.**

Claude will check Python, build a sandboxed environment, walk you through connecting your
broker (you log in yourself — it only ever gets read-only access), offer to personalize
the analysis to your strategy, and run your first report. After that, just say
**"analyze my portfolio"** any time, or **"let's personalize this"** to tune it.

See **[SETUP_FOR_CLAUDE.md](SETUP_FOR_CLAUDE.md)** for the full, detailed walkthrough and
**[START_HERE.md](START_HERE.md)** for the two-minute version.

## Personalize it to how you invest

The analysis sharpens a lot when it knows your thesis. During setup (or any time later)
Claude interviews you — passive vs. active, equities vs. options, buy vs. sell premium,
risk tolerance, concentration, any rules you follow — and writes it into
`docs/target_portfolio.md`. From then on the report is framed around *your* plan. A
passive index investor sees allocation drift and concentration; an options seller sees
premium capture and assignment risk. Same engine, different lens.

## Security & privacy

- **Read-only.** Both broker paths connect read-only. The tool cannot trade or move money.
- **Your credentials stay local.** They live in `.env`, which is gitignored — never
  commit it, never share it.
- **Your holdings stay local.** Snapshots and dashboards are written to `outputs/`, which
  is also gitignored.
- **Nothing is hosted.** There is no server, no account with us, no data collection.
- Revoke access any time: disconnect the broker in the SnapTrade dashboard, or turn off
  the API in IBKR's Gateway settings.

## Requirements

- [Claude Code](https://claude.com/claude-code) (or Claude desktop coding mode)
- Python 3.10+
- A SnapTrade developer account (free for personal use) **or** Interactive Brokers with
  IB Gateway/TWS

## License

[MIT](LICENSE) — free to use, modify, and share, with no warranty. See the disclaimer above.
