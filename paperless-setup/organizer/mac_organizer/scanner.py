"""Filesystem walker — explore Mac + VM shared folders + external volumes."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator

from .config import (
    Config, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS, DOCUMENT_EXTENSIONS,
)
from .db import Inventory

log = logging.getLogger(__name__)


def classify_kind(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in PHOTO_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    return "other"


def _is_excluded(path: Path, exclude_patterns: list[str]) -> bool:
    parts = set(path.parts)
    for pat in exclude_patterns:
        if "/" in pat:
            if pat in str(path):
                return True
        elif pat in parts:
            return True
    return False


def walk(cfg: Config) -> Iterator[Path]:
    """Yield candidate file paths under configured scan roots."""
    for root_s in cfg.scan_roots:
        root = Path(root_s).expanduser()
        if not root.exists():
            log.warning("Scan root missing: %s", root)
            continue
        log.info("Scanning %s", root)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=cfg.follow_symlinks):
            dp = Path(dirpath)
            # Prune excluded dirs in-place
            dirnames[:] = [
                d for d in dirnames
                if not _is_excluded(dp / d, cfg.exclude_dirs)
            ]
            for fn in filenames:
                if fn.startswith("."):
                    continue  # hidden files
                p = dp / fn
                try:
                    if p.is_symlink() and not cfg.follow_symlinks:
                        continue
                except OSError:
                    continue
                yield p


def scan(cfg: Config, inv: Inventory) -> dict:
    """Walk the filesystem and populate the inventory. Returns stats."""
    inv.log_phase("scan", "started")
    seen = 0
    kept = 0
    skipped_ext = 0
    skipped_size = 0
    errors = 0
    max_bytes = cfg.max_file_size_mb * 1024 * 1024

    for p in walk(cfg):
        seen += 1
        try:
            ext = p.suffix.lower().lstrip(".")
            if ext not in cfg.include_extensions:
                skipped_ext += 1
                continue
            st = p.stat()
            if st.st_size > max_bytes:
                skipped_size += 1
                continue
            if st.st_size == 0:
                continue
            kind = classify_kind(ext)
            inv.upsert_file(
                path=str(p.resolve()),
                size=st.st_size,
                mtime=st.st_mtime,
                ext=ext,
                kind=kind,
            )
            kept += 1
            if kept % 500 == 0:
                log.info("scanned=%d kept=%d", seen, kept)
        except (OSError, PermissionError) as e:
            errors += 1
            log.debug("scan error on %s: %s", p, e)

    stats = {"seen": seen, "kept": kept,
             "skipped_ext": skipped_ext, "skipped_size": skipped_size,
             "errors": errors}
    inv.log_phase("scan", "done", str(stats))
    log.info("Scan complete: %s", stats)
    return stats
