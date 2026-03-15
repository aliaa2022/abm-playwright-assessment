"""
================================================================================
  Task 1 — Stealth Assessment: Cloudflare Turnstile Automation
  Target: https://cd.captchaaiplus.com/turnstile.html
================================================================================

  WHAT THIS SCRIPT DOES:
  ─────────────────────
  1. Opens the Turnstile CAPTCHA page in a real Chromium browser
  2. Applies stealth patches so Cloudflare doesn't detect automation
  3. Waits for the Turnstile widget to load and clicks the checkbox
  4. Extracts the token, clicks Submit, and captures the success message
  5. Repeats 10 times, records a video, and reports the success rate

  INSTALL:
  ────────
    pip install playwright requests
    pip install playwright-stealth          ← anti-detection patches
    playwright install chromium

  RUN:
  ────
    python turnstile_automation.py          ← headless=False (visible window)
    python turnstile_automation.py --headless ← headless=True (invisible)

================================================================================
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# playwright-stealth patches ~30 browser properties that reveal automation
# Install with: pip install playwright-stealth
try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("[!] playwright-stealth not installed. Run: pip install playwright-stealth")
    print("    Continuing without stealth patches (lower success rate expected).\n")


# ── Configuration ─────────────────────────────────────────────────────────────

TARGET_URL    = "https://cd.captchaaiplus.com/turnstile.html"
MAX_ATTEMPTS  = 10          # Total attempts to run
SUCCESS_GOAL  = 0.60        # 60% minimum success rate
VIDEO_DIR     = Path("videos")   # Folder where Playwright saves .webm recordings
RESULTS_FILE  = "results.json"   # Final attempt log saved here

# Run headless or visible based on command-line flag
# --headless flag → headless=True (no window, faster)
# no flag        → headless=False (window visible, easier to debug)
HEADLESS = "--headless" in sys.argv


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 1 — build_context(playwright, attempt_number)
#
#  PURPOSE:
#    Creates a fresh browser + context for every attempt.
#    Each attempt gets its own clean context so cookies, storage, and
#    fingerprints don't carry over from previous runs.
#
#    KEY: We pass record_video_dir so Playwright automatically records
#    a .webm video of everything that happens in this context.
#
#  RETURNS: (browser, context, page)
# ══════════════════════════════════════════════════════════════════════════════

def build_context(playwright, attempt_number: int):
    """
    Launches a fresh Chromium browser with stealth settings and video recording.
    Returns the browser, context, and a new page (tab).
    """

    VIDEO_DIR.mkdir(exist_ok=True)   # Create videos/ folder if it doesn't exist

    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",  # Hide automation flag
            "--window-size=1280,800",
        ]
    )

    # new_context = a fresh browser profile (own cookies, storage, JS state)
    # record_video_dir = Playwright records .webm automatically while context is open
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        # Mimic a real Windows + Chrome user
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        # Tell Playwright to record video of this context to the videos/ folder
        record_video_dir=str(VIDEO_DIR),
        record_video_size={"width": 1280, "height": 800},
        # Locale and timezone help reduce bot-detection signals
        locale="en-US",
        timezone_id="America/New_York",
    )

    page = context.new_page()
    return browser, context, page


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 2 — apply_stealth(page)
#
#  PURPOSE:
#    Applies ~30 JavaScript patches to the page BEFORE it navigates anywhere.
#    These patches hide telltale signs that the browser is automated:
#
#    • navigator.webdriver = false        (normally "true" in automation)
#    • navigator.plugins has real entries  (normally empty in headless)
#    • window.chrome object exists        (missing in headless Chrome)
#    • WebGL renderer/vendor = real GPU   (returns "SwiftShader" in headless)
#    • navigator.languages has real value
#    • Removes "HeadlessChrome" from userAgent
#
#    Without these, Cloudflare's JS challenge detects automation in <1 second.
# ══════════════════════════════════════════════════════════════════════════════

def apply_stealth(page) -> None:
    """
    Patches the page's JavaScript environment to hide automation fingerprints.
    Must be called BEFORE page.goto() so patches run before any page JS loads.
    """

    if STEALTH_AVAILABLE:
        # playwright-stealth applies all patches in one call
        stealth_sync(page)
        print("    [stealth] Stealth patches applied via playwright-stealth.")
    else:
        # Manual fallback patches if playwright-stealth is not installed
        # These cover the most obvious detection signals
        page.add_init_script("""
            // 1. Hide webdriver flag — most basic automation detector
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });

            // 2. Add fake plugin list — headless Chrome has 0 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin' },
                    { name: 'Chrome PDF Viewer' },
                    { name: 'Native Client' }
                ]
            });

            // 3. Add window.chrome — missing in headless mode
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // 4. Fix permission query — headless behaves differently here
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(params);
        """)
        print("    [stealth] Manual fallback patches applied.")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 3 — open_page(page, url)
#
#  PURPOSE:
#    Navigates to the target URL and waits until the DOM is interactive.
#    We use "domcontentloaded" (not "networkidle") because Turnstile loads
#    asynchronously — waiting for full network idle can time out.
# ══════════════════════════════════════════════════════════════════════════════

def open_page(page, url: str) -> None:
    """
    Navigates to the URL and waits for the DOM to be ready.
    """

    print(f"    [nav] Opening: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    # Small pause: gives Turnstile's JavaScript time to inject the iframe
    page.wait_for_timeout(2000)
    print("    [nav] Page DOM ready.")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 4 — wait_for_turnstile_iframe(page)
#
#  PURPOSE:
#    Turnstile renders as a sandboxed <iframe> injected dynamically by
#    Cloudflare's JavaScript. We must wait for this iframe to appear
#    before we can interact with anything inside it.
#
#    The iframe's src contains "challenges.cloudflare.com/turnstile"
#    so we search for that selector pattern.
#
#  RETURNS: The FrameLocator object that lets us interact inside the iframe
# ══════════════════════════════════════════════════════════════════════════════

def wait_for_turnstile_iframe(page):
    """
    Waits for Cloudflare's Turnstile iframe to appear in the DOM.
    Returns a FrameLocator that lets us select elements inside the iframe.
    """

    print("    [turnstile] Waiting for Turnstile iframe...")

    # Wait up to 15 seconds for any iframe whose src contains "turnstile"
    # page.wait_for_selector() blocks until the element exists in the DOM
    page.wait_for_selector(
        "iframe[src*='turnstile'], iframe[src*='challenges.cloudflare.com']",
        timeout=15000
    )

    # frame_locator() returns a special locator scoped to the iframe's DOM
    # All .locator() calls on this object search inside the iframe, not the main page
    iframe_locator = page.frame_locator(
        "iframe[src*='turnstile'], iframe[src*='challenges.cloudflare.com']"
    )

    print("    [turnstile] Iframe found.")
    return iframe_locator


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 5 — click_turnstile_checkbox(iframe_locator)
#
#  PURPOSE:
#    Inside the Turnstile iframe there is a checkbox input with
#    the label "Verify you are human".
#    We locate it and click it — this triggers Cloudflare's verification.
#
#    IMPORTANT: We use a human-like click (small delay before clicking)
#    and wait for the checkbox to be visible before clicking.
# ══════════════════════════════════════════════════════════════════════════════

def click_turnstile_checkbox(iframe_locator) -> None:
    """
    Locates and clicks the Turnstile checkbox inside the iframe.
    Uses human-like timing to avoid instant-click detection.
    """

    print("    [turnstile] Locating checkbox...")

    # The Turnstile checkbox has role="checkbox" inside the iframe
    # We try multiple selectors in case Cloudflare changes the DOM
    checkbox = iframe_locator.locator(
        "input[type='checkbox'], [role='checkbox'], .cf-turnstile-wrapper, #cf-chl-widget-turnstile"
    ).first

    # Wait until the checkbox is visible on screen before clicking
    checkbox.wait_for(state="visible", timeout=10000)

    # Small random-ish pause before clicking — humans don't click instantly
    time.sleep(0.8)

    print("    [turnstile] Clicking checkbox...")
    checkbox.click()


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 6 — wait_for_verification(page, iframe_locator)
#
#  PURPOSE:
#    After clicking, Turnstile either:
#      A) Passes immediately (simple visitors) → checkbox turns green ✓
#      B) Shows an image challenge → user must solve it
#      C) Blocks (bot detected) → no response token generated
#
#    We poll for up to 20 seconds waiting for the token to appear.
#    The token is stored in a hidden <input> named "cf-turnstile-response"
#    on the MAIN page (not the iframe).
#
#  RETURNS: token string if verified, None if failed/timed out
# ══════════════════════════════════════════════════════════════════════════════

def wait_for_verification(page, iframe_locator) -> str | None:
    """
    Polls for the Turnstile response token for up to 20 seconds.
    Returns the token string on success, or None on failure.
    """

    print("    [turnstile] Waiting for verification...")

    deadline = time.time() + 20   # Give up after 20 seconds

    while time.time() < deadline:

        # METHOD 1: Check the hidden input on the main page
        # Cloudflare writes the token into <input name="cf-turnstile-response">
        token = page.evaluate("""
            () => {
                const input = document.querySelector(
                    'input[name="cf-turnstile-response"]'
                );
                return input ? input.value : null;
            }
        """)

        if token and len(token) > 10:
            print(f"    [turnstile] ✓ Token received ({len(token)} chars)")
            return token

        # METHOD 2: Check if the success checkmark appeared in the iframe
        try:
            success = iframe_locator.locator(
                "[class*='success'], [class*='checked'], svg[aria-label*='success']"
            ).is_visible()
            if success:
                # Re-check the input — token may now be present
                token = page.evaluate("""
                    () => {
                        const input = document.querySelector(
                            'input[name="cf-turnstile-response"]'
                        );
                        return input ? input.value : null;
                    }
                """)
                if token:
                    return token
        except Exception:
            pass

        # Poll every 500ms — not too fast (looks bot-like), not too slow
        time.sleep(0.5)

    print("    [turnstile] ✗ Verification timed out.")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 7 — click_submit(page)
#
#  PURPOSE:
#    After the Turnstile token is obtained, clicks the Submit button.
#    The form sends the token to the server for validation.
# ══════════════════════════════════════════════════════════════════════════════

def click_submit(page) -> None:
    """
    Clicks the submit button on the main page.
    Waits for the button to be visible and enabled first.
    """

    print("    [submit] Clicking submit button...")

    # Locate the submit button — try common patterns
    submit_btn = page.locator(
        "button[type='submit'], input[type='submit'], button:has-text('Submit')"
    ).first

    submit_btn.wait_for(state="visible", timeout=5000)
    submit_btn.click()


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 8 — get_success_message(page)
#
#  PURPOSE:
#    After submitting, the page shows a success message if the token was valid.
#    We wait for this message to appear and return its text.
#    This is our final proof that the entire flow worked end-to-end.
#
#  RETURNS: success message string or None if not found
# ══════════════════════════════════════════════════════════════════════════════

def get_success_message(page) -> str | None:
    """
    Waits for the post-submit success message to appear.
    Returns the message text or None if it doesn't appear within 10 seconds.
    """

    try:
        # Wait for any element containing typical success keywords
        page.wait_for_selector(
            "text=success, text=verified, text=passed, [class*='success'], [id*='success']",
            timeout=10000
        )

        # Extract the visible text of the success element
        message = page.locator(
            "text=success, text=verified, [class*='success'], [id*='result']"
        ).first.inner_text()

        return message.strip()

    except PWTimeout:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 9 — run_single_attempt(playwright, attempt_num)
#
#  PURPOSE:
#    Runs the full end-to-end flow for one attempt:
#      1. Build browser context (with video recording)
#      2. Apply stealth
#      3. Open page
#      4. Wait for Turnstile iframe
#      5. Click checkbox
#      6. Wait for token
#      7. Click submit
#      8. Capture success message
#      9. Close browser (video is saved automatically)
#
#  RETURNS: dict with attempt result data
# ══════════════════════════════════════════════════════════════════════════════

def run_single_attempt(playwright, attempt_num: int) -> dict:
    """
    Runs one complete Turnstile verification attempt.
    Returns a result dictionary: success, token, message, error, video_path.
    """

    print(f"\n{'─'*55}")
    print(f"  Attempt {attempt_num}/{MAX_ATTEMPTS}   [headless={HEADLESS}]")
    print(f"{'─'*55}")

    result = {
        "attempt":    attempt_num,
        "success":    False,
        "token":      None,
        "message":    None,
        "error":      None,
        "video_path": None,
        "timestamp":  datetime.now().isoformat(),
    }

    browser  = None
    context  = None

    try:
        # ── Build browser + context (video recording starts here) ────────────
        browser, context, page = build_context(playwright, attempt_num)

        # ── Stealth patches BEFORE navigation ────────────────────────────────
        apply_stealth(page)

        # ── Navigate to the page ─────────────────────────────────────────────
        open_page(page, TARGET_URL)

        # ── Find the Turnstile iframe ─────────────────────────────────────────
        iframe_loc = wait_for_turnstile_iframe(page)

        # ── Click the checkbox ───────────────────────────────────────────────
        click_turnstile_checkbox(iframe_loc)

        # ── Wait for the token ───────────────────────────────────────────────
        token = wait_for_verification(page, iframe_loc)

        if not token:
            result["error"] = "No token received — verification failed"
            return result

        result["token"] = token
        print(f"    [token] {token[:40]}...{token[-10:]}")

        # ── Submit the form ──────────────────────────────────────────────────
        click_submit(page)

        # ── Capture success message ───────────────────────────────────────────
        message = get_success_message(page)

        if message:
            result["success"] = True
            result["message"] = message
            print(f"    [result] ✓ SUCCESS — {message}")
        else:
            result["error"] = "Token obtained but no success message after submit"
            print("    [result] ✗ FAIL — no success message after submit")

        # Brief pause so the video captures the final state
        page.wait_for_timeout(1500)

    except Exception as e:
        result["error"] = str(e)
        print(f"    [error] Exception: {e}")

    finally:
        # Close context FIRST — this triggers Playwright to finalise the video
        if context:
            context.close()
            # Playwright saves videos as {VIDEO_DIR}/{uuid}.webm
            # We grab the most recently modified file in the video dir
            video_files = sorted(
                VIDEO_DIR.glob("*.webm"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            if video_files:
                new_name = VIDEO_DIR / f"attempt_{attempt_num:02d}.webm"
                video_files[0].rename(new_name)
                result["video_path"] = str(new_name)
                print(f"    [video] Saved → {new_name}")

        if browser:
            browser.close()

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 10 — run_all_attempts()
#
#  PURPOSE:
#    Orchestrates all 10 attempts, collects results, calculates the
#    success rate, prints a final summary, and saves results.json.
# ══════════════════════════════════════════════════════════════════════════════

def run_all_attempts() -> None:
    """
    Runs all 10 attempts sequentially, prints a summary, and saves results.
    """

    print("=" * 55)
    print(f"  Turnstile Automation — {MAX_ATTEMPTS} Attempts")
    print(f"  Mode: {'headless' if HEADLESS else 'visible window'}")
    print(f"  Target success rate: {int(SUCCESS_GOAL * 100)}%")
    print("=" * 55)

    all_results = []

    # sync_playwright() manages the Playwright server lifecycle
    # We keep it open across all attempts to avoid startup overhead
    with sync_playwright() as pw:
        for i in range(1, MAX_ATTEMPTS + 1):
            result = run_single_attempt(pw, i)
            all_results.append(result)

            # Small gap between attempts — helps avoid rate limiting
            if i < MAX_ATTEMPTS:
                print(f"  [pause] Waiting 3s before next attempt...")
                time.sleep(3)

    # ── Calculate and display final stats ────────────────────────────────────
    successes    = sum(1 for r in all_results if r["success"])
    failures     = MAX_ATTEMPTS - successes
    success_rate = successes / MAX_ATTEMPTS

    print("\n" + "=" * 55)
    print("  FINAL RESULTS")
    print("=" * 55)
    print(f"  Total attempts : {MAX_ATTEMPTS}")
    print(f"  Successes      : {successes}")
    print(f"  Failures       : {failures}")
    print(f"  Success rate   : {success_rate:.0%}")
    print(f"  Goal met       : {'✓ YES' if success_rate >= SUCCESS_GOAL else '✗ NO  (need 60%)'}")
    print()

    # Print each attempt summary
    print("  Attempt breakdown:")
    for r in all_results:
        status = "✓" if r["success"] else "✗"
        token_preview = (r["token"][:20] + "...") if r["token"] else "—"
        print(f"    [{status}] #{r['attempt']:02d}  token: {token_preview}")

    print()
    print(f"  Videos saved to: {VIDEO_DIR}/")

    # ── Save full results to JSON ─────────────────────────────────────────────
    summary = {
        "total_attempts":  MAX_ATTEMPTS,
        "successes":       successes,
        "failures":        failures,
        "success_rate":    f"{success_rate:.0%}",
        "goal_met":        success_rate >= SUCCESS_GOAL,
        "headless":        HEADLESS,
        "attempts":        all_results,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"  Results saved  → {RESULTS_FILE}")
    print("=" * 55)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_all_attempts()