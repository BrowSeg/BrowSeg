#!/bin/bash
# Runs each plan entry separately (closeBenchBrowsers uses PowerShell, a no-op on Linux) and closes the
# bench browsers between entries.
cd ~/Documents/MyGithubProject2/BrowSeg
T=~/Documents/MyGithubProject2/BrowSeg_tools
node serve.mjs 8090 --bench ../BrowSeg_cases/cases --out paper/data/browser > $T/serve.log 2>&1 &
SRV=$!; sleep 2
run() {  # $1 plan file, $2 index, $3 GPU
  python3 -c "import json,sys; json.dump([json.load(open('$1'))[$2]], open('$T/one.json','w'))"
  BROWSEG_GPU=$3 node paper/scripts/bench_run.mjs paper/data/browser $T/one.json
  pkill -f browseg_bench_profiles; sleep 5
}
run paper/scripts/plan_laptop.json 2 intel
run paper/scripts/plan_laptop_nv.json 0 nv
kill $SRV
echo FINISHED
