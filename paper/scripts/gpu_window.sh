#!/bin/bash
# Desktop GPU window (run from anywhere). Order keeps the CPU quiet during the timed runs:
#  0) wait for the CPU reference job (PID given as $1) to finish
#  1) browsers: web/bench.html plan (WebGPU + WASM, Chrome + Firefox)
#  2) Python TotalSegmentator 2.18 on the GPU, 3 repetitions (timing baseline + CPU-vs-GPU label differences)
#  -> writes paper_jiim/paper_benchmarks/data/GPU_WINDOW_DONE, after which the GPU can be handed back
#  3) CPU references for task total (117 classes) on 5 cases
cd "$(dirname "$0")/../../.."
LOG=paper_jiim/paper_benchmarks/data/gpu_window.log
PY=/c/Users/user/anaconda3/envs/ts218/python.exe
FIVE=ircad01,ircad02,ircad05,ircad10,ircad18
if [ -n "$1" ]; then while tasklist //FI "PID eq $1" | grep -q " $1 "; do sleep 20; done; fi
echo "$(date) native thread scaling (pre/post-processing share, single-thread estimate)" >> $LOG
mkdir -p paper_jiim/paper_benchmarks/data/native out/native
for t in 1 24; do
  for task in "total --roi liver" "liver_segments --roi -" "liver_vessels --roi -"; do
    name=$(echo $task | cut -d' ' -f1)
    ./build/Release/tsc_liver.exe data/ircad/1/PATIENT_DICOM weights out/native/case1_${name}_t$t --task $task --threads $t \
      > paper_jiim/paper_benchmarks/data/native/case1_${name}_threads$t.log 2>&1
  done
done
echo "$(date) start browsers" >> $LOG
node serve.mjs 8090 --bench data/bench_cases > data/serve_bench.log 2>&1 &
SERVER=$!
sleep 3
node paper_jiim/paper_benchmarks/scripts/bench_run.mjs paper_jiim/paper_benchmarks/data/browser paper_jiim/paper_benchmarks/scripts/plan_desktop.json >> $LOG 2>&1
kill $SERVER
echo "$(date) start python gpu" >> $LOG
for r in 1 2 3; do
  $PY paper_jiim/paper_benchmarks/scripts/make_refs.py data/bench_cases data/bench_refs/ts218_gpu_r$r gpu "total:liver;liver_segments:-;liver_vessels:-;total:-" $FIVE >> $LOG 2>&1
done
echo "$(date) GPU window done" >> $LOG
date > paper_jiim/paper_benchmarks/data/GPU_WINDOW_DONE
echo "$(date) start cpu total refs" >> $LOG
OMP_NUM_THREADS=12 $PY paper_jiim/paper_benchmarks/scripts/make_refs.py data/bench_cases data/bench_refs/ts218_cpu cpu "total:-" $FIVE >> $LOG 2>&1
echo "$(date) all done" >> $LOG
