import os
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = os.getenv("LMS_BASE_URL", "https://lms.iqra.edu.pk").rstrip("/")
SESSION_FILE = Path(__file__).parent / "lms_session.json"


class LMSLoginError(Exception):
    pass


def page_text(page):
    try:
        return page.locator("body").inner_text(timeout=10000).strip()
    except Exception:
        return ""


def fetch_lms_data():
    if not SESSION_FILE.exists():
        raise LMSLoginError("LMS session missing. Run save_lms_session.py first.")

    courses = {}
    assignments = {}
    announcements = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            storage_state=str(SESSION_FILE)
        )
        page = context.new_page()

        try:
            page.goto(
                BASE_URL + "/my/courses.php",
                wait_until="domcontentloaded",
                timeout=60000
            )
            page.wait_for_timeout(4000)

            if "login" in page.url.lower():
                raise LMSLoginError(
                    "LMS session expired. Run python save_lms_session.py again."
                )

            course_links = page.locator('a[href*="/course/view.php"]').all()

            for link in course_links:
                href = link.get_attribute("href") or ""
                name = next(
                    (line.strip() for line in link.inner_text().splitlines()
                     if line.strip() and line.strip().lower() != "course name"),
                    ""
                )

                if name.lower() == "course name":
                    continue

                course_id = parse_qs(urlparse(href).query).get("id", [None])[0]

                if not course_id or not name:
                    continue

                courses[course_id] = {
                    "id": course_id,
                    "name": name,
                    "url": urljoin(BASE_URL, href)
                }

            if not courses:
                raise LMSLoginError(
                    "Login verified, but no courses were found."
                )

            for course in courses.values():
                page.goto(
                    course["url"],
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                page.wait_for_timeout(2000)

                assignment_links = page.locator(
                    'a[href*="/mod/assign/view.php"]'
                ).evaluate_all("""
                    links => links.map(link => ({
                        href: link.href,
                        title: link.innerText.trim()
                    }))
                """)

                for link in assignment_links:
                    href = link["href"]
                    title = link["title"]

                    assignment_id = parse_qs(
                        urlparse(href).query
                    ).get("id", [None])[0]

                    if not assignment_id or assignment_id in assignments:
                        continue

                    assignment_url = urljoin(BASE_URL, href)
                    details = ""

                    try:
                        page.goto(
                            assignment_url,
                            wait_until="domcontentloaded",
                            timeout=20000
                        )
                        details = page_text(page)[:5000]
                    except Exception as exc:
                        print("Assignment skipped:", title, str(exc), flush=True)

                    assignments[assignment_id] = {
                        "id": assignment_id,
                        "title": title or "Assignment",
                        "course": course["name"],
                        "url": assignment_url,
                        "details": details
                    }

                page.goto(
                    course["url"],
                    wait_until="domcontentloaded",
                    timeout=45000
                )
                page.wait_for_timeout(1000)

                forum_links = page.locator(
                    'a[href*="/mod/forum/view.php"]'
                ).all()

                for link in forum_links:
                    label = link.inner_text().strip().lower()

                    if "announcement" not in label and "news forum" not in label:
                        continue

                    forum_url = urljoin(
                        BASE_URL,
                        link.get_attribute("href") or ""
                    )

                    try:
                        page.goto(
                            forum_url,
                            wait_until="domcontentloaded",
                            timeout=45000
                        )
                        page.wait_for_timeout(1000)

                        discussions = page.locator(
                            'a[href*="/mod/forum/discuss.php"]'
                        ).all()

                        for discussion in discussions:
                            discussion_href = discussion.get_attribute("href") or ""
                            title = discussion.inner_text().strip()

                            discussion_id = parse_qs(
                                urlparse(discussion_href).query
                            ).get("d", [None])[0]

                            if not discussion_id:
                                continue

                            if discussion_id in announcements:
                                continue

                            discussion_url = urljoin(
                                BASE_URL, discussion_href
                            )

                            try:
                                page.goto(
                                    discussion_url,
                                    wait_until="domcontentloaded",
                                    timeout=45000
                                )
                                page.wait_for_timeout(800)
                                body = page_text(page)[:4000]
                            except Exception:
                                body = ""

                            announcements[discussion_id] = {
                                "id": discussion_id,
                                "title": title or "Announcement",
                                "course": course["name"],
                                "body": body,
                                "url": discussion_url
                            }

                    except Exception:
                        continue

            return {
                "courses": list(courses.values()),
                "assignments": list(assignments.values()),
                "announcements": list(announcements.values())
            }

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    try:
        data = fetch_lms_data()
        print("LMS connection successful!")
        print("Courses:", len(data["courses"]))
        print("Assignments:", len(data["assignments"]))
        print("Announcements:", len(data["announcements"]))

        for item in data["courses"]:
            print("-", item["name"])

    except Exception as exc:
        print("LMS connection failed:", exc)
