#!/bin/bash
# LiTS logit tracing, Python (reference) side, desktop (2026-10-08). For each of the 10 case-task pairs where the
# public-build WebGPU output differs from the reference:
#   1) tools/make_reference.py: TotalSegmentator 2.18.0 on the CPU with dumps (input, logits, seg, crop bbox)
#   2) tie_check_pair.py / tie_check_resampled.py (PROBE_OUT): the network-grid points around each differing voxel
#      -> web/probe_specs/<key>.txt (the same spec is used by the BrowSeg probe build in the browser)
#   3) tools/probe_python.py: the same run with the sequential sliding window that records every tile at those points
# Outputs: data/native/m4_lits/<key>/ (dump, probe.log, tie.log). Run with nothing else timed on the machine.
set -u
ROOT="C:/Users/user/Desktop/TSC++Project"
PY=/c/Users/user/anaconda3/envs/ts218/python.exe
S="$ROOT/paper_jiim/paper_benchmarks/scripts"
OUT="$ROOT/paper_jiim/paper_benchmarks/data/native/m4_lits"
REF="$ROOT/data/bench_refs/ts218_cpu_lits"
BS="$ROOT/paper_jiim/paper_benchmarks/data/browser_lits_pub/lits_pub_chrome_webgpu"
mkdir -p "$OUT" "$ROOT/web/probe_specs"
export PYTHONIOENCODING=utf-8
# key  case  task  roi  model
while read -r KEY CASE TASK ROI MODEL; do
  D="$OUT/$KEY"; mkdir -p "$D"
  NII=$(ls "$ROOT/data/bench_cases_lits/$CASE"/*.nii.gz)
  echo "== $KEY $(date +%T)"
  [ -f "$D/dump/${MODEL}_logits.npy" ] || "$PY" "$ROOT/tools/make_reference.py" "$NII" "$D/dump" cpu "$TASK" "$ROI" > "$D/make_reference.log" 2>&1
  SPEC="$ROOT/web/probe_specs/$KEY.txt"; rm -f "$SPEC"
  TIE=tie_check_pair.py; [ "$MODEL" = 8 ] && TIE=tie_check_resampled.py
  PROBE_OUT="$SPEC" "$PY" "$S/$TIE" "$REF/$KEY.npy" "$BS/$KEY.u8" "$D/dump" "$MODEL" > "$D/tie.log" 2>&1
  sort -u "$SPEC" -o "$SPEC"
  echo "   spec $(wc -l < "$SPEC") lines"
  "$PY" "$ROOT/tools/probe_python.py" "$NII" "$D/python_probe" "$TASK" "$ROI" "$SPEC" > "$D/probe_python.log" 2>&1
  echo "   probe exit $?"
done <<'EOF'
lits_015__liver_segments_all lits_015 liver_segments - 570
lits_022__liver_segments_all lits_022 liver_segments - 570
lits_092__liver_segments_all lits_092 liver_segments - 570
lits_092__total_liver lits_092 total liver 291
lits_107__liver_segments_all lits_107 liver_segments - 570
lits_120__liver_segments_all lits_120 liver_segments - 570
lits_129__liver_segments_all lits_129 liver_segments - 570
lits_129__liver_vessels_all lits_129 liver_vessels - 8
lits_163__liver_segments_all lits_163 liver_segments - 570
lits_185__liver_segments_all lits_185 liver_segments - 570
EOF
echo ALLDONE
