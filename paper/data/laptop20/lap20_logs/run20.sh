#!/bin/bash
# 20-case laptop runs: NVIDIA WebGPU, single-thread build, WASM; one tag at a time, bench Chrome closed between tags.
cd ~/Documents/MyGithubProject2/BrowSeg
T=~/Documents/MyGithubProject2/BrowSeg_tools
nvidia-smi --query-gpu=timestamp,temperature.gpu,utilization.gpu,memory.used,clocks.sm,power.draw,clocks_throttle_reasons.active --format=csv -l 10 > $T/nvsmi_lap20.csv 2>&1 & NV=$!
node serve.mjs 8090 --bench ../BrowSeg_cases/cases --out paper/data/browser > $T/serve20.log 2>&1 & SRV=$!; sleep 2
for i in 0 1 2; do
  python3 -c "import json; json.dump([json.load(open('paper/scripts/plan_laptop20.json'))[$i]], open('$T/one20.json','w'))"
  BROWSEG_GPU=nv node paper/scripts/bench_run.mjs paper/data/browser $T/one20.json
  pkill -f browseg_bench_profiles; sleep 5
done
kill $SRV $NV
echo FINISHED
