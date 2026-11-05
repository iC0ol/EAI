#!/usr/bin/env python3
"""Fetch references and citing papers for key works from the public
Semantic Scholar Graph API. Read-only; used for forward/backward citation
chasing that OpenAlex's filter endpoint could not serve (429).

Writes sources/s2_citations.jsonl, one record per seed paper.
"""
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sources", "s2_citations.jsonl")

SEEDS = sys.argv[1:] or [
    "2510.02268",  # KYC camera conditioning
    "2610.18843",  # LIBERO-RIG tolerance per axis
    "2607.09825",  # More Structure failure taxonomy
    "2610.01626",  # action chunking error propagation
    "2512.02902",  # 4K-param alignment
    "2609.27247",  # Counterfactual Memory Audit
    "2610.12696",  # Spa-Bench
    "2606.02277",  # RoboSemanticBench
]

FIELDS = "title,year,venue,externalIds,abstract"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "literature-survey/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:
            sys.stderr.write(f"  retry {attempt}: {e}\n")
            time.sleep(6 * (attempt + 1))
    return None


def main():
    f = open(OUT, "a")
    for pid in SEEDS:
        rec = {"id": pid}
        base = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{pid}"
        d = get(f"{base}?fields=title,citationCount,referenceCount")
        if not d:
            rec["status"] = "error"
            f.write(json.dumps(rec) + "\n"); f.flush()
            continue
        rec.update({"title": d.get("title"), "citationCount": d.get("citationCount"),
                    "referenceCount": d.get("referenceCount"), "status": "ok"})
        time.sleep(3)
        cites = get(f"{base}/citations?fields={FIELDS}&limit=100")
        time.sleep(3)
        refs = get(f"{base}/references?fields={FIELDS}&limit=100")
        rec["citations"] = [x.get("citingPaper", {}) for x in (cites or {}).get("data", [])]
        rec["references"] = [x.get("citedPaper", {}) for x in (refs or {}).get("data", [])]
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
        sys.stderr.write(f"{pid}: cites={len(rec['citations'])} refs={len(rec['references'])}\n")
        time.sleep(3)
    f.close()


if __name__ == "__main__":
    main()
