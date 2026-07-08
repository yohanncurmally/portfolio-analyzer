# Sample written analysis

This is the kind of position-by-position read the tool produces, run against the
fabricated demo portfolio you get from:

```bash
python scripts/analyze.py --source demo
```

Everything below is invented. It is not a real portfolio, not anyone's holdings, and
not a recommendation. The point is to show the shape and candor of the output before you
connect a broker. The dashboard image in the [README](../README.md) is this same demo
book. Numbers here are the enriched figures the pipeline computes (spot, moneyness,
put-correct greeks, carry, and the risk flags), not hand-waving.

The demo assumes an aggressive, high-conviction investor tilted toward the AI buildout,
who buys options for leverage and prefers in-the-money LEAPS over out-of-the-money
lottery tickets, with one short put to show the premium-selling read. If your real
strategy is different, the tool reframes all of this once you personalize it.

---

## The one-paragraph read

This is a leveraged, concentrated AI-buildout book. Net worth on the screen is about
**$290.8k** (equities $128.1k, options $146.7k, cash $16.0k), but the options control
roughly **$997k** of underlying, so raw leverage is **3.4x**. The honest number is the
delta-adjusted one: **$585k of net directional exposure, or 2.0x** your account. Total
unrealized gain is about **+$72.1k**, split fairly evenly between the stock (+$39.7k) and
the options (+$32.3k). The structural risk is not the direction, which is fine, it is
**time**: about **$71.1k of extrinsic (time) value, 24.4% of the whole account**, will
decay to zero if the underlyings just sit still. Most of that decay risk is concentrated
in four short-dated, expensive-carry legs (MRVL, IREN, SMCI, NET) that are doing the
damage while the ITM LEAPS are doing the work. The fix is not to cut the thesis, it is to
roll the cheap-thesis, expensive-structure legs out and up before theta eats them.

---

## Exposure by AI capital-cycle bucket (whole book)

The tool tags every holding, stock and option alike, by where it sits in the AI capital
cycle, then sums whole-book directional exposure (equity market value plus option
delta-$) per bucket. On the dashboard this is a chart with a legend that spells out each
code, so you are never left guessing what G3A or G3B means:

| Bucket | Exposure | What's in it |
|---|---:|---|
| G3A picks & shovels, self-funded | $366.1k (51%) | The core of the book: NVDA stock plus AMD, MU, TSM, DELL, MRVL, SMCI calls. The crowded rotation; the risk is a capex blink from the hyperscalers. |
| G2 megacap spender | $140.9k (20%) | AAPL, AMZN, MSFT stock plus ORCL and TSLA calls. De-rated names funding the buildout from cash flow; earnings risk, not a multiple crash. |
| G1 beaten SaaS | $108.4k (15%) | CRWD and NET calls, plus the short PANW put. Re-rating stories with execution risk. |
| Untagged | $54.2k (8%) | VOO, COST, SCHD. Broad ETFs and a non-thesis stock, correctly sitting outside the AI-cycle map. |
| Non-AI-cycle | $22.1k (3%) | HOOD call. Fintech momentum, not an AI-capex name. |
| G3B debt-funded pure-play | $21.7k (3%) | IREN call. Highest torque up, first to break if financing tightens. |

The concentration flag is real: over half the directional exposure (51%) sits in one
bucket, G3A. That is a coherent bet if you believe the self-funded infrastructure names
are the safest way to own the buildout, but it is a single point of failure. A capex
pause hits all of them at once.

---

## Options, position by position

Sorted roughly best-structured to worst. "Carry" is the annualized percent the underlying
must move in your favor just to break even on the leverage, so low carry is cheap and high
carry is expensive.

### CORE HOLD, the LEAPS doing the work

**AMD $180 call, 353 DTE.** Spot $214, 19% ITM, delta 0.76, carry only **11.6%/yr**,
up **+$10.2k**. This is exactly what a leverage leg should look like: deep enough ITM to
move nearly one-for-one with the stock, over a year of runway, and cheap carry. Nothing to
do but hold it.

**MU $120 call, 353 DTE.** Spot $148, 23% ITM, delta 0.79, carry **9.1%/yr**, up
**+$7.5k**. Same profile, even cheaper carry. Core position.

**ORCL $175 call, 353 DTE.** Spot $208, 19% ITM, delta 0.79, carry **8.0%/yr**, up
**+$5.1k**. The cheapest carry in the book. Hold.

These three are the template. If every leg looked like this, there would be almost nothing
to flag.

### HOLD, fine but watch the clock

**CRWD $340 call, 171 DTE.** 15% ITM, delta 0.75, carry 14.7%, up +$3.6k. Solid, but
under six months of life. Fine for now.

**TSM $220 call, 171 DTE.** 12% ITM, delta 0.74, carry 13.9%, up +$3.6k. Good structure.

**HOOD $80 call, 143 DTE.** 20% ITM, delta 0.77, carry 18.6%, up +$2.4k. Deep ITM helps;
the higher carry is the 58% IV you are paying for. Watch it past 90 DTE.

**DELL $140 call, 143 DTE.** 11% ITM, delta 0.72, carry 18.0%, up +$3.2k. Fine.

### TRIM / ROLL

**TSLA $300 call, 80 DTE.** Barely ITM (spot $312, moneyness 1.04), delta 0.62, carry
**39.5%/yr**, down **-$1.0k**, flagged **HIGH_THETA**. This is the marginal leg: it sits
in G2 (megacap) but is the lowest-conviction name there, close to the money so it has the
most time value to lose, and under 90 days. Either roll it out and up to reset the decay
clock, or take it off. It is the one position that is neither a conviction hold nor a
clear cut.

### DE-RISK, the theta bleed

These four are the problem. The direction may well be right, but the structure is working
against you. Short-dated, high IV, and carry so high the stock has to rip just to break
even.

**MRVL $95 call, 52 DTE.** At the money (moneyness 1.01), IV 64%, carry **65.8%/yr**,
up +$2.1k, flagged HIGH_THETA + EXPENSIVE_CARRY. You are up, so take the win or roll it
to a LEAP. At 52 days and this carry, the gain evaporates fast if MRVL stalls.

**IREN $25 call, 52 DTE.** Out of the money (spot $23), IV 88%, carry **131%/yr**, up
+$1.6k, flagged HIGH_THETA + EXPENSIVE_CARRY. G3B debt-funded pure-play, the highest-torque,
first-to-break bucket, held through a short-dated OTM call. This is a lottery ticket that
happens to be green. Bank it.

**NET $205 call, 14 DTE.** OTM (spot $184, needs an 11% rise), IV 78%, carry **357%/yr**,
down **-$2.9k**, flagged SHORT_DATED + OTM + HIGH_THETA + EXPENSIVE_CARRY. Two weeks left
and 11% out of the money. This is nearly a coin flip on a binary outcome. If you still
believe the story, express it with a longer-dated ITM call, not this.

**SMCI $55 call, 24 DTE.** Deep OTM (spot $47, needs a 17% rise), IV **132%**, carry
**375%/yr**, down **-$3.0k**, flagged everything. The worst-structured leg in the book:
short-dated, deep out of the money, and the IV alone tells you the market is pricing a coin
flip. This is the position most likely to go to zero. Close it or accept it as a full
write-off.

### The short put

**PANW $175 put, short, 52 DTE.** Spot $196, so the put is 12% OTM and you are the seller.
Flat P/L, no risk flags. Correctly read as a **HOLD**: as a premium seller your risk here
is assignment (PANW falling below $175), not the time decay that hurts the long legs. Time
decay is on your side. The tool does not flag your short with the long-holder warnings,
which is the point of telling it you sell premium.

---

## Equities, quick pass

The stock sleeve is the ballast and it is all green:

| Symbol | Account | Qty | Cost | Price | Value | Unrealized |
|---|---|---:|---:|---:|---:|---:|
| VOO | Individual | 60 | $430 | $560 | $33.6k | +$7.8k |
| NVDA | Individual | 120 | $92 | $178 | $21.4k | +$10.3k |
| AAPL | Individual | 90 | $170 | $235 | $21.2k | +$5.9k |
| AMZN | Roth | 80 | $150 | $235 | $18.8k | +$6.8k |
| COST | Individual | 15 | $720 | $985 | $14.8k | +$4.0k |
| MSFT | Roth | 25 | $330 | $505 | $12.6k | +$4.4k |
| SCHD | Roth | 200 | $26 | $29 | $5.8k | +$0.6k |

Nothing to flag on the stock. VOO and SCHD are the diversifiers; NVDA is the largest single
gain. The Roth holds the long-term compounders (AMZN, MSFT) and the dividend sleeve (SCHD),
which is the tax-efficient place for them. This is a sensible base under an aggressive
options overlay.

---

## What the tool would suggest

Not advice, just the read the numbers point to:

1. **The thesis is fine; the structure is the problem.** You are directionally right (+$72k)
   and the LEAPS are cheap. The issue is the $71k of time value at risk, most of it in four
   short-dated legs.
2. **Roll the DE-RISK legs.** MRVL, IREN, SMCI, and NET are paying 60% to 375% annualized
   carry for exposure you could hold as ITM LEAPS at 8% to 15%. Two are green (bank them),
   two are red (SMCI especially is close to a write-off). If you still believe each story,
   re-express it the way AMD/MU/ORCL are held.
3. **Decide on TSLA.** It is the one leg that is neither conviction nor junk. Roll it out
   and up, or let it go.
4. **Mind the G3A concentration.** Over half your directional risk is one bucket. That is a
   deliberate bet, but a single capex-cycle headline moves all of it together.

Run it against your own book to see this read on your actual positions:
`python scripts/analyze.py` (see the [README](../README.md) to set up).
