"""SHA-256 hashing — chunked, resumable."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from .config import Config
from .db import Inventory

log = logging.getLogger(__name__)

CHUNK = 1024 * 1024  # 1 MB


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def hash_all(cfg: Config, inv: Inventory) -> dict:
    inv.log_phase("hash", "started")
    rows = inv.files_needing_hash()
    total = len(rows)
    done = 0
    errors = 0
    for row in rows:
        try:
            sha = hash_file(row["path"])
            inv.set_hash(row["id"], sha)
            done += 1
            if done % 100 == 0:
                log.info("hashed %d/%d", done, total)
        except (OSError, PermissionError) as e:
            errors += 1
            inv.mark_error(row["id"], f"hash: {e}")
    stats = {"hashed": done, "errors": errors, "total": total}
    inv.log_phase("hash", "done", str(stats))
    log.info("Hash complete: %s", stats)
    return stats
