"""
Drop-in replacement for Playwright's Page and Locator.

Usage:
    from healer import HealingPage
    ...
    page = HealingPage(context.new_page())
    page.get_by_role("button", name="Log In").click()   # self-heals!
"""

from playwright.sync_api import Page, Locator, TimeoutError
from healer.locator import heal_locator
from healer.cache import get_cached, save_cached
from healer.log import log_heal


# Actions that take a value
ACTIONS_WITH_VALUE = {"fill", "type", "select_option", "press", "set_input_files"}


class HealingLocator:
    """Wraps a Playwright Locator so actions self-heal on timeout."""

    def __init__(self, page: Page, original_locator: str, description: str = ""):
        self._page = page
        self._original = original_locator
        self._description = description

    def _playwright_locator(self) -> Locator:
        return self._page.locator(self._original)

    def _run(self, action: str, value=None, timeout: int = 8000):
        # 1. Try original
        try:
            el = self._playwright_locator()
            if action in ACTIONS_WITH_VALUE:
                return getattr(el, action)(value, timeout=timeout)
            return getattr(el, action)(timeout=timeout)
        except TimeoutError:
            print(f"🔴 {action}('{self._original}') FAILED.")

        # 2. Try cache
        cached = get_cached(self._original, self._page.url)
        if cached:
            print(f"⚡ Cache hit: '{cached['locator']}' (conf {cached['confidence']:.2f})")
            try:
                el = self._page.locator(cached["locator"])
                if action in ACTIONS_WITH_VALUE:
                    result = getattr(el, action)(value, timeout=timeout)
                else:
                    result = getattr(el, action)(timeout=timeout)
                log_heal(action, self._original, cached["locator"], self._page.url, "cache", cached["confidence"])
                print(f"✅ Healed (cached): {action}('{cached['locator']}') succeeded")
                return result
            except TimeoutError:
                print(f"⚠️ Cached locator no longer works. Asking AI...")

        # 3. Ask AI
        print(f"🤖 Asking AI to heal...")
        try:
            new_locator, confidence = heal_locator(self._page, self._original, action, value or "")
        except Exception as e:
            print(f"🚨 AI healing failed: {e}")
            raise TimeoutError(f"Healing failed for '{self._original}': {e}")

        print(f"🩹 AI suggested: '{new_locator}' (confidence {confidence:.2f})")

        # 4. Save + log
        save_cached(self._original, self._page.url, new_locator, confidence)
        log_heal(action, self._original, new_locator, self._page.url, "ai", confidence)

        # 5. Retry with healed locator
        try:
            el = self._page.locator(new_locator)
            if action in ACTIONS_WITH_VALUE:
                result = getattr(el, action)(value, timeout=timeout)
            else:
                result = getattr(el, action)(timeout=timeout)
            print(f"✅ Healed: {action}('{new_locator}') succeeded")
            return result
        except TimeoutError:
            print(f"⚠️ Healed locator also failed. Asking AI once more with context...")
        except Exception as e:
            print(f"🚨 Non-timeout error during heal retry: {e}")
            raise

        # 6. Second-chance heal
        try:
            hint = f"{self._original} (previously healed to '{new_locator}' but that also failed)"
            new_locator_2, confidence_2 = heal_locator(self._page, hint, action, value or "")
            print(f"🩹 AI 2nd suggestion: '{new_locator_2}' (confidence {confidence_2:.2f})")

            save_cached(self._original, self._page.url, new_locator_2, confidence_2)
            log_heal(action, self._original, new_locator_2, self._page.url, "ai-retry", confidence_2)

            el = self._page.locator(new_locator_2)
            if action in ACTIONS_WITH_VALUE:
                result = getattr(el, action)(value, timeout=timeout)
            else:
                result = getattr(el, action)(timeout=timeout)
            print(f"✅ Healed (2nd try): {action}('{new_locator_2}') succeeded")
            return result
        except Exception as e:
            print(f"🚨 Second-chance heal also failed: {e}")
            raise TimeoutError(
                f"All healing attempts failed for '{self._original}'. "
                f"Last error: {e}"
            )

    # --- Actions with a value ---
    def fill(self, value, **kwargs):
        return self._run("fill", value)

    def type(self, value, **kwargs):
        return self._run("type", value)

    def press(self, key, **kwargs):
        return self._run("press", key)

    def select_option(self, value, **kwargs):
        return self._run("select_option", value)

    def set_input_files(self, files, **kwargs):
        return self._run("set_input_files", files)

    # --- Actions without a value ---
    def click(self, **kwargs):
        return self._run("click")

    def check(self, **kwargs):
        return self._run("check")

    def uncheck(self, **kwargs):
        return self._run("uncheck")

    def hover(self, **kwargs):
        return self._run("hover")

    def wait_for(self, **kwargs):
        return self._run("wait_for")

    def text_content(self, **kwargs):
        return self._run("text_content")

    def inner_text(self, **kwargs):
        return self._run("inner_text")

    # --- Pass-through with .nth() / .first / .last preserved for healing ---
    def __getattr__(self, name):
        if name == "nth":
            def nth_wrapper(index):
                return HealingLocator(
                    self._page,
                    f"{self._original} >> nth={index}"
                )
            return nth_wrapper
        if name == "first":
            return HealingLocator(self._page, f"{self._original} >> nth=0")
        if name == "last":
            return HealingLocator(self._page, f"{self._original} >> nth=-1")
        return getattr(self._playwright_locator(), name)


class HealingPage:
    """Wraps a Playwright Page so locators self-heal."""

    def __init__(self, page: Page):
        self._page = page

    def locator(self, selector, **kwargs) -> HealingLocator:
        return HealingLocator(self._page, selector)

    def get_by_role(self, role, **kwargs) -> HealingLocator:
        name = kwargs.get("name")
        if name:
            selector = f'role={role}[name="{name}"]'
        else:
            selector = f"role={role}"
        return HealingLocator(self._page, selector)

    def get_by_text(self, text, **kwargs) -> HealingLocator:
        return HealingLocator(self._page, f'text="{text}"')

    def get_by_label(self, label, **kwargs) -> HealingLocator:
        return HealingLocator(self._page, f'label={label}')

    def get_by_placeholder(self, placeholder, **kwargs) -> HealingLocator:
        return HealingLocator(self._page, f'[placeholder="{placeholder}"]')

    def get_by_test_id(self, test_id) -> HealingLocator:
        return HealingLocator(self._page, f'[data-testid="{test_id}"]')

    def __getattr__(self, name):
        return getattr(self._page, name)