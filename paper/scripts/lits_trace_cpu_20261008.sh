#!/bin/bash
# LiTS logit tracing of the 9 CPU (WebAssembly) mismatches (2026-10-08), after the v1.1 desktop CPU re-measurement.
# Reference side as in lits_trace_python_20261008.sh (dump, grid points around the CPU-differing voxels, probe_python);
# BrowSeg side: the probe build (web/dist-probe) on the CPU under Node (tests/probe_wasm_node.mjs, NIfTI via
# Nifti.readRaw + tsc_set_volume_raw), whose label map must equal the measured CPU output.
set -u
ROOT="C:/Users/user/Desktop/TSC++Project"
PY=/c/Users/user/anaconda3/envs/ts218/python.exe
S="$ROOT/paper_jiim/paper_benchmarks/scripts"
OUT="$ROOT/paper_jiim/paper_benchmarks/data/native/m4_lits"
REF="$ROOT/data/bench_refs/ts218_cpu_lits"
CPU="$ROOT/paper_jiim/paper_benchmarks/data/browser_lits_v11"
W="$ROOT/weights"
export PYTHONIOENCODING=utf-8
mkdir -p "$OUT/cpu"
while read -r KEY CASE TASK ROI MODEL; do
  D="$OUT/$KEY"; C="$OUT/cpu/$KEY"; mkdir -p "$D" "$C"
  NII=$(ls "$ROOT/data/bench_cases_lits/$CASE"/*.nii.gz)
  U8=$(ls "$CPU"/lits_v11_chrome_wasm_*/"$KEY.u8" 2>/dev/null | head -1)
  echo "== $KEY $(date +%T) cpu u8 $U8"
  [ -f "$D/dump/${MODEL}_logits.npy" ] || "$PY" "$ROOT/tools/make_reference.py" "$NII" "$D/dump" cpu "$TASK" "$ROI" > "$D/make_reference.log" 2>&1
  SPEC="$C/spec.txt"; rm -f "$SPEC"
  TIE=tie_check_pair.py; [ "$MODEL" = 8 ] && TIE=tie_check_resampled.py
  PROBE_OUT="$SPEC" "$PY" "$S/$TIE" "$REF/$KEY.npy" "$U8" "$D/dump" "$MODEL" > "$C/tie.log" 2>&1
  sort -u "$SPEC" -o "$SPEC"; echo "   spec $(wc -l < "$SPEC") lines"
  "$PY" "$ROOT/tools/probe_python.py" "$NII" "$C/python_probe" "$TASK" "$ROI" "$SPEC" > "$C/probe_python.log" 2>&1
  echo "   python probe exit $?"
  node "$ROOT/tests/probe_wasm_node.mjs" "$NII" "$W" "$TASK" "$ROI" "$SPEC" "$C/browseg_probe.u8" "$U8" > "$C/browseg_probe_cpu.log" 2>&1
  echo "   node probe exit $? $(grep COMPARE "$C/browseg_probe_cpu.log")"
  python "$S/compare_probes.py" "$C/browseg_probe_cpu.log" "$C/python_probe/probe.log" > "$C/compare_cpu.txt" 2>&1
done <<'EOF'
lits_015__liver_segments_all lits_015 liver_segments - 570
lits_054__liver_vessels_all lits_054 liver_vessels - 8
lits_092__total_liver lits_092 total liver 291
lits_107__liver_segments_all lits_107 liver_segments - 570
lits_120__liver_segments_all lits_120 liver_segments - 570
lits_129__liver_segments_all lits_129 liver_segments - 570
lits_129__liver_vessels_all lits_129 liver_vessels - 8
lits_163__liver_segments_all lits_163 liver_segments - 570
lits_185__liver_segments_all lits_185 liver_segments - 570
EOF
echo ALLDONE
