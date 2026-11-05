#!/usr/bin/env python3
"""Fetch the arXiv LaTeXML HTML rendering of papers and store plain text.

Much smaller than the PDFs for this corpus (0.5 MB vs 10-17 MB), which matters
on a slow link. Falls back silently when no HTML rendering exists.
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser

OUT = os.path.join(os.path.dirname(__file__), "..", "papers")


class TextExtract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
        self.block = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "section",
                      "figcaption", "table", "br", "dt", "dd", "blockquote"}

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.block:
            self.parts.append("\n")
        if tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in self.block:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch(pid, version="v1"):
    url = f"https://export.arxiv.org/html/{pid}{version}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 literature reading"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", "ignore")
    p = TextExtract()
    p.feed(raw)
    text = "".join(p.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text


def main():
    pairs = [l.split() for l in open(sys.argv[1]) if l.strip()]
    for pid, slug in pairs:
        dest = os.path.join(OUT, f"{pid}__{slug}.txt")
        if os.path.exists(dest) and os.path.getsize(dest) > 2000:
            print("skip", pid)
            continue
        try:
            t = fetch(pid)
            if len(t) < 3000:
                print("short", pid, len(t))
                continue
            with open(dest, "w") as f:
                f.write(f"[source] arXiv HTML rendering {pid}v1\n")
                f.write(t)
            print("ok", pid, len(t))
        except Exception as e:
            print("fail", pid, type(e).__name__, e)
        time.sleep(1.5)


if __name__ == "__main__":
    main()
