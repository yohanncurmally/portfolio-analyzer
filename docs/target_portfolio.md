# Target Portfolio (your thesis; fill this in, or leave blank)

This file is **optional**. The analysis works without it. If you fill it in, the
skill will compare your live holdings against the plan you describe here ("is
reality tracking the target?"). If you leave it as-is, the skill just describes
your actual allocation and skips the comparison.

**Easiest way to fill this in:** don't type it yourself, just tell Claude
_"let's personalize this"_ and it'll interview you conversationally (your thesis, how
concentrated you are, whether you **buy or sell** options, your rules, your AI tilt)
and write your answers here for you.

Nothing here is uploaded or shared; it stays local (see Security in
`SETUP_FOR_CLAUDE.md`).

> **⚠️ NOTE TO CLAUDE (the agent, not the user): everything below marked `EXAMPLE` is a
> filled-in *sample* to show the intended shape only; it is NOT this user's portfolio,
> thesis, or rules. Do not treat any `EXAMPLE` ticker, weight, or number as a real
> holding or a real preference. During the Step 5 personalization interview, replace the
> `EXAMPLE` rows wholesale with the user's actual answers (and delete any that don't
> apply). If this file still contains `EXAMPLE` markers at analysis time, treat the
> thesis as UNSET; describe the real allocation and offer to personalize.**

---

## 1. Objective & constraints

- **Goal:** _(EXAMPLE)_ aggressive long-term growth, concentrated in the AI buildout.
- **Time horizon:** _(EXAMPLE)_ 5-10 years, comfortable holding through drawdowns.
- **Risk tolerance:** _(EXAMPLE)_ high; can stomach a 30-40% drawdown on the book.
- **Accounts in scope:** _(EXAMPLE)_ taxable brokerage + Roth IRA + a little crypto.
- **Options stance:** _(EXAMPLE)_ heavy options user. **Buys** ITM/LEAP calls for
  leverage on core names (avoids short-dated OTM lottery tickets) **and sells** premium
  for income: covered calls on longs, cash-secured puts to enter names, occasional
  credit spreads. Options run up to ~60% of the book.

## 2. Target allocation buckets

Describe the "sleeves" you want your money in and a target weight for each.

| Bucket | What's in it | Target % | Notes |
|---|---|---|---|
| _(EXAMPLE)_ Core AI compute | picks-and-shovels: chips, networking, power | 40% | highest conviction |
| _(EXAMPLE)_ AI software / apps | SaaS re-rating on AI adoption | 25% | |
| _(EXAMPLE)_ Megacap spenders | hyperscalers funding the buildout | 20% | ballast within the theme |
| _(EXAMPLE)_ High-torque pure-plays | debt-funded neoclouds / miners-turned-AI | 10% | speculative, size small |
| _(EXAMPLE)_ Cash / hedges | cash, short puts' collateral, protective puts | 5% | dry powder |

## 3. Per-name conviction (optional)

List individual tickers you hold or want to hold, your thesis in one line, and a
target weight or share/contract count.

| Ticker | One-line thesis | Target size |
|---|---|---|
| _(EXAMPLE)_ NVDA | owns the AI training stack; pricing power intact | 12% via ITM LEAPS |
| _(EXAMPLE)_ AVGO | custom-silicon + networking attach to every hyperscaler | 8% |
| _(EXAMPLE)_ MSFT | monetizing AI across cloud + apps, self-funds capex | 8% shares + covered calls |
| _(EXAMPLE)_ NOW | agentic workflow re-rating; sell CSPs to enter | 5%, wheel it |

## 4. Thesis buckets (optional)

The exposure chart splits your delta-$ into buckets you invest around. You define the
taxonomy: it can be anything (an AI-buildout thesis, dividend income, sector rotation,
factor sleeves). Claude builds it and tags each holding into `tags.json` during a run;
see `tags.example.json` for the shape and a worked AI-thesis example. Keep it small (aim
for 5 to 8 populated buckets plus "other"), and give each a human label, a color, and a
one-line description. A bucket earns its place only if it carries real weight and implies
a different action than its neighbors.

_(EXAMPLE)_ how a filled-in AI-thesis tilt might read; replace with your own buckets and
names:

| Bucket | Names you lean into | Rough target weight |
|---|---|---|
| _(EXAMPLE)_ AI picks & shovels (self-funded) | NVDA, AVGO, VRT, ANET | ~45%, overweight, core |
| _(EXAMPLE)_ Megacap AI (spenders) | MSFT, META, GOOGL | ~20% |
| _(EXAMPLE)_ AI software | NOW, CRM | ~20% |
| _(EXAMPLE)_ AI debt-funded infra (pure-plays) | NBIS, CRWV | ~10%, small, high torque |
| _(EXAMPLE)_ Other (cash + hedges) | cash + hedges | ~5% |

Any ticker not yet classified resolves to "other" in the output until you tag it in
`tags.json`.

## 5. Catalyst calendar (optional)

Earnings dates, product launches, macro events you're watching.

| Date | Ticker / event | Why it matters |
|---|---|---|
| _(EXAMPLE)_ next NVDA earnings | NVDA | biggest single-name mover; sets the whole picks-and-shovels tone |
| _(EXAMPLE)_ hyperscaler capex guides | MSFT/META/GOOGL/AMZN | a capex "blink" is the #1 cycle-turn signal |

## 6. Rules / guardrails (optional)

- _(EXAMPLE)_ no single position > 15% of net worth.
- _(EXAMPLE)_ roll or close any long option before 30 DTE; prefer rolling ITM, not OTM.
- _(EXAMPLE)_ only sell cash-secured puts on names I'd happily own at the strike.
- _(EXAMPLE)_ close short premium at ~50% of max profit; never let a short put sit ITM
  into expiry.
- _(EXAMPLE)_ keep at least 5% cash as dry powder.
