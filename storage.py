"""Simple JSON-file audit log for classification decisions."""

import json
from datetime import datetime, timezone
from pathlib import Path

# audit_log.json lives in the project root (same folder as this file).
AUDIT_LOG_PATH = Path(__file__).resolve().parent / "audit_log.json"


def _read_log() -> list:
    """Load all log entries from disk, or [] if the file does not exist yet."""
    if not AUDIT_LOG_PATH.exists():
        return []
    with AUDIT_LOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _write_log(entries: list) -> None:
    """Persist the full log array to audit_log.json."""
    with AUDIT_LOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def log_submission(
    content_id: str,
    creator_id: str,
    attribution: str,
    confidence: float,
    llm_score: float,
    stylometry_score: float,
    status: str = "classified",
) -> None:
    """Append one classified submission to the audit log."""
    entries = _read_log()
    entries.append(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attribution": attribution,
            "confidence": confidence,
            "llm_score": llm_score,
            "stylometry_score": stylometry_score,
            "status": status,
        }
    )
    _write_log(entries)


def get_log(limit: int = 50) -> list:
    """Return the most recent log entries (newest first)."""
    entries = _read_log()
    return list(reversed(entries[-limit:]))
