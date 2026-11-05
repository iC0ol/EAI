#!/usr/bin/env python3
"""Query Google Scholar's public results page and print titles, venues and
citation counts. Read-only, low volume, used to check for work that the arXiv
API cannot surface (different wording, non-arXiv venues).

Usage: scholar_probe.py "query" [num]
"""
import html
import re
import sys
import time
import urllib.parse
import urllib.request

q = sys.argv[1]
url = "https://scholar.google.com/scholar?" + urllib.parse.urlencode({"q": q, "hl": "en"})
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (literature survey)"})
with urllib.request.urlopen(req, timeout=40) as r:
    page = r.read().decode("utf-8", "ignore")

blocks = re.findall(r'<div class="gs_r gs_or gs_scl".*?</div>\s*</div>', page, re.S)
if not blocks:
    print("NO_RESULTS or blocked; page length", len(page))
for b in blocks[: int(sys.argv[2]) if len(sys.argv) > 2 else 10]:
    t = re.search(r'<h3 class="gs_rt".*?>(.*?)</h3>', b, re.S)
    title = html.unescape(re.sub("<[^>]+>", "", t.group(1))) if t else "?"
    meta = re.search(r'<div class="gs_a">(.*?)</div>', b, re.S)
    venue = html.unescape(re.sub("<[^>]+>", "", meta.group(1))) if meta else ""
    cites = re.search(r'Cited by (\d+)', b)
    print(f"- {title.strip()[:120]}\n    {venue.strip()[:110]} | cited={cites.group(1) if cites else 0}")
time.sleep(2)
