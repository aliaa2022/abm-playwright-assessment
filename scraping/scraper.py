"""
================================================================================
  DOM Scraping Assessment — egypt.blsspainglobal.com CAPTCHA Page
================================================================================

  WHAT THIS SCRIPT DOES:
  ─────────────────────
  1. Opens the target URL in a real (but hidden) Chrome browser using Selenium,
     because the site blocks plain HTTP requests and requires JavaScript to run.

  2. Scrapes ALL <img> elements found anywhere in the page DOM (100+),
     converts each one to a Base64 string, and saves them to → allimages.json

  3. Scrapes only the VISIBLE images (the 9 a human can actually see on screen),
     converts each to Base64, and saves them to → visible_images_only.json

  4. Scrapes all VISIBLE text instructions on the page and prints + saves them
     to → visible_text.txt

  HOW TO INSTALL DEPENDENCIES:
  ─────────────────────────────
      pip install selenium webdriver-manager requests

  HOW TO RUN:
  ───────────
      python dom_scraper.py

================================================================================
"""

# ── Standard library imports ──────────────────────────────────────────────────

import json          # Used to save data as JSON files
import base64        # Used to encode raw image bytes into Base64 strings
import time          # Used to add small delays while the page loads
import os            # Used for file path operations

# ── Third-party imports ───────────────────────────────────────────────────────

import requests      # Used to download image files by their URL

# Selenium: controls a real Chrome browser from Python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service       # Manages ChromeDriver process
from selenium.webdriver.chrome.options import Options       # Sets browser launch flags
from selenium.webdriver.common.by import By                 # Lets us find elements (By.TAG_NAME, etc.)
from selenium.webdriver.support.ui import WebDriverWait     # Waits until conditions are met
from selenium.webdriver.support import expected_conditions as EC  # Conditions like "element visible"

# webdriver-manager: auto-downloads the correct ChromeDriver for your Chrome version
from webdriver_manager.chrome import ChromeDriverManager


# ── Target URL ────────────────────────────────────────────────────────────────

TARGET_URL = (
    "https://egypt.blsspainglobal.com/Global/CaptchaPublic/GenerateCaptcha"
    "?data=4CDiA9odF2%2b%2bsWCkAU8htqZkgDyUa5SR6waINtJfg1ThGb6rPIIpxNjefP9Uk"
    "AaSp%2fGsNNuJJi5Zt1nbVACkDRusgqfb418%2bScFkcoa1F0I%3d"
)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 1 — launch_browser()
#  Creates and returns a headless Chrome browser instance.
#  "Headless" means the browser runs invisibly in the background (no window).
# ══════════════════════════════════════════════════════════════════════════════

def launch_browser() -> webdriver.Chrome:
    """
    Configures Chrome options and launches a headless browser.
    Returns the WebDriver object used to control the browser.
    """

    options = Options()
    # Run Chrome without opening a visible window
    options.add_argument("--headless=new")
    # Required in most Linux/server environments (no display server)
    options.add_argument("--no-sandbox")
    # Prevents crashes in containerised / low-memory environments
    options.add_argument("--disable-dev-shm-usage")
    # Set a realistic window size so that "visibility" checks work correctly
    options.add_argument("--window-size=1920,1080")
    # Pretend to be a real browser — some sites reject requests without this
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # ChromeDriverManager downloads the correct chromedriver binary automatically
    service = Service(ChromeDriverManager().install())

    # Create and return the Chrome WebDriver with our options
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 2 — open_page(driver, url)
#  Navigates the browser to the target URL and waits for the page to fully load.
# ══════════════════════════════════════════════════════════════════════════════

def open_page(driver: webdriver.Chrome, url: str) -> None:
    """
    Opens the given URL in the browser and waits until the <body> tag is present,
    meaning the HTML has been parsed and the DOM is ready.
    """

    print(f"[*] Opening URL: {url}")
    driver.get(url)   # Tells Chrome to navigate to the URL

    # Wait up to 15 seconds for the <body> tag to appear in the DOM
    # This ensures the page has finished its initial HTML render
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    # Extra pause to allow JavaScript-driven content (lazy images, etc.) to load
    time.sleep(3)
    print("[+] Page loaded successfully.")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 3 — url_to_base64(url, session_cookies)
#  Downloads an image from a URL and returns it as a Base64-encoded string.
#  We pass the browser's cookies so the server accepts our download request.
# ══════════════════════════════════════════════════════════════════════════════

def url_to_base64(image_url: str, session_cookies: dict) -> str:
    """
    Downloads the image at `image_url` using the browser's session cookies,
    then encodes the raw bytes as a Base64 string.

    Returns:
        A Base64 string like "iVBORw0KGgo..." or an empty string on failure.
    """

    try:
        # Send an HTTP GET request with the browser's cookies to avoid 403 errors
        response = requests.get(image_url, cookies=session_cookies, timeout=10)
        response.raise_for_status()   # Raises an error if status is 4xx or 5xx

        # Encode the raw image bytes to Base64 and decode bytes→str for JSON storage
        encoded = base64.b64encode(response.content).decode("utf-8")
        return encoded

    except Exception as error:
        # If download fails, log the reason and return an empty string
        print(f"    [!] Could not download {image_url}: {error}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 4 — inline_src_to_base64(src)
#  Handles <img> tags whose src is already a Base64 data-URI
#  (e.g. src="data:image/png;base64,iVBORw0...").
#  In that case we just strip the header and return the raw Base64 part.
# ══════════════════════════════════════════════════════════════════════════════

def inline_src_to_base64(src: str) -> str:
    """
    If the image src is a data-URI (already embedded Base64),
    extract and return just the Base64 payload after the comma.

    Example input:  "data:image/png;base64,iVBORw0KGgo..."
    Example output: "iVBORw0KGgo..."
    """

    # data-URIs always contain a comma separating header from data
    if "," in src:
        return src.split(",", 1)[1]   # Take everything after the first comma
    return src                         # Fallback: return as-is if format is unexpected


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 5 — is_element_visible(driver, element)
#  Checks whether a specific DOM element is actually visible to the human eye.
#  Uses JavaScript because Selenium's is_displayed() misses CSS-hidden elements.
# ══════════════════════════════════════════════════════════════════════════════

def is_element_visible(driver: webdriver.Chrome, element) -> bool:
    """
    Runs a JavaScript snippet inside the browser to check:
      - The element has a non-zero width and height
      - CSS visibility is not 'hidden'
      - CSS display is not 'none'
      - CSS opacity is greater than 0
      - The element is within the current viewport boundaries

    Returns True if all conditions pass (element is visible), False otherwise.
    """

    js_visibility_check = """
        var el = arguments[0];

        // getBoundingClientRect gives us the element's position and size on screen
        var rect = el.getBoundingClientRect();

        // getComputedStyle reads the final CSS applied to the element
        var style = window.getComputedStyle(el);

        return (
            rect.width  > 0 &&                        // Has a visible width
            rect.height > 0 &&                        // Has a visible height
            style.visibility !== 'hidden' &&           // Not CSS-hidden
            style.display    !== 'none'  &&            // Not CSS-removed from layout
            parseFloat(style.opacity)    > 0  &&       // Not transparent
            rect.top    < window.innerHeight &&        // Top edge is above viewport bottom
            rect.bottom > 0              &&            // Bottom edge is below viewport top
            rect.left   < window.innerWidth  &&        // Left edge is before viewport right
            rect.right  > 0                            // Right edge is after viewport left
        );
    """

    try:
        # execute_script runs JavaScript in the browser and returns the result to Python
        return driver.execute_script(js_visibility_check, element)
    except Exception:
        return False   # If anything goes wrong, treat element as not visible


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 6 — scrape_all_images(driver)
#  Finds every <img> tag in the entire DOM (visible or not) and converts each
#  to a Base64-encoded entry. Returns a list of dictionaries.
# ══════════════════════════════════════════════════════════════════════════════

def scrape_all_images(driver: webdriver.Chrome) -> list:
    """
    Locates all <img> elements in the page (regardless of visibility),
    downloads or extracts each image, and returns a list like:

    [
      {
        "index": 0,
        "src": "https://...",
        "alt": "some text",
        "width": 100,
        "height": 100,
        "base64": "iVBORw0KGgo..."
      },
      ...
    ]
    """

    print("\n[*] Scraping ALL images from DOM...")

    # Grab every <img> element anywhere on the page
    all_img_elements = driver.find_elements(By.TAG_NAME, "img")
    print(f"    Found {len(all_img_elements)} <img> elements in total.")

    # Collect the browser's current cookies to use when downloading images
    # (cookies keep us authenticated / recognised by the server)
    raw_cookies = driver.get_cookies()
    # Convert Selenium's cookie list format into a simple {name: value} dict
    session_cookies = {c["name"]: c["value"] for c in raw_cookies}

    # The current page URL is used to resolve relative image paths
    page_url = driver.current_url

    results = []   # Will hold one dict per image

    for index, img in enumerate(all_img_elements):

        # Read the src attribute — this is the image URL or data-URI
        src = img.get_attribute("src") or ""
        # Read the alt attribute — a text description of the image
        alt = img.get_attribute("alt") or ""
        # Read rendered width/height (in pixels) from the browser
        width  = img.get_attribute("width")  or img.size.get("width",  0)
        height = img.get_attribute("height") or img.size.get("height", 0)

        print(f"    [{index + 1}/{len(all_img_elements)}] Processing: {src[:80]}...")

        # ── Determine the Base64 encoding based on the src type ──────────────

        if src.startswith("data:"):
            # Image is already embedded as a Base64 data-URI — just extract it
            b64 = inline_src_to_base64(src)

        elif src.startswith("http"):
            # Image is a full absolute URL — download and encode it
            b64 = url_to_base64(src, session_cookies)

        elif src:
            # Image has a relative path — combine it with the page URL to get full URL
            absolute_url = urljoin(page_url, src)
            b64 = url_to_base64(absolute_url, session_cookies)

        else:
            # No src attribute found at all
            b64 = ""

        # Build a record for this image and add it to the results list
        results.append({
            "index":  index,
            "src":    src,
            "alt":    alt,
            "width":  width,
            "height": height,
            "base64": b64,
        })

    print(f"[+] Done. Collected {len(results)} images.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 7 — scrape_visible_images(driver)
#  Same as above but ONLY returns images that pass the visibility check.
# ══════════════════════════════════════════════════════════════════════════════

def scrape_visible_images(driver: webdriver.Chrome) -> list:
    """
    Finds all <img> elements, then filters to only those that are visually
    rendered on screen (what a human would actually see).

    Returns the same structure as scrape_all_images() but only for visible imgs.
    """

    print("\n[*] Scraping VISIBLE images only...")

    all_img_elements = driver.find_elements(By.TAG_NAME, "img")

    raw_cookies   = driver.get_cookies()
    session_cookies = {c["name"]: c["value"] for c in raw_cookies}
    page_url      = driver.current_url

    results        = []
    visible_count  = 0

    for index, img in enumerate(all_img_elements):

        # Skip this image entirely if it is not visible on screen
        if not is_element_visible(driver, img):
            continue

        visible_count += 1
        src    = img.get_attribute("src") or ""
        alt    = img.get_attribute("alt") or ""
        width  = img.get_attribute("width")  or img.size.get("width",  0)
        height = img.get_attribute("height") or img.size.get("height", 0)

        print(f"    [Visible #{visible_count}] {src[:80]}...")

        if src.startswith("data:"):
            b64 = inline_src_to_base64(src)
        elif src.startswith("http"):
            b64 = url_to_base64(src, session_cookies)
        elif src:
            b64 = url_to_base64(urljoin(page_url, src), session_cookies)
        else:
            b64 = ""

        results.append({
            "visible_index": visible_count,
            "src":    src,
            "alt":    alt,
            "width":  width,
            "height": height,
            "base64": b64,
        })

    print(f"[+] Done. Found {len(results)} visible images.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 8 — scrape_visible_text(driver)
#  Extracts all text that is rendered and visible on the page.
#  Uses JavaScript to walk the DOM and collect text from visible nodes.
# ══════════════════════════════════════════════════════════════════════════════

def scrape_visible_text(driver: webdriver.Chrome) -> list:
    """
    Walks every text node in the DOM using JavaScript.
    Returns only the text that is actually visible to a human user
    (not hidden by CSS, not inside <script>/<style> tags).

    Returns a list of unique, non-empty text strings.
    """

    print("\n[*] Scraping visible text instructions...")

    js_get_visible_text = """
        var results = [];

        // TreeWalker iterates over every node in the DOM
        // NodeFilter.SHOW_TEXT = only visit text nodes (the actual words)
        var walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        while (walker.nextNode()) {
            var node   = walker.currentNode;
            var text   = node.textContent.trim();

            // Skip empty text nodes (whitespace only)
            if (!text) continue;

            // Get the parent element to check its visibility
            var parent = node.parentElement;
            if (!parent) continue;

            // Skip text inside <script> tags (JavaScript code, not human text)
            if (parent.tagName === 'SCRIPT') continue;
            // Skip text inside <style> tags (CSS rules, not human text)
            if (parent.tagName === 'STYLE')  continue;

            // Read the computed CSS of the parent element
            var style = window.getComputedStyle(parent);

            // Only collect text whose parent element is actually rendered
            if (
                style.display    !== 'none'   &&
                style.visibility !== 'hidden' &&
                parseFloat(style.opacity) > 0
            ) {
                results.push(text);
            }
        }

        return results;
    """

    # Run the JavaScript and get back a Python list of strings
    raw_texts = driver.execute_script(js_get_visible_text)

    # Remove duplicates while preserving order using a seen-set
    seen   = set()
    unique = []
    for text in raw_texts:
        if text not in seen:
            seen.add(text)
            unique.append(text)

    print(f"[+] Found {len(unique)} unique visible text strings.")
    return unique


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 9 — save_json(data, filename)
#  Serialises a Python object to a JSON file with readable indentation.
# ══════════════════════════════════════════════════════════════════════════════

def save_json(data: object, filename: str) -> None:
    """
    Writes `data` (list or dict) to `filename` as formatted JSON.
    `ensure_ascii=False` preserves Arabic / non-ASCII characters correctly.
    """

    with open(filename, "w", encoding="utf-8") as f:
        # indent=2 makes the JSON human-readable (pretty-printed)
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[+] Saved → {filename}  ({os.path.getsize(filename):,} bytes)")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 10 — save_text(lines, filename)
#  Writes a list of strings to a plain text file, one string per line.
# ══════════════════════════════════════════════════════════════════════════════

def save_text(lines: list, filename: str) -> None:
    """
    Joins all strings with a newline separator and writes them to `filename`.
    """

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))   # One text entry per line

    print(f"[+] Saved → {filename}  ({os.path.getsize(filename):,} bytes)")


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTION 11 — run()
#  The main orchestrator. Calls every function above in the correct order.
# ══════════════════════════════════════════════════════════════════════════════

def run() -> None:
    """
    Master function that ties everything together:
      1. Launches the browser
      2. Opens the target page
      3. Scrapes all images      → allimages.json
      4. Scrapes visible images  → visible_images_only.json
      5. Scrapes visible text    → visible_text.txt
      6. Closes the browser
    """

    # We need this import here because urljoin is used inside scrape functions
    # but must be available at module level too — so we import at top and use here
    driver = None   # Initialise to None so the finally-block works even on early errors

    try:
        # ── Step 1: Start the browser ────────────────────────────────────────
        print("=" * 60)
        print("  DOM Scraping Assessment")
        print("=" * 60)
        driver = launch_browser()

        # ── Step 2: Navigate to the target page ──────────────────────────────
        open_page(driver, TARGET_URL)

        # ── Step 3: Scrape all images and save ───────────────────────────────
        all_images = scrape_all_images(driver)
        save_json(all_images, "allimages.json")

        # ── Step 4: Scrape only visible images and save ───────────────────────
        visible_images = scrape_visible_images(driver)
        save_json(visible_images, "visible_images_only.json")

        # ── Step 5: Scrape visible text and save ─────────────────────────────
        visible_texts = scrape_visible_text(driver)

        # Print to console so the assessor can read them immediately
        print("\n── Visible Text Instructions ──────────────────────────────")
        for i, line in enumerate(visible_texts, start=1):
            print(f"  {i:>3}. {line}")

        save_text(visible_texts, "visible_text.txt")

        # ── Summary ──────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  DONE — Output files:")
        print("    • allimages.json          (all images, Base64 encoded)")
        print("    • visible_images_only.json (visible images only)")
        print("    • visible_text.txt         (visible text instructions)")
        print("=" * 60)

    except Exception as e:
        # Catch any unexpected error and print it clearly
        print(f"\n[ERROR] Script failed: {e}")
        raise

    finally:
        # Always close the browser, even if an error occurred
        # This prevents orphaned Chrome processes from running in the background
        if driver:
            driver.quit()
            print("[*] Browser closed.")


# ── Entry point ───────────────────────────────────────────────────────────────
# This block only runs when the script is executed directly (not when imported)
if __name__ == "__main__":
    from urllib.parse import urljoin   # Needed for resolving relative image URLs
    run()