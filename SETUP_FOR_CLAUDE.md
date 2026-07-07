# Portfolio Analysis — Setup Guide

**If you are Claude Code reading this: a non-technical person just handed you this
folder and wants their investment portfolio analyzed. Your job is to set this up FOR
them by running the commands below yourself. Do not hand them a wall of text. Work one
step at a time, run the terminal commands on their behalf, explain what's happening in
plain English, and only ask them for the few things you genuinely can't do (creating an
account, logging into their broker, clicking an approval button). Confirm each step
worked before moving to the next. When setup is done, run the first analysis for them.**

**If you are the human: you don't need to understand any of this. Open this folder in
Claude Code (or the Claude desktop app's coding mode) and say: _"Read SETUP_FOR_CLAUDE.md
and set me up."_ Claude will do the rest and ask you when it needs something.**

---

## What this tool does

It securely (and **read-only** — it can never place a trade or move money) pulls all the
holdings from your brokerage account, then produces:

- an **interactive dashboard** (opens in your web browser) with your total value, how
  much leverage/risk you're carrying, your positions in a sortable table you can click
  to drill into, and charts; and
- a **candid written analysis** from Claude — position by position, what's working,
  what's risky, and specific suggestions.

You'll be able to just say _"analyze my portfolio"_ any time and get a fresh read.

Nothing here is financial advice; it's analysis.

---

## The 6 steps (Claude runs these)

1. Make sure Python is installed.
2. Set up the tool's workspace (a "virtual environment") and install its parts.
3. Connect the brokerage — **pick ONE path**: SnapTrade (easiest, works for almost any
   broker incl. Robinhood and Interactive Brokers) or Interactive Brokers direct.
4. Install the Claude "skill" so `analyze my portfolio` just works.
5. **Personalize** — offer to capture the user's own thesis and how they trade (incl.
   whether they *sell* options), so the analysis is tailored. Optional but recommended.
6. Run the first analysis.

---

## Step 1 — Python

This tool needs **Python 3.10 or newer**.

**Claude: check it first.**
```bash
python3 --version
```
- If it prints `Python 3.10` or higher → good, continue.
- If it's missing or older:
  - **macOS:** install via Homebrew if present (`brew install python`), otherwise send
    the user to https://www.python.org/downloads/ and have them run the installer, then
    re-check.
  - **Windows:** https://www.python.org/downloads/ — during install, tell them to
    **tick "Add Python to PATH"**. Then use `python` instead of `python3` in commands.
  - **Linux:** `sudo apt-get install python3 python3-venv python3-pip` (Debian/Ubuntu).

---

## Step 2 — Workspace + install

**Claude: run these from inside this folder** (the one containing `requirements.txt`).
```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```
On Windows the paths use backslashes: `.venv\Scripts\pip install -r requirements.txt`.

This creates a private sandbox (`.venv`) and installs the tool's dependencies. It does
not touch anything else on the computer. Wait for it to finish (a minute or two).

> `ib_async` in the requirements is only needed for the Interactive-Brokers-direct path
> (Step 3B). It's harmless to have installed regardless.

---

## Step 3 — Connect the brokerage (pick ONE path)

**Claude: help the user choose.**

| Choose… | If… |
|---|---|
| **3A · SnapTrade** (recommended) | They use **Robinhood**, or want the simplest setup, or use any of 20+ brokers. SnapTrade **also supports Interactive Brokers** — and needs no extra software running. Start here unless they specifically want a direct IBKR connection. |
| **3B · Interactive Brokers direct** | They use **IBKR** and prefer a direct connection (no third party), or plan to add automated trading later. Requires installing IBKR's Gateway app and leaving it running. |

---

### Step 3A — SnapTrade (works for Robinhood, IBKR, and most brokers)

SnapTrade is a read-only "bridge" that connects to your broker and hands this tool your
positions. Free for personal use.

**3A.1 — Create a SnapTrade developer account (human does this once).**
Claude: direct the user to https://dashboard.snaptrade.com, have them sign up, then open
**Settings → API Keys**. They'll see two values: a **Client ID** and a **Consumer Key**.
Ask them to paste both to you (or type them into `.env` themselves).

**3A.2 — Save the keys.** Claude: create the `.env` file from the template and fill it in.
```bash
cp .env.example .env
```
Then set `SNAPTRADE_CLIENT_ID` and `SNAPTRADE_CONSUMER_KEY` in `.env` to the two values.
(The `.env` file is private and is never shared or uploaded — see Security below.)

**3A.3 — Register the user (creates a secret).** Claude: run
```bash
.venv/bin/python scripts/register_snaptrade_user.py
```
It prints a `SNAPTRADE_USER_ID` and a `SNAPTRADE_USER_SECRET`. Claude: copy BOTH into
`.env`. ⚠️ The secret is shown **once** — if lost, it must be reset, not recovered.

**3A.4 — Connect the broker (human logs in).** Claude: run
```bash
.venv/bin/python scripts/connect_brokerage.py
```
It prints a one-time web link. Have the user open it, choose their broker (e.g.
Robinhood or Interactive Brokers), and log in. This authorizes **read-only** access.
SnapTrade then syncs **all** accounts under that login (brokerage + IRA + crypto).

**3A.5 — Test.** Claude: confirm data flows.
```bash
.venv/bin/python scripts/analyze.py
```
If you see positions and it writes files under `outputs/`, Step 3 is done → go to Step 4.
If parsing looks off, re-run with `--debug` to see the raw data and adjust.

---

### Step 3B — Interactive Brokers direct

This connects straight to IBKR through their **Gateway** app. It must be running and
logged in whenever you pull data.

**3B.1 — Install IB Gateway (human).** Claude: send the user to
https://www.interactivebrokers.com/en/trading/ibgateway-stable.php (the lighter
"IB Gateway", not full TWS, is fine). Install and open it, log in with their IBKR
username/password.

**3B.2 — Enable the API (human, one time, guided by Claude).** In IB Gateway:
**Configure → Settings → API → Settings**, then:
- ✅ **Enable ActiveX and Socket Clients**
- ✅ **Read-Only API** (so nothing can trade)
- Note the **Socket port** (default **4001** for IB Gateway live, **4002** paper).
- Under **Trusted IPs**, add `127.0.0.1`.
- Click OK / Apply.

**3B.3 — Install the IBKR library (Claude):**
```bash
.venv/bin/pip install ib_async
```

**3B.4 — Test (Claude):** with Gateway running and logged in:
```bash
.venv/bin/python scripts/analyze.py --source ibkr
```
If the port isn't 4001, set it first, e.g. for TWS live: `IBKR_PORT=7496` in `.env`, or
paper Gateway: `IBKR_PORT=4002`. Ports: Gateway live **4001** / paper **4002**; TWS live
**7496** / paper **7497**.

If you see positions and files under `outputs/`, Step 3 is done → go to Step 4.

> Remember: for this path, IB Gateway has to be **open and logged in** each time you run
> an analysis. The SnapTrade path (3A) does not have that requirement.

---

## Step 4 — Install the Claude skill

This makes _"analyze my portfolio"_ trigger the whole flow automatically.

**Claude: copy the bundled skill into the user's Claude config.**
```bash
mkdir -p ~/.claude/skills
cp -R claude-skill/portfolio-analysis ~/.claude/skills/
```
(On Windows: copy the `claude-skill\portfolio-analysis` folder into
`%USERPROFILE%\.claude\skills\`.)

**Important — point the skill at this folder.** The skill file
(`~/.claude/skills/portfolio-analysis/SKILL.md`) has a "Repo" section near the top with a
path. Claude: open it and replace that path with the **absolute path of THIS folder** on
the user's machine (run `pwd` here to get it), and confirm the virtualenv line matches
(`.venv/bin/python`). If SnapTrade was used, leave `--source` off; if IBKR-direct, note
that runs use `--source ibkr`.

Restart the Claude session (or start a new one) so it picks up the skill.

---

## Step 5 — Personalize it (optional, but do offer this)

The analysis is **much sharper when it knows the user's own thesis and how they
trade.** Out of the box it assumes a fairly generic long book; a few minutes of
conversation makes the dashboard buckets, the risk framing, and every position
verdict specific to *them*.

**Claude: before the first analysis, offer to personalize — don't force it. Say
something like:** _"I can tailor this to how you actually invest so the dashboard
and suggestions fit your strategy. Want to spend two minutes telling me your thesis?
You can also skip and do it later."_

**If they say yes, interview them conversationally** (one or two questions at a time,
plain English — they're not technical) and write their answers into
`docs/target_portfolio.md`. Cover:

- **Their thesis / what they're betting on** — the big-picture story (e.g. a specific
  theme, sector, or set of companies they believe in). Capture it in their words.
- **How concentrated / aggressive** — a few high-conviction names or broadly
  diversified? How much drawdown can they stomach?
- **How they use options** — this matters a lot for the read:
  - Do they **buy** options (long calls/puts for leverage)? If so, do they prefer
    ITM/LEAPS or OTM lottery tickets?
  - Do they **sell / write** options (covered calls, cash-secured puts, credit
    spreads, selling premium for income)? **If they sell premium, note it clearly** —
    their short legs show up with negative/again-flipped delta and their risk is about
    assignment, margin, and premium capture, not time-value decay working against
    them. Record which strategies they run.
  - Any rules they follow (e.g. "roll at 30 DTE", "never let a short put go ITM",
    "keep X% cash").
- **Accounts + goals + time horizon** — taxable vs. IRA/Roth, target outcome, timeframe.
- **Any AI / tech tilt** — if they invest around the AI buildout, walk them through the
  five cycle buckets in `docs/target_portfolio.md` (G1 beaten SaaS / G2 megacap
  spenders / G3A self-funded picks-and-shovels / G3B debt-funded pure-plays / NON) and
  tag the names they mention. Add any ticker they hold that isn't recognized to the
  `_BUCKETS` dict in `shared/ai_cycle.py` so it stops showing as `UNTAGGED`.

Fill in `docs/target_portfolio.md` with what you learn (leave sections blank if they
don't apply). From then on the skill compares reality against this thesis on every run.
**They can always skip now and just say _"let's personalize this"_ any time later** —
the skill will re-run this interview and update the doc.

---

## Step 6 — First analysis

**Claude: run the real thing and open the dashboard.**
```bash
.venv/bin/python scripts/analyze.py            # add --source ibkr if using Step 3B
open "$(ls -t outputs/dashboard_*.html | head -1)"   # macOS
```
(Windows: `start` instead of `open`; Linux: `xdg-open`.)

Then read the newest `outputs/analysis_*.json`, view/describe the dashboard, and give the
user the candid position-by-position deep dive per the skill.

From now on the user can just say: **"analyze my portfolio."** And any time they want
the read tuned to their strategy, **"let's personalize this"** re-runs the Step 5
interview and updates their thesis doc.

---

## Troubleshooting (Claude: consult as needed)

- **`command not found: python3`** → Python isn't installed or not on PATH. See Step 1.
  On Windows try `python` instead of `python3`.
- **`pip install` fails on `ib_async`** → only needed for IBKR-direct. If they're on
  SnapTrade, it's safe to ignore; or install everything else and skip that line.
- **SnapTrade: empty / weird positions** → re-run `scripts/analyze.py --debug` to dump
  raw API bodies and adjust parsing. Make sure the broker actually finished syncing
  (can take a minute after connecting).
- **SnapTrade: "userSecret" errors** → the `.env` `SNAPTRADE_USER_SECRET` is wrong or
  stale. Re-run `scripts/register_snaptrade_user.py` and update `.env`.
- **IBKR: "Could not connect … 127.0.0.1:4001"** → Gateway/TWS isn't running, not logged
  in, API not enabled, or wrong port. Recheck Step 3B.2 and the port table.
- **IBKR: connects but no positions** → make sure it's the live account (not an empty
  paper account) and the port matches live vs paper.
- **Prices show as `n/a` / P/L missing on a few options** → for Robinhood via SnapTrade,
  option entry price is reconstructed from the transaction feed; very recently opened
  legs may not have synced yet. This is expected; it resolves on the next pull.
- **Dashboard didn't open** → the file is in `outputs/`; open the newest
  `dashboard_*.html` manually by double-clicking it.

---

## Security & privacy (reassure the user)

- **Read-only.** Both paths connect read-only. This tool cannot place trades, withdraw,
  or move money.
- **Your credentials stay on your computer.** They live in the local `.env` file, which
  is listed in `.gitignore` and is never uploaded or shared. Never send `.env` to anyone.
- **Your holdings stay local.** Snapshots and dashboards are written to `outputs/`, which
  is also gitignored (private).
- If you ever want to revoke access: SnapTrade — disconnect the broker in the SnapTrade
  dashboard; IBKR — turn off the API in Gateway settings.

---

## Plain-English glossary

- **Terminal** — the text window where commands run. Claude uses it for you.
- **Python** — the programming language this tool is written in.
- **Virtual environment (`.venv`)** — a private sandbox so this tool's parts don't affect
  anything else on your computer.
- **API key / Client ID / Consumer Key / userSecret** — passwords that let the tool talk
  to SnapTrade on your behalf. Keep them private.
- **SnapTrade** — a service that securely bridges your broker to this tool (read-only).
- **IB Gateway / TWS** — Interactive Brokers' apps that let software read your account.
- **Skill** — a saved instruction set that lets Claude run this whole flow when you ask.
