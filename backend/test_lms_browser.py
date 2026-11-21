import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

url = os.getenv("LMS_BASE_URL", "https://lms.iqra.edu.pk")
username = os.getenv("LMS_USERNAME")
password = os.getenv("LMS_PASSWORD")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(url + "/login/index.php", wait_until="domcontentloaded")
    print("Login page:", page.title())

    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(password)
    page.locator('button[type="submit"], input[type="submit"]').first.click()

    page.wait_for_load_state("domcontentloaded")
    print("Current URL:", page.url)
    print("Page title:", page.title())

    if "/login/" not in page.url:
        print("Login may be successful. Checking dashboard...")
    else:
        print("Login may have failed.")
        print("Page message:", page.locator("body").inner_text()[:1000])

    browser.close()
