"""
Move planner + executor.

Produces a move plan (dry-run-able), then applies it.

Target tree (max 3 levels):
  <target_root>/<category>/<subcategory>/[<year>|<project>]/<filename>
  <target_root>/12_Photos/<year>/<filename>
  <target_root>/13_Videos/<year>/<filename>
  <target_root>/00_Doublons/<original_category>/<filename>
  <target_root>/99_NonClasse/<filename>
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .config import Config
from .db import Inventory
from .deduplicator import get_canonical_for_duplicate
from .taxonomy import (
    DUPLICATES_CATEGORY, UNCLASSIFIED_CATEGORY, CATEGORIES_BY_SLUG,
)

log = logging.getLogger(__name__)


def safe_unique_path(target: Path) -> Path:
    """If target exists, append _1, _2, ... before extension."""
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def build_target_for_media(target_root: Path, year: str, kind: str, filename: str) -> Path:
    """Photos/videos: <root>/12_Photos/<year>/<filename> (2 levels)."""
    folder = "12_Photos" if kind == "photo" else "13_Videos"
    year = year if year and year.isdigit() else "0000_Inconnu"
    return target_root / folder / year / filename


def build_target_for_document(target_root: Path, classification_row, filename: str) -> Path:
    """Documents: <root>/<category>/<subcategory>[/<year_or_project>]/<filename>."""
    cat = classification_row["category"]
    sub = classification_row["subcategory"]
    year = classification_row["year"]
    proj = classification_row["project_name"]

    if cat == UNCLASSIFIED_CATEGORY:
        return target_root / UNCLASSIFIED_CATEGORY / filename

    base = target_root / cat
    if sub:
        base = base / sub
    # Level 3 optional
    cat_def = CATEGORIES_BY_SLUG.get(cat)
    if cat == "15_Projets" and proj:
        base = base / proj
    elif cat_def and cat_def.use_year and year:
        base = base / year

    return base / filename


def build_target_for_duplicate(target_root: Path, canonical_category: str, filename: str) -> Path:
    """Duplicates: <root>/00_Doublons/<canonical_category>/<filename>."""
    sub = canonical_category or "autre"
    return target_root / DUPLICATES_CATEGORY / sub / filename


def plan_moves(cfg: Config, inv: Inventory) -> dict:
    inv.log_phase("plan", "started")
    target_root = Path(cfg.target_root).expanduser()
    planned = 0
    duplicates_planned = 0

    with inv.connect() as c:
        # 1) Canonical documents — use classification
        rows = c.execute(
            """SELECT f.id, f.path, f.kind, cl.category, cl.subcategory,
                      cl.year, cl.project_name, cl.suggested_name
               FROM files f JOIN classifications cl ON cl.file_id = f.id
               WHERE f.status != 'duplicate' AND f.status != 'applied'"""
        ).fetchall()
        for r in rows:
            src = Path(r["path"])
            filename = r["suggested_name"] or src.name
            if not Path(filename).suffix and src.suffix:
                filename += src.suffix
            target = build_target_for_document(target_root, r, filename)
            target = safe_unique_path(target)
            inv.plan_move(r["id"], str(src), str(target), is_dup=False)
            planned += 1

        # 2) Canonical photos/videos — EXIF-based path
        media_rows = c.execute(
            """SELECT id, path, kind, exif_date FROM files
               WHERE kind IN ('photo', 'video') AND status != 'duplicate'
                 AND status != 'applied'"""
        ).fetchall()
        for r in media_rows:
            src = Path(r["path"])
            year = (r["exif_date"] or "")[:4]
            target = build_target_for_media(target_root, year, r["kind"], src.name)
            target = safe_unique_path(target)
            inv.plan_move(r["id"], str(src), str(target), is_dup=False)
            planned += 1

        # 3) Duplicates — route to _Doublons under their canonical's category
        dup_rows = c.execute(
            """SELECT id, path, kind FROM files WHERE status = 'duplicate'"""
        ).fetchall()
        for r in dup_rows:
            src = Path(r["path"])
            canonical_id = get_canonical_for_duplicate(inv, r["id"])
            canonical_cat = "autre"
            if canonical_id:
                cc = c.execute(
                    """SELECT cl.category, cl.subcategory, f.kind
                       FROM files f LEFT JOIN classifications cl ON cl.file_id = f.id
                       WHERE f.id=?""",
                    (canonical_id,),
                ).fetchone()
                if cc:
                    if cc["category"]:
                        canonical_cat = cc["category"]
                    elif cc["kind"] == "photo":
                        canonical_cat = "12_Photos"
                    elif cc["kind"] == "video":
                        canonical_cat = "13_Videos"
            target = build_target_for_duplicate(target_root, canonical_cat, src.name)
            target = safe_unique_path(target)
            inv.plan_move(r["id"], str(src), str(target),
                          is_dup=True, dup_of=canonical_id)
            duplicates_planned += 1

    stats = {"planned_moves": planned, "planned_duplicates": duplicates_planned}
    inv.log_phase("plan", "done", str(stats))
    log.info("Plan complete: %s", stats)
    return stats


def export_plan(inv: Inventory, out_path: str) -> int:
    """Export planned moves as JSONL for manual review before apply."""
    count = 0
    with inv.connect() as c, open(out_path, "w", encoding="utf-8") as f:
        rows = c.execute(
            """SELECT m.file_id, m.source_path, m.target_path, m.is_duplicate,
                      f.size, f.sha256, cl.confidence, cl.category, cl.subcategory
               FROM moves m
               JOIN files f ON f.id = m.file_id
               LEFT JOIN classifications cl ON cl.file_id = m.file_id
               WHERE m.applied = 0"""
        ).fetchall()
        for r in rows:
            f.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
            count += 1
    return count


def apply_moves(cfg: Config, inv: Inventory) -> dict:
    if cfg.dry_run:
        log.warning("DRY RUN: no files will be moved. Set dry_run: false in config.")
    inv.log_phase("apply", "started")
    rows = inv.pending_moves()
    moved = 0
    errors = 0
    for r in rows:
        src = Path(r["source_path"])
        dst = Path(r["target_path"])
        try:
            if not src.exists():
                inv.mark_move_error(r["file_id"], "source missing")
                errors += 1
                continue
            if cfg.dry_run:
                moved += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Final collision check (in case of concurrent planning)
            if dst.exists():
                dst = safe_unique_path(dst)
            shutil.move(str(src), str(dst))
            inv.mark_move_applied(r["file_id"])
            moved += 1
            if moved % 100 == 0:
                log.info("moved %d", moved)
        except (OSError, shutil.Error) as e:
            errors += 1
            inv.mark_move_error(r["file_id"], str(e))
            log.error("move failed %s -> %s: %s", src, dst, e)

    stats = {"moved": moved, "errors": errors, "dry_run": cfg.dry_run}
    inv.log_phase("apply", "done", str(stats))
    log.info("Apply complete: %s", stats)
    return stats
