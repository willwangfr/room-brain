"""Life updates: what changed for people William knows, from evidence already in the CRM.

Two change sources, both diffs between snapshots he already collected himself:
LinkedIn Company/Position per connection across Connections.csv exports, and
Instagram bio text per handle across profile scrapes. Nothing here fetches
anything; it compares stored source_record rows, so it is exact and offline.
"""
import json
import sqlite3
from collections import defaultdict

from crm.db import connect
from crm.links import person_links

SOURCES = {"job": ("linkedin", "connection"), "bio": ("instagram", "profile_bio")}


def _canon(conn, pid):
    seen = set()
    while pid is not None and pid not in seen:
        seen.add(pid)
        row = conn.execute("select merged_into_id from person where id=?", (pid,)).fetchone()
        if row is None or row["merged_into_id"] is None:
            return pid
        pid = row["merged_into_id"]
    return pid


def _profile(conn, pid):
    cur = conn.execute("select * from person_current where person_id=?", (pid,)).fetchone()
    st = conn.execute("select * from person_stats where person_id=?", (pid,)).fetchone()
    n = sum((st[k] or 0) for k in ("n_imessage", "n_ig_dm", "n_linkedin_msg", "n_whatsapp")) if st else 0
    sources = json.loads(st["sources"]) if st and st["sources"] else []
    return {"person_id": pid, "name": cur["display_name"] if cur else None,
            "employer": cur["employer"] if cur else None, "title": cur["title"] if cur else None,
            "links": person_links(cur) if cur else [], "n_messages": n,
            "last_contact_at": st["last_contact_at"] if st else None, "how_we_know": sources}


def _snapshots(conn, kind):
    """{(person_key, external_id): {run_started_at: (label, name)}} for one change kind."""
    source, record_kind = SOURCES[kind]
    runs = {r["id"]: r["started_at"] for r in conn.execute("select id, started_at from import_run")}
    rows = conn.execute(
        """select sr.id sr_id, sr.import_run_id run, sr.external_id ext, sr.raw_json j, pi.person_id pid
           from source_record sr
           left join identity_assertion ia on ia.source_record_id = sr.id
           left join identity i on i.id = ia.identity_id and i.kind != 'display_name'
           left join person_identity pi on pi.identity_id = i.id
           where sr.source = ? and sr.record_kind = ?""", (source, record_kind))
    by = defaultdict(dict)
    for r in rows:
        j = json.loads(r["j"])
        if kind == "job":
            label = " @ ".join(x for x in ((j.get("Position") or "").strip(), (j.get("Company") or "").strip()) if x)
            name = (j.get("First Name", "") + " " + j.get("Last Name", "")).strip()
        else:
            label = (j.get("bio") or "").strip()
            name = j.get("full_name") or j.get("username") or r["ext"]
        key = _canon(conn, r["pid"]) if r["pid"] is not None else f"ext:{r['ext']}"
        # One timeline per account, not per person: someone with two accounts
        # must not read as a "change" just because the two bios differ.
        by[(key, r["ext"])][runs.get(r["run"], "")] = (label, name)
    return by


def life_updates(kind="all", known_only=True, limit=25):
    """Job/title and Instagram-bio changes, people William actually talks to first.

    Args:
        kind: "all", "job" (LinkedIn Company/Position) or "bio" (Instagram bio text).
        known_only: keep only people with message history or two or more sources.
        limit: maximum rows returned.
    Returns:
        List of {person_id, name, kind, before, after, observed: [first, last],
        employer, title, links, n_messages, last_contact_at, how_we_know}.
    """
    kinds = ["job", "bio"] if kind == "all" else [kind]
    conn = connect()
    conn.row_factory = sqlite3.Row
    try:
        out = []
        for k in kinds:
            for (key, ext), snaps in _snapshots(conn, k).items():
                if len(snaps) < 2:
                    continue
                ordered = sorted(snaps.items())
                (t0, (before, name0)), (t1, (after, name1)) = ordered[0], ordered[-1]
                if before == after or not after:
                    continue
                prof = _profile(conn, key) if isinstance(key, int) else {
                    "person_id": None, "name": name1 or name0, "employer": None, "title": None,
                    "links": [], "n_messages": 0, "last_contact_at": None, "how_we_know": []}
                if known_only and not (prof["n_messages"] > 0 or len(prof["how_we_know"]) >= 2):
                    continue
                prof.update({"name": prof["name"] or name1 or name0, "kind": k, "before": before,
                             "after": after, "observed": [t0[:10], t1[:10]]})
                out.append(prof)
        out.sort(key=lambda p: (-p["n_messages"], -len(p["how_we_know"]), p["name"] or ""))
        return out[:limit]
    finally:
        conn.close()


def changes_for(person_id):
    """Every recorded change for one person, both kinds."""
    return [u for u in life_updates(kind="all", known_only=False, limit=100000)
            if u["person_id"] == person_id]


def self_person_ids():
    """Canonical person ids that are William himself, via self_identity plus his display name."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("select pi.person_id from self_identity si "
                            "join person_identity pi on pi.identity_id = si.identity_id").fetchall()
        ids = {_canon(conn, r["person_id"]) for r in rows}
        rows = conn.execute("select person_id from person_current where display_name = 'william wang'").fetchall()
        return ids | {r["person_id"] for r in rows}
    finally:
        conn.close()


if __name__ == "__main__":
    for u in life_updates(limit=10):
        print(u["name"], "|", u["kind"], "|", u["before"][:40], "->", u["after"][:40], "|", u["n_messages"], u["how_we_know"])
