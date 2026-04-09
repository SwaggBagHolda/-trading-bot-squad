#!/usr/bin/env python3
"""
Agent Browser — Playwright-based web content extractor.
Used by OpenClaw agent-browser skill and NEXUS browse_url().

Usage:
  python3 browse.py "https://example.com"
  python3 browse.py "https://example.com" --selector ".content" --json
  python3 browse.py "https://example.com" --screenshot /tmp/page.png
"""

import argparse, json, sys


def browse(url: str, selector: str = None, wait: int = 3, screenshot: str = None) -> dict:
    """Browse a URL and extract content."""
    from playwright.sync_api import sync_playwright

    result = {"url": url, "title": "", "text": "", "links": [], "error": None}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page.set_default_timeout(30000)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(wait * 1000)

            result["title"] = page.title()

            if selector:
                elements = page.query_selector_all(selector)
                result["text"] = "\n".join(el.inner_text() for el in elements)
            else:
                result["text"] = page.inner_text("body")

            # Extract links
            links = page.eval_on_selector_all(
                "a[href]",
                "els => els.slice(0, 50).map(e => ({text: e.innerText.trim().slice(0,100), href: e.href}))"
            )
            result["links"] = [l for l in links if l["text"] and l["href"].startswith("http")]

            if screenshot:
                page.screenshot(path=screenshot, full_page=True)
                result["screenshot"] = screenshot

            browser.close()
    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Browse a URL and extract content")
    parser.add_argument("url", help="URL to browse")
    parser.add_argument("--selector", help="CSS selector to extract specific elements")
    parser.add_argument("--wait", type=int, default=3, help="Seconds to wait for JS (default: 3)")
    parser.add_argument("--screenshot", help="Save screenshot to path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = browse(args.url, args.selector, args.wait, args.screenshot)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["error"]:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"Title: {result['title']}")
        print(f"URL: {result['url']}")
        print("---")
        # Truncate to reasonable length for terminal
        text = result["text"]
        if len(text) > 5000:
            text = text[:5000] + f"\n... [{len(text) - 5000} more chars]"
        print(text)
