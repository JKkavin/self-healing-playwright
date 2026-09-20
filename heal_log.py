import json
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent / "healing_log.jsonl"


def log_heal(
    action: str,
    old: str,
    new: str,
    page_url: str,
    source: str,          # "ai" | "cache"
    confidence: float = 1.0,
    heal_type: str = "locator",   # "locator" | "api"
) -> None:
    """Append a healing event to the JSONL log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": heal_type,
        "action": action,
        "old": old,
        "new": new,
        "page": page_url,
        "source": source,
        "confidence": round(confidence, 3),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    if confidence < 0.7:
        print(f"⚠️  LOW CONFIDENCE ({confidence:.2f}) — review: {LOG_FILE.name}")