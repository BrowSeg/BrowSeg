# LiTS logit tracing, both sides (2026-10-08, desktop)

Pairs: the 10 case-task pairs where BrowSeg WebGPU (public build 7ee2d83, Chrome, RTX 4070) differs from the reference
(TotalSegmentator 2.18.0, CPU, desktop). Same tools as the 3D-IRCADb-01 tracing of 10-06 (M4_SUMMARY_20261006.md).

| side | how | unchanged output |
|---|---|---|
| reference | tools/make_reference.py (dump) + tie_check_pair.py / tie_check_resampled.py (grid points, PROBE_OUT -> web/probe_specs/<key>.txt) + tools/probe_python.py | final_can.npy = ts218_cpu_lits/<key>.npy, 10/10 (0 voxels) |
| BrowSeg | web/dist-probe rebuilt 10-08 (same engine + raw NIfTI loading), bench.html?probe=, Chrome WebGPU (data/browser_m4probe_lits) | label hash = lits_pub_chrome_webgpu record, 10/10 |

Comparison: scripts/compare_probes.py -> compare/compare_webgpu_<key>.txt.

| pair | decisive grid point (z,y,x) | first tile where the fp16 accumulator differs | final (BrowSeg / reference) | label BrowSeg / reference |
|---|---|---|---|---|
| lits_015 segments (1) | (89,155,61) | 8 | class 1: 9.3594 / 9.3516 (+1 ulp) | 1 / 2 |
| lits_015 segments (2) | (89,197,215) | 15 | class 4: 7.1250 / 7.1289 (-1 ulp) | 8 / 4 |
| lits_022 segments | (81,187,184) | 11 | class 8: 8.3906 / 8.3984 (-1 ulp) | 4 / 8 |
| lits_092 segments | (103,183,120) | 16 | class 2: 10.4922 / 10.5000 (-1 ulp) | 0 / 2 |
| lits_092 liver (total) | (76,80,81) | 0 | class 0: 10.5625 / 10.5547 (+1 ulp) | 0 / 5 |
| lits_107 segments | (111,180,51) | 21 | class 0: 9.0625 / 9.0703 (-1 ulp) | 2 / 0 |
| lits_120 segments | (132,56,183) | 26 | class 0: 6.8711 / 6.8672 (+1 ulp) | 0 / 7 |
| lits_129 segments | (78,217,231) | 22 | class 8: 6.0234 / 6.0273 (-1 ulp) | 4 / 8 |
| lits_129 vessels | net (51,231,101) | 8 | class 0: 1.08984 / 1.09082 (-1 ulp); back-resampled crop voxel (111,261,115): background 2.908203 / 2.910156, vessel 2.910156 / 2.910156 (tie in the reference) | 2 / 0 |
| lits_163 segments | (74,130,156) | 22 | class 0: 7.5000 / 7.5039 (-1 ulp) | 1 / 0 |
| lits_185 segments | (73,28,286) | 11 | class 0: 7.8203 / 7.8164 (+1 ulp) | 0 / 7 |

All 10 pairs (11 decisive points): network outputs differ by a few fp32 ulps (convolution summation order), one tile's
fp16 accumulation of one class rounds 1 fp16-ulp apart, the difference survives to the final logits (1 ulp), and two
classes that were tied or 1 ulp apart change order. Same mechanism as the 3D-IRCADb-01 tracing.
