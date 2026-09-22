"""Fetch a public web page as plain text, for enriching a CRM contact.

enrich_url() goes through Bright Data's Web Unlocker when BRIGHTDATA_API_KEY is
set (POST https://api.brightdata.com/request, format=raw) and otherwise does a
plain GET. It never raises; errors come back as status='error'.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request

BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
TIMEOUT = 20

_BLOCK_RE = re.compile(
    r"<(script|style|noscript|svg|template)\b[^>]*>.*?</\1\s*>", re.I | re.S
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")


def _attrs(tag: str) -> dict:
    out = {}
    for m in _ATTR_RE.finditer(tag):
        out[m.group(1).lower()] = m.group(2) or m.group(3) or m.group(4) or ""
    return out


def _og_description(raw: str) -> str:
    for tag in _META_RE.findall(raw):
        a = _attrs(tag)
        key = a.get("property") or a.get("name") or ""
        if key.lower() in ("og:description", "description") and a.get("content"):
            return a["content"]
    return ""


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s).replace("\ufeff", "")).strip()


def html_to_text(raw: str, max_chars: int = 2500) -> str:
    """Title and og:description first, then the visible body text, capped."""
    title_m = _TITLE_RE.search(raw)
    title = _clean(_TAG_RE.sub("", title_m.group(1))) if title_m else ""
    desc = _clean(_og_description(raw))
    body = _BLOCK_RE.sub(" ", raw)
    body = _COMMENT_RE.sub(" ", body)
    body = re.sub(r"<(br|/p|/div|/li|/h\d|/tr)\b[^>]*>", "\n", body, flags=re.I)
    body = _clean(_TAG_RE.sub(" ", body))
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if desc:
        parts.append(f"Description: {desc}")
    if body:
        parts.append(body)
    text = "\n".join(parts)
    return text[:max_chars]


def _redact(msg: str, key: str | None) -> str:
    if key:
        msg = msg.replace(key, "<redacted>")
    return msg


def _fetch_direct(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": DESKTOP_UA, "Accept": "text/html,*/*;q=0.8",
                 "Accept-Language": "en-US,en;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def _fetch_brightdata(url: str, key: str) -> str:
    payload = json.dumps({
        "zone": os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1"),
        "url": url,
        "format": "raw",
    }).encode()
    req = urllib.request.Request(
        BRIGHTDATA_ENDPOINT,
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def enrich_url(url: str, max_chars: int = 2500) -> dict:
    """Return {url, status, text, via}. Never raises."""
    key = os.environ.get("BRIGHTDATA_API_KEY") or None
    via = "brightdata" if key else "direct"
    if not url or not re.match(r"^https?://", url, re.I):
        return {"url": url, "status": "error", "via": via,
                "text": "invalid url (must start with http:// or https://)"}
    try:
        raw = _fetch_brightdata(url, key) if key else _fetch_direct(url)
        text = html_to_text(raw, max_chars)
        if not text:
            return {"url": url, "status": "error", "via": via,
                    "text": "page returned no readable text"}
        return {"url": url, "status": "ok", "via": via, "text": text}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(300).decode("utf-8", "replace")
        except Exception:
            pass
        msg = f"HTTP {e.code} {e.reason}" + (f": {_clean(body)}" if body else "")
        return {"url": url, "status": "error", "via": via, "text": _redact(msg, key)}
    except Exception as e:  # network, timeout, decode, anything
        msg = f"{type(e).__name__}: {e}"
        return {"url": url, "status": "error", "via": via, "text": _redact(msg, key)}


def public_profile_summary(name: str, links, max_chars: int = 2500) -> dict:
    """Fetch the first non-Instagram link and return {name, source_url, summary_text}."""
    if isinstance(links, str):
        links = [links]
    candidates = [
        str(l).strip() for l in (links or [])
        if l and "instagram.com" not in str(l).lower()
    ]
    if not candidates:
        return {"name": name, "source_url": None,
                "summary_text": "no fetchable public link (Instagram blocks anonymous fetches)"}
    url = candidates[0]
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    res = enrich_url(url, max_chars=max_chars)
    if res["status"] != "ok":
        return {"name": name, "source_url": url,
                "summary_text": f"fetch failed ({res['via']}): {res['text']}"}
    return {"name": name, "source_url": url, "summary_text": res["text"]}


if __name__ == "__main__":
    import sys
    for u in sys.argv[1:] or ["https://example.com"]:
        r = enrich_url(u)
        print(r["via"], r["status"], u)
        print(r["text"][:200])
