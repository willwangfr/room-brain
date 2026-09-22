"""Tool functions over the personal CRM sqlite DB; remember_note() is the only write."""
import json
import datetime as _dt
from typing import Any, Dict, List, Optional

from crm.db import connect
from crm.derive import _canonical_groups
from crm.identity import canonical as _canonical
from crm.links import person_links, profile_url
from crm.normalize import is_placeholder_handle

NOTE_FIELDS = {"how_we_met", "my_type", "their_type", "attractiveness", "height",
               "age", "ethnicity_self_reported", "medical", "dating_history",
               "likes", "dislikes", "goals", "freeform"}
_MSG_COLS = ("n_imessage", "n_ig_dm", "n_linkedin_msg", "n_whatsapp")
_HANDLE_KINDS = (("instagram_handle", "instagram"), ("linkedin_handle", "linkedin_slug"),
                 ("twitter_handle", "twitter"))


def _canon_map(conn) -> Dict[int, int]:
    return {m: keep for keep, members in _canonical_groups(conn).items() for m in members}


def _n_messages(stats) -> int:
    return sum(int(stats[c] or 0) for c in _MSG_COLS) if stats else 0


def _sources(stats) -> List[str]:
    if not stats or not stats["sources"]:
        return []
    try:
        return [s for s in json.loads(stats["sources"]) if s != "luma"]
    except ValueError:
        return []


def _person_summary(conn, pid: int) -> Dict[str, Any]:
    cur = conn.execute("select * from person_current where person_id=?", (pid,)).fetchone()
    stats = conn.execute("select * from person_stats where person_id=?", (pid,)).fetchone()
    return {"person_id": pid,
            "name": cur["display_name"] if cur else None,
            "employer": cur["employer"] if cur else None,
            "title": cur["title"] if cur else None,
            "how_we_know": _sources(stats),
            "n_messages": _n_messages(stats),
            "n_calls": int(stats["n_calls"] or 0) if stats else 0,
            "last_contact_at": stats["last_contact_at"] if stats else None,
            "links": person_links(cur)}


def _guests(conn, event_api_id: str):
    """(guest_dict, {canonical person ids linked by a strong identity}) per guest."""
    canon = _canon_map(conn)
    rows = conn.execute(
        "select sr.id, sr.raw_json from source_record sr join import_run ir"
        " on ir.id = sr.import_run_id where ir.source='luma' and ir.source_path=?"
        " and sr.record_kind='guest'", (event_api_id,)).fetchall()
    if not rows:
        return []
    ids = ",".join(str(int(r["id"])) for r in rows)
    people: Dict[int, set] = {}
    for r in conn.execute(
            "select ia.source_record_id sr, pi.person_id pid from identity_assertion ia"
            " join identity i on i.id = ia.identity_id"
            " join person_identity pi on pi.identity_id = ia.identity_id"
            f" where ia.source_record_id in ({ids}) and i.kind != 'display_name'"):
        people.setdefault(r["sr"], set()).add(canon.get(r["pid"], r["pid"]))
    out, seen = [], set()
    for r in rows:
        raw = json.loads(r["raw_json"])
        key = raw.get("api_id") or r["id"]
        if key in seen:
            continue
        seen.add(key)
        out.append((raw.get("user") or {}, people.get(r["id"], set())))
    return out


def list_events() -> List[Dict[str, Any]]:
    """List every imported Luma event.

    Returns:
        One dict per Luma import_run: event_api_id, imported_at, n_guests.
    """
    conn = connect()
    try:
        return [{"event_api_id": r["event_api_id"], "imported_at": r["imported_at"],
                 "n_guests": r["n_guests"]} for r in conn.execute(
            "select ir.source_path event_api_id, coalesce(ir.finished_at, ir.started_at)"
            " imported_at, (select count(*) from source_record sr where"
            " sr.import_run_id = ir.id and sr.record_kind='guest') n_guests"
            " from import_run ir where ir.source='luma' order by imported_at")]
    finally:
        conn.close()


def who_do_i_know_at(event_api_id: str) -> List[Dict[str, Any]]:
    """Guests at a Luma event that the CRM already knows from somewhere else.

    Args:
        event_api_id: Luma event id (evt-...), from list_events().

    Returns:
        People linked to a guest by a strong (non display_name) identity with a
        non-luma source or message history, sorted by n_messages desc then name:
        person_id, name, employer, title, how_we_know, n_messages, n_calls,
        last_contact_at, links, bio_short.
    """
    conn = connect()
    try:
        out, seen = [], set()
        for user, pids in _guests(conn, event_api_id):
            for pid in pids:
                if pid in seen:
                    continue
                s = _person_summary(conn, pid)
                if s["how_we_know"] or s["n_messages"]:
                    seen.add(pid)
                    s["bio_short"] = user.get("bio_short")
                    out.append(s)
        out.sort(key=lambda d: (-d["n_messages"], (d["name"] or "").lower()))
        return out
    finally:
        conn.close()


def strangers_at(event_api_id: str, limit: int = 60) -> List[Dict[str, Any]]:
    """Guests at a Luma event with no evidence outside the guest list itself.

    Args:
        event_api_id: Luma event id (evt-...).
        limit: Maximum number of guests to return.

    Returns:
        Dicts with name, bio_short, website, links (from the guest's own handles).
    """
    conn = connect()
    try:
        out = []
        for user, pids in _guests(conn, event_api_id):
            stats = [conn.execute("select * from person_stats where person_id=?",
                                  (pid,)).fetchone() for pid in pids]
            if any(_sources(s) or _n_messages(s) for s in stats):
                continue
            links = [profile_url(kind, user.get(k)) for k, kind in _HANDLE_KINDS
                     if user.get(k) and not is_placeholder_handle(user.get(k))]
            out.append({"name": user.get("name"), "bio_short": user.get("bio_short"),
                        "website": user.get("website"), "links": [u for u in links if u]})
            if len(out) >= limit:
                break
        return out
    finally:
        conn.close()


def find_person(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search people by display name, employer, title or any handle.

    Args:
        query: Case-insensitive substring.
        limit: Maximum people to return; most-messaged first.
    Returns:
        Dicts with person_id, name, employer, title, links, n_messages,
        last_contact_at, how_we_know.
    """
    conn = connect()
    try:
        q = f"%{query.lower()}%"
        canon = _canon_map(conn)
        pids = [r["person_id"] for r in conn.execute(
            "select person_id from person_current where lower(display_name) like ?"
            " or lower(employer) like ? or lower(title) like ?", (q, q, q))]
        matched = [r["id"] for r in conn.execute(
            "select id from identity where value_norm like ? and kind != 'display_name'", (q,))]
        for i in range(0, len(matched), 900):
            chunk = matched[i:i + 900]
            pids += [r["person_id"] for r in conn.execute(
                "select distinct person_id from person_identity where identity_id in"
                f" ({','.join('?' * len(chunk))})", chunk)]
        uniq = list(dict.fromkeys(canon.get(p, p) for p in pids))
        out = [_person_summary(conn, p) for p in uniq]
        out.sort(key=lambda d: (-d["n_messages"], (d["name"] or "").lower()))
        return out[:limit]
    finally:
        conn.close()


def dossier(person_id: int) -> Dict[str, Any]:
    """Everything the CRM holds on one person.

    Args:
        person_id: Any person id; merged ids resolve to the canonical person.
    Returns:
        person_id, name, employer, title, links, identities [{kind, value}]
        (no display_name), stats (person_stats row), events (guest-list event
        ids this person appears in), notes (person_note rows).
    """
    conn = connect()
    try:
        pid = _canonical(conn, int(person_id))
        d = {k: v for k, v in _person_summary(conn, pid).items()
             if k in ("person_id", "name", "employer", "title", "links")}
        d["identities"] = [{"kind": r["kind"], "value": r["value_norm"]} for r in conn.execute(
            "select i.kind, i.value_norm from person_identity pi join identity i"
            " on i.id = pi.identity_id where pi.person_id=? and i.kind != 'display_name'"
            " order by i.kind, i.value_norm", (pid,))]
        s = conn.execute("select * from person_stats where person_id=?", (pid,)).fetchone()
        d["stats"] = dict(s) if s else None
        d["events"] = [f"{r['source']}:{r['source_path']}" for r in conn.execute(
            "select distinct ir.source, ir.source_path from person_identity pi"
            " join identity_assertion ia on ia.identity_id = pi.identity_id"
            " join identity i on i.id = ia.identity_id"
            " join source_record sr on sr.id = ia.source_record_id"
            " join import_run ir on ir.id = sr.import_run_id"
            " where pi.person_id=? and sr.record_kind='guest' and i.kind != 'display_name'",
            (pid,))]
        d["notes"] = [dict(r) for r in conn.execute(
            "select field, value, updated_at from person_note where person_id=?", (pid,))]
        return d
    finally:
        conn.close()


def remember_note(person_id: int, field: str, value: str) -> Dict[str, Any]:
    """Save a personal judgment about someone (the only write in this module).

    Args:
        person_id: Person to annotate; merged ids resolve to the canonical one.
        field: One of how_we_met, my_type, their_type, attractiveness, height,
            age, ethnicity_self_reported, medical, dating_history, likes,
            dislikes, goals, freeform.
        value: The note text.

    Returns:
        The saved person_note row as a dict.
    """
    if field not in NOTE_FIELDS:
        raise ValueError(f"field must be one of {sorted(NOTE_FIELDS)}")
    conn = connect()
    try:
        pid = _canonical(conn, int(person_id))
        now = _dt.datetime.now().isoformat(timespec="seconds")
        conn.execute("insert or replace into person_note (person_id, field, value, updated_at)"
                     " values (?,?,?,?)", (pid, field, value, now))
        conn.commit()
        return dict(conn.execute("select * from person_note where person_id=? and field=?",
                                 (pid, field)).fetchone())
    finally:
        conn.close()
