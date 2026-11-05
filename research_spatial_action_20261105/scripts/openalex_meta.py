#!/usr/bin/env python3
"""Look up publication metadata for registered arXiv IDs via OpenAlex.

Uses the single-work endpoint (the search/filter endpoints are rate-limited on
this network). Records type, venue and citation count so the source register can
state publication status instead of 'UNKNOWN'. Read-only, public API.
"""
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sources", "openalex_meta.jsonl")

ids = [json.loads(l)["id"] for l in open(os.path.join(ROOT, "sources", "papers.jsonl"))]
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        done.add(json.loads(l)["id"])

f = open(OUT, "a")
fails = 0
for pid in ids:
    if pid in done:
        continue
    url = f"https://api.openalex.org/works/https://doi.org/10.48550/arXiv.{pid}"
    rec = {"id": pid}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "literature-survey/1.0 (mailto:none)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        src = ((d.get("primary_location") or {}).get("source") or {})
        rec.update({
            "type": d.get("type"),
            "year": d.get("publication_year"),
            "venue": src.get("display_name"),
            "doi": d.get("doi"),
            "cited_by_count": d.get("cited_by_count"),
            "referenced_works_count": d.get("referenced_works_count"),
            "status": "ok",
        })
        fails = 0
    except Exception as e:
        rec.update({"status": "error", "error": str(e)[:120]})
        fails += 1
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.flush()
    sys.stderr.write(f"{pid} {rec.get('type')} {rec.get('venue')}\n")
    if fails >= 4:
        sys.stderr.write("too many failures, stopping\n")
        break
    time.sleep(1.2)
f.close()
print("done")
