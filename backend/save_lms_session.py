import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
URL = os.getenv("LMS_BASE_URL", "https://lms.iqra.edu.pk").rstrip("/")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(URL + "/login/index.php")

    input("Microsoft 365 se login karo. Dashboard open ho jaye to ENTER dabao...")

    title = page.title()
    body = page.locator("body").inner_text()

    if "Dashboard" in title and "My courses" in body:
        context.storage_state(path="lms_session.json")
        print("SUCCESS: Session save ho gayi!")
    else:
        print("ERROR: Dashboard verify nahi hua.")
        print("Page title:", title)

    browser.close()
