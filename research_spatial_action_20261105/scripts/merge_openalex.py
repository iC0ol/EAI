#!/usr/bin/env python3
"""Merge OpenAlex publication metadata into sources/papers.jsonl.

Replaces 'venue_status: UNKNOWN/preprint' with what OpenAlex actually indexes
(conference proceedings vs arXiv preprint), and records the DOI. Also applies a
small read-level correction for papers opened after the first pass.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
meta = {}
for line in open(os.path.join(ROOT, "sources", "openalex_meta.jsonl")):
    r = json.loads(line)
    meta[r["id"]] = r

read_fix = {
    "2609.18514": "PARTIAL_TEXT",
    "2512.02902": "PARTIAL_TEXT",
    "2610.22997": "PARTIAL_TEXT",
    "2509.18644": "ABSTRACT_ONLY",
    "2604.09338": "PARTIAL_TEXT",
}

# Asset check, 2026-11-05: none of these four papers contains a project or code
# URL in its arXiv HTML or PDF (only arXiv/LaTeXML boilerplate). GitHub repository
# search for "LIBERO-RIG" returns no matching repo. Recorded explicitly so the
# register does not imply availability.
ASSET_FIX = {
    "2607.09825": "NO_URL_IN_PAPER",
    "2610.18843": "NO_URL_IN_PAPER (paper states the benchmark is released, but no URL appears in the text; GitHub search finds no matching repo)",
    "2610.01626": "NO_URL_IN_PAPER",
    "2512.02902": "NO_URL_IN_PAPER",
}

rows = [json.loads(l) for l in open(os.path.join(ROOT, "sources", "papers.jsonl"))]
for r in rows:
    m = meta.get(r["id"])
    if m and m.get("status") == "ok":
        venue = m.get("venue")
        if m.get("type") == "conference-paper" and venue:
            r["venue_status"] = f"published: {venue} (OpenAlex record, retrieved 2026-11-05)"
        else:
            r["venue_status"] = "preprint: arXiv only; no journal/conference record in OpenAlex at retrieval"
        r["openalex_doi"] = m.get("doi")
        r["openalex_type"] = m.get("type")
        r["openalex_cited_by"] = m.get("cited_by_count")
    if r["id"] in read_fix:
        r["read_level"] = read_fix[r["id"]]
    if r["id"] in ASSET_FIX:
        r["code"] = ASSET_FIX[r["id"]]

with open(os.path.join(ROOT, "sources", "papers.jsonl"), "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("merged", len(rows))
