#!/usr/bin/env bash
# Download arXiv PDFs for the core reading set. Public arXiv only.
set -u
cd "$(dirname "$0")/../papers" || exit 1
while read -r pid slug; do
  [ -z "$pid" ] && continue
  out="${pid}__${slug}.pdf"
  txt="${pid}__${slug}.txt"
  if [ -s "$out" ] && [ -s "$txt" ]; then echo "skip $out"; continue; fi
  if [ ! -s "$out" ]; then
    code=$(curl -sSL -A "Mozilla/5.0 (research literature reading)" --max-time 300 \
      -w "%{http_code}" "https://export.arxiv.org/pdf/${pid}" -o "$out")
    echo "$pid $code $(stat -c%s "$out" 2>/dev/null)"
    sleep 2
  fi
  if [ -s "$out" ] && [ ! -s "$txt" ]; then pdftotext -layout "$out" "$txt" 2>/dev/null; fi
done < ../scripts/missing.txt
echo DONE
