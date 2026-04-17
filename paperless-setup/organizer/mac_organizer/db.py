"""SQLite-backed inventory for resumable pipeline."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    path            TEXT UNIQUE NOT NULL,
    size            INTEGER NOT NULL,
    mtime           REAL NOT NULL,
    extension       TEXT,
    sha256          TEXT,
    kind            TEXT,           -- document | photo | video | audio | other
    scanned_at      REAL DEFAULT (strftime('%s','now')),
    hashed_at       REAL,
    extracted_text  TEXT,
    extracted_at    REAL,
    exif_date       TEXT,           -- YYYY-MM-DD for photos/videos
    status          TEXT DEFAULT 'scanned'
                    -- scanned | hashed | extracted | classified | planned | applied | duplicate | error | skipped
);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_files_kind ON files(kind);

CREATE TABLE IF NOT EXISTS classifications (
    file_id         INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    category        TEXT NOT NULL,
    subcategory     TEXT NOT NULL,
    year            TEXT,
    project_name    TEXT,
    suggested_name  TEXT,
    confidence      REAL NOT NULL,
    raw_response    TEXT,
    model           TEXT,
    classified_at   REAL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS moves (
    file_id         INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    source_path     TEXT NOT NULL,
    target_path     TEXT NOT NULL,
    is_duplicate    INTEGER DEFAULT 0,
    duplicate_of    INTEGER,          -- file_id of canonical copy
    applied         INTEGER DEFAULT 0,
    applied_at      REAL,
    error           TEXT
);
CREATE INDEX IF NOT EXISTS idx_moves_applied ON moves(applied);

CREATE TABLE IF NOT EXISTS run_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phase           TEXT NOT NULL,
    started_at      REAL DEFAULT (strftime('%s','now')),
    ended_at        REAL,
    status          TEXT,
    details         TEXT
);
"""


class Inventory:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init()

    def _init(self) -> None:
        with self.connect() as c:
            c.executescript(SCHEMA)
            c.commit()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            yield conn
        finally:
            conn.close()

    # --- Scan ---
    def upsert_file(self, path: str, size: int, mtime: float, ext: str, kind: str) -> int:
        with self.connect() as c:
            cur = c.execute(
                """INSERT INTO files(path, size, mtime, extension, kind)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET
                     size=excluded.size, mtime=excluded.mtime,
                     extension=excluded.extension, kind=excluded.kind
                   RETURNING id""",
                (path, size, mtime, ext, kind),
            )
            row = cur.fetchone()
            c.commit()
            return row["id"]

    def files_needing_hash(self, limit: int | None = None):
        q = "SELECT id, path, size FROM files WHERE sha256 IS NULL AND status != 'error'"
        if limit:
            q += f" LIMIT {int(limit)}"
        with self.connect() as c:
            return c.execute(q).fetchall()

    def set_hash(self, file_id: int, sha256: str) -> None:
        with self.connect() as c:
            c.execute(
                "UPDATE files SET sha256=?, hashed_at=strftime('%s','now'), status='hashed' WHERE id=?",
                (sha256, file_id),
            )
            c.commit()

    def mark_error(self, file_id: int, msg: str) -> None:
        with self.connect() as c:
            c.execute("UPDATE files SET status='error' WHERE id=?", (file_id,))
            c.execute(
                "INSERT INTO run_log(phase, ended_at, status, details) VALUES ('file_error', strftime('%s','now'), 'error', ?)",
                (f"file_id={file_id}: {msg}",),
            )
            c.commit()

    # --- Dedup ---
    def duplicate_groups(self):
        q = """SELECT sha256, COUNT(*) as n, GROUP_CONCAT(id) as ids
               FROM files WHERE sha256 IS NOT NULL
               GROUP BY sha256 HAVING n > 1"""
        with self.connect() as c:
            return c.execute(q).fetchall()

    def get_file(self, file_id: int):
        with self.connect() as c:
            return c.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()

    # --- Extract ---
    def files_needing_extraction(self):
        with self.connect() as c:
            return c.execute(
                """SELECT id, path, extension, kind FROM files
                   WHERE sha256 IS NOT NULL AND extracted_text IS NULL
                     AND kind = 'document' AND status != 'error'"""
            ).fetchall()

    def set_extraction(self, file_id: int, text: str | None) -> None:
        with self.connect() as c:
            c.execute(
                """UPDATE files SET extracted_text=?, extracted_at=strftime('%s','now'),
                   status='extracted' WHERE id=?""",
                (text, file_id),
            )
            c.commit()

    def set_exif_date(self, file_id: int, date_str: str) -> None:
        with self.connect() as c:
            c.execute(
                "UPDATE files SET exif_date=?, status='extracted' WHERE id=?",
                (date_str, file_id),
            )
            c.commit()

    # --- Classify ---
    def files_needing_classification(self):
        """Only canonical (non-duplicate) files get classified."""
        with self.connect() as c:
            return c.execute(
                """SELECT f.id, f.path, f.extension, f.kind, f.extracted_text, f.exif_date
                   FROM files f
                   LEFT JOIN classifications cl ON cl.file_id = f.id
                   WHERE cl.file_id IS NULL
                     AND f.status IN ('extracted', 'hashed')
                     AND f.status != 'duplicate'
                     AND f.kind = 'document'"""
            ).fetchall()

    def save_classification(self, file_id: int, **kwargs) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO classifications(file_id, category, subcategory, year,
                   project_name, suggested_name, confidence, raw_response, model)
                   VALUES (:file_id, :category, :subcategory, :year, :project_name,
                   :suggested_name, :confidence, :raw_response, :model)
                   ON CONFLICT(file_id) DO UPDATE SET
                     category=excluded.category, subcategory=excluded.subcategory,
                     year=excluded.year, project_name=excluded.project_name,
                     suggested_name=excluded.suggested_name,
                     confidence=excluded.confidence,
                     raw_response=excluded.raw_response, model=excluded.model""",
                {"file_id": file_id, **kwargs},
            )
            c.execute("UPDATE files SET status='classified' WHERE id=?", (file_id,))
            c.commit()

    # --- Plan / apply ---
    def plan_move(self, file_id: int, source: str, target: str,
                  is_dup: bool = False, dup_of: int | None = None) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO moves(file_id, source_path, target_path, is_duplicate, duplicate_of)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(file_id) DO UPDATE SET
                     source_path=excluded.source_path,
                     target_path=excluded.target_path,
                     is_duplicate=excluded.is_duplicate,
                     duplicate_of=excluded.duplicate_of,
                     applied=0, error=NULL""",
                (file_id, source, target, 1 if is_dup else 0, dup_of),
            )
            c.execute("UPDATE files SET status='planned' WHERE id=?", (file_id,))
            c.commit()

    def pending_moves(self):
        with self.connect() as c:
            return c.execute(
                "SELECT file_id, source_path, target_path, is_duplicate FROM moves WHERE applied=0"
            ).fetchall()

    def mark_move_applied(self, file_id: int) -> None:
        with self.connect() as c:
            c.execute(
                "UPDATE moves SET applied=1, applied_at=strftime('%s','now') WHERE file_id=?",
                (file_id,),
            )
            c.execute("UPDATE files SET status='applied' WHERE id=?", (file_id,))
            c.commit()

    def mark_move_error(self, file_id: int, err: str) -> None:
        with self.connect() as c:
            c.execute("UPDATE moves SET error=? WHERE file_id=?", (err, file_id))
            c.commit()

    def mark_duplicate(self, file_id: int) -> None:
        with self.connect() as c:
            c.execute("UPDATE files SET status='duplicate' WHERE id=?", (file_id,))
            c.commit()

    # --- Stats ---
    def stats(self) -> dict:
        with self.connect() as c:
            out = {}
            out["total"] = c.execute("SELECT COUNT(*) n FROM files").fetchone()["n"]
            for status in ("scanned", "hashed", "extracted", "classified",
                           "planned", "applied", "duplicate", "error"):
                out[status] = c.execute(
                    "SELECT COUNT(*) n FROM files WHERE status=?", (status,)
                ).fetchone()["n"]
            out["duplicate_groups"] = c.execute(
                """SELECT COUNT(*) n FROM (SELECT sha256 FROM files
                   WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING COUNT(*) > 1)"""
            ).fetchone()["n"]
            return out

    def log_phase(self, phase: str, status: str, details: str = "") -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO run_log(phase, ended_at, status, details)
                   VALUES (?, strftime('%s','now'), ?, ?)""",
                (phase, status, details),
            )
            c.commit()
