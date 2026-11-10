#!/usr/bin/env bash
set -u
URL="https://downloads.cs.stanford.edu/downloads/rt_benchmark/square/mh/image.hdf5"
OUT="/home/asus/EAI/gate_b_v2/assets/square_mh/image.hdf5"
TARGET=6959859145
for attempt in $(seq 1 30); do
    size=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
    if [ "$size" -ge "$TARGET" ]; then echo "complete $size"; exit 0; fi
    echo "attempt $attempt from $size"
    curl -L -C - --retry 5 --retry-delay 3 --connect-timeout 30 --speed-time 60 --speed-limit 1024 -o "$OUT" "$URL"
    sleep 3
done
echo "gave up"; exit 1
