#!/usr/bin/env python3
"""
Iqra University LMS -> Discord watcher  (ALL-IN-ONE FILE)
==========================================================

Har 15 minute baad student ke taur par LMS mein login karta hai, announcements
aur assignments scrape karta hai, pichli baar se compare karta hai, aur sirf
NAYE items Discord webhook par embeds ki shakal mein post karta hai.

Scraped data
------------
  Announcements : title, body, posted_at, course_code
  Assignments   : title, course, due_date, submitted (yes/no)

SETUP
-----
  1. pip install playwright requests python-dotenv
     playwright install chromium

  2. python lms_discord_bot.py --init
     (yeh `.env.example` bana dega; usay `.env` mein copy karke bharo)

  3. Discord webhook: Channel settings > Integrations > Webhooks > New Webhook
     > Copy URL  -> DISCORD_WEBHOOK_URL

  4. SELECTORS (zaroori, ek baar): neeche SELECTORS dict placeholder hai kyun ke
     har LMS ka HTML alag hota hai. Chalao:
         python lms_discord_bot.py --once --debug
     Yeh browser kholta hai aur ./debug/ mein HTML + screenshot save karta hai.
     Page par right-click > Inspect karke SELECTORS dict update karo, jab tak
     log mein sahi counts na aayein, e.g. "Scraped 12 announcements, 8 assignments".

RUN
---
  python lms_discord_bot.py            # loop, har POLL_INTERVAL_MINUTES baad
  python lms_discord_bot.py --once     # ek cycle (cron ke liye)
  cron:  */15 * * * * cd /path && python lms_discord_bot.py --once >> watcher.log 2>&1

DIFFING
-------
  * Har item ka ID = hash(course, title, date); dekhe hue IDs state.json mein.
  * Pehli run silently state seed karti hai (backlog post nahi hota).
    POST_BACKLOG_ON_FIRST_RUN=true karo to sab post hoga.
  * State sirf Discord post kamyab hone ke BAAD save hota hai.
  * state.json delete karo to reset ho jata hai.

NOTES
-----
  * .env aur state.json ko git mein mat daalo.
  * CAPTCHA/MFA ho to headless login kaam nahi karega.
  * University ki acceptable-use policy check karlo; 15 min se kam interval mat rakho.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright, TimeoutError as PWTimeout

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

STATE_FILE = Path(os.getenv("STATE_FILE", BASE_DIR / "state.json"))
DEBUG_DIR = BASE_DIR / "debug"

log = logging.getLogger("lms-watcher")

# ===========================================================================
# .env.example template (python lms_discord_bot.py --init  se file ban jati hai)
# ===========================================================================
ENV_EXAMPLE = """\
# --- LMS credentials (apna student account) ---
LMS_USERNAME=your_student_id
LMS_PASSWORD=your_password

# --- LMS URLs (browser ki address bar se copy karo) ---
LMS_LOGIN_URL=https://your-lms-domain/login
LMS_ANNOUNCEMENTS_URL=https://your-lms-domain/announcements
LMS_ASSIGNMENTS_URL=https://your-lms-domain/assignments

# --- Discord ---
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXXXXXX/XXXXXXXX
# Optional: naye items par @mention ke liye role ID (khali = no ping)
DISCORD_PING_ROLE_ID=

# --- Behaviour ---
POLL_INTERVAL_MINUTES=15
# false = pehli run sirf maujooda items yaad rakhegi, post nahi karegi
POST_BACKLOG_ON_FIRST_RUN=false
HEADLESS=true
# STATE_FILE=./state.json
"""

# ===========================================================================
# CSS SELECTORS  -- PLACEHOLDERS! Apne LMS ke HTML ke mutabiq badlo.
# "item" = repeating row/card; baaqi field selectors item ke ANDAR ke hain.
# ===========================================================================
SELECTORS = {
    "login": {
        "username": "input[name='username'], input#username, input[type='text']",
        "password": "input[name='password'], input#password, input[type='password']",
        "submit": "button[type='submit'], input[type='submit']",
        "success_marker": "",  # optional: koi element jo sirf login ke baad dikhe
    },
    "announcements": {
        "item": ".announcement, .announcement-item, .card.announcement",
        "title": ".title, h3, h4",
        "body": ".body, .content, .message",
        "posted_at": ".date, .posted, time",
        "course_code": ".course, .course-code",
        "course_code_regex": r"[A-Z]{2,4}\s?-?\d{3,4}",
    },
    "assignments": {
        "item": "table.assignments tbody tr, .assignment, .assignment-item",
        "title": ".title, td:nth-child(1), a",
        "course": ".course, td:nth-child(2)",
        "due_date": ".due, .due-date, td:nth-child(3)",
        "status": ".status, td:nth-child(4)",
        "submitted_regex": r"submitted|turned in|completed|done",
        "not_submitted_regex": r"not submitted|no submission|pending|missing|not turned in",
    },
}

# ------------------------------------------------------------------ config --


def env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and not val:
        sys.exit(f"Missing required env var: {name} (run --init, phir .env bharo)")
    return val or ""


@dataclass
class Config:
    username: str
    password: str
    webhook_url: str
    login_url: str
    announcements_url: str
    assignments_url: str
    interval_min: int
    post_backlog_on_first_run: bool
    ping_role_id: str
    headless: bool

    @classmethod
    def load(cls, debug: bool = False) -> "Config":
        return cls(
            username=env("LMS_USERNAME", required=True),
            password=env("LMS_PASSWORD", required=True),
            webhook_url=env("DISCORD_WEBHOOK_URL", required=True),
            login_url=env("LMS_LOGIN_URL", required=True),
            announcements_url=env("LMS_ANNOUNCEMENTS_URL", required=True),
            assignments_url=env("LMS_ASSIGNMENTS_URL", required=True),
            interval_min=int(env("POLL_INTERVAL_MINUTES", "15")),
            post_backlog_on_first_run=env("POST_BACKLOG_ON_FIRST_RUN", "false").lower() == "true",
            ping_role_id=env("DISCORD_PING_ROLE_ID", ""),
            headless=not debug and env("HEADLESS", "true").lower() == "true",
        )


# ------------------------------------------------------------------ models --


def sha(*parts: str) -> str:
    norm = "|".join(re.sub(r"\s+", " ", p).strip().lower() for p in parts)
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


@dataclass
class Announcement:
    title: str
    body: str
    posted_at: str
    course_code: str

    @property
    def uid(self) -> str:
        return sha("ann", self.course_code, self.title, self.posted_at)


@dataclass
class Assignment:
    title: str
    course: str
    due_date: str
    submitted: bool

    @property
    def uid(self) -> str:
        # submitted flag ID mein shamil nahi: status badalne par dobara post nahi hoga
        return sha("asg", self.course, self.title, self.due_date)


# ---------------------------------------------------------------- scraping --


def clean(text: str | None) -> str:
    return re.sub(r"[ \t]+", " ", (text or "")).strip()


def field(el, selector: str) -> str:
    if not selector:
        return ""
    node = el.query_selector(selector)
    return clean(node.inner_text()) if node else ""


def dump_debug(page: Page, name: str) -> None:
    DEBUG_DIR.mkdir(exist_ok=True)
    (DEBUG_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(DEBUG_DIR / f"{name}.png"), full_page=True)


def login(page: Page, cfg: Config) -> None:
    s = SELECTORS["login"]
    page.goto(cfg.login_url, wait_until="domcontentloaded")
    page.fill(s["username"], cfg.username)
    page.fill(s["password"], cfg.password)
    page.click(s["submit"])
    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except PWTimeout:
        pass
    if page.query_selector(s["password"]) and page.is_visible(s["password"]):
        dump_debug(page, "login_failed")
        raise RuntimeError("Login failed (password field abhi bhi nazar aa rahi hai). Credentials/selectors check karo.")
    if s.get("success_marker") and not page.query_selector(s["success_marker"]):
        dump_debug(page, "login_unverified")
        raise RuntimeError("Login success marker nahi mila. SELECTORS['login']['success_marker'] check karo.")


def scrape_announcements(page: Page, cfg: Config) -> list[Announcement]:
    s = SELECTORS["announcements"]
    page.goto(cfg.announcements_url, wait_until="networkidle")
    items: list[Announcement] = []
    for el in page.query_selector_all(s["item"]):
        title = field(el, s["title"])
        if not title:
            continue
        course = field(el, s["course_code"])
        rx = s.get("course_code_regex")
        if rx and (m := re.search(rx, course or title)):
            course = m.group(0)
        items.append(Announcement(title, field(el, s["body"]), field(el, s["posted_at"]), course))
    return items


def scrape_assignments(page: Page, cfg: Config) -> list[Assignment]:
    s = SELECTORS["assignments"]
    page.goto(cfg.assignments_url, wait_until="networkidle")
    yes = re.compile(s["submitted_regex"], re.I)
    no = re.compile(s["not_submitted_regex"], re.I) if s.get("not_submitted_regex") else None
    items: list[Assignment] = []
    for el in page.query_selector_all(s["item"]):
        title = field(el, s["title"])
        if not title:
            continue
        status_text = field(el, s["status"]) if s.get("status") else clean(el.inner_text())
        submitted = bool(yes.search(status_text)) and not (no and no.search(status_text))
        items.append(Assignment(title, field(el, s["course"]), field(el, s["due_date"]), submitted))
    return items


# ------------------------------------------------------------------- state --


def load_state() -> dict | None:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


# ----------------------------------------------------------------- discord --

BLUE, ORANGE, GREEN, RED = 0x3B82F6, 0xF59E0B, 0x22C55E, 0xEF4444


def trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def announcement_embed(a: Announcement) -> dict:
    return {
        "title": trunc(f"📢 {a.title}", 256),
        "description": trunc(a.body or "_(no body)_", 1800),
        "color": BLUE,
        "fields": [
            {"name": "Course", "value": a.course_code or "—", "inline": True},
            {"name": "Posted", "value": a.posted_at or "—", "inline": True},
        ],
        "footer": {"text": "Iqra University LMS • Announcement"},
        "timestamp": now_iso(),
    }


def assignment_embed(a: Assignment) -> dict:
    return {
        "title": trunc(f"📝 {a.title}", 256),
        "color": GREEN if a.submitted else ORANGE,
        "fields": [
            {"name": "Course", "value": a.course or "—", "inline": True},
            {"name": "Due", "value": a.due_date or "—", "inline": True},
            {"name": "Submitted", "value": "✅ Yes" if a.submitted else "❌ No", "inline": True},
        ],
        "footer": {"text": "Iqra University LMS • Assignment"},
        "timestamp": now_iso(),
    }


def embed_size(e: dict) -> int:
    n = len(e.get("title", "")) + len(e.get("description", "")) + len(e.get("footer", {}).get("text", ""))
    return n + sum(len(f["name"]) + len(f["value"]) for f in e.get("fields", []))


def batches(embeds: list[dict]):
    """Discord limit: 10 embeds aur 6000 chars total per message."""
    cur: list[dict] = []
    size = 0
    for e in embeds:
        s = embed_size(e)
        if cur and (len(cur) == 10 or size + s > 5500):
            yield cur
            cur, size = [], 0
        cur.append(e)
        size += s
    if cur:
        yield cur


def post_embeds(cfg: Config, embeds: list[dict], content: str = "") -> None:
    for chunk in batches(embeds):
        payload = {"embeds": chunk, "username": "Iqra LMS", "allowed_mentions": {"parse": ["roles"]}}
        if content:
            payload["content"] = content
            content = ""  # ping sirf ek baar
        for _ in range(5):
            r = requests.post(cfg.webhook_url, json=payload, timeout=20)
            if r.status_code == 429:
                wait = float(r.json().get("retry_after", 2))
                log.warning("Discord rate limit, %.1fs sleep", wait)
                time.sleep(wait + 0.5)
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError("Discord webhook baar baar 429 de raha hai")
        time.sleep(1)


def post_error(cfg: Config, err: Exception) -> None:
    try:
        post_embeds(cfg, [{
            "title": "⚠️ LMS watcher error",
            "description": trunc(str(err), 1500),
            "color": RED,
            "timestamp": now_iso(),
        }])
    except Exception:  # noqa: BLE001
        log.exception("Error embed post nahi ho saka")


# -------------------------------------------------------------------- main --


def run_once(cfg: Config, debug: bool = False) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=cfg.headless)
        ctx = browser.new_context()
        ctx.set_default_timeout(30_000)
        page = ctx.new_page()
        try:
            login(page, cfg)
            announcements = scrape_announcements(page, cfg)
            if debug:
                dump_debug(page, "announcements")
            assignments = scrape_assignments(page, cfg)
            if debug:
                dump_debug(page, "assignments")
        finally:
            browser.close()

    log.info("Scraped %d announcements, %d assignments", len(announcements), len(assignments))

    state = load_state()
    first_run = state is None
    state = state or {"announcements": [], "assignments": []}
    seen_a, seen_s = set(state["announcements"]), set(state["assignments"])

    new_a = [a for a in announcements if a.uid not in seen_a]
    new_s = [a for a in assignments if a.uid not in seen_s]

    if first_run and not cfg.post_backlog_on_first_run:
        log.info("Pehli run: %d items state mein seed kiye, post nahi kiye.", len(new_a) + len(new_s))
        new_a, new_s = [], []
    else:
        log.info("Naye: %d announcements, %d assignments", len(new_a), len(new_s))

    embeds = [announcement_embed(a) for a in reversed(new_a)] + [assignment_embed(a) for a in reversed(new_s)]
    if embeds:
        ping = f"<@&{cfg.ping_role_id}>" if cfg.ping_role_id else ""
        post_embeds(cfg, embeds, content=ping)

    # State post kamyab hone ke baad hi save hota hai, warna agli cycle retry karegi
    state["announcements"] = sorted(seen_a | {a.uid for a in announcements})
    state["assignments"] = sorted(seen_s | {a.uid for a in assignments})
    save_state(state)


def main() -> None:
    ap = argparse.ArgumentParser(description="Iqra LMS -> Discord watcher")
    ap.add_argument("--init", action="store_true", help=".env.example file bana do aur exit")
    ap.add_argument("--once", action="store_true", help="ek cycle chalao aur exit")
    ap.add_argument("--debug", action="store_true", help="visible browser + ./debug mein HTML/screenshots")
    args = ap.parse_args()

    if args.init:
        target = BASE_DIR / ".env.example"
        target.write_text(ENV_EXAMPLE, encoding="utf-8")
        print(f"Bana diya: {target}\nAb usay `.env` naam se copy karo aur values bharo.")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Config.load(debug=args.debug)

    last_error = ""
    while True:
        try:
            run_once(cfg, debug=args.debug)
            last_error = ""
        except Exception as e:  # noqa: BLE001
            log.exception("Cycle fail hui")
            if str(e) != last_error:  # same error baar baar channel mein spam na ho
                post_error(cfg, e)
                last_error = str(e)
            if args.once:
                sys.exit(1)
        if args.once:
            return
        time.sleep(cfg.interval_min * 60)


if __name__ == "__main__":
    main()
