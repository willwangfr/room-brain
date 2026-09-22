"""Render tonight's room as a live radial map: me in the middle, the people I
already know floating on an inner ring (edge color = how we know each other,
size = how much we talk, pink ring = recent job or bio change), strangers who
wrote a bio on an outer ring. Bubbles are draggable; labels stay horizontal.

    ./run.sh -m brain.graph [event_api_id]   ->  data/graph.html
"""
import json
import os
import sys
from pathlib import Path

from brain import crm_tools as ct
from brain.updates import life_updates, self_person_ids

ROOT = Path(__file__).resolve().parent.parent
# Order of "how strongly do I know you": in-person channels first.
STRONG = ("whatsapp", "imessage", "calls", "contacts", "gmail", "instagram", "linkedin")


def strongest(sources):
    for s in STRONG:
        if s in sources:
            return s
    return "luma"


def build(event_api_id, anon=False):
    """anon=True replaces names, employers, bios and links so the page can be shown publicly."""
    me = self_person_ids()
    known = [p for p in ct.who_do_i_know_at(event_api_id) if p["person_id"] not in me]
    strangers = [s for s in ct.strangers_at(event_api_id, limit=400) if s.get("bio_short")]
    changed = {u["person_id"] for u in life_updates(limit=100000)}
    registered = next((e["n_guests"] for e in ct.list_events() if e["event_api_id"] == event_api_id), None)
    return {
        "known": [{"id": p["person_id"], "label": f"Person {i + 1}" if anon else p["name"],
                   "employer": "" if anon else (p.get("employer") or ""),
                   "title": "" if anon else (p.get("title") or ""), "how": p.get("how_we_know") or [],
                   "via": strongest(p.get("how_we_know") or []), "msgs": p.get("n_messages", 0),
                   "last": "" if anon else (p.get("last_contact_at") or "")[:10],
                   "changed": p["person_id"] in changed,
                   "links": [] if anon else (p.get("links") or [])} for i, p in enumerate(known)],
        "strangers": [{"label": f"Guest {i + 1}" if anon else s["name"],
                       "bio": "" if anon else (s.get("bio_short") or ""),
                       "links": [] if anon else (s.get("links") or [])} for i, s in enumerate(strangers)],
        "stats": {"registered": registered, "known": len(known), "strangers": len(strangers),
                  "changed": sum(1 for p in known if p["person_id"] in changed)},
    }


HTML = """<!doctype html><meta charset=utf-8><title>Room Brain</title>
<style>
body{margin:0;background:#0b0f14;color:#e6edf3;font:14px/1.45 -apple-system,Helvetica,Arial;overflow:hidden}
#hud{position:fixed;left:22px;top:18px;max-width:340px}#hud h1{font-size:20px;margin:0 0 2px;font-weight:650}
#hud .stats{color:#8b949e;margin-bottom:12px}.legend div{margin:3px 0;color:#c9d1d9}
.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:7px;vertical-align:-1px}
.ring{display:inline-block;width:9px;height:9px;border-radius:50%;border:2px solid #f778ba;margin-right:7px;vertical-align:-1px}
#tip{position:fixed;pointer-events:none;background:#161b22;border:1px solid #30363d;padding:9px 11px;border-radius:7px;max-width:340px;display:none;font-size:13px}
#tip b{font-size:14px}#tip .m{color:#8b949e}
svg{width:100vw;height:100vh;display:block}text{fill:#e6edf3;pointer-events:none;paint-order:stroke;stroke:#0b0f14;stroke-width:3px}
circle.k,circle.s{cursor:grab}
</style>
<div id=hud><h1>Room Brain · tonight's room</h1><div class=stats>__STATS__</div>
<div class=legend>
<div><i class=dot style="background:#3fb950"></i>we text / call / are in each other's contacts</div>
<div><i class=dot style="background:#bc8cff"></i>Instagram</div>
<div><i class=dot style="background:#58a6ff"></i>LinkedIn</div>
<div><i class=ring></i>changed job or bio since my last snapshot</div>
<div><i class=dot style="background:#6e7681"></i>outer ring: people I have not met who wrote a bio (hover)</div>
<div style="color:#8b949e;margin-top:6px">drag any bubble</div>
</div></div>
<div id=tip></div><svg viewBox="-560 -560 1120 1120" preserveAspectRatio="xMidYMid meet"></svg>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
const D=__DATA__, R1=300, R2=470;
const col={whatsapp:'#3fb950',imessage:'#3fb950',calls:'#3fb950',contacts:'#3fb950',gmail:'#d29922',instagram:'#bc8cff',linkedin:'#58a6ff',luma:'#6e7681'};
const cap=s=>(s||'').replace(/\\b\\w/g,c=>c.toUpperCase());
const svg=d3.select('svg'), tip=document.getElementById('tip');
const show=(e,html)=>{tip.style.display='block';tip.style.left=Math.min(e.clientX+14,innerWidth-360)+'px';tip.style.top=(e.clientY+14)+'px';tip.innerHTML=html};
const hide=()=>tip.style.display='none';
svg.append('circle').attr('r',R1).attr('fill','none').attr('stroke','#21262d');
svg.append('circle').attr('r',R2).attr('fill','none').attr('stroke','#21262d').attr('stroke-dasharray','3 6');
const nk=D.known.length, ns=D.strangers.length;
const nodes=[{id:'me',kind:'me',r:26,fx:0,fy:0,label:'me'}];
D.known.forEach((k,i)=>{const a=(i/Math.max(nk,1))*2*Math.PI-Math.PI/2;nodes.push({...k,id:'k'+k.id,kind:'k',r:7+2.6*Math.log1p(k.msgs),x:R1*Math.cos(a),y:R1*Math.sin(a),i})});
D.strangers.forEach((s,i)=>{const a=(i/Math.max(ns,1))*2*Math.PI-Math.PI/2;nodes.push({...s,id:'s'+i,kind:'s',r:4.5,x:R2*Math.cos(a),y:R2*Math.sin(a)})});
const links=nodes.filter(n=>n.kind==='k').map(n=>({source:'me',target:n.id,via:n.via,msgs:n.msgs}));
const g=svg.append('g');
const line=g.selectAll('line').data(links).join('line').attr('stroke',d=>col[d.via]||'#6e7681').attr('stroke-opacity',0.7).attr('stroke-width',d=>1+Math.log1p(d.msgs)/1.6);
const dot=g.selectAll('circle').data(nodes.filter(n=>n.kind!=='me')).join('circle').attr('class',d=>d.kind)
 .attr('r',d=>d.r).attr('fill',d=>d.kind==='s'?'#6e7681':(col[d.via]||'#6e7681'))
 .attr('stroke',d=>d.changed?'#f778ba':'#0b0f14').attr('stroke-width',d=>d.changed?3:1.5)
 .on('mousemove',(e,d)=>show(e,d.kind==='s'?`<b>${cap(d.label)}</b><div class=m>not met yet</div><div><i>${d.bio}</i></div>`
   :`<b>${cap(d.label)}</b>${d.title||d.employer?`<div>${[d.title,d.employer].filter(Boolean).join(' @ ')}</div>`:''}<div class=m>via ${d.how.join(', ')} · ${d.msgs} messages${d.last?` · last ${d.last}`:''}</div>${d.changed?'<div style="color:#f778ba">changed job or bio recently</div>':''}`))
 .on('mouseleave',hide)
 .call(d3.drag().on('start',(e,d)=>{sim.alphaTarget(0.25).restart();d.fx=d.x;d.fy=d.y}).on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y}).on('end',(e,d)=>{sim.alphaTarget(0)}));
const lab=g.selectAll('text').data(nodes.filter(n=>n.kind==='k')).join('text').attr('font-size',13)
 .text(d=>cap(d.label)+(d.employer&&d.employer.length<=16?` · ${d.employer}`:''));
svg.append('circle').attr('r',26).attr('fill','#3fb950').attr('stroke','#0b0f14').attr('stroke-width',2);
svg.append('text').attr('dy','0.35em').attr('text-anchor','middle').attr('font-weight',650).attr('font-size',13).attr('fill','#0b0f14').attr('stroke','none').text('me');
const sim=d3.forceSimulation(nodes)
 .force('radial',d3.forceRadial(d=>d.kind==='k'?R1:d.kind==='s'?R2:0).strength(0.9))
 .force('collide',d3.forceCollide(d=>d.kind==='k'?d.r+36:d.r+3).iterations(2))
 .force('charge',d3.forceManyBody().strength(d=>d.kind==='k'?-30:-4))
 .force('link',d3.forceLink(links).id(d=>d.id).strength(0))
 .alpha(0.6).alphaDecay(0.03);
sim.on('tick',()=>{
 line.attr('x1',0).attr('y1',0).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
 dot.attr('cx',d=>d.x).attr('cy',d=>d.y);
 lab.each(function(d){const side=Math.abs(d.x)>0.6*R1; const t=d3.select(this);
   if(side){t.attr('text-anchor',d.x>0?'start':'end').attr('x',d.x+(d.x>0?1:-1)*(d.r+7)).attr('y',d.y).attr('dy','0.35em')}
   else{const up=d.y<0, stagger=(d.i%3)*15; t.attr('text-anchor','middle').attr('x',d.x).attr('y',d.y+(up?-(d.r+9+stagger):(d.r+9+stagger))).attr('dy',up?'0':'0.9em')}});
});
</script>"""


if __name__ == "__main__":
    anon = "--anon" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ev = args[0] if args else os.environ.get("ROOM_BRAIN_EVENT", "evt-sBdX3tSZl05miG7")
    g = build(ev, anon=anon)
    st = g["stats"]
    stats = (f"{st['registered'] or '?'} registered · {st['known']} I already know · "
             f"{st['strangers']} strangers with bios · {st['changed']} changed job or bio recently"
             + (" · names hidden for sharing" if anon else ""))
    out = ROOT / "data" / ("graph_anon.html" if anon else "graph.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(HTML.replace("__STATS__", stats).replace("__DATA__", json.dumps(g, default=str)))
    print(out)
