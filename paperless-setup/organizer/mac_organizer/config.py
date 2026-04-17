"""Configuration loader."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


DEFAULT_EXCLUDE_DIRS = [
    ".Trash", ".git", ".svn", ".hg",
    "node_modules", ".venv", "venv", "__pycache__",
    "Library/Caches", "Library/Containers", "Library/Application Support",
    "Library/Logs", "Library/Mail", "Library/CoreData",
    "Library/Developer", ".Spotlight-V100", ".fseventsd",
    ".DocumentRevisions-V100", ".TemporaryItems",
    "System", "Applications",
    # Paperless / Docker internals
    "paperless-data", "paperless-media",
]

DEFAULT_INCLUDE_EXTENSIONS = {
    # Documents
    "pdf", "docx", "doc", "odt", "rtf", "txt", "md", "pages",
    "xlsx", "xls", "ods", "numbers", "csv",
    "pptx", "ppt", "odp", "key",
    # Images / photos
    "jpg", "jpeg", "png", "heic", "heif", "tiff", "tif", "webp",
    "raw", "dng", "cr2", "cr3", "nef", "arw", "orf", "rw2",
    # Videos
    "mp4", "mov", "m4v", "avi", "mkv", "mpg", "mpeg", "wmv",
    # Audio
    "mp3", "m4a", "flac", "wav", "aac", "ogg",
    # Email / archives
    "eml", "msg",
    "zip",
}

PHOTO_EXTENSIONS = {
    "jpg", "jpeg", "png", "heic", "heif", "tiff", "tif", "webp",
    "raw", "dng", "cr2", "cr3", "nef", "arw", "orf", "rw2",
}

VIDEO_EXTENSIONS = {
    "mp4", "mov", "m4v", "avi", "mkv", "mpg", "mpeg", "wmv",
}

AUDIO_EXTENSIONS = {"mp3", "m4a", "flac", "wav", "aac", "ogg"}

DOCUMENT_EXTENSIONS = {
    "pdf", "docx", "doc", "odt", "rtf", "txt", "md", "pages",
    "xlsx", "xls", "ods", "numbers", "csv",
    "pptx", "ppt", "odp", "key",
    "eml", "msg",
}


@dataclass
class Config:
    # Paths
    scan_roots: list[str] = field(default_factory=list)
    target_root: str = "/Volumes/SSD2TB"
    db_path: str = "./mac_organizer.db"

    # Scanner
    exclude_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_DIRS))
    include_extensions: set[str] = field(default_factory=lambda: set(DEFAULT_INCLUDE_EXTENSIONS))
    max_file_size_mb: int = 5000
    follow_symlinks: bool = False

    # DeepInfra
    deepinfra_api_key: str = ""
    model: str = "meta-llama/Llama-3.3-70B-Instruct"
    api_base: str = "https://api.deepinfra.com/v1/openai"
    temperature: float = 0.1
    max_tokens: int = 400
    max_text_chars: int = 8000  # Text sent to LLM per doc
    confidence_threshold: float = 0.85
    retry_on_low_confidence: bool = True
    max_retries: int = 2
    concurrent_classifications: int = 4

    # Organizer
    dry_run: bool = True
    create_missing_dirs: bool = True
    hardlink_if_same_volume: bool = False  # Use move; set True to hardlink for safety

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = cls()
        for key, value in data.items():
            if hasattr(cfg, key):
                if key == "include_extensions" and isinstance(value, list):
                    value = set(value)
                setattr(cfg, key, value)
        # Env override for API key
        import os
        env_key = os.environ.get("DEEPINFRA_API_KEY")
        if env_key:
            cfg.deepinfra_api_key = env_key
        return cfg
