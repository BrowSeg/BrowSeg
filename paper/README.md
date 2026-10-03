# Benchmark records of the BrowSeg paper

【原稿確定後に整える】

- `browser/<tag>/` — one folder per browser run (`environment.json`: browser, GPU, limits; `<case>__<task>.json`: timings per repetition, output hash, engine log). The label maps themselves (`.u8`) are not in the repository (derived from 3D-IRCADb-01, CC BY-NC-ND 4.0).
- `python_refs/` — TotalSegmentator 2.18.0 reference runs: version, resampling order, device, seconds, labels present (`.json`; the label maps are not redistributed).
- `native/` — BrowSeg C++ build, stage timings with 1 and 24 threads.
- `scripts/` — `make_refs.py` (runs TotalSegmentator 2.18 on the cases and saves the reference label maps and timings), `bench_run.mjs` + `plan_*.json` (drives `web/bench.html` through the browsers for the recorded runs), `compare.py` (browser output vs Python reference, per case: differing voxels, Dice per label, repeatability), `hashes.py` (hash tables of the label maps), `tie_check.py` (fp16 logits of the two leading structures at the differing voxels), `analyze.py` (tables of the paper), `native_*` (before/after check of the post-measurement engine fixes).

To reproduce: obtain 3D-IRCADb-01 from IRCAD (https://www.ircad.fr/research/data-sets/liver-segmentation-3d-ircadb-01/), extract `PATIENT_DICOM` of each case into `cases/ircadNN/`, run TotalSegmentator 2.18.0 with `scripts/make_refs.py`, then open `bench.html` as described in `scripts/README.md`.

## Reproducing the agreement from the public page

`https://browseg.github.io/BrowSeg/bench.html?local=1` runs the same benchmark page that produced `browser/<tag>/`,
but reads the cases from a folder you choose and keeps the results in the browser (nothing is uploaded). It compares the
label-map hashes with `data/desktop_hashes.json` (WebGPU runs: tag `desk_chrome_webgpu_final` for the three liver tasks
and `desk_chrome_webgpu_total_20` for the 117 structures, 80 case x task pairs) or `data/desktop_hashes_wasm20.json`
(CPU/WebAssembly runs, tag `desk_chrome_wasm_20`, 60 pairs), each run against the record of the path it ran on;
`tools/verify_bench.py` does the same
comparison on the downloaded JSON. See the top-level README, section "Reproduce the paper's agreement from the public URL".
