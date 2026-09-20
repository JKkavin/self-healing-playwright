from playwright.sync_api import sync_playwright
from healer import self_healing_action

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # --- Login flow ---
    page.goto("https://pltqa.citiustech.com/uamwebapp/")
    page.wait_for_timeout(2000)

    self_healing_action(page, "input[name='wrong_username_field']", "fill", "Sa")
    self_healing_action(page, "input[name='password']", "fill", "Password_123")
    self_healing_action(page, "button[type='submit']", "click")

    page.wait_for_timeout(5000)
    print("\n✅ Login flow complete. Browser will stay open 15s for inspection.")
    page.wait_for_timeout(15000)

    context.close()
    browser.close()