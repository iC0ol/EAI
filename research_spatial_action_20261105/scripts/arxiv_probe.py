#!/usr/bin/env python3
"""Minimal arXiv API probe used by the literature investigation.

Only queries the public arXiv Atom API and writes JSONL metadata.
No third-party code is imported; stdlib only.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
API = "https://export.arxiv.org/api/query"


def query(q, max_results=50, sort="relevance"):
    params = {
        "search_query": q,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate" if sort == "date" else "relevance",
        "sortOrder": "descending",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                raw = r.read()
            break
        except Exception as e:  # network flake / rate limit
            sys.stderr.write(f"retry {attempt}: {e}\n")
            time.sleep(5 * (attempt + 1))
    else:
        return []
    root = ET.fromstring(raw)
    out = []
    for e in root.findall("a:entry", NS):
        aid = e.find("a:id", NS).text.rsplit("/", 1)[-1]
        out.append(
            {
                "id": aid,
                "title": " ".join(e.find("a:title", NS).text.split()),
                "published": e.find("a:published", NS).text[:10],
                "updated": e.find("a:updated", NS).text[:10],
                "abstract": " ".join(e.find("a:summary", NS).text.split()),
                "authors": [a.find("a:name", NS).text for a in e.findall("a:author", NS)],
                "primary_category": e.find("arxiv:primary_category", NS).attrib.get("term"),
                "comment": (e.find("arxiv:comment", NS).text if e.find("arxiv:comment", NS) is not None else ""),
            }
        )
    return out


def main():
    spec = json.load(open(sys.argv[1]))
    outpath = sys.argv[2]
    seen = {}
    log = []
    with open(outpath, "w") as f:
        for item in spec:
            res = query(item["q"], item.get("n", 50), item.get("sort", "relevance"))
            log.append({"query": item["q"], "label": item.get("label"), "n": len(res)})
            sys.stderr.write(f"[{item.get('label')}] {item['q']} -> {len(res)}\n")
            for r in res:
                if r["published"] > "2026-11-05":
                    continue
                if r["id"] not in seen:
                    seen[r["id"]] = True
                    r["query_label"] = item.get("label")
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            time.sleep(3.2)
    json.dump(log, open(outpath + ".queries.json", "w"), indent=1)
    sys.stderr.write(f"unique={len(seen)}\n")


if __name__ == "__main__":
    main()
