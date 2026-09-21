from playwright.sync_api import sync_playwright
from healer import HealingPage


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = HealingPage(context.new_page())

        # Public site with a healing demo
        page.goto("https://www.testmuai.com/selenium-playground/auto-healing/")
        page.wait_for_timeout(3000)

        # 🔴 DELIBERATELY WRONG LOCATOR — no try/except
        # The real field id is 'username', but we're asking for 'wrong_field_id'
        # HealingPage should catch the timeout, ask AI, find the right field,
        # and fill it — all without crashing the script.
        page.locator("#wrongname").fill("test_user")

        print("✅ Script finished — check above for healing logs")

        page.wait_for_timeout(10000)
        context.close()
        browser.close()


if __name__ == "__main__":
    run()