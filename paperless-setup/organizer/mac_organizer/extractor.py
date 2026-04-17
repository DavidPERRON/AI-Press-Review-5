"""
Text extraction from documents + EXIF date extraction from photos/videos.

Strategy: try the lightest method first (native text), fall back to OCR.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from .config import Config
from .db import Inventory

log = logging.getLogger(__name__)


def extract_pdf_text(path: str, max_chars: int) -> str:
    """Try pdfminer first, fallback to ocrmypdf+tesseract for scanned PDFs."""
    text = ""
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(path) or ""
    except Exception as e:
        log.debug("pdfminer failed on %s: %s", path, e)

    if len(text.strip()) < 100:
        # Likely scanned; try ocrmypdf via subprocess (sidecar)
        try:
            result = subprocess.run(
                ["ocrmypdf", "--sidecar", "-", "--quiet", "--skip-text",
                 "--output-type", "none", path, "-"],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout:
                text = result.stdout.decode("utf-8", errors="ignore")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.debug("ocrmypdf unavailable or timed out for %s: %s", path, e)

    return text[:max_chars]


def extract_docx_text(path: str, max_chars: int) -> str:
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)[:max_chars]
    except Exception as e:
        log.debug("docx failed on %s: %s", path, e)
        return ""


def extract_plain_text(path: str, max_chars: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception as e:
        log.debug("plain read failed on %s: %s", path, e)
        return ""


def extract_text(path: str, ext: str, max_chars: int) -> str:
    ext = ext.lower()
    if ext == "pdf":
        return extract_pdf_text(path, max_chars)
    if ext == "docx":
        return extract_docx_text(path, max_chars)
    if ext in ("txt", "md", "csv", "rtf", "eml"):
        return extract_plain_text(path, max_chars)
    # Best-effort: let Apple textutil handle rtf/pages/doc if available (macOS)
    try:
        r = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", path],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="ignore")[:max_chars]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def extract_exif_date(path: str) -> str | None:
    """Return 'YYYY-MM-DD' from EXIF DateTimeOriginal, or None."""
    try:
        from PIL import Image, ExifTags
        img = Image.open(path)
        exif = img._getexif() or {}
        tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
            if key in tags:
                dt = datetime.strptime(str(tags[key]), "%Y:%m:%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d")
    except Exception as e:
        log.debug("exif failed on %s: %s", path, e)
    return None


def extract_video_date(path: str) -> str | None:
    """Use ffprobe for video creation date."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "flat",
             "-show_entries", "format_tags=creation_time", path],
            capture_output=True, timeout=15,
        )
        out = r.stdout.decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "creation_time" in line and "=" in line:
                val = line.split("=", 1)[1].strip().strip('"')
                return val[:10]  # YYYY-MM-DD
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def fallback_mtime_date(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def run_extraction(cfg: Config, inv: Inventory) -> dict:
    inv.log_phase("extract", "started")
    # Documents
    doc_rows = inv.files_needing_extraction()
    total_docs = len(doc_rows)
    for i, row in enumerate(doc_rows, 1):
        text = extract_text(row["path"], row["extension"], cfg.max_text_chars)
        inv.set_extraction(row["id"], text or None)
        if i % 50 == 0:
            log.info("extracted text %d/%d", i, total_docs)

    # Photos / videos — EXIF only, no LLM
    with inv.connect() as c:
        media_rows = c.execute(
            """SELECT id, path, mtime, kind FROM files
               WHERE sha256 IS NOT NULL AND exif_date IS NULL
                 AND kind IN ('photo', 'video') AND status != 'duplicate'"""
        ).fetchall()
    for row in media_rows:
        if row["kind"] == "photo":
            d = extract_exif_date(row["path"]) or fallback_mtime_date(row["mtime"])
        else:
            d = extract_video_date(row["path"]) or fallback_mtime_date(row["mtime"])
        inv.set_exif_date(row["id"], d)

    stats = {"documents_extracted": total_docs, "media_dated": len(media_rows)}
    inv.log_phase("extract", "done", str(stats))
    log.info("Extraction complete: %s", stats)
    return stats
