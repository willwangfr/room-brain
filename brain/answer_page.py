"""Render a saved agent answer as a chat-style page for screenshots.

    ./run.sh -m brain.answer_page data/demo1.txt "question" [--anon]
      -> data/agent.html, or data/agent_anon.html with names, links and
         employers of tonight's guests replaced so the page can be shared.
"""
import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOISE = re.compile(r"cognee\.shared|Log file created|Cognee 1\.0 changes|Database storage|auth posture|^EXIT=")


def linkify(text):
    text = html.escape(text)
    return re.sub(r"(https?://[^\s)]+)", r'<a href="\1">\1</a>', text)


def anonymize(text):
    """Replace names, links and employers of people on tonight's guest list."""
    from brain import crm_tools as ct
    event = os.environ.get("ROOM_BRAIN_EVENT", "evt-sBdX3tSZl05miG7")
    people = ct.who_do_i_know_at(event) + ct.strangers_at(event, limit=400)
    text = re.sub(r"https?://[^\s)]+", "", text)
    text = re.sub(r"\b[\w-]+\.(com|io|ai|xyz|space|me|co)\b", "[site]", text)
    n = 0
    for p in people:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        if len(name) < 4:  # a two-letter display name would mangle ordinary words
            continue
        if re.search(rf"\b{re.escape(name)}\b", text, flags=re.I):
            n += 1
            label = f"Person {n}"
            text = re.sub(rf"\b{re.escape(name)}\b", label, text, flags=re.I)
            first = name.split()[0]
            if len(first) >= 4:
                text = re.sub(rf"\b{re.escape(first)}\b", label, text, flags=re.I)
        emp = (p.get("employer") or "").strip()
        if len(emp) >= 3:
            text = re.sub(re.escape(emp), "[employer]", text, flags=re.I)
            head = emp.split()[0].strip(",.")
            if len(head) >= 5:  # "Ideaflow Inc." is written as "Ideaflow" in prose
                text = re.sub(rf"\b{re.escape(head)}\b", "[employer]", text, flags=re.I)
    return re.sub(r"\(\s*\)", "", text)


def render(answer_path, question, anon=False):
    raw = Path(answer_path).read_text()
    # Some model runs put every bullet on one line ("... . - next name (") ; break those apart.
    raw = re.sub(r"\.\s+-\s+(?=[A-Za-z][\w' .-]{1,40}\s\()", ".\n\n- ", raw)
    if anon:
        raw = anonymize(raw)
    lines = [l.rstrip() for l in raw.splitlines() if not NOISE.search(l)]
    blocks, cur = [], []
    for l in lines:
        t = l.strip()
        if t.startswith(("- ", "• ")):  # a bullet is always its own block
            if cur:
                blocks.append(" ".join(cur))
            cur = [t]
        elif t:
            cur.append(t)
        elif cur:
            blocks.append(" ".join(cur))
            cur = []
    if cur:
        blocks.append(" ".join(cur))
    items = []
    for b in blocks:
        cls = "li" if b.startswith(("- ", "• ")) else "p"
        items.append(f'<div class="{cls}">{linkify(b.lstrip("-• "))}</div>')
    note = " · names and links hidden for sharing" if anon else ""
    return f"""<!doctype html><meta charset=utf-8><title>Room Brain · agent</title>
<style>body{{margin:0;background:#0b0f14;color:#e6edf3;font:15px/1.5 -apple-system,Helvetica,Arial;padding:30px 40px}}
.hdr{{color:#8b949e;font-size:13px;margin-bottom:18px}}.hdr b{{color:#e6edf3;font-size:18px;display:block;margin-bottom:2px}}
.q{{background:#1f6feb22;border:1px solid #1f6feb66;border-radius:14px 14px 4px 14px;padding:12px 16px;margin:0 0 16px 25%}}
.a{{background:#161b22;border:1px solid #30363d;border-radius:14px 14px 14px 4px;padding:14px 18px;margin-right:12%}}
.li{{padding:5px 0 5px 14px;border-left:2px solid #30363d;margin:6px 0}}.p{{margin:8px 0}}
a{{color:#58a6ff;text-decoration:none}}.tools{{color:#8b949e;font-size:12px;margin-top:12px}}</style>
<div class=hdr><b>Room Brain</b>Strands Agent · 8 tools over my CRM · memory: Cognee store · model via Strands OpenAIModel{note}</div>
<div class=q>{html.escape(question)}</div>
<div class=a>{''.join(items)}<div class=tools>tools called: who_do_i_know_at · strangers_at · memory_search &nbsp;·&nbsp; nothing was sent</div></div>"""


if __name__ == "__main__":
    anon = "--anon" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0] if args else str(ROOT / "data" / "demo1.txt")
    q = args[1] if len(args) > 1 else "Who do I know at tonight's hackathon, and who should I go meet?"
    out = ROOT / "data" / ("agent_anon.html" if anon else "agent.html")
    out.write_text(render(src, q, anon))
    print(out)
