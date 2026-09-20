from playwright.sync_api import sync_playwright
from healing_page import HealingPage

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = HealingPage(context.new_page())   # ← THE ONE-LINE CHANGE

    page.goto("https://pltqa.citiustech.com/uamwebapp/")
    page.wait_for_timeout(2000)

    # Original Playwright code — with a deliberately WRONG locator
    page.get_by_placeholder("wrong_placeholder_nobody_uses").fill("Sa")
    page.get_by_role("textbox", name="Password").fill("Password_123")
    page.get_by_role("button", name="Log In").click()

    page.wait_for_timeout(5000)
    print("\n✅ Login flow complete. Browser stays open 15s.")
    page.wait_for_timeout(15000)

    context.close()
    browser.close()