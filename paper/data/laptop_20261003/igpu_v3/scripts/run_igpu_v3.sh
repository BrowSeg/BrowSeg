#!/bin/bash
# BrowSeg v3 iGPU (Intel UHD) chunked-submission runs: one plan entry per call, Intel Vulkan ICD,
# kernel i915 lines captured for the run's time window, bench Chrome closed afterwards.
# usage: run_igpu_v3.sh <plan.json> <index>
cd ~/Documents/MyGithubProject2/BrowSeg_v3
T=~/Documents/MyGithubProject2/BrowSeg_tools
L=$T/igpu_v3; mkdir -p $L
PLAN=$1; I=$2
TAG=$(python3 -c "import json; print(json.load(open('$PLAN'))[$I]['tag'])")
python3 -c "import json; json.dump([json.load(open('$PLAN'))[$I]], open('$T/one_igpu.json','w'))"
node serve.mjs 8090 --bench ../BrowSeg_cases/cases --out paper/data/browser > $L/serve_$TAG.log 2>&1 & SRV=$!; sleep 2
START=$(date '+%Y-%m-%d %H:%M:%S'); echo "start $START" > $L/time_$TAG.txt
{ echo "load at start:"; uptime; free -h; top -bn1 -o %CPU | sed -n 7,12p; } >> $L/time_$TAG.txt
BROWSEG_GPU=intel node paper/scripts/bench_run.mjs paper/data/browser $T/one_igpu.json 2>&1 | tee $L/bench_$TAG.log
END=$(date '+%Y-%m-%d %H:%M:%S'); echo "end $END" >> $L/time_$TAG.txt
pkill -f browseg_bench_profiles; sleep 5
kill $SRV
journalctl -k --since "$START" --until "$(date '+%Y-%m-%d %H:%M:%S')" | grep -i -E "i915|rcs0|GPU HANG" > $L/kernel_$TAG.txt
echo "kernel i915 lines: $(wc -l < $L/kernel_$TAG.txt)"
echo FINISHED $TAG
