#!/usr/bin/env bash
# usage: dl_one.sh "<id> <slug>"
set -u
line="$1"
pid=$(echo "$line" | awk '{print $1}')
slug=$(echo "$line" | awk '{print $2}')
cd /home/asus/EAI/research_spatial_action_20261105/papers || exit 1
out="${pid}__${slug}.pdf"
txt="${pid}__${slug}.txt"
if [ -s "$out" ]; then
  [ -s "$txt" ] || pdftotext -layout "$out" "$txt" 2>/dev/null
  echo "skip $pid"
  exit 0
fi
for attempt in 1 2 3; do
  code=$(timeout 100 curl -sSL --connect-timeout 15 -A "Mozilla/5.0 (literature reading)" \
    -w "%{http_code}" "https://export.arxiv.org/pdf/${pid}" -o "$out.part")
  if [ "$code" = "200" ] && [ -s "$out.part" ]; then
    mv "$out.part" "$out"
    pdftotext -layout "$out" "$txt" 2>/dev/null
    echo "ok $pid $(stat -c%s "$out")"
    exit 0
  fi
  rm -f "$out.part"
  sleep 3
done
echo "FAIL $pid"
