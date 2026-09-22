"""HTML report of life updates with word-level diff highlighting.

    ./run.sh -m brain.report [all|bio|job] [limit] [--anon]
      -> data/updates.html, or data/updates_anon.html with names, links and
         handles replaced so the page can be shown publicly.
"""
import difflib
import html
import re
import sys
from pathlib import Path

from brain.updates import life_updates

ROOT = Path(__file__).resolve().parent.parent


def diff_html(a, b):
    aw, bw = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, aw, bw)
    out_a, out_b = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        sa, sb = html.escape(" ".join(aw[i1:i2])), html.escape(" ".join(bw[j1:j2]))
        if op == "equal":
            out_a.append(sa)
            out_b.append(sb)
        else:
            if sa:
                out_a.append(f"<del>{sa}</del>")
            if sb:
                out_b.append(f"<ins>{sb}</ins>")
    return " ".join(out_a), " ".join(out_b)


def anonymize(text, name):
    """Strip URLs, @handles and the person's own name parts from free text."""
    t = re.sub(r"https?://\S+|\b[\w.-]+\.(com|io|ai|xyz|me|co)\b\S*", "link", text or "")
    t = re.sub(r"@\w+", "@user", t)
    for part in (name or "").split():
        if len(part) >= 4:
            t = re.sub(re.escape(part), "…", t, flags=re.I)
    return t


CSS = """body{margin:0;background:#0b0f14;color:#e6edf3;font:14px/1.45 -apple-system,Helvetica,Arial;padding:28px}
h1{font-size:22px;margin:0 0 4px}p.sub{color:#8b949e;margin:0 0 18px}
table{border-collapse:collapse;width:100%}th{text-align:left;color:#8b949e;font-weight:500;padding:8px 10px;border-bottom:1px solid #30363d}
td{padding:10px;border-bottom:1px solid #21262d;vertical-align:top}td.k{color:#8b949e;white-space:nowrap}
del{background:#5c1a1a;color:#ffb4b4;text-decoration:none;border-radius:3px;padding:0 3px}
ins{background:#123d1f;color:#9fe0af;text-decoration:none;border-radius:3px;padding:0 3px}
small{color:#8b949e}.pill{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:1px 8px;margin-right:6px;font-size:12px}"""


def render(kind="all", limit=40, anon=False):
    rows = life_updates(kind=kind, limit=limit)
    everything = life_updates(kind="all", known_only=True, limit=100000)
    n_bio = sum(u["kind"] == "bio" for u in everything)
    n_job = sum(u["kind"] == "job" for u in everything)
    body = []
    for i, u in enumerate(rows):
        name = f"Person {i + 1}" if anon else (u["name"] or "?")
        before = anonymize(u["before"], u["name"]) if anon else (u["before"] or "")
        after = anonymize(u["after"], u["name"]) if anon else (u["after"] or "")
        a, b = diff_html(before, after)
        links = "" if anon else " ".join(
            f'<a href="{html.escape(l)}" style="color:#58a6ff">{html.escape(l.split("//")[-1][:34])}</a>'
            for l in (u["links"] or [])[:2])
        body.append(
            f"<tr><td><b>{html.escape(name)}</b><br><small>{html.escape(', '.join(u['how_we_know']))} · "
            f"{u['n_messages']} msgs</small><br><small>{links}</small></td><td class=k>{u['kind']}</td>"
            f"<td>{a}</td><td>{b}</td><td class=k><small>{u['observed'][0]}<br>to {u['observed'][1]}</small></td></tr>")
    note = " · names, handles and links replaced for sharing" if anon else ""
    return f"""<!doctype html><meta charset=utf-8><title>Room Brain · life updates</title><style>{CSS}</style>
<h1>Life updates · what changed for people I actually know</h1>
<p class=sub><span class=pill>{n_bio} Instagram bio changes</span><span class=pill>{n_job} LinkedIn job or title changes</span>
diffed across snapshots I already hold, no scraping at demo time, ranked by how much we actually talk{note}</p>
<table><tr><th>Who</th><th>Kind</th><th>Before</th><th>After</th><th>Seen</th></tr>{''.join(body)}</table>"""


if __name__ == "__main__":
    anon = "--anon" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kind = args[0] if args else "all"
    limit = int(args[1]) if len(args) > 1 else 40
    out = ROOT / "data" / ("updates_anon.html" if anon else "updates.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(render(kind, limit, anon))
    print(out)
