"""Cognee-backed memory for the Strands agent.

Three backends, picked at start-up so a missing key never kills the demo:
  cloud  Cognee Cloud REST (COGNEE_API_KEY, COGNEE_API_URL, COGNEE_TENANT_ID)
  local  the cognee Python SDK on this machine (needs LLM_API_KEY to build the graph)
  plain  keyword search over the fact lines we ingested (no LLM, no network)
The store implements Strands' MemoryStore protocol, so the agent gets
memory_search / memory_add tools and automatic recall injection.
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from strands.memory import MemoryEntry

DATASET = os.environ.get("COGNEE_DATASET", "room_brain")
ROOT = Path(__file__).resolve().parent.parent
PLAIN = ROOT / "data" / "memory_lines.jsonl"


READY = ROOT / "data" / ".cognee_ready"


def backend():
    """ROOM_BRAIN_MEMORY=cloud|local|plain forces a backend; otherwise auto.

    Auto prefers Cognee Cloud when its key is present, then the local cognee
    graph only after one ingest has completed (the READY marker), so a demo
    never waits on a graph that is still being built.
    """
    forced = os.environ.get("ROOM_BRAIN_MEMORY")
    if forced in ("cloud", "local", "plain"):
        return forced
    if os.environ.get("COGNEE_API_KEY") and os.environ.get("COGNEE_API_URL"):
        return "cloud"
    if os.environ.get("LLM_API_KEY") and READY.exists():
        return "local"
    return "plain"


def _text(x):
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        for k in ("text", "content", "search_result", "answer"):
            if x.get(k):
                return _text(x[k])
        return json.dumps(x)[:500]
    if isinstance(x, list):
        return "\n".join(_text(i) for i in x)
    for k in ("text", "content"):
        if getattr(x, k, None):
            return str(getattr(x, k))
    return str(x)[:500]


class Cloud:
    def __init__(self):
        import requests
        self.s = requests.Session()
        self.base = os.environ["COGNEE_API_URL"].rstrip("/")
        self.s.headers.update({"X-Api-Key": os.environ["COGNEE_API_KEY"],
                               "X-Tenant-Id": os.environ.get("COGNEE_TENANT_ID", "")})

    def _add(self, lines):
        r = self.s.post(f"{self.base}/api/v1/add_text", json={"textData": lines, "datasetName": DATASET}, timeout=120)
        r.raise_for_status()
        r = self.s.post(f"{self.base}/api/v1/cognify", json={"datasets": [DATASET], "runInBackground": False}, timeout=900)
        r.raise_for_status()
        return {"added": len(lines), "cognify": r.json() if r.content else {}}

    def _search(self, query, k):
        r = self.s.post(f"{self.base}/api/v1/search", json={"query": query, "searchType": "CHUNKS",
                                                           "datasets": [DATASET], "topK": k}, timeout=60)
        r.raise_for_status()
        return [_text(x) for x in (r.json() or [])][:k]

    async def add(self, lines):
        return await asyncio.to_thread(self._add, lines)

    async def search(self, query, k):
        return await asyncio.to_thread(self._search, query, k)


class Local:
    async def add(self, lines):
        import cognee
        res = await cognee.remember(lines, dataset_name=DATASET, self_improvement=False)
        return {"added": len(lines), "result": str(res)[:200]}

    async def search(self, query, k):
        import cognee
        res = await cognee.recall(query, datasets=[DATASET], top_k=k)
        return [_text(r) for r in res][:k]


class Plain:
    def _lines(self):
        return [json.loads(l)["t"] for l in PLAIN.read_text().splitlines()] if PLAIN.exists() else []

    async def add(self, lines):
        PLAIN.parent.mkdir(parents=True, exist_ok=True)
        with PLAIN.open("a") as f:
            for t in lines:
                f.write(json.dumps({"t": t}) + "\n")
        return {"added": len(lines), "total": len(self._lines())}

    async def search(self, query, k):
        toks = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        scored = [(sum(t in l.lower() for t in toks), l) for l in self._lines()]
        return [l for s, l in sorted(scored, key=lambda x: -x[0]) if s > 0][:k]


class RoomBrainMemory:
    """Strands MemoryStore over Cognee: what William already knows about people."""
    name = "room_brain"
    description = ("What William already knows about people: how he knows them, shared "
                   "events, employers, and recent job or bio changes.")
    max_search_results = 8
    writable = True
    extraction = False

    def __init__(self):
        self.kind = backend()
        self.impl = {"cloud": Cloud, "local": Local, "plain": Plain}[self.kind]()

    async def search(self, query, options=None):
        k = None
        if options is not None:
            k = options.get("max_results") if isinstance(options, dict) else getattr(options, "max_results", None)
        try:
            hits = await self.impl.search(query, k or self.max_search_results)
        except Exception as exc:
            hits = [f"memory backend error ({self.kind}): {type(exc).__name__}: {str(exc)[:120]}"]
        return [MemoryEntry(content=h, metadata={"backend": self.kind}) for h in hits]

    async def add(self, content, metadata=None):
        return await self.impl.add([content])


def event_lines(event_api_id):
    from brain import crm_tools as ct
    lines = []
    for p in ct.who_do_i_know_at(event_api_id):
        how = ", ".join(p.get("how_we_know") or []) or "no other source"
        lines.append(f"{p['name']} is attending event {event_api_id}. William knows them via {how}; "
                     f"{p.get('n_messages', 0)} messages, last contact {p.get('last_contact_at') or 'unknown'}. "
                     f"Employer: {p.get('employer') or 'unknown'}. Title: {p.get('title') or 'unknown'}. "
                     f"Bio: {p.get('bio_short') or ''}".strip())
    for s in ct.strangers_at(event_api_id, limit=200):
        if s.get("bio_short"):
            lines.append(f"{s['name']} is attending event {event_api_id}; William has not met them. Bio: {s['bio_short']}")
    return lines


def update_lines(limit=80):
    from brain.updates import life_updates
    return [f"{u['name']} changed {u['kind']}: '{u['before'][:120]}' -> '{u['after'][:120]}' "
            f"(between {u['observed'][0]} and {u['observed'][1]}). William knows them via "
            f"{', '.join(u['how_we_know']) or 'one source'}; {u['n_messages']} messages."
            for u in life_updates(limit=limit)]


async def _main(argv):
    store = RoomBrainMemory()
    print("backend:", store.kind, file=sys.stderr)
    if argv[:1] == ["ingest"]:
        event = argv[1] if len(argv) > 1 else os.environ.get("ROOM_BRAIN_EVENT", "evt-sBdX3tSZl05miG7")
        lines = event_lines(event) + update_lines()
        print("lines:", len(lines), file=sys.stderr)
        print(json.dumps(await store.impl.add(lines), default=str)[:400])
        if store.kind == "local":
            READY.write_text("ok\n")
    elif argv[:1] == ["search"]:
        for e in await store.search(" ".join(argv[1:])):
            print("-", e.content[:200])
    else:
        print("usage: python -m brain.memory ingest [event_api_id] | search <query>")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
