# scripts/book_desk.py
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import sys

# Required secrets from environment variables
EMAIL = os.environ.get("BOOKER_EMAIL")
PASSWORD = os.environ.get("BOOKER_PASSWORD")
BOOKING_URL = os.environ.get("BOOKING_URL")
DESK_ID = os.environ.get("BOOKER_DESK", "08")

# Timezone and office moved to environment so no literals remain in the repo
BOOKER_TIMEZONE = os.environ.get("BOOKER_TIMEZONE")
BOOKER_OFFICE = os.environ.get("BOOKER_OFFICE")

# Optional manual override for booking date in YYYY-MM-DD format
BOOKING_DATE = os.environ.get("BOOKING_DATE")

# Fail fast if required secrets are missing
if not EMAIL or not PASSWORD or not BOOKING_URL:
    sys.exit("Missing BOOKER_EMAIL, BOOKER_PASSWORD, or BOOKING_URL environment variable")

if not BOOKER_TIMEZONE:
    sys.exit("Missing BOOKER_TIMEZONE environment variable")

if not BOOKER_OFFICE:
    sys.exit("Missing BOOKER_OFFICE environment variable")

# Compute target date
if BOOKING_DATE:
    try:
        TARGET_DATE = datetime.fromisoformat(BOOKING_DATE).date()
    except Exception:
        sys.exit("Invalid BOOKING_DATE format; expected YYYY-MM-DD")
else:
    tz = ZoneInfo(BOOKER_TIMEZONE)
    today_local = datetime.now(tz).date()
    TARGET_DATE = today_local + timedelta(days=14)

day_str = f"{TARGET_DATE.day:02d}.{TARGET_DATE.month:02d}"
day_name = TARGET_DATE.strftime('%A')

# Print only non-secret operational info
print(f"Local date now: {datetime.now(ZoneInfo(BOOKER_TIMEZONE)).date().isoformat()}")
print(f"Booking target date: {TARGET_DATE.isoformat()} {day_name} {day_str}")
print(f"Booking desk {DESK_ID} for {day_name} {day_str}...")

# Canvas and click coordinates
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

        # Navigate to booking page and select office using env value
        page.goto(BOOKING_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.locator('[class*="dropdown"]').first.click()
        page.wait_for_timeout(500)
        page.click(f'text={BOOKER_OFFICE}')
        page.wait_for_timeout(2000)

        # Check if target date is in the booking window
        body = page.inner_text('body')
        if day_str not in body:
            print(f"❌ {day_str} is NOT yet in the booking window")
            print("Window contents (dates visible):")
            for line in body.split('\n'):
                l = line.strip()
                if len(l) == 5 and l[2] == '.' and l[:2].isdigit():
                    print(f"  {l}")
        else:
            print(f"✅ {day_str} is in the booking window")
            rows = page.locator('[data-day-type="deskAvailable"]')
            target_row = None
            for i in range(rows.count()):
                if day_str in rows.nth(i).inner_text():
                    target_row = rows.nth(i)
                    break
            if not target_row:
                print(f"ℹ️  No CHOOSE button for {day_str}")
                if f'{DESK_ID} is yours' in body and day_str in body:
                    print("✅ Already booked")
            else:
                try:
                    target_row.locator('button:has-text("CHOOSE")').click()
                except:
                    target_row.locator('button:has-text("Choose")').click()
                page.wait_for_timeout(3000)
                page.mouse.click(DESK_08_CLICK_X, DESK_08_CLICK_Y)
                page.wait_for_timeout(1500)
                modal = page.inner_text('body')[:600]
                if f'Selected desk: {BOOKER_OFFICE} / {DESK_ID}' in modal:
                    print(f"✅ Desk {DESK_ID} selected")
                    page.click('button:has-text("BOOK THIS DESK")')
                    page.wait_for_timeout(4000)
                    print("🎉 Booking submitted")
                    after = page.inner_text('body')
                    if f'{DESK_ID} is yours' in after:
                        print(f"🎉 CONFIRMED: Desk {DESK_ID} booked for {day_name} {day_str}")
                    else:
                        print("⚠️ Check site to confirm")
                else:
                    print(f"❌ Desk {DESK_ID} not selectable")
                    try:
                        page.click('button:has-text("CANCEL")', timeout=2000)
                    except:
                        pass
    finally:
        browser.close()
