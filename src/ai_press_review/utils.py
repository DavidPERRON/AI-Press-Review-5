from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dateutil import parser as date_parser
from slugify import slugify


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query='', fragment='')
    return urlunparse(cleaned)


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix('www.')


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def within_hours(value: str | None, hours: int) -> bool:
    dt = parse_dt(value)
    if dt is None:
        return True
    return dt >= utcnow() - timedelta(hours=hours)


def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def normalize_title(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def title_similarity(a: str, b: str) -> float:
    left = normalize_title(a)
    right = normalize_title(b)
    if not left or not right:
        return 0.0
    ratio = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    jaccard = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    return max(ratio, jaccard)


def fingerprint(title: str, url: str) -> str:
    raw = f"{normalize_title(title)}::{normalize_url(url)}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def safe_slug(text: str) -> str:
    result = slugify(text, max_length=80)
    return result if result else "untitled"


def read_json(path: Path, default):
    if not path.exists():
        return default
    # Corrupt state files (conflict markers, truncated writes) must not crash
    # the whole pipeline. We log-and-quarantine the bad file, then return the
    # default so the caller can rebuild state from scratch. The release blocker
    # on 2026-04-16 was caused by committed `<<<<<<< Updated upstream` markers
    # in data/state/used_sources_{en,fr}.json — a crash here stopped every
    # daily run that reused that state.
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        quarantine = path.with_suffix(path.suffix + '.corrupt')
        try:
            path.replace(quarantine)
        except OSError:
            pass  # best-effort; even if quarantine fails we must not crash
        import sys
        print(
            f'WARN: {path} is not valid JSON ({exc}); quarantined to '
            f'{quarantine} and returning default state.',
            file=sys.stderr,
        )
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
