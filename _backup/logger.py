import json
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent / "healing_log.jsonl"


def log_heal(
    action: str,
    old_locator: str,
    new_locator: str,
    page_url: str,
    source: str,          # "ai" | "cache"
    confidence: float = 1.0,
) -> None:
    """Append a healing event to the JSONL log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "old": old_locator,
        "new": new_locator,
        "page": page_url,
        "source": source,
        "confidence": round(confidence, 3),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Warn if confidence is low
    if confidence < 0.7:
        print(f"⚠️  LOW CONFIDENCE ({confidence:.2f}) — heal may be wrong. Review: {LOG_FILE.name}")