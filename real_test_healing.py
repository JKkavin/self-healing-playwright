from playwright.sync_api import sync_playwright
from healing_page import HealingPage


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = HealingPage(context.new_page())

        # ============ STEP 1: LOGIN ============
        print("\n=== STEP 1: Login ===")
        page.goto("https://pltqa.citiustech.com/uamwebapp/")
        page.wait_for_timeout(3000)

        page.get_by_role("textbox", name="Username or email").fill("Sa")
        page.get_by_role("textbox", name="Password").fill("Password_123")
        page.get_by_role("button", name="Log In").click()
        page.wait_for_timeout(6000)

        # ============ STEP 2: HOME → RMM POPUP ============
        print("\n=== STEP 2: Home page → click RMM heading ===")
        page.goto("https://pltqa.citiustech.com/uamwebapp/#/home")
        page.wait_for_timeout(3000)

        popup = None
        try:
            with page.expect_popup(timeout=15000) as popup_info:
                page.get_by_role("heading", name="Rules Management Module").click(timeout=10000)
            popup = popup_info.value
            print(f"✅ Popup opened: {popup.url[:100]}...")
        except Exception as e:
            print(f"⚠️  Popup trigger failed: {e}")

        # ============ STEP 3: RMM WEBAPP → RULES ============
        if popup:
            print("\n=== STEP 3: RMM app → Rules list ===")
            rmm = HealingPage(popup)
            rmm.wait_for_timeout(5000)

            try:
                rmm.goto("https://pltqa.citiustech.com/rmmwebapp/#/rules/list")
                rmm.wait_for_timeout(5000)
                print(f"✅ Rules list loaded")
            except Exception as e:
                print(f"⚠️  Rules list navigation failed: {e}")

            # ============ STEP 4: AUDIT → MEASURE REPORTS ============
            print("\n=== STEP 4: Audit → Measure Reports ===")
            try:
                rmm.get_by_role("button", name="Audit").click(timeout=10000)
                rmm.wait_for_timeout(1500)
                rmm.get_by_role("menuitem", name="Navigate to Measure Reports").click(timeout=10000)
                rmm.wait_for_timeout(2000)
                print("✅ Navigated to Measure Reports")
            except Exception as e:
                print(f"⚠️  Audit flow failed: {e}")

            # ============ STEP 5: PROCEED → DOWNLOAD ============
            print("\n=== STEP 5: Proceed → Download ===")
            try:
                rmm.get_by_role("button", name="Click here to proceed").click(timeout=10000)
                rmm.wait_for_timeout(2000)

                with rmm._page.expect_download(timeout=20000) as download_info:
                    rmm.get_by_role("link", name="Click here to download report").click(timeout=10000)
                download = download_info.value
                print(f"✅ Download triggered: {download.suggested_filename}")
            except Exception as e:
                print(f"⚠️  Download flow failed: {e}")

        print("\n✅ Full flow complete. Browser stays open 20s for inspection.")
        page.wait_for_timeout(20000)

        context.close()
        browser.close()


if __name__ == "__main__":
    run()