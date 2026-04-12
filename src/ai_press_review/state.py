from __future__ import annotations

from .settings import DATA_DIR
from .utils import read_json, write_json

USED_SOURCES_PATH = DATA_DIR / 'state' / 'used_sources.json'
EPISODE_HISTORY_PATH = DATA_DIR / 'state' / 'episode_history.json'


def load_episode_history() -> dict:
    return read_json(EPISODE_HISTORY_PATH, {'episodes': []})


def save_episode_history(data: dict) -> None:
    write_json(EPISODE_HISTORY_PATH, data)


def load_used_sources() -> dict:
    return read_json(USED_SOURCES_PATH, {'items': []})


def save_used_sources(data: dict) -> None:
    write_json(USED_SOURCES_PATH, data)
