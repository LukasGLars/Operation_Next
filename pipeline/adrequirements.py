# -*- coding: utf-8 -*-
"""What an ad actually asks for, kept next to the joblist.

The joblist is a markdown table, so a multi-line requirements list cannot live
in a cell. It goes in a JSON sidecar keyed by canonical URL instead, and the app
renders it as a tooltip on the role.

The point is triage speed. Of 41 open rows only 2 had been applied to, and the
cost of finding out a role is wrong was opening the ad. One requirement line —
"stort intresse för tekniska lösningar inom ljud, bild och nätverk" — is often
all it takes to reject, and reading it should not cost a page load.

The bullets come back from the judge call that already reads the whole ad to
score it, so they cost output tokens and nothing else.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT  = Path(__file__).parent.parent
STORE = ROOT / "jobsearch" / "requirements.json"

MAX_BULLETS = 6
MAX_BULLET_CHARS = 160


def load() -> dict:
    """url -> [requirement, ...]. Missing or corrupt reads as empty: a tooltip
    is a convenience, and losing it must never break the joblist."""
    if not STORE.exists():
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f"requirements store unreadable: {e}")
        return {}


def clean(bullets) -> list:
    """Trim to something a tooltip can show. Anything that is not a list of
    strings is dropped rather than guessed at."""
    if not isinstance(bullets, list):
        return []
    out = []
    for b in bullets:
        if not isinstance(b, str):
            continue
        text = " ".join(b.split()).lstrip("-•* ").strip()
        if text:
            out.append(text[:MAX_BULLET_CHARS])
    return out[:MAX_BULLETS]


def save(entries: dict) -> int:
    """Merge `entries` into the store. Existing URLs are overwritten only when
    the new value is non-empty, so a run that failed to extract anything cannot
    wipe what an earlier run captured."""
    if not entries:
        return 0
    store = load()
    written = 0
    for url, bullets in entries.items():
        bullets = clean(bullets)
        if not bullets:
            continue
        store[url] = bullets
        written += 1
    if written:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True),
                         encoding="utf-8")
    return written


def prune(keep_urls) -> int:
    """Drop entries whose row is gone, so the sidecar cannot outgrow the list."""
    store = load()
    keep = set(keep_urls)
    trimmed = {u: b for u, b in store.items() if u in keep}
    if len(trimmed) == len(store):
        return 0
    STORE.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2, sort_keys=True),
                     encoding="utf-8")
    return len(store) - len(trimmed)
