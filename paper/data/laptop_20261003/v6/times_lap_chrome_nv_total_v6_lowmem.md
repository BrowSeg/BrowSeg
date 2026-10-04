# lap_chrome_nv_total_v6_lowmem: T1200 (4 GB), Chrome 142, total:- (117 structures), gpulowmem=1, reps=1

seconds; model = modelSeconds; GPU part = sum of "part: tiles" in engineLog; desktop = RTX (desk_chrome_webgpu_total_20, 3 reps) and CPU (desk_chrome_wasm_total_20) for reference.

| case | seconds | model | part tiles (s) | backend | gpuErrors | check | desktop webgpu (s) | desktop wasm (s) |
|---|---|---|---|---|---|---|---|---|
| ircad01 | 48.4 | 0.75 | 45.3 | webgpu | 0 | MATCH (exact) | 9.8 / 8.4 / 8.5 | 147.2 |
| ircad02 | 99.0 | 0.00 | 95.9 | webgpu | 0 | MATCH (exact) | 19.3 / 18.7 / 18.7 | 324.0 |
| ircad03 | 46.8 | 0.00 | 44.8 | webgpu | 0 | MATCH (exact) | 9.0 / 9.0 / 9.0 | 143.3 |
| ircad04 | 52.3 | 0.00 | 50.4 | webgpu | 0 | SAME-AS-DESKTOP-NONEXACT (4 voxels) | 9.8 / 9.8 / 9.8 | 161.2 |
| ircad05 | 100.8 | 0.00 | 98.3 | webgpu | 0 | SAME-AS-DESKTOP-NONEXACT (4 voxels) | 18.1 / 18.1 / 18.2 | 322.6 |
| ircad06 | 98.5 | 0.00 | 96.3 | webgpu | 0 | MATCH (exact) | 18.0 / 18.0 / 18.0 | 322.2 |
| ircad07 | 99.3 | 0.00 | 96.8 | webgpu | 0 | DIFFERENT (copy .u8) | 18.3 / 18.4 / 18.4 | 322.5 |
| ircad08 | 46.3 | 0.00 | 45.0 | webgpu | 0 | MATCH (exact) | 8.3 / 8.3 / 8.2 | 143.5 |
| ircad09 | 99.5 | 0.00 | 96.6 | webgpu | 0 | MATCH (exact) | 18.8 / 18.6 / 18.6 | 327.0 |
| ircad10 | 97.6 | 0.00 | 95.7 | webgpu | 0 | MATCH (exact) | 17.6 / 17.7 / 17.7 | 327.2 |
| ircad11 | 97.8 | 0.00 | 95.8 | webgpu | 0 | MATCH (exact) | 17.7 / 17.7 / 17.8 | 328.2 |
| ircad12 | 98.6 | 0.00 | 96.4 | webgpu | 0 | MATCH (exact) | 17.9 / 17.8 / 17.8 | 324.2 |
| ircad13 | 47.1 | 0.00 | 45.3 | webgpu | 0 | MATCH (exact) | 8.7 / 8.8 / 8.8 | 143.6 |
| ircad14 | 51.9 | 0.00 | 50.0 | webgpu | 0 | MATCH (exact) | 9.8 / 9.8 / 9.8 | 161.2 |
| ircad15 | 100.6 | 0.00 | 98.1 | webgpu | 0 | MATCH (exact) | 17.9 / 18.0 / 17.9 | 322.5 |
| ircad16 | 100.9 | 0.00 | 98.6 | webgpu | 0 | MATCH (exact) | 17.8 / 17.9 / 17.9 | 322.2 |
| ircad17 | 50.9 | 0.00 | 49.0 | webgpu | 0 | MATCH (exact) | 9.9 / 9.9 / 9.9 | 161.2 |
| ircad18 | 50.5 | 0.00 | 48.7 | webgpu | 0 | MATCH (exact) | 9.9 / 9.9 / 9.9 | 161.5 |
| ircad19 | 148.7 | 0.00 | 144.4 | webgpu | 0 | MATCH (exact) | 28.1 / 27.4 / 27.3 | 484.5 |
| ircad20 | 150.3 | 0.00 | 145.3 | webgpu | 0 | MATCH (exact) | 36.6 / 36.3 / 36.2 | 493.2 |

total 28.1 min, mean 84.3 s per case
