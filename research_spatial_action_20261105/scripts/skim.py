#!/usr/bin/env python3
"""Print structured skim of an extracted paper text: title/abstract head, and
limitation / conclusion / discussion region, plus reference start line."""
import re
import sys

path, head_n, tail_n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()

ref = None
for i, l in enumerate(lines):
    if re.match(r"^\s*(R\s?EFERENCES|References|REFERENCES)\s*$", l):
        ref = i  # keep last occurrence: HTML renderings repeat it in the table of contents
if ref is None:
    ref = len(lines)

print(f"### {path}  total_lines={len(lines)} refs_at={ref}")
print("--- HEAD ---")
print("\n".join(lines[:head_n]))
print("--- PRE-REFERENCES TAIL ---")
start = max(head_n, ref - tail_n)
print("\n".join(lines[start:ref]))
