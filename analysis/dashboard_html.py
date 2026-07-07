"""Interactive, self-contained HTML dashboard for an enriched snapshot.

Emits a single .html file (no external CDNs; inline data + SVG charts + vanilla JS,
so it opens offline) with: KPI cards, allocation / AI-cycle-bucket / moneyness-vs-DTE /
exposure-by-underlying / expiry-wall charts, and a sortable, filterable positions table
where every row expands into a full per-position drilldown with a candid verdict.

Reads only from EnrichedSnapshot (same object viz.render uses), so PNG and HTML stay
in lockstep. Per-position greeks/carry/bucket/flags come straight from analysis.enrich.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from analysis.enrich import EnrichedSnapshot
from shared.ai_cycle import LABELS as BUCKET_LABELS


def _verdict(o) -> tuple[str, str]:
    """Return (tag, one-line rationale): the candid per-position call."""
    f = set(o.flags)
    dte = o.dte if o.dte is not None else 999
    ext_pct = (o.extrinsic_value / abs(o.market_value)) if o.market_value else 0.0
    if dte < 0:
        return ("EXPIRED?", "Past expiration in the feed; verify it actually settled/closed.")
    if "LOTTERY" in f:
        return ("CLOSE / ROLL", "Deep-OTM + short-dated lottery ticket, the exact profile to exit. "
                "Bank it or roll into an ITM/LEAP with real delta.")
    if "EXPENSIVE_CARRY" in f:
        return ("DE-RISK", f"Carry {o.carry_pct_yr:.0f}%/yr; you're renting expensive leverage. "
                "Roll down-and-out (lower strike, more time) to cut the annualized cost.")
    if "SHORT_DATED" in f and ext_pct > 0.5:
        return ("DECIDE NOW", f"{dte}d left and {ext_pct*100:.0f}% of value is decaying time; "
                "roll out or take it off before theta does.")
    if "SHORT_DATED" in f:
        return ("DECIDE NOW", f"{dte}d to expiry; needs a hold/roll/close call this week.")
    if "HIGH_THETA" in f:
        return ("TRIM / ROLL", f"{ext_pct*100:.0f}% of MV is time value under 120d; heavy theta bleed.")
    if "LEAP" in f and (o.carry_pct_yr or 99) < 25:
        return ("CORE HOLD", "Long-dated, cheap carry; this is the kind of leverage to keep.")
    if o.moneyness is not None and o.moneyness >= 1.05:
        return ("HOLD", "ITM with real intrinsic; lower-risk leg, let it work.")
    return ("HOLD", "No acute flag; monitor against thesis and expiry.")


def _num(x):
    return None if x is None else round(float(x), 4)


def _build_data(es: EnrichedSnapshot) -> dict:
    snap = es.snap
    total = snap.total_value or 1.0

    opt_pl = sum(o.unrealized_pl for o in es.options if o.unrealized_pl is not None)
    eq_pl = sum(e.unrealized_pl for a in snap.accounts for e in a.equities
                if e.unrealized_pl is not None)

    positions = []
    for o in es.options:
        tag, why = _verdict(o)
        ext_pct_mv = (o.extrinsic_value / abs(o.market_value)) if o.market_value else None
        positions.append({
            "symbol": o.symbol, "type": o.option_type, "side": o.side,
            "strike": o.strike, "expiration": o.expiration[:10] if o.expiration else None,
            "dte": o.dte, "qty": o.quantity, "mark": _num(o.mark),
            "mv": _num(o.market_value), "avg_price": _num(o.avg_price),
            "unrealized_pl": _num(o.unrealized_pl), "spot": _num(o.spot),
            "moneyness": _num(o.moneyness), "pct_to_strike": _num(o.pct_to_strike),
            "intrinsic": _num(o.intrinsic_per_share), "extrinsic_ps": _num(o.extrinsic_per_share),
            "extrinsic_value": _num(o.extrinsic_value), "extrinsic_pct_mv": _num(ext_pct_mv),
            "notional": _num(o.notional), "iv": _num(o.iv), "delta": _num(o.delta),
            "delta_notional": _num(o.delta_notional), "carry_pct_yr": _num(o.carry_pct_yr),
            "cycle_bucket": o.cycle_bucket, "flags": o.flags,
            "verdict": tag, "why": why,
        })
    positions.sort(key=lambda p: -(p["mv"] or 0))

    # AI-cycle buckets (delta-$)
    buckets = []
    for code, dv in es.notional_by_bucket.items():
        buckets.append({"code": code, "label": BUCKET_LABELS.get(code, code),
                        "delta_notional": round(dv), "pct": round(dv / total * 100, 1)})

    # exposure by underlying (delta-$)
    by_sym = defaultdict(float)
    for o in es.options:
        by_sym[o.symbol] += (o.delta_notional or 0.0)
    underlyings = [{"symbol": s, "delta_notional": round(v)}
                   for s, v in sorted(by_sym.items(), key=lambda kv: -abs(kv[1]))]

    # expiry wall
    ext_m, int_m, cnt_m = defaultdict(float), defaultdict(float), defaultdict(int)
    for o in es.options:
        try:
            m = datetime.strptime(o.expiration[:10], "%Y-%m-%d").strftime("%Y-%m")
        except (ValueError, TypeError):
            continue
        ext_m[m] += o.extrinsic_value
        int_m[m] += o.intrinsic_per_share * 100 * o.quantity
        cnt_m[m] += 1
    expiry = [{"month": m, "intrinsic": round(int_m[m]), "extrinsic": round(ext_m[m]),
               "count": cnt_m[m]} for m in sorted(set(ext_m) | set(int_m))]

    # prioritized action list
    actions = []
    sd = sorted({p["symbol"] for p in positions if "SHORT_DATED" in p["flags"]})
    lot = sorted({p["symbol"] for p in positions if "LOTTERY" in p["flags"]})
    exp = sorted({p["symbol"] for p in positions if "EXPENSIVE_CARRY" in p["flags"]})
    if sd:
        actions.append(("THIS WEEK", f"Expiring <30d, hold/roll/close decision: {', '.join(sd)}"))
    if lot:
        actions.append(("DE-RISK", f"Deep-OTM lottery tickets to exit/roll ITM: {', '.join(lot)}"))
    if exp:
        actions.append(("DE-RISK", f"Expensive carry (>40%/yr), roll down-and-out: {', '.join(exp)}"))
    top = underlyings[0] if underlyings else None
    if top and abs(top["delta_notional"]) / total > 0.6:
        actions.append(("CONCENTRATION",
                        f"{top['symbol']} is {abs(top['delta_notional'])/total:.2f}x NAV of delta-$ "
                        ", single-name concentration risk."))
    if snap.cash / total < 0.10:
        actions.append(("LIQUIDITY", f"Cash is {snap.cash/total*100:.0f}% of NAV, thin dry powder."))
    dlev = es.net_delta_notional / total
    if dlev > 2.5:
        actions.append(("LEVERAGE", f"Delta-adjusted exposure {dlev:.2f}x NAV, directional risk is high."))

    return {
        "meta": {"timestamp": snap.timestamp, "source": snap.source,
                 "generated": datetime.now().strftime("%Y-%m-%d %H:%M")},
        "totals": {
            "total_value": round(total), "equity_value": round(snap.equity_value),
            "options_value": round(snap.options_value), "cash": round(snap.cash),
            "cash_pct": round(snap.cash / total * 100, 1),
            "controlled_notional": round(es.total_notional),
            "net_delta_notional": round(es.net_delta_notional),
            "leverage_x": round(es.total_notional / total, 2),
            "delta_leverage_x": round(es.net_delta_notional / total, 2),
            "extrinsic_at_risk": round(es.total_extrinsic),
            "extrinsic_pct_nav": round(es.total_extrinsic / total * 100, 1),
            "opt_pl": round(opt_pl), "eq_pl": round(eq_pl),
        },
        "accounts": [{"name": a.name, "type": a.account_type, "total": round(a.total_value),
                      "cash": round(a.cash), "equity_value": round(a.equity_value),
                      "options_value": round(a.options_value)} for a in snap.accounts],
        "buckets": buckets, "underlyings": underlyings, "expiry": expiry,
        "positions": positions, "actions": actions,
    }


def render(es: EnrichedSnapshot, path: str) -> str:
    data = _build_data(es)
    html = _TEMPLATE.replace("/*__DATA__*/", json.dumps(data))
    with open(path, "w") as f:
        f.write(html)
    return path


# --------------------------------------------------------------------------------------
# Single-file template. Data is injected in place of the /*__DATA__*/ token. All charts
# are hand-drawn SVG (no CDN) so the file is fully portable/offline.
# --------------------------------------------------------------------------------------
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portfolio Dashboard</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2230;--line:#2a323d;--tx:#e6edf3;--mut:#8b949e;
--grn:#3fb950;--red:#f85149;--org:#e3934f;--blu:#58a6ff;--pur:#bc8cff;--yel:#e3b341;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial}
.wrap{max-width:1360px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 2px}
.sub{color:var(--mut);font-size:13px;margin-bottom:20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:22px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .l{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.kpi .v{font-size:22px;font-weight:700;margin-top:4px}
.kpi .h{font-size:11px;margin-top:3px;color:var(--mut)}
.pos{color:var(--grn)}.neg{color:var(--red)}.warn{color:var(--org)}.blu{color:var(--blu)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{margin:0 0 12px;font-size:13px;font-weight:600;color:var(--tx)}
.full{grid-column:1/-1}
.actions{list-style:none;padding:0;margin:0}
.actions li{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line)}
.actions li:last-child{border:0}
.badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;white-space:nowrap;text-transform:uppercase;letter-spacing:.4px}
.b-week{background:#5a2a00;color:#ffb972}.b-derisk{background:#5a1717;color:#ff9d97}
.b-conc{background:#2a2350;color:#c4b5ff}.b-liq{background:#003a4d;color:#8fd6ff}.b-lev{background:#4d0033;color:#ff9de0}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.controls input{background:var(--panel2);border:1px solid var(--line);color:var(--tx);border-radius:8px;padding:7px 10px;font-size:13px;min-width:180px}
.chip{cursor:pointer;font-size:11px;padding:4px 10px;border-radius:20px;border:1px solid var(--line);background:var(--panel2);color:var(--mut);user-select:none}
.chip.on{background:var(--blu);color:#001a33;border-color:var(--blu);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 9px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--mut);font-weight:600;cursor:pointer;position:sticky;top:0;background:var(--panel);user-select:none}
th:first-child,td:first-child{text-align:left}th.a-l{text-align:left}
tr.row{cursor:pointer}tr.row:hover td{background:var(--panel2)}
.tag{font-size:10px;font-weight:700;padding:2px 6px;border-radius:5px}
.t-close,.t-derisk{background:#5a1717;color:#ff9d97}.t-now,.t-trim{background:#5a2a00;color:#ffb972}
.t-hold{background:#123a1a;color:#7ee29a}.t-core{background:#0d2a4d;color:#8fc4ff}
.fl{font-size:9px;padding:1px 5px;border-radius:4px;background:var(--panel2);color:var(--mut);margin-left:3px}
.drill{background:var(--panel2)}
.drill td{padding:0}
.dwrap{padding:16px 18px}
.why{background:#0d1117;border-left:3px solid var(--org);padding:10px 14px;border-radius:6px;margin-bottom:14px;color:var(--tx)}
.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 11px}
.stat .l{color:var(--mut);font-size:10px;text-transform:uppercase}.stat .v{font-size:15px;font-weight:600;margin-top:2px}
.muted{color:var(--mut)} svg{display:block;width:100%}
.lgd{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--mut);margin-top:8px}
.lgd span{display:inline-flex;align-items:center;gap:5px}.dot{width:9px;height:9px;border-radius:2px;display:inline-block}
</style></head><body><div class="wrap">
<h1>Portfolio Dashboard</h1><div class="sub" id="sub"></div>
<div class="kpis" id="kpis"></div>
<div class="card full" style="margin-bottom:22px"><h3>Prioritized actions</h3><ul class="actions" id="actions"></ul></div>
<div class="grid">
  <div class="card"><h3>Asset allocation</h3><div id="alloc"></div><div class="lgd" id="alloc-lgd"></div></div>
  <div class="card"><h3>Delta-$ by AI-cycle bucket</h3><div id="buckets"></div></div>
  <div class="card"><h3>Moneyness vs. days-to-expiry <span class="muted">(bubble = delta-$)</span></h3><div id="scatter"></div></div>
  <div class="card"><h3>Delta-$ exposure by underlying (top 14)</h3><div id="unders"></div></div>
  <div class="card full"><h3>Expiry wall: intrinsic (real) vs. extrinsic (decaying)</h3><div id="expiry"></div>
    <div class="lgd"><span><i class="dot" style="background:var(--blu)"></i>Intrinsic</span><span><i class="dot" style="background:var(--red)"></i>Extrinsic (time value at risk)</span></div></div>
</div>
<div class="card full">
  <h3>Positions (click any row to drill down)</h3>
  <div class="controls">
    <input id="search" placeholder="Filter by ticker…" oninput="applyFilter()">
    <span class="chip" data-f="ITM">ITM</span><span class="chip" data-f="OTM">OTM</span>
    <span class="chip" data-f="SHORT_DATED">&lt;30d</span><span class="chip" data-f="LEAP">LEAP</span>
    <span class="chip" data-f="LOTTERY">Lottery</span><span class="chip" data-f="EXPENSIVE_CARRY">Expensive carry</span>
    <span class="chip" data-f="HIGH_THETA">High theta</span>
  </div>
  <div style="overflow:auto;max-height:640px"><table id="tbl"><thead><tr>
    <th class="a-l" data-k="symbol">Ticker</th><th data-k="strike">Strike</th><th class="a-l" data-k="expiration">Exp</th>
    <th data-k="dte">DTE</th><th data-k="qty">Qty</th><th data-k="mark">Mark</th><th data-k="mv">MV</th>
    <th data-k="moneyness">Mny</th><th data-k="delta">Δ</th><th data-k="delta_notional">Δ-$</th>
    <th data-k="carry_pct_yr">Carry/yr</th><th data-k="extrinsic_value">Extrinsic</th>
    <th data-k="unrealized_pl">P/L</th><th class="a-l" data-k="cycle_bucket">Bucket</th><th class="a-l">Verdict</th>
  </tr></thead><tbody id="tb"></tbody></table></div>
</div>
<div class="sub" id="foot" style="margin-top:18px"></div>
</div>
<script>
const D=/*__DATA__*/;
function money(n){if(n==null)return '—';const s=n<0?'-':'';return s+'$'+Math.abs(Math.round(n)).toLocaleString();}
function k(n){if(n==null)return '—';const s=n<0?'-':'';const a=Math.abs(n);return s+'$'+(a>=1000?(a/1000).toFixed(0)+'k':Math.round(a));}
function pct(n,d){return n==null?'—':(n).toFixed(d==null?1:d)+'%';}
function num(n,d){return n==null?'—':n.toFixed(d==null?2:d);}
const clr=v=>v>0?'pos':v<0?'neg':'';
const BC={G1:'#58a6ff',G2:'#bc8cff',G3A:'#e3934f',G3B:'#f85149',NON:'#8b949e',UNTAGGED:'#e3b341'};

// ---- KPIs ----
const T=D.totals;
document.getElementById('sub').innerHTML=`Snapshot ${D.meta.timestamp?D.meta.timestamp.slice(0,16):''} · source ${D.meta.source||'—'} · generated ${D.meta.generated}`;
const kpis=[
 ['Total value',money(T.total_value),`Cash ${T.cash_pct}% · Opt ${money(T.options_value)} · Eq ${money(T.equity_value)}`,''],
 ['Delta-adj leverage',T.delta_leverage_x+'x',`Gross notional ${T.leverage_x}x (${money(T.controlled_notional)})`,T.delta_leverage_x>2.5?'warn':''],
 ['Net directional Δ-$',money(T.net_delta_notional),'True directional exposure',''],
 ['Time value at risk',money(T.extrinsic_at_risk),`${T.extrinsic_pct_nav}% of NAV decays absent a move`,T.extrinsic_pct_nav>40?'warn':''],
 ['Unrealized P/L',money(T.opt_pl+T.eq_pl),`Opt ${money(T.opt_pl)} · Eq ${money(T.eq_pl)}`,clr(T.opt_pl+T.eq_pl)],
 ['Cash',money(T.cash),`${T.cash_pct}% dry powder`,T.cash_pct<10?'warn':''],
];
document.getElementById('kpis').innerHTML=kpis.map(x=>`<div class="kpi"><div class="l">${x[0]}</div><div class="v ${x[3]}">${x[1]}</div><div class="h">${x[2]}</div></div>`).join('');

// ---- actions ----
const bmap={'THIS WEEK':'b-week','DE-RISK':'b-derisk','CONCENTRATION':'b-conc','LIQUIDITY':'b-liq','LEVERAGE':'b-lev'};
document.getElementById('actions').innerHTML=(D.actions.length?D.actions:[['OK','No acute flags; book is within tolerances.']])
 .map(a=>`<li><span class="badge ${bmap[a[0]]||''}">${a[0]}</span><span>${a[1]}</span></li>`).join('');

// ---- SVG helpers ----
const NS='http://www.w3.org/2000/svg';
function svg(w,h){const s=document.createElementNS(NS,'svg');s.setAttribute('viewBox',`0 0 ${w} ${h}`);s.setAttribute('width','100%');return s;}
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e;}
function txt(x,y,s,a,p,cls){const t=el('text',{x,y,fill:cls||'#8b949e','font-size':a&&a.fs||11,'text-anchor':a&&a.anchor||'start'},p);t.textContent=s;return t;}

// donut allocation
(function(){const items=[['Equities',T.equity_value,'#58a6ff'],['Options',T.options_value,'#e3934f'],['Cash',T.cash,'#3fb950']];
 const tot=items.reduce((s,i)=>s+i[1],0)||1;const W=280,H=180,cx=90,cy=90,r=70,rin=42;let a0=-Math.PI/2;
 const s=svg(W,H);for(const it of items){const frac=it[1]/tot,a1=a0+frac*2*Math.PI;
  const x0=cx+r*Math.cos(a0),y0=cy+r*Math.sin(a0),x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1);
  const xi1=cx+rin*Math.cos(a1),yi1=cy+rin*Math.sin(a1),xi0=cx+rin*Math.cos(a0),yi0=cy+rin*Math.sin(a0);
  const big=frac>0.5?1:0;
  el('path',{d:`M${x0},${y0} A${r},${r} 0 ${big} 1 ${x1},${y1} L${xi1},${yi1} A${rin},${rin} 0 ${big} 0 ${xi0},${yi0} Z`,fill:it[2]},s);a0=a1;}
 txt(cx,cy+4,money(tot),{anchor:'middle',fs:15},s,'#e6edf3');
 document.getElementById('alloc').appendChild(s);
 document.getElementById('alloc-lgd').innerHTML=items.map(i=>`<span><i class="dot" style="background:${i[2]}"></i>${i[0]} ${((i[1]/tot)*100).toFixed(0)}%</span>`).join('');
})();

// horizontal bars generic
function hbars(elid,rows,fmt){const W=560,rowH=26,H=rows.length*rowH+14;const s=svg(W,H);
 const max=Math.max(1,...rows.map(r=>Math.abs(r.v)));const lblW=52,x0=lblW+6,bw=W-x0-70;
 rows.forEach((r,i)=>{const y=i*rowH+8;txt(lblW,y+13,r.label,{anchor:'end',fs:11},s,'#e6edf3');
  const w=Math.abs(r.v)/max*bw;el('rect',{x:x0,y:y+3,width:w,height:16,rx:3,fill:r.color||'#8172b3'},s);
  txt(x0+w+5,y+15,fmt(r.v),{fs:10},s,'#8b949e');});
 document.getElementById(elid).appendChild(s);}
hbars('buckets',D.buckets.map(b=>({label:b.code,v:b.delta_notional,color:BC[b.code]||'#8172b3'})),v=>k(v)+'');
hbars('unders',D.underlyings.slice(0,14).map(u=>({label:u.symbol,v:u.delta_notional,color:u.delta_notional<0?'#f85149':'#8172b3'})),v=>k(v));

// scatter moneyness vs dte
(function(){const P=D.positions.filter(p=>p.moneyness!=null&&p.dte!=null);const W=560,H=300,ml=44,mb=30,mt=10,mr=12;
 const xs=P.map(p=>p.dte),ys=P.map(p=>p.moneyness);const xmax=Math.max(60,...xs),ymin=Math.min(0.7,...ys),ymax=Math.max(1.3,...ys);
 const px=d=>ml+(d/xmax)*(W-ml-mr),py=m=>mt+(1-(m-ymin)/(ymax-ymin))*(H-mt-mb);const s=svg(W,H);
 el('line',{x1:ml,y1:py(1),x2:W-mr,y2:py(1),stroke:'#2a323d','stroke-dasharray':'4 3'},s);txt(W-mr,py(1)-3,'ATM',{anchor:'end',fs:9},s,'#8b949e');
 [0,30,60,90,180,270].filter(d=>d<=xmax).forEach(d=>{el('line',{x1:px(d),y1:mt,x2:px(d),y2:H-mb,stroke:'#1c2230'},s);txt(px(d),H-mb+13,d+'d',{anchor:'middle',fs:9},s);});
 [0.8,1.0,1.2].forEach(m=>txt(ml-6,py(m)+3,m.toFixed(1),{anchor:'end',fs:9},s));
 const dmax=Math.max(1,...P.map(p=>Math.abs(p.delta_notional||0)));
 P.forEach(p=>{const r=6+Math.sqrt(Math.abs(p.delta_notional||0)/dmax)*22;
  const c=p.moneyness>=1?'#3fb950':p.moneyness>=0.85?'#e3934f':'#f85149';
  const g=el('g',{},s);const cir=el('circle',{cx:px(p.dte),cy:py(p.moneyness),r:r,fill:c,'fill-opacity':.45,stroke:c},g);
  cir.appendChild(el('title',{},cir)).textContent=`${p.symbol} ${p.strike}${p.type[0]} ${p.expiration} · Δ-$ ${k(p.delta_notional)}`;
  txt(px(p.dte),py(p.moneyness)+3,p.symbol,{anchor:'middle',fs:8},g,'#e6edf3');});
 document.getElementById('scatter').appendChild(s);})();

// expiry wall stacked
(function(){const E=D.expiry;if(!E.length){document.getElementById('expiry').textContent='—';return;}
 const W=1280,H=220,ml=54,mb=34,mt=10;const max=Math.max(1,...E.map(m=>m.intrinsic+m.extrinsic));
 const bw=(W-ml-10)/E.length,pw=Math.min(70,bw*0.6);const s=svg(W,H);const H0=H-mb;
 E.forEach((m,i)=>{const x=ml+i*bw+(bw-pw)/2;const hi=m.intrinsic/max*(H0-mt),he=m.extrinsic/max*(H0-mt);
  el('rect',{x,y:H0-hi,width:pw,height:hi,fill:'#58a6ff'},s);
  el('rect',{x,y:H0-hi-he,width:pw,height:he,fill:'#f85149'},s);
  txt(x+pw/2,H0+13,m.month,{anchor:'middle',fs:10},s);
  txt(x+pw/2,H0-hi-he-4,k(m.intrinsic+m.extrinsic),{anchor:'middle',fs:9},s,'#e6edf3');
  txt(x+pw/2,H0+25,m.count+' legs',{anchor:'middle',fs:8},s);});
 document.getElementById('expiry').appendChild(s);})();

// ---- positions table ----
let SORT={k:'mv',dir:-1},FILTERS=new Set(),Q='';
const tb=document.getElementById('tb');
function verdictCls(v){return v==='CLOSE / ROLL'||v==='DE-RISK'?'t-close':v==='DECIDE NOW'||v==='TRIM / ROLL'?'t-now':v==='CORE HOLD'?'t-core':'t-hold';}
function rowHtml(p,i){
 const fl=p.flags.map(f=>`<span class="fl">${f}</span>`).join('');
 return `<tr class="row" data-i="${i}">
  <td class="a-l"><b>${p.symbol}</b> <span class="muted">${p.type[0].toUpperCase()}${p.side==='short'?'·S':''}</span></td>
  <td>${p.strike}</td><td class="a-l">${p.expiration||'—'}</td><td>${p.dte==null?'—':p.dte}</td>
  <td>${p.qty}</td><td>${num(p.mark)}</td><td>${k(p.mv)}</td>
  <td>${num(p.moneyness)}</td><td>${num(p.delta)}</td><td>${k(p.delta_notional)}</td>
  <td class="${(p.carry_pct_yr||0)>40?'warn':''}">${p.carry_pct_yr==null?'—':p.carry_pct_yr.toFixed(0)+'%'}</td>
  <td>${k(p.extrinsic_value)}</td><td class="${clr(p.unrealized_pl)}">${p.unrealized_pl==null?'n/a':k(p.unrealized_pl)}</td>
  <td class="a-l"><span style="color:${BC[p.cycle_bucket]||'#8b949e'}">●</span> ${p.cycle_bucket}</td>
  <td class="a-l"><span class="tag ${verdictCls(p.verdict)}">${p.verdict}</span></td></tr>
  <tr class="drill" id="dr-${i}" style="display:none"><td colspan="15"><div class="dwrap">
   <div class="why"><b>${p.verdict}.</b> ${p.why} ${fl}</div>
   <div class="dgrid">
    ${stat('Spot',num(p.spot))}${stat('Strike / DTE',p.strike+' · '+(p.dte==null?'—':p.dte+'d'))}
    ${stat('Moneyness',num(p.moneyness))}${stat('% to strike',pct(p.pct_to_strike))}
    ${stat('Implied vol',p.iv==null?'—':(p.iv*100).toFixed(0)+'%')}${stat('Delta',num(p.delta))}
    ${stat('Delta-$ (directional)',money(p.delta_notional))}${stat('Carry / yr',p.carry_pct_yr==null?'—':p.carry_pct_yr.toFixed(0)+'%')}
    ${stat('Mark / Avg',num(p.mark)+' / '+(p.avg_price==null?'n/a':num(p.avg_price)))}${stat('Market value',money(p.mv))}
    ${stat('Intrinsic / sh',num(p.intrinsic))}${stat('Extrinsic / sh',num(p.extrinsic_ps))}
    ${stat('Extrinsic $ (at risk)',money(p.extrinsic_value))}${stat('Extrinsic % of MV',pct(p.extrinsic_pct_mv==null?null:p.extrinsic_pct_mv*100))}
    ${stat('Controlled notional',money(p.notional))}${stat('Unrealized P/L',p.unrealized_pl==null?'n/a':money(p.unrealized_pl))}
   </div></div></td></tr>`;}
function stat(l,v){return `<div class="stat"><div class="l">${l}</div><div class="v">${v}</div></div>`;}
function render(){
 let rows=D.positions.map((p,i)=>[p,i]);
 if(Q)rows=rows.filter(([p])=>p.symbol.toLowerCase().includes(Q));
 if(FILTERS.size)rows=rows.filter(([p])=>[...FILTERS].every(f=>p.flags.includes(f)));
 rows.sort((a,b)=>{let x=a[0][SORT.k],y=b[0][SORT.k];if(x==null)x=-Infinity;if(y==null)y=-Infinity;
  if(typeof x==='string')return SORT.dir*x.localeCompare(y);return SORT.dir*(x-y);});
 tb.innerHTML=rows.map(([p,i])=>rowHtml(p,i)).join('');
 tb.querySelectorAll('tr.row').forEach(tr=>tr.onclick=()=>{const d=document.getElementById('dr-'+tr.dataset.i);d.style.display=d.style.display==='none'?'':'none';});
}
function applyFilter(){Q=document.getElementById('search').value.trim().toLowerCase();render();}
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{const f=c.dataset.f;if(FILTERS.has(f)){FILTERS.delete(f);c.classList.remove('on');}else{FILTERS.add(f);c.classList.add('on');}render();});
document.querySelectorAll('#tbl th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;SORT.dir=SORT.k===k?-SORT.dir:-1;SORT.k=k;render();});
render();
document.getElementById('foot').textContent=`${D.positions.length} option legs · buckets: `+D.buckets.map(b=>`${b.code} ${b.pct}%`).join(' · ');
</script></body></html>"""
