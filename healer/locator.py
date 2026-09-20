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

ACTIONS_WITH_VALUE = {"fill", "select_option", "press", "type"}


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


def get_dom_snapshot(page: Page) -> str:
    elements = page.evaluate("""() => {
        const els = document.querySelectorAll('input, button, a, select, textarea, [role="button"], [role="menuitem"], [role="link"], [role="tab"]');
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


def heal_locator(page: Page, failed_locator: str, action_type: str, value: str = ""):
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
    elif action == "text_content":
        return element.text_content(timeout=timeout)
    elif action == "inner_text":
        return element.inner_text(timeout=timeout)
    else:
        raise ValueError(f"Unsupported action: {action}")


def self_healing_action(page: Page, locator: str, action: str, value=None):
    if action in ACTIONS_WITH_VALUE and value is None:
        raise ValueError(f"Action '{action}' requires a value")

    try:
        result = _perform(page, locator, action, value)
        print(f"✅ {action}('{locator}') succeeded")
        return result if result is not None else locator
    except TimeoutError:
        print(f"🔴 {action}('{locator}') FAILED.")

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

    print(f"🤖 Asking AI to heal...")
    new_locator, confidence = heal_locator(page, locator, action, value or "")
    print(f"🩹 AI suggested: '{new_locator}' (confidence {confidence:.2f})")

    save_cached(locator, page.url, new_locator, confidence)
    log_heal(action, locator, new_locator, page.url, "ai", confidence)

    result = _perform(page, new_locator, action, value)
    print(f"✅ Healed: {action}('{new_locator}') succeeded")
    return result if result is not None else new_locator