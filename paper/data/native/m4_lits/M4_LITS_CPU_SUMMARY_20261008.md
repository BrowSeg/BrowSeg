# LiTS logit tracing of the 9 CPU (WebAssembly) mismatches (2026-10-08, desktop)

BrowSeg side: web/dist-probe on the CPU under Node (tests/probe_wasm_node.mjs, NIfTI via Nifti.readRaw + tsc_set_volume_raw),
label map identical to the measured v1.1 CPU output for 9/9 pairs (cpu_run.log, "differing voxels 0"). Reference side:
tools/probe_python.py on the grid points around the CPU-differing voxels (cpu/<key>/spec.txt). Comparison: cpu/<key>/compare_cpu.txt.

| pair | decisive grid point (z,y,x) | first tile with a differing fp16 accumulator | final (BrowSeg / reference) | label BrowSeg / reference |
|---|---|---|---|---|
| lits_015 segments | (89,155,61) | 8 | class 1: 9.3594 / 9.3516 (+1 ulp) | 1 / 2 |
| lits_092 liver | (76,80,81) | 3 | class 0: 10.5625 / 10.5547 (+1 ulp) | 0 / 5 |
| lits_107 segments | (111,180,51) | 21 | class 0: 9.0625 / 9.0703 (-1 ulp) | 2 / 0 |
| lits_120 segments | (132,56,183) | 26 | class 0: 6.8711 / 6.8672 (+1 ulp) | 0 / 7 |
| lits_129 segments (1) | (78,217,231) | 22 | class 8: 6.0234 / 6.0273 (-1 ulp) | 4 / 8 |
| lits_129 segments (2) | (132,135,333) | 43 | class 0: 6.6055 / 6.5977 (+2 ulp) | 0 / 8 |
| lits_129 vessels | net (51,231,101) | 8 | class 0: 1.08984 / 1.09082 (-1 ulp); crop voxel decides | 2 / 0 |
| lits_163 segments | (74,130,156) | 22 | class 0: 7.5000 / 7.5039 (-1 ulp) | 1 / 0 |
| lits_185 segments | (73,28,286) | 11 | class 0: 7.8203 / 7.8164 (+1 ulp) | 0 / 7 |
| lits_054 vessels | none of the 48 recorded grid points differs | — | back-resampled crop voxel (21,183,99): background 3.125 / 3.126953, vessel 3.126953 / 3.126953 (tie in the reference) | 1 / 0 |

8 of 9 pairs: the same mechanism as the WebGPU pairs (one tile's fp16 accumulation 1 ulp apart; 2 ulp at one point of
lits_129 segments). lits_054 vessels (5 mm slices, nnU-Net's internal resampling with separate z): the 48 recorded
network-grid points are identical on both sides, and the 1-ulp difference appears only after the back-resampling to the
original grid; whether a grid point outside the recorded stencil or the interpolation itself causes it is not established.
