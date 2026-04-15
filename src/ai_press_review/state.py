from __future__ import annotations

import os

from .settings import DATA_DIR
from .utils import read_json, write_json


def _locale_suffix() -> str:
    """Return `_<locale>` suffix when APR_LOCALE is set, else empty string.

    Empty suffix preserves legacy file names for the single-locale EN pipeline.
    Once matrix EN/FR runs are live, each job sets APR_LOCALE and writes to
    its own state files — so EN and FR histories never collide.
    """
    loc = os.getenv('APR_LOCALE', '').strip().lower()
    return f'_{loc}' if loc else ''


def _used_sources_path():
    return DATA_DIR / 'state' / f'used_sources{_locale_suffix()}.json'


def _episode_history_path():
    return DATA_DIR / 'state' / f'episode_history{_locale_suffix()}.json'


def _pending_draft_path():
    return DATA_DIR / 'state' / f'pending_draft{_locale_suffix()}.json'


# Backward-compat module-level constants (read at import time, no locale).
# Callers should prefer the load/save functions below which respect APR_LOCALE.
USED_SOURCES_PATH = _used_sources_path()
EPISODE_HISTORY_PATH = _episode_history_path()
PENDING_DRAFT_PATH = _pending_draft_path()


def load_episode_history() -> dict:
    return read_json(_episode_history_path(), {'episodes': []})


def save_episode_history(data: dict) -> None:
    write_json(_episode_history_path(), data)


def load_used_sources() -> dict:
    return read_json(_used_sources_path(), {'items': []})


def save_used_sources(data: dict) -> None:
    write_json(_used_sources_path(), data)


def load_pending_draft() -> dict:
    return read_json(_pending_draft_path(), {})


def save_pending_draft(data: dict) -> None:
    write_json(_pending_draft_path(), data)


def delete_pending_draft() -> None:
    path = _pending_draft_path()
    if path.exists():
        path.unlink()
