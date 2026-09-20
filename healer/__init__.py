"""
self-healing-playwright
~~~~~~~~~~~~~~~~~~~~~~~

Self-healing Playwright automation powered by Google Gemini.

    from healer import HealingPage, self_healing_action, self_healing_get

    page = HealingPage(context.new_page())
    page.get_by_role("button", name="Submit").click()   # heals on failure
"""

from healer.locator import self_healing_action, heal_locator
from healer.page import HealingPage, HealingLocator
from healer.api import self_healing_get
from healer.log import log_heal

__version__ = "0.1.0"
__all__ = [
    "HealingPage",
    "HealingLocator",
    "self_healing_action",
    "self_healing_get",
    "heal_locator",
    "log_heal",
]