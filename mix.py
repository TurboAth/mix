#!/usr/bin/env python3
"""
mix.py — NP-Downloader direct link extractor + auto-downloader
Zero deps beyond stdlib.

Usage:
  python3 mix.py <slug>
  python3 mix.py download-CIA-2026-season-1-episode-3
"""

import sys
import re
import http.cookiejar
import urllib.request
import urllib.error
from html.parser import HTMLParser

BASE_URL = "https://vdl.np-downloader.com/sdm_downloads/download-"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def fetch(url: str, referer: str = "") -> tuple[str, str]:
    """Returns (html, final_url). For binary responses returns ('', final_url)."""
    hdrs = dict(HEADERS)
    if referer:
        hdrs["Referer"] = referer
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with _opener.open(req, timeout=25) as r:
            final_url = r.geturl()
            ct = r.headers.get("Content-Type", "")
            # Binary / file download — don't try to decode, just return final URL
            if any(t in ct for t in ("octet-stream", "video/", "audio/", "binary")):
                r.read(1)  # consume minimal data
                return "", final_url
            m = re.search(r"charset=([\w-]+)", ct)
            charset = m.group(1) if m else "utf-8"
            # Guard against non-standard charset names
            try:
                return r.read().decode(charset, errors="replace"), final_url
            except LookupError:
                return r.read().decode("utf-8", errors="replace"), final_url
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {e.reason} → {url}")
    except Exception as e:
        raise RuntimeError(f"Fetch error: {e}")


# ── Step 1: parse sdm_download href from NP-Downloader page ──────────────────

class SDMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        d = dict(attrs)
        if "sdm_download" in d.get("class", "") and d.get("href"):
            self.links.append(d["href"])


def find_sdm_link(html: str) -> str | None:
    p = SDMParser()
    p.feed(html)
    if p.links:
        return p.links[0]
    # fallback regex
    for pat in [
        r'href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*sdm_download',
        r'class=["\'][^"\']*sdm_download[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1)
    return None


# ── Step 2: parse wildbutton onclick from wildshare page ──────────────────────
# Target: <span class="wildbutton" onclick="window.location = 'URL'; return false;">

def find_wildbutton_url(html: str) -> str | None:
    # Extract all <span ...> tags and check for wildbutton + window.location
    # Use a broad pattern: find the wildbutton span's full opening tag
    span_pat = re.compile(r"<span\b[^>]*>", re.I | re.S)
    wloc_pat = re.compile(r"""window\.location\s*=\s*['"]([^'"]+)['"]""", re.I)

    for m in span_pat.finditer(html):
        tag = m.group(0)
        if "wildbutton" not in tag.lower():
            continue
        loc = wloc_pat.search(tag)
        if loc:
            return loc.group(1)

    # Fallback A: any onclick with window.location on the page
    onclick_pat = re.compile(r"""onclick\s*=\s*["']([^"']{15,})["']""", re.I | re.S)
    for m in onclick_pat.finditer(html):
        loc = wloc_pat.search(m.group(1))
        if loc:
            url = loc.group(1)
            # must look like a real URL, not a CSS resource
            if url.startswith("http") and not url.endswith((".css", ".js", ".png", ".jpg")):
                return url

    # Fallback B: href to wildshare with a ?pt= token (direct download token)
    token_pat = re.compile(
        r"""href=['"](https?://(?:wildshare\.net|wildshare\.io)[^'"]*\?pt=[^'"]+)['"]""",
        re.I,
    )
    m = token_pat.search(html)
    if m:
        return m.group(1)

    return None


# ── Step 3: follow the token URL, extract the real file link ─────────────────

def find_download_link(html: str, final_url: str) -> list[str]:
    results = []

    # Direct file extension links
    ext_pat = re.compile(
        r"""href=['"](https?://[^'"]+\.(?:mkv|mp4|avi|mov|wmv|ts|zip|rar|7z)(?:\?[^'"]*)?)['"]""",
        re.I,
    )
    results.extend(ext_pat.findall(html))

    # data-url attributes
    data_pat = re.compile(r"""data-url=['"](https?://[^'"]{20,})['"]""", re.I)
    results.extend(data_pat.findall(html))

    # Links containing /download/ or /file/ path segments
    dl_pat = re.compile(
        r"""href=['"](https?://[^'"]*(?:/download/|/file/|/get/)[^'"]*)['"]""", re.I
    )
    results.extend(dl_pat.findall(html))

    # Dedupe preserving order, filter out CSS/JS
    seen = set()
    out = []
    for l in results:
        if l not in seen and not l.endswith((".css", ".js")):
            seen.add(l)
            out.append(l)
    return out


# ─── Output helpers ───────────────────────────────────────────────────────────

def step(n: int, label: str, url: str):
    print(f"\n  [{n}/3] {label}")
    print(f"        {url}")

def ok(msg: str):    print(f"  ✓ {msg}")
def err(msg: str):   print(f"\n  ✗ {msg}\n"); sys.exit(1)
def hr():            print("  " + "─" * 64)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(slug: str):
    slug = slug.strip("/")
    page1 = f"{BASE_URL}{slug}/"

    print()
    print("  ┌─ mix ──────────────────────────────────────────────────────┐")
    print(f"  │  {slug[:60]:<60}  │")
    print("  └────────────────────────────────────────────────────────────┘")

    # ── Step 1: NP-Downloader page → sdm_download href ───────────────
    step(1, "NP-Downloader page", page1)
    html1, _ = fetch(page1)
    wildshare_page = find_sdm_link(html1)
    if not wildshare_page:
        err(f"No sdm_download link found on:\n    {page1}")
    ok(f"Wildshare page: {wildshare_page}")

    # ── Step 2: Wildshare page → wildbutton onclick URL ──────────────
    step(2, "Wildshare file page", wildshare_page)
    html2, final2 = fetch(wildshare_page, referer=page1)
    token_url = find_wildbutton_url(html2)
    if not token_url:
        err(
            f"No wildbutton onclick found.\n"
            f"    Final URL was: {final2}\n"
            f"    First 800 chars of page:\n"
            + "\n".join("    " + l for l in html2[:800].splitlines())
        )
    ok(f"Token URL: {token_url}")

    # ── Step 3: Token URL → real download link ────────────────────────
    step(3, "Token/download page", token_url)
    html3, final3 = fetch(token_url, referer=wildshare_page)
    links = find_download_link(html3, final3)

    print()
    hr()
    print(f"\n  SLUG   : {slug}")
    print(f"  STEP 1 : {page1}")
    print(f"  STEP 2 : {wildshare_page}")
    print(f"  STEP 3 : {token_url}")
    print()

    file_exts = (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".ts", ".zip", ".rar", ".7z")
    binary_redirect = not html3 or any(final3.lower().endswith(e) for e in file_exts)
    direct = final3 if binary_redirect else (links[0] if links else None)

    if not direct:
        print("  Could not extract direct link.")
        print(f"  Final URL of step 3: {final3}")
        print("  Try opening in browser — download may start automatically.")
        print()
        hr()
        print()
        return

    print(f"  DIRECT FILE URL:")
    print(f"  {direct}")
    print()
    print("  Other options:")
    print(f'  aria2c -x 8 -s 8 "{direct}"')
    print()
    hr()
    print()

    import subprocess, shutil
    print("  Launching wget...")
    print()
    if shutil.which("wget") is None:
        print("  wget not found. Install with: sudo apt install wget")
        return
    try:
        subprocess.run(["wget", "-c", "--content-disposition", direct], check=False)
    except KeyboardInterrupt:
        print("\n  Download interrupted.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    run(sys.argv[1])
