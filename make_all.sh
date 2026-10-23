#!/bin/bash
# Builds the four standard editions from docs/folio.js and audits every link.
set -e
cd "$(dirname "$0")"
mkdir -p dist
for ed in "daily:" "weekly:--weekly"; do
  for ws in "monday:" "sunday:--sunday"; do
    name="the-folio-2026-27-${ed%%:*}-${ws%%:*}"
    python3 build.py ${ed#*:} ${ws#*:} --out "dist/$name.pdf" > /dev/null
    echo "== $name: $(pdfinfo dist/$name.pdf | awk '/Pages/{print $2}') pages, $(du -h dist/$name.pdf | cut -f1)"
    python3 audit.py "dist/$name.pdf" "dist/$name.ids.json" | head -2
    rm "dist/$name.ids.json"
  done
done
