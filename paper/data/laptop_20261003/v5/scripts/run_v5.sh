#!/bin/bash
# BrowSeg v5 runs: one plan entry per call (BROWSEG_GPU=nv for the NVIDIA T1200, otherwise Intel),
# kernel GPU lines (i915 / NVRM / Xid) captured for the run window, bench Chrome closed afterwards.
# usage: run_v5.sh <plan.json> <index>
cd ~/Documents/MyGithubProject2/BrowSeg_v5
T=~/Documents/MyGithubProject2/BrowSeg_tools
L=$T/v5; mkdir -p $L
PLAN=$1; I=$2
TAG=$(python3 -c "import json; print(json.load(open('$PLAN'))[$I]['tag'])")
python3 -c "import json; json.dump([json.load(open('$PLAN'))[$I]], open('$T/one_igpu.json','w'))"
node serve.mjs 8090 --bench ../BrowSeg_cases/cases --out paper/data/browser > $L/serve_$TAG.log 2>&1 & SRV=$!; sleep 2
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total,clocks.sm,power.draw --format=csv -l 2 > $L/nvsmi_$TAG.csv 2>&1 & NV=$!
START=$(date '+%Y-%m-%d %H:%M:%S'); echo "start $START" > $L/time_$TAG.txt
{ echo "load at start:"; uptime; free -h; top -bn1 -o %CPU | sed -n 7,12p; } >> $L/time_$TAG.txt
BROWSEG_GPU=${BROWSEG_GPU:-intel} node paper/scripts/bench_run.mjs paper/data/browser $T/one_igpu.json 2>&1 | tee $L/bench_$TAG.log
END=$(date '+%Y-%m-%d %H:%M:%S'); echo "end $END" >> $L/time_$TAG.txt
pkill -f browseg_bench_profiles; sleep 5
kill $SRV $NV
journalctl -k --since "$START" --until "$(date '+%Y-%m-%d %H:%M:%S')" | grep -i -E "i915|rcs0|GPU HANG|NVRM|Xid|nvidia|oom|killed process" > $L/kernel_$TAG.txt
echo "kernel GPU lines: $(wc -l < $L/kernel_$TAG.txt)"
echo FINISHED $TAG
