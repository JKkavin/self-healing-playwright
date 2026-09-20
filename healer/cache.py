import json
from pathlib import Path
from typing import Optional, Dict

CACHE_FILE = Path(__file__).parent.parent / "healed_locators.json"


def _load() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(data: dict) -> None:
    CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _key(failed_locator: str, page_url: str) -> str:
    clean_url = page_url.split("?")[0].split("#")[0]
    return f"{clean_url}::{failed_locator}"


def get_cached(failed_locator: str, page_url: str) -> Optional[Dict]:
    data = _load()
    entry = data.get(_key(failed_locator, page_url))
    if not entry:
        return None
    if isinstance(entry, str):
        return {"locator": entry, "confidence": 1.0}
    return entry


def save_cached(failed_locator: str, page_url: str, healed_locator: str, confidence: float = 1.0) -> None:
    data = _load()
    data[_key(failed_locator, page_url)] = {
        "locator": healed_locator,
        "confidence": confidence,
    }
    _save(data)
    print(f"💾 Cached: '{failed_locator}' → '{healed_locator}' (conf {confidence:.2f})")