"""
DeepInfra classifier using Llama 3.3 70B Instruct (OpenAI-compatible API).

Reliability strategy (>95% target):
- Closed-world taxonomy (LLM chooses from fixed list, validated server-side).
- Low temperature (0.1) for determinism.
- JSON-only responses with strict parsing + validation.
- Confidence threshold (0.85 default); below → 99_NonClasse/.
- Up to 2 retries on invalid/low-confidence responses.
- Few-shot guidance via the taxonomy description.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from .config import Config
from .db import Inventory
from .prompts import build_prompt
from .taxonomy import (
    UNCLASSIFIED_CATEGORY,
    allowed_category_slugs,
    validate_classification,
)

log = logging.getLogger(__name__)


class DeepInfraClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.endpoint = f"{cfg.api_base.rstrip('/')}/chat/completions"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {cfg.deepinfra_api_key}",
            "Content-Type": "application/json",
        })

    def classify_once(self, system: str, user: str) -> dict:
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "response_format": {"type": "json_object"},
        }
        r = self.session.post(self.endpoint, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        raw = data["choices"][0]["message"]["content"]
        return parse_json_response(raw)


def parse_json_response(raw: str) -> dict:
    """Extract JSON object from LLM response — tolerant of minor formatting issues."""
    raw = raw.strip()
    # Strip code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Find first {...} block
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not m:
            raise ValueError(f"No JSON object found: {raw[:200]}")
        return json.loads(m.group(0))


def sanitize_filename(name: str, fallback: str) -> str:
    if not name or not isinstance(name, str):
        return fallback
    # Replace slashes, keep simple ASCII + underscores
    name = name.strip().replace("/", "_").replace("\\", "_")
    # Collapse whitespace
    name = re.sub(r"\s+", "_", name)
    # Remove dangerous chars
    name = re.sub(r"[^A-Za-z0-9._\-]", "", name)
    if not name or name.startswith("."):
        return fallback
    return name[:180]  # filesystem-safe length


def validate_and_clean(response: dict, fallback_name: str,
                       threshold: float) -> dict:
    """Validate LLM response. Returns dict with category, subcategory,
    year, project_name, suggested_name, confidence."""
    cat = str(response.get("category", "")).strip()
    sub = str(response.get("subcategory", "")).strip()
    year = response.get("year")
    if year is not None:
        year = str(year).strip()
        if not re.fullmatch(r"\d{4}", year):
            year = None
    proj = response.get("project_name")
    if proj:
        proj = sanitize_filename(str(proj), "Projet")
    suggested = sanitize_filename(response.get("suggested_filename") or "", fallback_name)
    try:
        conf = float(response.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0.0

    if cat == "UNKNOWN" or not validate_classification(cat, sub) or conf < threshold:
        return {
            "category": UNCLASSIFIED_CATEGORY,
            "subcategory": "",
            "year": year,
            "project_name": proj,
            "suggested_name": suggested,
            "confidence": conf,
            "valid": False,
        }

    return {
        "category": cat,
        "subcategory": sub,
        "year": year,
        "project_name": proj,
        "suggested_name": suggested,
        "confidence": conf,
        "valid": True,
    }


def classify_file(client: DeepInfraClient, cfg: Config, row) -> dict:
    """Classify a single document row. Retries on low confidence."""
    path = row["path"]
    ext = row["extension"]
    content = row["extracted_text"] or ""
    filename = Path(path).name
    fallback_name = filename

    system, user = build_prompt(filename, ext, content)

    last_raw = None
    last_result = None
    for attempt in range(cfg.max_retries + 1):
        try:
            resp = client.classify_once(system, user)
            last_raw = json.dumps(resp, ensure_ascii=False)
            result = validate_and_clean(resp, fallback_name, cfg.confidence_threshold)
            last_result = result
            if result["valid"] or not cfg.retry_on_low_confidence:
                break
        except (requests.HTTPError, requests.ConnectionError,
                requests.Timeout, ValueError, KeyError) as e:
            log.warning("classification attempt %d failed for %s: %s", attempt + 1, path, e)
            time.sleep(min(2 ** attempt, 10))
    if last_result is None:
        last_result = {
            "category": UNCLASSIFIED_CATEGORY,
            "subcategory": "", "year": None, "project_name": None,
            "suggested_name": fallback_name, "confidence": 0.0, "valid": False,
        }
    last_result["raw_response"] = last_raw
    return last_result


def run_classification(cfg: Config, inv: Inventory) -> dict:
    if not cfg.deepinfra_api_key:
        raise RuntimeError(
            "DEEPINFRA_API_KEY not set. Export it or add to config.yaml."
        )
    inv.log_phase("classify", "started")
    client = DeepInfraClient(cfg)
    rows = inv.files_needing_classification()
    total = len(rows)
    done = 0
    unclassified = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=cfg.concurrent_classifications) as pool:
        futures = {pool.submit(classify_file, client, cfg, r): r for r in rows}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                result = fut.result()
                inv.save_classification(
                    file_id=row["id"],
                    category=result["category"],
                    subcategory=result["subcategory"],
                    year=result["year"],
                    project_name=result["project_name"],
                    suggested_name=result["suggested_name"],
                    confidence=result["confidence"],
                    raw_response=result.get("raw_response"),
                    model=cfg.model,
                )
                done += 1
                if not result["valid"]:
                    unclassified += 1
                if done % 25 == 0:
                    log.info("classified %d/%d (unclassified=%d)",
                             done, total, unclassified)
            except Exception as e:
                errors += 1
                log.error("classify failed for %s: %s", row["path"], e)

    stats = {
        "total": total, "classified": done,
        "unclassified": unclassified, "errors": errors,
    }
    inv.log_phase("classify", "done", str(stats))
    log.info("Classification complete: %s", stats)
    return stats
