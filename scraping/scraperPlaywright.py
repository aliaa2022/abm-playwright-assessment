"""
================================================================================
  DOM Scraping Assessment — Playwright Version
  Target: egypt.blsspainglobal.com CAPTCHA Page
================================================================================

  OUTPUT FILES PRODUCED:
  ─────────────────────
    • allimages.json          — ALL images in the DOM, as Base64 strings
    • visible_images_only.json — Only images a human can see (9 visible ones)
    • visible_text.txt        — All visible text instructions on the page

  HOW TO INSTALL:
  ───────────────
    pip install playwright requests
    playwright install chromium

  HOW TO RUN:
  ───────────
    python dom_scraper_playwright.py

================================================================================
"""

# ── Standard library ──────────────────────────────────────────────────────────
import json          # Saves Python data as JSON files
import base64        # Converts raw image bytes → Base64 strings
import os            # File size checks and path joining

# ── Third-party ───────────────────────────────────────────────────────────────
import requests                              # Downloads images by URL
from urllib.parse import urljoin             # Turns relative URLs into absolute ones
from playwright.sync_api import sync_playwright  # Controls a real Chromium browser


# ── Target URL ────────────────────────────────────────────────────────────────
TARGET_URL = (
    "https://egypt.blsspainglobal.com/Global/CaptchaPublic/GenerateCaptcha"
    "?data=4CDiA9odF2%2b%2bsWCkAU8htqZkgDyUa5SR6waINtJfg1ThGb6rPIIpxNjefP9Uk"
    "AaSp%2fGsNNuJJi5Zt1nbVACkDRusgqfb418%2bScFkcoa1F0I%3d"
)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 1 — launch_browser(playwright)
#
#  PURPOSE:
#    Creates a real (but invisible) Chromium browser with settings that
#    make the site think we are a normal human visitor.
#
#  WHY PLAYWRIGHT OVER SELENIUM?
#    • Built-in headless support, no separate driver download needed
#    • Faster page load detection (waitUntil / wait_for_load_state)
#    • Cleaner API for cookies and JavaScript execution
#    • playwright install chromium handles everything automatically
#
#  RETURNS: (browser, page) — the browser object and the open tab
# ══════════════════════════════════════════════════════════════════════════════

def launch_browser(playwright):
    """
    Launches a headless Chromium browser and opens a new page (tab).
    Returns both the browser and the page so we can close the browser later.
    """

    browser = playwright.chromium.launch(
        headless=True,                  # Run invisibly — no window appears
        args=[
            "--no-sandbox",             # Required in Linux/WSL environments
            "--disable-dev-shm-usage",  # Prevents crashes with low shared memory
            "--window-size=1920,1080",  # Full HD size so visibility checks work
        ]
    )

    # Create a new browser context — like a fresh browser profile
    # Setting a real user-agent prevents the site from detecting automation
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )

    # Open a new tab (page) inside the context
    page = context.new_page()

    return browser, page


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 2 — open_page(page, url)
#
#  PURPOSE:
#    Navigates the browser tab to the target URL and waits until:
#      1. The network goes quiet (no more HTTP requests firing)
#      2. Extra JavaScript has had time to run (3 second pause)
#
#  WHY WAIT?
#    The CAPTCHA page loads images dynamically via JavaScript.
#    If we scrape too early, many images won't exist in the DOM yet.
# ══════════════════════════════════════════════════════════════════════════════

def open_page(page, url: str) -> None:
    """
    Opens the target URL and waits for the page to fully load.
    """

    print(f"[*] Opening: {url[:80]}...")

    page.goto(
        url,
        wait_until="networkidle",   # Wait until no network requests for 500ms
        timeout=30000               # Give up after 30 seconds if still loading
    )

    # Extra pause: some JS frameworks render content after network goes idle
    page.wait_for_timeout(3000)     # 3000 milliseconds = 3 seconds

    print("[+] Page loaded.")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 3 — get_session_cookies(page)
#
#  PURPOSE:
#    Reads the browser's current cookies and converts them to a simple
#    dictionary that the `requests` library can use when downloading images.
#
#  WHY DO WE NEED COOKIES?
#    The BLS Spain site is protected. Without the session cookies the server
#    returns a 403 Forbidden error when we try to download images by URL.
#    Reusing the browser's cookies lets us "pretend" we are still logged in.
#
#  RETURNS: dict like {"ASP.NET_SessionId": "abc123", ...}
# ══════════════════════════════════════════════════════════════════════════════

def get_session_cookies(page) -> dict:
    """
    Extracts cookies from the live browser session and returns them
    as a plain {name: value} dictionary ready for use with requests.get().
    """

    # page.context.cookies() returns a list of cookie dicts from Playwright
    raw_cookies = page.context.cookies()

    # Convert list → flat dict:  [{"name": "x", "value": "y"}] → {"x": "y"}
    return {cookie["name"]: cookie["value"] for cookie in raw_cookies}


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 4 — url_to_base64(image_url, cookies)
#
#  PURPOSE:
#    Downloads an image from a URL using the session cookies,
#    then encodes the raw bytes as a Base64 string for JSON storage.
#
#  WHY BASE64?
#    JSON files can only store text. Base64 converts binary image data
#    into a safe text format that can be stored, transmitted, and later
#    decoded back into the original image.
#
#  RETURNS: Base64 string like "iVBORw0KGgo..." or "" on failure
# ══════════════════════════════════════════════════════════════════════════════

def url_to_base64(image_url: str, cookies: dict) -> str:
    """
    Downloads the image at `image_url` with session cookies and
    returns it as a Base64-encoded string.
    """

    try:
        response = requests.get(
            image_url,
            cookies=cookies,    # Pass the browser session cookies
            timeout=10,         # Don't hang forever on slow images
            headers={           # Mimic a real browser request
                "Referer": TARGET_URL,
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )
        response.raise_for_status()   # Raises exception for 4xx/5xx responses

        # base64.b64encode() returns bytes → .decode("utf-8") converts to string
        return base64.b64encode(response.content).decode("utf-8")

    except Exception as error:
        print(f"    [!] Download failed for {image_url[:60]}: {error}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 5 — extract_inline_base64(src)
#
#  PURPOSE:
#    Some <img> tags embed the image directly in the src attribute as a
#    data-URI instead of a URL. Example:
#       src="data:image/png;base64,iVBORw0KGgo..."
#    In this case there is nothing to download — we just strip the header
#    and return the Base64 payload that's already there.
#
#  RETURNS: Just the Base64 string after the comma
# ══════════════════════════════════════════════════════════════════════════════

def extract_inline_base64(src: str) -> str:
    """
    Extracts the Base64 payload from a data-URI image source.
    Input:  "data:image/png;base64,iVBORw0KGgo..."
    Output: "iVBORw0KGgo..."
    """

    if "," in src:
        return src.split(",", 1)[1]   # Everything after the first comma
    return src                         # Safety fallback


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 6 — is_visible(page, element_handle)
#
#  PURPOSE:
#    Determines whether a specific DOM element is actually visible to a human.
#    Uses JavaScript executed inside the browser to check multiple CSS rules
#    and the element's position on screen.
#
#  WHAT MAKES AN ELEMENT VISIBLE?
#    All of these must be true:
#      • Width > 0 and Height > 0         (has physical size)
#      • display !== 'none'               (not removed from layout)
#      • visibility !== 'hidden'          (not CSS-hidden)
#      • opacity > 0                      (not transparent)
#      • Inside the viewport boundaries  (actually on the visible screen area)
#
#  RETURNS: True if visible, False if hidden
# ══════════════════════════════════════════════════════════════════════════════

def is_visible(page, element_handle) -> bool:
    """
    Runs a JavaScript check inside the browser to determine if
    the given element is visually rendered on the screen.
    """

    js_check = """
        el => {
            // getBoundingClientRect: gets element's size and screen position
            const rect  = el.getBoundingClientRect();
            // getComputedStyle: reads the final CSS applied to the element
            const style = window.getComputedStyle(el);

            return (
                rect.width  > 0 &&
                rect.height > 0 &&
                style.display     !== 'none'   &&
                style.visibility  !== 'hidden' &&
                parseFloat(style.opacity) > 0  &&
                rect.top    < window.innerHeight &&   // above the bottom edge
                rect.bottom > 0                  &&   // below the top edge
                rect.left   < window.innerWidth  &&   // before the right edge
                rect.right  > 0                       // after the left edge
            );
        }
    """

    try:
        # evaluate_handle runs JavaScript with the element as the argument
        return page.evaluate(js_check, element_handle)
    except Exception:
        return False   # Treat as hidden if evaluation fails


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 7 — resolve_src(src, page_url)
#
#  PURPOSE:
#    Image src attributes can be three things:
#      1. Absolute URL:   "https://example.com/img.png"
#      2. Relative path:  "/images/img.png" or "../img.png"
#      3. Data-URI:       "data:image/png;base64,..."
#
#    This function normalises all cases so the caller always gets
#    either a full "https://..." URL or a "data:..." string.
#
#  RETURNS: Resolved absolute src string
# ══════════════════════════════════════════════════════════════════════════════

def resolve_src(src: str, page_url: str) -> str:
    """
    Converts any image src into a usable absolute URL or data-URI.
    """

    if not src:
        return ""
    if src.startswith("data:"):
        return src                          # Already a data-URI, use as-is
    if src.startswith("http"):
        return src                          # Already absolute, use as-is
    return urljoin(page_url, src)           # Relative → combine with page URL


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 8 — process_image(src, page_url, cookies)
#
#  PURPOSE:
#    Central image-to-Base64 converter. Decides which method to use
#    based on the src type, then returns the Base64 string.
#    This keeps functions 9 and 10 clean — they just call this one.
#
#  RETURNS: Base64 string or ""
# ══════════════════════════════════════════════════════════════════════════════

def process_image(src: str, page_url: str, cookies: dict) -> str:
    """
    Converts an image src (URL or data-URI) into a Base64 string.
    Handles all three src types automatically.
    """

    resolved = resolve_src(src, page_url)

    if not resolved:
        return ""

    if resolved.startswith("data:"):
        # Image is already embedded — just extract the Base64 part
        return extract_inline_base64(resolved)
    else:
        # Image is a URL — download it and encode it
        return url_to_base64(resolved, cookies)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 9 — scrape_all_images(page)
#
#  PURPOSE:
#    Finds EVERY <img> element in the entire DOM — visible or not —
#    converts each one to Base64, and returns a list of records.
#
#  WHY SCRAPE HIDDEN IMAGES TOO?
#    The task asks for all 100+ images. Many are hidden by CSS but still
#    exist in the DOM (e.g. CAPTCHA options not yet shown to the user).
#
#  RETURNS: List of dicts, one per image
# ══════════════════════════════════════════════════════════════════════════════

def scrape_all_images(page) -> list:
    """
    Scrapes ALL <img> elements from the DOM regardless of visibility.
    Returns a list of records with src, alt, dimensions, and base64 data.
    """

    print("\n[*] Scraping ALL images (visible + hidden)...")

    # query_selector_all("img") finds every <img> in the DOM
    all_imgs     = page.query_selector_all("img")
    page_url     = page.url
    cookies      = get_session_cookies(page)
    total        = len(all_imgs)

    print(f"    Found {total} <img> elements in the DOM.")

    results = []

    for index, img in enumerate(all_imgs):

        # Read attributes directly from the DOM element
        src    = img.get_attribute("src")    or \
                 img.get_attribute("data-src") or ""   # data-src = lazy-load
        alt    = img.get_attribute("alt")    or ""
        width  = img.get_attribute("width")  or "0"
        height = img.get_attribute("height") or "0"

        print(f"    [{index + 1}/{total}] {src[:70]}...")

        # Convert to Base64 using our central helper
        b64 = process_image(src, page_url, cookies)

        results.append({
            "index":  index,        # Position in the DOM (0-based)
            "src":    src,          # Original src value
            "alt":    alt,          # Alt text description
            "width":  width,        # Width attribute (may be "0" if not set)
            "height": height,       # Height attribute
            "base64": b64,          # The Base64-encoded image data
        })

    print(f"[+] Collected {len(results)} total images.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 10 — scrape_visible_images(page)
#
#  PURPOSE:
#    Same as scrape_all_images() but SKIPS any image that fails
#    the is_visible() check. This gives us only the 9 images a human
#    actually sees when they look at the page.
#
#  RETURNS: List of dicts for visible images only
# ══════════════════════════════════════════════════════════════════════════════

def scrape_visible_images(page) -> list:
    """
    Scrapes only the <img> elements that are visually rendered on screen.
    Uses is_visible() to filter out CSS-hidden images.
    """

    print("\n[*] Scraping VISIBLE images only...")

    all_imgs     = page.query_selector_all("img")
    page_url     = page.url
    cookies      = get_session_cookies(page)

    results      = []
    visible_num  = 0

    for img in all_imgs:

        # ── Skip this image if it's not visible to a human ───────────────────
        if not is_visible(page, img):
            continue

        visible_num += 1
        src    = img.get_attribute("src")    or \
                 img.get_attribute("data-src") or ""
        alt    = img.get_attribute("alt")    or ""
        width  = img.get_attribute("width")  or "0"
        height = img.get_attribute("height") or "0"

        print(f"    [Visible #{visible_num}] {src[:70]}...")

        b64 = process_image(src, page_url, cookies)

        results.append({
            "visible_index": visible_num,   # Count among visible images only
            "src":    src,
            "alt":    alt,
            "width":  width,
            "height": height,
            "base64": b64,
        })

    print(f"[+] Found {len(results)} visible images.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 11 — scrape_visible_text(page)
#
#  PURPOSE:
#    Extracts all text that a human can read on the page.
#    Uses a JavaScript TreeWalker to visit every text node in the DOM,
#    then filters out text from invisible parent elements.
#
#  WHAT IS A TEXT NODE?
#    In HTML, the actual words between tags are separate "text nodes".
#    E.g. in <p>Hello</p> → "Hello" is a text node child of <p>.
#    TreeWalker lets us visit all of these efficiently.
#
#  RETURNS: Deduplicated list of visible text strings
# ══════════════════════════════════════════════════════════════════════════════

def scrape_visible_text(page) -> list:
    """
    Walks the DOM and collects all text that is visible to a human.
    Skips <script>, <style> tags and any CSS-hidden parent elements.
    Returns a deduplicated list of strings.
    """

    print("\n[*] Scraping visible text instructions...")

    js_collect_text = """
        () => {
            const texts = [];

            // TreeWalker visits every TEXT node in the entire document
            // NodeFilter.SHOW_TEXT = only text nodes, not element nodes
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );

            while (walker.nextNode()) {
                const node   = walker.currentNode;
                const text   = node.textContent.trim();

                // Skip whitespace-only nodes (indentation, newlines, etc.)
                if (!text) continue;

                const parent = node.parentElement;
                if (!parent) continue;

                // Skip JavaScript code embedded in <script> tags
                if (parent.tagName === 'SCRIPT') continue;
                // Skip CSS rules embedded in <style> tags
                if (parent.tagName === 'STYLE')  continue;

                // Read the computed (final) CSS of the parent element
                const style = window.getComputedStyle(parent);

                // Only collect text whose container is visually rendered
                if (
                    style.display     !== 'none'   &&
                    style.visibility  !== 'hidden' &&
                    parseFloat(style.opacity) > 0
                ) {
                    texts.push(text);
                }
            }

            return texts;
        }
    """

    # Run the JavaScript inside the real browser and get results back in Python
    raw = page.evaluate(js_collect_text)

    # Remove duplicates while preserving original order
    seen   = set()
    unique = []
    for text in raw:
        if text not in seen:
            seen.add(text)
            unique.append(text)

    print(f"[+] Found {len(unique)} unique visible text strings.")
    return unique


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 12 — save_json(data, filename)
#
#  PURPOSE:
#    Serialises a Python list or dict to a JSON file.
#    ensure_ascii=False preserves Arabic and other non-ASCII characters.
#    indent=2 makes the output human-readable (pretty-printed).
# ══════════════════════════════════════════════════════════════════════════════

def save_json(data: object, filename: str) -> None:
    """Saves a Python object to a formatted JSON file."""

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size = os.path.getsize(filename)
    print(f"[+] Saved → {filename}  ({size:,} bytes)")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 13 — save_text(lines, filename)
#
#  PURPOSE:
#    Writes a list of strings to a plain .txt file, one string per line.
# ══════════════════════════════════════════════════════════════════════════════

def save_text(lines: list, filename: str) -> None:
    """Saves a list of strings to a plain text file."""

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    size = os.path.getsize(filename)
    print(f"[+] Saved → {filename}  ({size:,} bytes)")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 14 — run()
#
#  PURPOSE:
#    The master orchestrator function. Calls every other function in order:
#      1. Start Playwright and launch browser
#      2. Open the target page
#      3. Scrape all images       → allimages.json
#      4. Scrape visible images   → visible_images_only.json
#      5. Scrape visible text     → visible_text.txt
#      6. Print summary and close browser
#
#  The `with sync_playwright() as pw` block ensures Playwright always
#  shuts down cleanly, even if an error occurs.
# ══════════════════════════════════════════════════════════════════════════════

def run() -> None:
    """
    Main entry point. Orchestrates the full scraping workflow.
    """

    print("=" * 60)
    print("  DOM Scraping Assessment — Playwright")
    print("=" * 60)

    # `with` block guarantees Playwright is stopped even if script crashes
    with sync_playwright() as pw:

        # ── Step 1: Launch the browser ───────────────────────────────────────
        browser, page = launch_browser(pw)

        try:

            # ── Step 2: Navigate to the target page ──────────────────────────
            open_page(page, TARGET_URL)

            # ── Step 3: Scrape all images → allimages.json ───────────────────
            all_images = scrape_all_images(page)
            save_json(all_images, "allimages.json")

            # ── Step 4: Scrape visible images → visible_images_only.json ─────
            visible_images = scrape_visible_images(page)
            save_json(visible_images, "visible_images_only.json")

            # ── Step 5: Scrape visible text → visible_text.txt ───────────────
            visible_texts = scrape_visible_text(page)

            # Print to console so the assessor can read them immediately
            print("\n── Visible Text Instructions ──────────────────────────")
            for i, line in enumerate(visible_texts, start=1):
                print(f"  {i:>3}. {line}")

            save_text(visible_texts, "visible_text.txt")

            # ── Summary ───────────────────────────────────────────────────────
            print("\n" + "=" * 60)
            print("  COMPLETED — Output files created:")
            print(f"    • allimages.json           ({len(all_images)} images)")
            print(f"    • visible_images_only.json ({len(visible_images)} images)")
            print(f"    • visible_text.txt         ({len(visible_texts)} lines)")
            print("=" * 60)

        except Exception as e:
            print(f"\n[ERROR] {e}")
            raise

        finally:
            # Always close the browser — prevents orphaned Chrome processes
            browser.close()
            print("[*] Browser closed.")


# ── Entry point ───────────────────────────────────────────────────────────────
# Only runs when this file is executed directly, not when imported as a module
if __name__ == "__main__":
    run()