# Building and verifying BrowSeg

BrowSeg is a C++ re-implementation of the TotalSegmentator inference pipeline (DICOM → resampling → nnU-Net
sliding window → post-processing) that compiles natively and to WebAssembly. The 3D U-Net runs either in
C++ (CPU, WASM SIMD + threads) or in WebGPU compute shaders (`web/gpu_unet.js`). This file explains how to
build it and how to check that its output is identical to Python TotalSegmentator.

## Layout

```
src/tsc/      engine: dicom.* (DICOM → canonical RAS volume), resample.* (exact scipy.ndimage.zoom and
              nnU-Net separate-z resampling), nnunet.* (normalisation, sliding window, fp16 accumulation),
              unet.* (CPU network), pipeline.* (TotalSegmentator task flow), mesh.* (Surface Nets), weights.*
cli/main.cpp  command-line tool (native)
web/          wasm_api.cpp (C API), worker.js (engine in a Web Worker), gpu_unet.js (WebGPU network),
              index.html + js/ (viewer, label editing, export), bench.html (benchmark runner),
              gputest.html (WebGPU network vs PyTorch layer test), config.js (where the weights are)
tools/        export_weights.py (TotalSegmentator checkpoint → .tsw), make_reference.py (Python reference
              dumps of every stage), ref_to_npy.py, make_layer_ref.py
tests/        test_task (stage-by-stage comparison with the reference), test_unet, test_resample,
              test_wasm_node.mjs (WASM CPU path under Node)
weights/      classmaps.txt (in git), MANIFEST.json + NOTICE; the .tsw files come from the GitHub release
paper/        benchmark records and scripts of the paper
```

## Prerequisites

- CMake ≥ 3.20, a C++17 compiler (tested: MSVC 2022 on Windows; GCC/Clang should work), Node ≥ 18
- Emscripten (tested: 4.0.23) for the WebAssembly build; `build_wasm.bat` expects it in `C:\emsdk`
- For the Python reference: a Python environment with `TotalSegmentator==2.18.0` (nnunetv2 2.7.0) and its
  weights downloaded once (`TotalSegmentator -i <ct> -o x --task total --roi_subset liver` does that)

## 1. Weights

Download the `.tsw` files of the release into `weights/` (see `weights/MANIFEST.json` for names and
SHA-256), or convert them yourself from the TotalSegmentator checkpoints on your machine:

```
python tools/export_weights.py 298 weights/total6mm_298.tsw
python tools/export_weights.py 291 weights/organs_291.tsw      (292 vertebrae, 293 cardiac, 294 muscles, 295 ribs)
python tools/export_weights.py 570 weights/liver_segments_570.tsw
python tools/export_weights.py 8   weights/liver_vessels_8.tsw
python tools/export_classmaps.py                                (weights/classmaps.txt)
```

The conversion changes the file format only; `sha256sum` of your files should match the manifest.

## 2. Native build and command line

```
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
build\Release\tsc_liver.exe <DICOM folder> weights out\case --task total --roi liver     → out\case_labels.nii, .obj, .stl
   --task liver_segments --roi -      --task liver_vessels --roi -      --threads N      --resampling_order 1|3
```

`--resampling_order 1` (default) matches TotalSegmentator ≥ 2.16; `3` matches ≤ 2.15.

## 3. WebAssembly build and browser

```
build_wasm.bat                       → web/dist/tsc.js, tsc.wasm
node serve.mjs 8080                  → http://localhost:8080/web/   (drop a DICOM folder on the page)
node serve.mjs 8080 <DICOM folder>   → http://localhost:8080/web/?demo=1 loads that folder
```

The engine uses WASM threads, so the page must be served with `Cross-Origin-Opener-Policy: same-origin`
and `Cross-Origin-Embedder-Policy: require-corp`; `serve.mjs` sends them. URL parameters of the app:
`cpu=1` (force the CPU path), `fp16=1` (half-precision weights, faster download, not bit-identical),
`order=3` (TotalSegmentator ≤ 2.15 resampling), `threads=N`.

## 4. Verifying against Python TotalSegmentator

`tools/make_reference.py` runs the Python version and saves every intermediate stage (resampled input,
normalised network input, fp16 logits, argmax of each model, crop mask, final label map); `test_task`
runs the C++ engine on the same DICOM folder and compares stage by stage:

```
python tools/make_reference.py <DICOM> ref/case1_liver cpu                       (total, roi_subset liver)
python tools/make_reference.py <DICOM> ref/case1_segments cpu liver_segments -
python tools/make_reference.py <DICOM> ref/case1_vessels cpu liver_vessels -
python tools/ref_to_npy.py ref/case1_liver                                        (same for the others)
build\Release\test_task.exe total liver <DICOM> weights ref/case1_liver final_liver_can.npy
build\Release\test_task.exe liver_segments - <DICOM> weights ref/case1_segments
build\Release\test_task.exe liver_vessels - <DICOM> weights ref/case1_vessels
node tests/test_wasm_node.mjs <DICOM> weights ref/case1_liver/final_liver_can.npy  (WASM CPU path)
```

Expected: every stage `EXACT` and `RESULT: ALL CHECKED STAGES IDENTICAL`. The fp16 logits legitimately
differ in a small fraction of elements by one rounding step (summation order); the argmax and the final
label map do not. `make_reference.py` writes `resampling_order.txt` and `ts_version.txt` so that
`test_task` uses the same resampling order as the Python version that made the reference.

For the network alone, `python tools/make_layer_ref.py 291 ref/case1_liver/291_pre.npy ref/layers_291`
+ `build\Release\test_unet.exe weights/organs_291.tsw ref/layers_291` compares every layer with PyTorch,
and `web/gputest.html` does the same for the WebGPU shaders (serve with a DICOM folder for `/ref`).

## 5. Benchmarks (as in the paper)

```
node serve.mjs 8090 --bench <cases dir> --out <records dir>
   <cases dir>/<case>/  = DICOM files (or one .nii/.nii.gz) per case
open http://localhost:8090/web/bench.html?tag=<name>&cases=a,b&tasks=total:liver;liver_segments:-&reps=3
python paper/scripts/make_refs.py <cases dir> <refs dir> cpu "total:liver;liver_segments:-;liver_vessels:-"
python paper/scripts/compare.py <records dir> <refs dir> summary.csv
```

`paper/scripts/bench_run.mjs` runs a whole plan (several browsers and settings) unattended.

## Design notes that matter for exactness

- Resampling reproduces `scipy.ndimage.zoom` (spline prefilter, `mode='nearest'`) in double precision,
  including the order of operations; that is why the pre-/post-processing stays on the CPU (WebGPU has no
  64-bit floats).
- TotalSegmentator accumulates the Gaussian-weighted tile outputs in fp16; BrowSeg does the same, in the same
  order, on the CPU and in the WebGPU `accum` shader.
- nnU-Net's own resampling (task `liver_vessels`) and its separate-z path for thick slices
  (`skimage.transform.resize` per slice, nearest neighbour along z) are re-implemented, not approximated.
- The WebGPU network computes in fp32; `shader-f16` is not used.
