import os
import json
import time
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
from heal_log import log_heal

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

MODEL_FALLBACKS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]

API_CACHE_FILE = Path(__file__).parent / "api_cache.json"


# ---------- LLM call with retry + fallback ----------

def _call_gemini_with_retry(prompt: str) -> str:
    """Call Gemini with retry on 503, skip retired models on 404."""
    last_error = None
    for model in MODEL_FALLBACKS:
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                if model != MODEL_FALLBACKS[0]:
                    print(f"🤖 Fallback model used: {model}")
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(1.5 ** attempt)
                    continue
                if "404" in err_str or "NOT_FOUND" in err_str:
                    print(f"⚠️  Model '{model}' retired, trying next...")
                    break
                break
    raise last_error


# ---------- Cache ----------

def _load_cache() -> dict:
    if not API_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(API_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(data: dict) -> None:
    API_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _cache_key(endpoint: str, old_key: str) -> str:
    clean = endpoint.split("?")[0].split("#")[0]
    return f"{clean}::{old_key}"


def get_cached_key(endpoint: str, old_key: str) -> Optional[dict]:
    return _load_cache().get(_cache_key(endpoint, old_key))


def save_cached_key(endpoint: str, old_key: str, new_key: str, confidence: float) -> None:
    data = _load_cache()
    data[_cache_key(endpoint, old_key)] = {
        "key": new_key,
        "confidence": confidence,
    }
    _save_cache(data)
    print(f"💾 Cached API mapping: '{old_key}' → '{new_key}' (conf {confidence:.2f})")


# ---------- Key healing ----------

def heal_key(endpoint: str, old_key: str, response_sample: Any):
    """Returns (new_key: str, confidence: float)."""
    sample_json = json.dumps(response_sample, indent=2)[:4000]

    prompt = f"""You are an expert API integration engineer.

An API response changed and a test failed with KeyError: '{old_key}'.
The endpoint was: `{endpoint}`

Here is the ACTUAL response returned by the API now:
{sample_json}

Return your answer in EXACTLY this JSON format, nothing else:
{{
  "key": "<the top-level key that replaces '{old_key}'>",
  "confidence": <number between 0.0 and 1.0>
}}

Rules:
- Return ONLY a top-level key name that exists in the response above.
- If no good match exists, set "key" to "NO_MATCH".
- confidence = how sure you are (1.0 = certain, 0.5 = guessing).
"""

    raw = _call_gemini_with_retry(prompt)

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        key = str(parsed.get("key", "NO_MATCH")).strip()
        confidence = float(parsed.get("confidence", 0.5))
    except (json.JSONDecodeError, ValueError, TypeError):
        key = raw.strip('`"\'').strip()
        confidence = 0.5

    return key, confidence


# ---------- Public API ----------

def self_healing_get(data: dict, key: str, endpoint: str = "unknown") -> Any:
    """Like data[key], but self-heals when the key changed."""
    if key in data:
        return data[key]

    print(f"🔴 KeyError: '{key}' not in response from '{endpoint}'")

    cached = get_cached_key(endpoint, key)
    if cached and cached["key"] in data:
        new_key = cached["key"]
        print(f"⚡ Cache hit: '{key}' → '{new_key}' (conf {cached['confidence']:.2f})")
        log_heal("api_get", key, new_key, endpoint, "cache", cached["confidence"], "api")
        return data[new_key]

    print(f"🤖 Asking AI to heal key...")
    new_key, confidence = heal_key(endpoint, key, data)
    print(f"🩹 AI suggested: '{new_key}' (confidence {confidence:.2f})")

    if new_key == "NO_MATCH" or new_key not in data:
        log_heal("api_get", key, new_key, endpoint, "ai", confidence, "api")
        raise KeyError(f"No healing found for '{key}'. AI suggested '{new_key}'")

    save_cached_key(endpoint, key, new_key, confidence)
    log_heal("api_get", key, new_key, endpoint, "ai", confidence, "api")

    print(f"✅ Healed: '{key}' → '{new_key}'")
    return data[new_key]