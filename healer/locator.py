import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import Page, TimeoutError
from healer.cache import get_cached, save_cached
from healer.log import log_heal

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

ACTIONS_WITH_VALUE = {
    "fill", "select_option", "press", "type",
    "set_input_files",   # NEW
}

# NEW: raise if confidence is below this (set to 0.0 to disable)
MIN_CONFIDENCE_THRESHOLD = 0.4


# ---------- LLM call with retry + fallback ----------

def _call_gemini_with_retry(prompt: str) -> str:
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


# ---------- DOM snapshot ----------

def get_dom_snapshot(page: Page) -> str:
    elements = page.evaluate("""() => {
        const els = document.querySelectorAll(
            'input, button, a, select, textarea, ' +
            '[role="button"], [role="menuitem"], [role="link"], [role="tab"], ' +
            '[role="checkbox"], [role="radio"], [role="combobox"]'
        );
        return Array.from(els).map(el => ({
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type'),
            id: el.id,
            name: el.getAttribute('name'),
            placeholder: el.getAttribute('placeholder'),
            text: (el.innerText || el.value || '').trim().slice(0, 80),
            aria_label: el.getAttribute('aria-label'),
            role: el.getAttribute('role')
        }));
    }""")
    return json.dumps(elements, indent=2)


# ---------- Locator healing ----------

def heal_locator(page: Page, failed_locator: str, action_type: str, value: str = ""):
    """Ask Gemini to heal the locator. Returns (new_locator, confidence)."""
    dom = get_dom_snapshot(page)
    value_hint = f" with value `{value}`" if value else ""

    prompt = f"""You are an expert Playwright automation engineer.

A test failed because this locator was not found: `{failed_locator}`
The action attempted was: `{action_type}`{value_hint}

Here are the interactive elements on the page:
{dom}

Return your answer in EXACTLY this JSON format, nothing else:
{{
  "locator": "<the CSS selector>",
  "confidence": <number between 0.0 and 1.0>
}}

Rules:
- Use CSS selectors only.
- Match element type to action:
  - fill/type → input or textarea
  - click → button, a, or clickable element
  - check/uncheck → input[type=checkbox] or input[type=radio]
  - select_option → select
  - set_input_files → input[type=file]
- Prefer id, then name, then a stable attribute.
- confidence = how sure you are that this is the correct element (1.0 = certain, 0.5 = guessing).
"""

    raw = _call_gemini_with_retry(prompt)

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        locator = str(parsed.get("locator", "")).strip()
        confidence = float(parsed.get("confidence", 0.5))
    except (json.JSONDecodeError, ValueError, TypeError):
        locator = raw.strip('`"\'').strip()
        confidence = 0.5

    return locator, confidence


# ---------- Action runner (now supports more actions) ----------

def _perform(page: Page, locator: str, action: str, value=None, timeout: int = 5000):
    element = page.locator(locator)
    if action == "fill":
        element.fill(value, timeout=timeout)
    elif action == "type":
        element.type(value, timeout=timeout)
    elif action == "click":
        element.click(timeout=timeout)
    elif action == "check":
        element.check(timeout=timeout)
    elif action == "uncheck":
        element.uncheck(timeout=timeout)
    elif action == "select_option":
        element.select_option(value, timeout=timeout)
    elif action == "press":
        element.press(value, timeout=timeout)
    elif action == "hover":
        element.hover(timeout=timeout)
    elif action == "set_input_files":
        element.set_input_files(value, timeout=timeout)
    elif action == "wait_for":
        element.wait_for(timeout=timeout)
    elif action == "text_content":
        return element.text_content(timeout=timeout)
    elif action == "inner_text":
        return element.inner_text(timeout=timeout)
    else:
        raise ValueError(f"Unsupported action: {action}")


# ---------- Main healing action (with retry-after-heal + confidence check) ----------

def self_healing_action(page: Page, locator: str, action: str, value=None):
    if action in ACTIONS_WITH_VALUE and value is None:
        raise ValueError(f"Action '{action}' requires a value")

    # 1. Try original
    try:
        result = _perform(page, locator, action, value)
        print(f"✅ {action}('{locator}') succeeded")
        return result if result is not None else locator
    except TimeoutError:
        print(f"🔴 {action}('{locator}') FAILED.")

    # 2. Try cache
    cached = get_cached(locator, page.url)
    if cached:
        print(f"⚡ Cache hit: '{cached['locator']}' (conf {cached['confidence']:.2f})")
        try:
            result = _perform(page, cached["locator"], action, value)
            print(f"✅ Healed (cached): {action}('{cached['locator']}') succeeded")
            log_heal(action, locator, cached["locator"], page.url, "cache", cached["confidence"])
            return result if result is not None else cached["locator"]
        except TimeoutError:
            print(f"⚠️ Cached locator '{cached['locator']}' no longer works. Asking AI...")

    # 3. Ask AI (first attempt)
    print(f"🤖 Asking AI to heal...")
    new_locator, confidence = heal_locator(page, locator, action, value or "")
    print(f"🩹 AI suggested: '{new_locator}' (confidence {confidence:.2f})")

    # NEW: low-confidence warning
    if confidence < MIN_CONFIDENCE_THRESHOLD:
        print(f"🚨 LOW CONFIDENCE ({confidence:.2f} < {MIN_CONFIDENCE_THRESHOLD}). Heal may be wrong — proceeding anyway.")

    # 4. Save + log
    save_cached(locator, page.url, new_locator, confidence)
    log_heal(action, locator, new_locator, page.url, "ai", confidence)

    # 5. Retry with healed locator
    try:
        result = _perform(page, new_locator, action, value)
        print(f"✅ Healed: {action}('{new_locator}') succeeded")
        return result if result is not None else new_locator
    except TimeoutError:
        print(f"⚠️ Healed locator also failed. Asking AI once more with context...")

    # 6. NEW: Second-chance heal — give AI more context
    hint = f"{locator} (previously healed to '{new_locator}' but that also failed)"
    new_locator_2, confidence_2 = heal_locator(page, hint, action, value or "")
    print(f"🩹 AI 2nd suggestion: '{new_locator_2}' (confidence {confidence_2:.2f})")

    save_cached(locator, page.url, new_locator_2, confidence_2)
    log_heal(action, locator, new_locator_2, page.url, "ai-retry", confidence_2)

    # 7. Final retry
    result = _perform(page, new_locator_2, action, value)
    print(f"✅ Healed (2nd try): {action}('{new_locator_2}') succeeded")
    return result if result is not None else new_locator_2