#!/usr/bin/env python3
"""Print the body abstract of an extracted paper text (handles both PDF -layout
and arXiv HTML renderings, which repeat the abstract heading after a TOC)."""
import re
import sys

path = sys.argv[1]
lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()

idx = [i for i, l in enumerate(lines) if re.match(r"^\s*(Abstract|ABSTRACT|A BSTRACT)\s*$", l)]
if not idx:
    print("\n".join(lines[:40]))
    sys.exit()
start = idx[-1] if len(idx) > 1 else idx[0]
out = []
for l in lines[start:start + 60]:
    if re.match(r"^\s*(\d+\s+)?(Introduction|I NTRODUCTION|1 Introduction)\s*$", l):
        break
    out.append(l)
print("\n".join(out))
