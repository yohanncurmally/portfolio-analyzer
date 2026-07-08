---
name: portfolio-analysis
description: Pull the user's live brokerage portfolio (taxable + IRA + crypto) via SnapTrade or Interactive Brokers and produce a deep, position-by-position analysis with an interactive dashboard. Use when asked to analyze "my portfolio", "my positions", "my options", check P/L, review allocation/risk, or get forward guidance on current holdings.
---

# Portfolio Analysis

Pulls the user's live holdings across all connected accounts (brokerage, IRA,
crypto) read-only through **SnapTrade** or **Interactive Brokers**, enriches
options with live spot prices and risk analytics, renders a dashboard, then
delivers a candid, broker-agnostic analysis.

## Repo

All code lives in `<ABSOLUTE_PATH_TO_THIS_FOLDER>`. Replace this with the real
absolute path of the tool folder on this machine (run `pwd` from inside it).
Use its virtualenv: `.venv/bin/python`. The `.env` there holds the broker creds.

> **Data source.** If the user connected via SnapTrade (the default), run the
> commands below as written. If they connected Interactive Brokers *directly*
> (IB Gateway/TWS), append `--source ibkr` to `analyze.py` and make sure Gateway/
> TWS is running and logged in first. When in doubt, see `SETUP_FOR_CLAUDE.md`.

## Steps

1. **Pull, then tag, then render.** The pipeline splits into two stages so you can
   classify holdings into the user's thesis buckets *between* the pull and the dashboard.
   From the repo root:
   ```
   cd <ABSOLUTE_PATH_TO_THIS_FOLDER>
   .venv/bin/python scripts/analyze.py --stage pull      # add --source ibkr for IBKR-direct
   ```
   - This writes `outputs/snapshot_<ts>.json` and prints a **NEEDS TAGGING** list of any
     tickers not yet classified in `tags.json`.
   - **Tag the untagged names (see step 1a), then render:**
     ```
     .venv/bin/python scripts/analyze.py --stage render
     ```
   - Or run both at once with `.venv/bin/python scripts/analyze.py` (no `--stage`), which
     pulls, prints the untagged list, and renders in one shot. Prefer the two-stage flow on
     a first run or whenever new names appear, so the dashboard reflects correct tags.
   - Add `--cached` (alias for `--stage render`) to re-render the newest snapshot without a
     fresh pull (use when the user just pulled, or SnapTrade is rate-limiting).
   - Add `--debug` to dump raw broker bodies if parsing looks wrong.
   - `render` writes `outputs/dashboard_<ts>.png` (static), `outputs/dashboard_<ts>.html`
     (**interactive**), and `outputs/analysis_<ts>.json`, and prints the console report.

1a. **Tag holdings into the user's thesis buckets (`tags.json`).** This is what makes the
   thematic read specific and correct instead of forcing names into generic sectors. The
   tagging system lives in `shared/tagging.py`; the data lives in `tags.json` at the repo
   root (gitignored; `tags.example.json` is the shipped template). It has three parts:
   - `taxonomy`: the buckets the exposure chart splits into, each with a human `label`,
     `color`, and one-line `desc`. **Keep it small: aim for <=8 buckets, hard stop ~10**,
     beyond which the chart stops splitting cleanly. **Always keep an `other` catch-all** so
     nothing is force-fit. The taxonomy should come from the user's actual strategy in
     `docs/target_portfolio.md` (AI-cycle, dividend income, sector rotation, whatever). Only
     regenerate the taxonomy on a deliberate re-personalization, so dashboard history stays
     comparable; tags *within* it can be filled in freely.
     **The real rule for whether a bucket earns its place:** a bucket is worth having only if
     it (a) carries meaningful weight in the book AND (b) leads to a *different action or read*
     than its neighbors. If two buckets would always be traded/thought about the same way, merge
     them; if a bucket is a thin sliver, fold it into `other` rather than giving a rounding-error
     its own slice. Split on the distinction that changes a decision (e.g. self-funded picks &
     shovels vs. debt-funded infra, because one breaks first if financing tightens), not on
     surface taxonomy. Ideal is ~5-7 populated thesis buckets plus `other`. Note the dashboard
     already **auto-collapses any bucket under 4% of exposure into `other` on the chart only**
     (each holding keeps its precise tag in the tables), so you don't need to hand-merge slivers
     for display; the rule above is about the *taxonomy design*, not chart cosmetics.
   - `holdings`: `TICKER -> {tag, asset_class, confidence, note}` where `tag` is a taxonomy id.
   - `overrides`: same shape; these win over `holdings` (for the user's hand-corrections).
   Resolution order per ticker is `overrides > holdings > other`.
   **When `--stage pull` reports untagged names:** for each one, work out what it actually is
   (use your own knowledge; **WebSearch any ticker you're unsure of**, e.g. recent IPOs) and
   how the book expresses it, then add it to `tags.json` `holdings` with the right bucket id.
   **Match granularity to the instrument:** a single stock gets a leaf bucket (e.g. AI picks &
   shovels vs debt-funded infra); a **basket ETF/fund gets the parent theme only** (e.g. an AI
   ETF -> an `ai-basket`/theme bucket, never a leaf) because you cannot honestly split a mixed
   fund into a leaf sub-bucket without look-through into its holdings. Treat broad-market index
   ETFs (VOO, VTI, VT, SCHD) as a `broad-market` diversification bucket, not concentration.
   Then run `--stage render`. Only new tickers ever need this; existing tags are cached.

2. **Read the data + surface the interactive dashboard.**
   - Open the newest `outputs/analysis_<ts>.json` (Read tool) for the machine-readable
     enriched figures.
   - **Open the interactive HTML dashboard for the user.** It's self-contained
     (offline, no CDNs): `open outputs/dashboard_<ts>.html` (macOS; use `start` on
     Windows, `xdg-open` on Linux). It **adapts to the shape of the book**: KPI cards,
     a prioritized action list, an allocation donut, an **exposure-by-thesis-bucket
     chart with an on-page legend** that spells out whatever buckets the user's taxonomy
     defines (labels and one-line descriptions read from `tags.json`), an **exposure-by-holding
     chart** (equity market value + option delta-$, meaningful for any book), an
     **Equities & ETFs table**, and, when there are options, a **moneyness-vs-DTE bubble,
     an expiry wall, and a sortable/filterable options table where every row expands into
     a full drilldown** (all greeks, carry, extrinsic %, flags) with a candid per-position
     verdict (CLOSE/ROLL, DECIDE NOW, DE-RISK, CORE HOLD, HOLD). Table headers carry hover
     tooltips explaining each metric. Options-only KPIs (delta-leverage, TVaR, net Δ-$) and
     the options charts appear only when the book holds options; the bucket chart appears
     only when a meaningful share of the book sits in thesis buckets (not all in `other`),
     so an equities-only portfolio renders cleanly with no blank panels.
   - The PNG (`dashboard_<ts>.png`) remains as a static snapshot; view it if you want to
     describe visuals inline. The HTML is generated by `analysis/dashboard_html.py` and
     stays in lockstep with the PNG (both read the same `EnrichedSnapshot`).

   Each option carries put-correct greeks and leverage economics (computed in
   `analysis/enrich.py` off the canonical BS lib in `shared/blackscholes.py`):
   - `iv`: implied vol backed out of the mark (solved against the *correct* call/put
     pricer; see put-IV note below).
   - `delta`: per-share, **signed for side**: long call `+`, long put `−`, shorts flip.
   - `delta_notional`: delta-adjusted $ exposure, the **honest directional risk**
     (raw `notional` overstates it for OTM/short-dated legs).
   - `carry_pct_yr`: annualized % the underlying must move in the option's favor to
     break even. Low = cheap leverage (ITM/LEAP); high = expensive (deep OTM). Legs
     ≥40%/yr get the `EXPENSIVE_CARRY` flag.
   - `cycle_bucket`: the thesis bucket id this name resolves to (from `tags.json` via
     `shared/tagging.py`); the dashboard renders its human label + color from the taxonomy.
   Portfolio totals add `net_delta_notional`, `delta_leverage_x` (the leverage number
   to lead with), `notional_by_bucket` (option delta-$ by cycle role), and the
   whole-book views `exposure_by_bucket` and `exposure_by_symbol` (equity market value +
   option delta-$, so equities-only books still get a thematic and concentration read).

2b. **Adapt the read to the shape of the book AND the user's stated strategy.** Do not
   force an options-heavy, AI-cycle narrative onto a book that isn't one. First look at
   what they actually hold and what `docs/target_portfolio.md` says they're trying to do,
   then pick the frame:
   - **Equities-only (stocks/ETFs, no options):** skip greeks/carry/expiry entirely.
     Lead with allocation, single-name and sector/bucket concentration
     (`exposure_by_symbol`, `exposure_by_bucket`), unrealized P/L and cost basis vs.
     conviction, cash drag, and drift from their target plan. For a passive indexer the
     read is diversification, concentration, and fees, not leverage. Treat broad-market
     ETFs (VOO, VTI, VT, SCHD, BND and the like) as diversification, not single-name
     concentration, even when one is a large share of the book.
   - **Equities + options (mix):** cover the stock sleeve as the base (allocation,
     concentration, gains), then the options overlay with the full greeks/carry/expiry
     treatment below. Relate the two: is the options book leveraging the same names the
     equity sleeve already owns (doubling exposure) or diversifying it?
   - **Options-heavy / options-only:** the full leverage, delta-$, carry, and expiry
     analysis below is the main event.
   - **Premium sellers:** flip the framing for short legs (see below).
   Always lead through *their* thesis, risk tolerance, and rules from
   `docs/target_portfolio.md` if it's filled in. Match the depth and vocabulary to how
   they described themselves; a hands-off index investor and a full-time options trader
   should get very different write-ups from the same engine.

3. **Deep dive, for each material position** (sort by market value / notional):
   - State the live numbers: spot, strike, DTE, moneyness, MV, unrealized P/L,
     extrinsic (time value) at risk, controlled notional, **delta-$ (`delta_notional`),
     and carry/yr (`carry_pct_yr`)**.
   - **Carry/yr LEAP screen:** call out which legs are cheap vs. expensive leverage.
     For **long** legs, ITM/LEAP legs should show low carry; anything flagged
     `EXPENSIVE_CARRY`/`LOTTERY` is the deep-OTM lottery-ticket profile, the first
     candidate to roll ITM/out or close if the user prefers less-risky leverage.
   - **Premium sellers (short options): the framing flips.** If the user's thesis
     (see `docs/target_portfolio.md`) says they *sell* premium (covered calls,
     cash-secured puts, credit spreads), then for their **short** legs a high carry or
     rich extrinsic is what they're *harvesting*, not bleeding. For those positions
     read: how much premium is captured, probability of assignment (short-leg delta ≈
     P(ITM)), days to expiry, and margin/collateral tied up, not "time value at risk."
     Long legs in the same book keep the long framing above. Let the recorded strategy,
     not the sign alone, decide the verdict.
   - If `docs/target_portfolio.md` has been filled in, compare against that thesis (the
     5-bucket target model plus how they trade): is reality tracking the plan? **If it's
     still the blank template, proactively offer to personalize** (see below) before or
     after this run, then describe the actual allocation in the meantime.
   - Give a **specific best move**: hold / trim / roll out / roll up-and-out to ITM
     or LEAPS / close.
   - Flag near-term catalysts/earnings and any expiry within ~30 days that needs a
     decision now.

4. **Portfolio-level synthesis** (include only the parts that fit the book; an
   equities-only or non-AI portfolio skips the leverage/TVaR/cycle items and leads with
   allocation, concentration, and drift instead):
   - Leverage (only if they hold options): lead with **`delta_leverage_x`** (delta-adjusted
     net directional exposure vs. net worth), the honest number. Cite raw
     `controlled_notional` / `leverage_x` as the gross figure and explain the gap.
   - Time-value-at-risk (options only): total extrinsic that decays to zero absent a move.
   - **AI-cycle positioning (only if the book tilts into these buckets; use
     `exposure_by_bucket` for the whole-book view, or `notional_by_bucket` for the options
     slice):** show delta-$ by cycle role
     (G1 beaten SaaS, G2 megacap spenders, G3A self-funded picks&shovels, G3B
     debt-funded pure-plays). Situate the book on the spenders-vs-picks-and-shovels
     map: how much sits in the crowded/capex-blink-risk G3A bucket, how much in the
     highest-torque/first-to-break G3B, and whether that matches conviction. Any name that
     falls to the `other` bucket is untagged: classify it into `tags.json` (see step 1a).
   - Concentration by underlying and by thematic bucket vs. target weights.
   - Expiry wall: capital/decision clusters by month.
   - **5-indicator cycle-turn watchlist** (frame the macro backdrop the book is
     exposed to; pull latest data points where cheap): (1) capex blink, hyperscaler
     guide cuts; (2) circular-financing strain, vendor-financing / SPV leverage;
     (3) GPU pricing & utilization, rental rates, neocloud backlog (CRWV/NBIS);
     (4) leverage layer, debt issuance by G3B names; (5) megacap multiples vs. ROIC.
     Watch sequence #3 → #2 → #1 → #4. A turn here is what would break the G3A/G3B legs.
   - Specific, prioritized action list (what to do this week vs. this month).

## Cost-basis caveat

Some brokers (e.g. Robinhood) do not expose option entry price via SnapTrade. The
repo reconstructs it from the transaction feed
(`data_sources/snaptrade/transactions.py`), but very recently opened legs may not
have synced to the activity feed yet and will show `avg_price: null` / P/L `n/a`.
Note this rather than guessing. (IBKR-direct exposes average cost natively, so this
doesn't apply to the `--source ibkr` path.)

## Greeks caveat (put-IV)

IV/delta come from `shared/blackscholes.py`, which is **put-correct**: `implied_vol`
solves against the right call/put pricer and put delta is `N(d1)−1` (negative). Long
puts show negative `delta`/`delta_notional`, so `net_delta_notional` nets hedges
correctly. If you ever add a scenario/what-if tool, price puts off this same lib,
never a call-only solver.

## Personalization (offer it; keep it current)

The analysis is far sharper when it knows the user's own thesis and how they trade.
Check `docs/target_portfolio.md`:

- **If it's still the blank template**, proactively offer (once, not naggingly):
  _"Want me to tailor this to your actual strategy? Two minutes of your thesis and I'll
  make the buckets and every verdict specific to you."_ If yes, interview them
  conversationally about thesis, conviction, **how they use options (buy vs. sell
  premium, ITM/LEAPS vs. OTM, any rules)**, accounts and horizon, and AI-cycle tilt, and
  write it into `docs/target_portfolio.md`, and derive a small bucket taxonomy from their
  strategy into `tags.json` (see step 1a). Tag any `other`/untagged names into `tags.json`.
- **If it's filled in**, respect it: lead the read through *their* stated strategy, and
  when reality drifts from the plan, say so. If they mention a new position, rule, or
  view, update the doc so it stays current.
- If the user ever says _"personalize this"_ or _"update my thesis"_, re-run the
  interview and rewrite the relevant sections.

## Tone

Be direct and unbiased. The user wants to know what's good AND what to change, not
validation. Lead with risk. Not financial advice; frame as analysis.
