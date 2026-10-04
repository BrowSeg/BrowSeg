# BrowSeg

TotalSegmentator in the web browser, with the same output as the Python version.

BrowSeg runs the CT segmentation models of [TotalSegmentator](https://github.com/wasserth/TotalSegmentator)
(nnU-Net) entirely inside the browser: the DICOM series is read, resampled, segmented and written back on your
own computer. Nothing is installed and no image leaves the machine; the only download is the model weights,
which the browser caches after the first use. The network runs on the GPU through WebGPU, or on the CPU
(WebAssembly) when WebGPU is not available. On the 20 CTs of 3D-IRCADb-01 the label maps were voxel-identical to
TotalSegmentator 2.18 run on the CPU in 75 of the 80 case x task pairs on the WebGPU path and 55 of 60 on the CPU
path; the remaining pairs differ in 1 to 4 voxels out of tens of millions (see the paper and `tools/`).

> **Not a medical device.** BrowSeg is research software. Do not use its output for diagnosis or treatment
> without independent verification.

## Use it

Open **https://browseg.github.io/BrowSeg/** in Chrome or Edge (Windows, macOS, Linux; version 113 or
later) and drop a folder with the DICOM files of one CT series onto the page. Then pick a task:

| Task | TotalSegmentator task | Output | Weights download (first time only) |
|---|---|---|---|
| Liver | `total --roi_subset liver` | liver | 191 MB |
| Abdominal organs | `total --roi_subset ...` | selected organs | 191 MB |
| All structures | `total` | 117 structures | 624 MB |
| Liver segments | `liver_segments` | Couinaud segments 1–8 | 189 MB |
| Liver vessels | `liver_vessels` | intrahepatic vessels, liver tumour | 189 MB |

Results can be saved as NIfTI label maps (`.nii.gz`) and as meshes (OBJ / STL).

**Requirements.** A browser with WebGPU: Chrome or Edge 113+ (recommended). On Linux, Chrome needs WebGPU enabled
(`--enable-unsafe-webgpu --enable-features=Vulkan` in our tests with Chrome 142). In Firefox 156 on Windows, one GPU
submission per patch sometimes exceeded the GPU driver's time limit and the GPU was reset; BrowSeg detects this and
retries with the network submitted in parts, which completes but was slower than Firefox's CPU path in our tests, so
Firefox users are better served by the CPU path or by Chrome/Edge (Firefox on Linux has WebGPU off by default). About
3 GB of free memory for the liver tasks and 4 GB for the
117-structure task (the application's heap reached 3.5 GB on one of the test CTs, case 20 with 225 slices; 4 GB is
the 32-bit WebAssembly limit), and a GPU with at least 2 GB of memory for the GPU path. Uncompressed DICOM
(Implicit/Explicit VR Little Endian) or NIfTI input. Multi-frame DICOM and JPEG-compressed series are not
supported yet.

**Two builds.** The page picks the build automatically:
- *multi-threaded* (fast pre/post-processing) — needs a cross-origin-isolated page (COOP/COEP headers);
  on GitHub Pages this is done by a small service worker, which reloads the page once on the first visit;
- *single-threaded* — used when isolation is not available (for example when the app is embedded in another
  page). Same results, slower pre/post-processing.

## Check the results yourself

BrowSeg is meant to give exactly the same label map as TotalSegmentator. To verify this on your own CT:

1. In BrowSeg, run a task and save the labels (`browseg_labels.nii.gz`).
2. Run TotalSegmentator (2.16 or later) on the same CT **on the CPU**:
   `TotalSegmentator -i <dicom folder> -o ts.nii.gz --ml --task liver_segments --device cpu`
   (for the liver: `--task total --roi_subset liver`).
3. `python tools/compare_with_totalsegmentator.py browseg_labels.nii.gz ts.nii.gz`

The script prints the number of differing voxels and the Dice coefficient per label. TotalSegmentator's own
output on a GPU differs from its CPU output by tens to thousands of voxels (up to about 27,000 in one case) and
changes from run to run, so compare against a CPU run. Versions before 2.16 resampled the input with a cubic spline; add `?order=3` to the
BrowSeg URL to reproduce them.

## Reproduce the paper's agreement from the public URL

The paper reports that BrowSeg's label maps equal those of TotalSegmentator 2.18 (CPU) voxel for voxel on the 20 CTs
of 3D-IRCADb-01 in 75 of 80 case x task pairs (WebGPU) and 55 of 60 (CPU path), with differences of 1 to 4 voxels in
the others, and that repeated runs give identical output. You can check this with the published page and your own
copy of the data, without installing anything (the records below hold the hash of every label map the paper's desktop
produced, including the ones that differ from TotalSegmentator):

1. Obtain 3D-IRCADb-01 from IRCAD (https://www.ircad.fr/research/data-sets/liver-segmentation-3d-ircadb-01/;
   CC BY-NC-ND, so it is not included here) and arrange the cases as `cases/ircad01/ … cases/ircad20/`, each folder
   holding the DICOM files of `PATIENT_DICOM`.
2. Open one of the links below in Chrome or Edge, press *Choose the cases folder…* and select `cases/`, then *Run*.
   One page covers all conditions: the network (WebGPU or CPU/WebAssembly), the build (multi- or single-threaded), the
   thread limit, the tasks and the number of runs per case are chosen on the page; the links below only preset them. By
   default every case is run once per task (the paper used three runs). The time of each run is reported together with
   the part spent loading the model (weights from the browser cache, GPU upload), so the segmentation time can be read
   separately.

   | Condition | Link | Time for the 20 cases (desktop of the paper) |
   |---|---|---|
   | WebGPU, 4 tasks | https://browseg.github.io/BrowSeg/bench.html?local=1&tasks=total:liver;liver_segments:-;liver_vessels:-;total:- | about 10 min |
   | CPU (WebAssembly, all threads), 4 tasks | https://browseg.github.io/BrowSeg/bench.html?local=1&cpu=1&tasks=total:liver;liver_segments:-;liver_vessels:-;total:- | about 70 min for the three liver tasks; about 3 h with the 117-structure task (estimate: the paper did not time this task on the CPU path; remove `total:-` from the tasks box to skip it) |
   | Single-threaded build (pages without cross-origin isolation), WebGPU | https://browseg.github.io/BrowSeg/bench.html?local=1&st=1&nocoi=1&tasks=total:liver;liver_segments:-;liver_vessels:- | about 12 min (estimate; the paper measured this build on the laptop only, about 17 min there) |

   The paper's records cover the WebGPU and CPU paths; `threads=N` limits the number of threads of the multi-threaded build.
   *GPU: submit per layer* (`gpuchunk=1`) sends the network to the GPU one compute step at a time instead of one patch
   at a time; it is meant for integrated GPUs whose driver resets a GPU job that runs longer than its time limit (the
   paper's Limitations describe such a case). It does not change the arithmetic, only the submission, and is off in
   the paper's measurements.
3. The page shows, for every case and task, the hash of the label map of each run next to the hash recorded for the
   paper (`paper/data/desktop_hashes.json` for WebGPU, 80 case x task pairs; `paper/data/desktop_hashes_wasm20.json`
   for the CPU path, 60 pairs: the paper did not run the 117-structure task on the CPU path, so it has no CPU record
   and is reported as "no record"), each run against the record of the path it actually used
   (runs without a record are left out of the verdict and the table says how many runs were compared), and
   whether the repeated runs were identical. *Download results (JSON)* saves everything (environment, timings, hashes).
4. `python tools/verify_bench.py <downloaded>.json` prints the same comparison and exits with status 0 when all
   recorded case x task pairs match.

The hash is FNV-1a over the label map on the original CT grid (one byte per voxel), the same function the paper's
benchmark server used, so equal hashes mean equal label maps. The CT never leaves your computer; the page only
downloads the weights (the files of this repository's release, served with the page). Timings measured this way include the first download of the
weights over the internet; the paper's timings were measured with the weights served from the same computer.

## Models and licences

The weights in `weights/` are the official TotalSegmentator checkpoints (fold 0 of the `3d_fullres` nnU-Net
models) converted to BrowSeg's `.tsw` format, unchanged in value. Only tasks that TotalSegmentator releases
under the Apache License 2.0 are included; see `weights/MANIFEST.json` for the upstream release, file
hashes and licence of every file, and `weights/NOTICE` for the required attribution. When you use BrowSeg in
research, please cite TotalSegmentator and nnU-Net (below) and the BrowSeg paper.

BrowSeg itself (the C++ / WebAssembly engine in `src/` and `web/`, the JavaScript, the tools and the built bundles in
`web/dist/` and `web/dist-st/`) is released under the Apache License 2.0 (`LICENSE`). `DEVELOPING.md` describes how
to build it.

## Paper

【投稿後に記載: 著者、誌名、DOI、プレプリント】

## Citations

- Wasserthal J, Breit H-C, Meyer MT, et al. TotalSegmentator: Robust segmentation of 104 anatomic structures
  in CT images. Radiol Artif Intell 2023;5(5):e230024. doi:10.1148/ryai.230024
- Isensee F, Jaeger PF, Kohl SAA, Petersen J, Maier-Hein KH. nnU-Net: a self-configuring method for deep
  learning-based biomedical image segmentation. Nat Methods 2021;18:203–211. doi:10.1038/s41592-020-01008-z
- liver_segments model: 【TS README が求める引用（Couinaud 区域の論文 doi:10.1007/978-3-030-32692-0_32）を照合して記載】
- liver_vessels model: 【TS README が求める引用（arXiv:1902.09063, Medical Segmentation Decathlon）を照合して記載】

## Reproducing the paper's numbers

`paper/` holds the benchmark records (timings, environments, hashes of every output) and the scripts that
turn them into the paper's tables. The CT images (3D-IRCADb-01) are not redistributed; obtain them from
IRCAD and place them as described in `paper/README.md`.

### Version measured in the paper vs. this release

The measurements in the paper were made with the build in this repository at commit f94295b (2026-09-29)
(`web/dist/tsc.wasm` SHA-256 `7799e295…`). A code review after the measurements led to two changes in the
inference engine that do **not** change the output on the evaluated data: the native builds before and after the
changes produce identical label maps for all 20 cases x 4 tasks (`paper/data/native/native_before_after_review_fixes.log`,
scripts `paper/scripts/native_verify.sh`, `native_before_after.py`), and the released WebAssembly reproduces the
recorded browser outputs on the cases whose result hinges on an fp16 tie (`tests/test_wasm_node.mjs`):

1. The 6 mm crop model now uses the sliding-window step 0.8 of TotalSegmentator 2.18 (it used 0.5, the 2.13 rule).
   With the 64-voxel patch of that model the tiling is identical up to 96 voxels (patch + one step) per axis at 6 mm,
   i.e. about 580 mm of field of view; the evaluated CTs reach 83 voxels. Longer scans get a different (TS 2.18) tiling.
2. The Gaussian tile weights are rounded to fp16 through float32, as torch does (there was no difference for the
   patch sizes of the bundled models).

Browser-side changes of the same review (CPU fallback after a lost device, weight-file integrity check, query
parameters, benchmark server hardening) do not touch the computation. The WebAssembly in `web/dist/` and `web/dist-st/`
is built from the source in this repository (version string "BrowSeg 0.1"); its SHA-256 hashes are in `EXPORT_INFO.txt`.

GPU safeguards added after the measurements (they do not change the computation): every GPU submission ends with a
small counter update, and a model's result is used only if the counter shows that all submitted work ran; otherwise,
and when the GPU returns an empty label map, the task is retried once on the GPU and then recomputed on the CPU. The
retry submits the network in parts of 4 steps; after an out-of-memory error it instead runs one model at a time on the
GPU (low-memory mode, `?gpulowmem=1` to start in it); a GPU lost by the failure is replaced by a new one first. On
Intel GPUs the network is submitted in parts from the start (`?gpuchunk=0` restores the single submission). Reasons:
on an Intel UHD integrated GPU (Linux) and with Firefox on Windows, a single submission per patch sometimes exceeded
the driver's time limit, the GPU was reset, and on Intel some results were wrong without any error; on a 4 GB GPU the
117-structure task ran out of memory (in low-memory mode it ran on the GPU, about 1.5 GB). The output does not change.

