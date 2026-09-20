from pathlib import Path
from playwright.sync_api import sync_playwright
from healer import self_healing_action

base = Path(__file__).parent.resolve()
v1_path = (base / "login_v1.html").as_uri()
v2_path = (base / "login_v2.html").as_uri()

ORIGINAL_PASSWORD_LOCATOR = "#password"
ORIGINAL_LOGIN_BUTTON = "#login-btn"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("\n=== TEST 1: login_v1.html (everything works normally) ===")
    page.goto(v1_path)
    self_healing_action(page, "#username", "fill", "testuser")
    self_healing_action(page, ORIGINAL_PASSWORD_LOCATOR, "fill", "mypassword123")
    self_healing_action(page, ORIGINAL_LOGIN_BUTTON, "click")
    page.wait_for_timeout(1000)

    print("\n=== TEST 2: login_v2.html (password broken, AI heals) ===")
    page.goto(v2_path)
    self_healing_action(page, "#username", "fill", "testuser")
    self_healing_action(page, ORIGINAL_PASSWORD_LOCATOR, "fill", "mypassword123")
    self_healing_action(page, ORIGINAL_LOGIN_BUTTON, "click")
    page.wait_for_timeout(1500)

    browser.close()