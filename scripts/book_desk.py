# scripts/book_desk.py
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import os
import sys

# Read secrets from environment variables (set these as GitHub Actions secrets)
EMAIL = os.environ.get("BOOKER_EMAIL")
PASSWORD = os.environ.get("BOOKER_PASSWORD")
BOOKING_URL = os.environ.get("BOOKING_URL")
DESK_ID = os.environ.get("BOOKER_DESK", "08")  # default desk 08

# Fail fast if secrets are missing
if not EMAIL or not PASSWORD or not BOOKING_URL:
    sys.exit("Missing BOOKER_EMAIL, BOOKER_PASSWORD, or BOOKING_URL environment variable")

# Compute Warsaw local date at runtime and add 14 days
warsaw_tz = ZoneInfo("Europe/Warsaw")
today_warsaw = datetime.now(warsaw_tz).date()
TARGET_DATE = today_warsaw + timedelta(days=14)

# Optional: ensure TARGET_DATE weekday matches run intent (not strictly necessary)
# day_name = TARGET_DATE.strftime('%A')
day_str = f"{TARGET_DATE.day:02d}.{TARGET_DATE.month:02d}"  # "DD.MM"
day_name = TARGET_DATE.strftime('%A')

print(f"Local Warsaw date now: {today_warsaw.isoformat()}")
print(f"Booking target date (Warsaw +14d): {TARGET_DATE.isoformat()} ({day_name} {day_str})")
print(f"Booking desk {DESK_ID} for {day_name} {day_str}...")

# Canvas and click coordinates (keep your existing values)
CANVAS_X, CANVAS_Y = 33.5, 97.1875
CANVAS_W, CANVAS_H = 1198, 650
DESK_08_CLICK_X = CANVAS_X + 0.69736981 * CANVAS_W
DESK_08_CLICK_Y = CANVAS_Y + 0.20009786 * CANVAS_H

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        # Login
        page.goto(BOOKING_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.locator('input').first.fill(EMAIL)
        page.wait_for_timeout(300)
        page.click('button:has-text("Continue"), input[value="Continue"]')
        page.wait_for_timeout(3000)
        page.fill('input[type="password"]', PASSWORD)
        page.wait_for_timeout(300)
        page.click('button:has-text("Sign in"), input[value="Sign in"]')
        page.wait_for_timeout(6000)
        for text in ["GOT IT", "OK"]:
            try:
                page.click(f'button:has-text("{text}")', timeout=2000)
            except:
                pass
        print("✅ Logged in")
        # Select Warszawa Inflancka
        page.goto(BOOKING_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.locator('[class*="dropdown"]').first.click()
        page.wait_for_timeout(500)
        page.click('text=Warszawa Inflancka')
        page.wait_for_timeout(2000)
        # Check if target date is in the window
        body = page.inner_text('body')
        if day_str not in body:
            print(f"❌ {day_str} is NOT yet in the booking window (still outside 14 days)")
            print("Window contents (dates visible):")
            for line in body.split('\n'):
                l = line.strip()
                if len(l) == 5 and l[2] == '.' and l[:2].isdigit():
                    print(f"  {l}")
        else:
            print(f"✅ {day_str} is in the booking window!")
            # Find the CHOOSE button row for the target date
            rows = page.locator('[data-day-type="deskAvailable"]')
            target_row = None
            for i in range(rows.count()):
                if day_str in rows.nth(i).inner_text():
                    target_row = rows.nth(i)
                    break
            if not target_row:
                print(f"ℹ️  No CHOOSE button for {day_str} — may already be booked or unavailable")
                # Check if already booked
                if f'{DESK_ID} is yours' in body and day_str in body:
                    print("✅ Already booked!")
            else:
                # Click CHOOSE
                try:
                    target_row.locator('button:has-text("CHOOSE")').click()
                except:
                    target_row.locator('button:has-text("Choose")').click()
                page.wait_for_timeout(3000)
                # Click desk coordinates (adjust if DESK_ID changes)
                page.mouse.click(DESK_08_CLICK_X, DESK_08_CLICK_Y)
                page.wait_for_timeout(1500)
                modal = page.inner_text('body')[:600]
                if f'Selected desk: Warszawa Inflancka / {DESK_ID}' in modal:
                    print(f"✅ Desk {DESK_ID} selected!")
                    page.click('button:has-text("BOOK THIS DESK")')
                    page.wait_for_timeout(4000)
                    print("🎉 Booking submitted!")
                    after = page.inner_text('body')
                    if f'{DESK_ID} is yours' in after:
                        print(f"🎉 CONFIRMED: Desk {DESK_ID} booked for {day_name} {day_str}!")
                    else:
                        print("⚠️ Check site to confirm")
                else:
                    print(f"❌ Desk {DESK_ID} not selectable — taken by a colleague")
                    try:
                        page.click('button:has-text("CANCEL")', timeout=2000)
                    except:
                        pass
    finally:
        browser.close()
