#!/bin/bash
# One Firefox v4 run: serve.mjs, nvidia-smi log, firefox_bench.sh, kernel GPU lines for the run window.
# usage: run_ff_v4.sh <tag> <query> <timeoutMin>
cd ~/Documents/MyGithubProject2/BrowSeg_v4
T=~/Documents/MyGithubProject2/BrowSeg_tools; L=$T/v4; mkdir -p $L
TAG=$1
node serve.mjs 8090 --bench ../BrowSeg_cases/cases --out paper/data/browser > $L/serve_$TAG.log 2>&1 & SRV=$!; sleep 2
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,clocks.sm,power.draw --format=csv -l 5 > $L/nvsmi_$TAG.csv 2>&1 & NV=$!
START=$(date '+%Y-%m-%d %H:%M:%S'); echo "start $START" > $L/time_$TAG.txt
{ echo "load at start:"; uptime; free -h; top -bn1 -o %CPU | sed -n 7,12p; } >> $L/time_$TAG.txt
BROWSEG_GPU=nv $T/firefox_bench.sh "$@" 2>&1 | tee $L/bench_$TAG.log
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv >> $L/nvsmi_apps_$TAG.txt 2>&1
echo "end $(date '+%Y-%m-%d %H:%M:%S')" >> $L/time_$TAG.txt
kill $SRV $NV
journalctl -k --since "$START" --until "$(date '+%Y-%m-%d %H:%M:%S')" | grep -i -E "i915|rcs0|GPU HANG|NVRM|Xid|nvidia|oom|killed process" > $L/kernel_$TAG.txt
echo "kernel GPU lines: $(wc -l < $L/kernel_$TAG.txt)"
echo FINISHED $TAG
