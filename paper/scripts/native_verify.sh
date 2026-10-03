#!/bin/bash
# Native (CLI) run of every case x task after a code change, to confirm the label maps are unchanged.
# usage: bash native_verify.sh <out dir>      (then: python native_verify_compare.py <out dir>)
# Writes <out>/<case>__<task>_<roi>_labels.nii with build/Release/tsc_liver.exe (24 threads).
set -u
cd "$(dirname "$0")/../../.."
OUT=${1:?out dir}
mkdir -p "$OUT"
for i in $(seq -w 1 20); do
  c=ircad$i
  for spec in "total liver" "liver_segments -" "liver_vessels -" "total -"; do
    set -- $spec
    key="${c}__$1_$([ "$2" = "-" ] && echo all || echo "$2")"
    [ -f "$OUT/${key}_labels.nii" ] && continue
    ./build/Release/tsc_liver.exe "data/bench_cases/$c" weights "$OUT/$key" --task "$1" --roi "$2" --threads 24 > "$OUT/$key.log" 2>&1 || echo "FAILED $key"
    echo "$(date +%H:%M:%S) $key"
  done
done
echo ALL DONE
