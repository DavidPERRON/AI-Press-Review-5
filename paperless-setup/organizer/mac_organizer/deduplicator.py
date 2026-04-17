"""
Deduplication logic.

Groups files by sha256. In each group:
- Pick ONE canonical file (best location + oldest mtime).
- Mark all others as 'duplicate' (they will move to _Doublons/).
"""
from __future__ import annotations

import logging

from .db import Inventory

log = logging.getLogger(__name__)

# Lower score = higher priority to keep as canonical.
# Files already in organized locations beat files in Downloads/Desktop/Trash.
LOCATION_PENALTIES = [
    ("/.Trash", 1000),
    ("/Trash", 1000),
    ("/Downloads", 500),
    ("/Desktop", 400),
    ("/A_Trier", 300),
    ("/_A_TRIER", 300),
    ("/tmp", 800),
    ("/Caches", 900),
]


def location_score(path: str) -> int:
    score = 0
    for frag, penalty in LOCATION_PENALTIES:
        if frag in path:
            score += penalty
    # Prefer shorter paths (closer to user-organized roots)
    score += len(path.split("/"))
    return score


def pick_canonical(files: list) -> int:
    """Return id of canonical file. `files` is list of sqlite3.Row."""
    def sort_key(row):
        return (location_score(row["path"]), row["mtime"] or 0, row["id"])
    sorted_files = sorted(files, key=sort_key)
    return sorted_files[0]["id"]


def deduplicate(inv: Inventory) -> dict:
    """For each hash group with >1 member, mark duplicates."""
    inv.log_phase("dedupe", "started")
    groups = inv.duplicate_groups()
    dupes_marked = 0
    with inv.connect() as c:
        for g in groups:
            ids = [int(i) for i in g["ids"].split(",")]
            rows = c.execute(
                f"SELECT id, path, mtime FROM files WHERE id IN ({','.join('?'*len(ids))})",
                ids,
            ).fetchall()
            canonical_id = pick_canonical(rows)
            for r in rows:
                if r["id"] != canonical_id:
                    c.execute("UPDATE files SET status='duplicate' WHERE id=?", (r["id"],))
                    dupes_marked += 1
        c.commit()
    stats = {"duplicate_groups": len(groups), "duplicates_marked": dupes_marked}
    inv.log_phase("dedupe", "done", str(stats))
    log.info("Dedupe complete: %s", stats)
    return stats


def get_canonical_for_duplicate(inv: Inventory, duplicate_file_id: int) -> int | None:
    """Given a duplicate file_id, return the canonical file_id (same sha256, status != duplicate)."""
    with inv.connect() as c:
        row = c.execute("SELECT sha256 FROM files WHERE id=?", (duplicate_file_id,)).fetchone()
        if not row or not row["sha256"]:
            return None
        r = c.execute(
            "SELECT id FROM files WHERE sha256=? AND status != 'duplicate' LIMIT 1",
            (row["sha256"],),
        ).fetchone()
        return r["id"] if r else None
