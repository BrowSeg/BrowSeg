# BrowSeg v3: Intel UHD (TGL GT1) WebGPU with split submission (gpuchunk) - times

seconds per run (reps separated by /); model = modelSeconds; check = hashes.py check vs desktop_hashes.json;
kernel = i915/rcs0/GPU HANG lines in journalctl -k for the run window.

| tag | case | task | seconds | model | backend | fallback | gpuErrors | check | kernel | lap20 wasm (CPU) | lap20 nv webgpu (T1200) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lap_igpu_chunk1 | ircad01 | total_liver | 45.9 | 0.71 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk1 | ircad01 | liver_segments_all | 143.5 | 0.98 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk1 | ircad01 | liver_vessels_all | 140.2 | 0.95 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk1_nowait | ircad01 | total_liver | 43.8 | 0.67 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk1_nowait | ircad01 | liver_segments_all | 124.4 | 0.49 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk1_nowait | ircad01 | liver_vessels_all | 133.4 | 0.46 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk4 | ircad01 | total_liver | 33.8 | 0.59 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk4 | ircad01 | liver_segments_all | 101.9 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk4 | ircad01 | liver_vessels_all | 103.3 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk8 | ircad01 | total_liver | 42.4 | 0.65 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk8 | ircad01 | liver_segments_all | 125.2 | 0.51 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk8 | ircad01 | liver_vessels_all | 107.6 | 0.46 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk0_control | ircad01 | total_liver | 37.9 | 0.62 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk4_5cases | ircad01 | total_liver | 41.0 | 0.63 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk4_5cases | ircad01 | liver_segments_all | 112.1 | 0.45 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk4_5cases | ircad01 | liver_vessels_all | 101.1 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk4_5cases | ircad02 | total_liver | 64.0 | 0.39 | webgpu | None | 0 | MATCH (exact) | 0 | 110.7 | 9.0 / 8.2 / 8.2 |
| lap_igpu_chunk4_5cases | ircad02 | liver_segments_all | 137.4 | 0.55 | webgpu | None | 0 | MATCH (exact) | 0 | 238.7 | 17.5 / 17.1 / 17.0 |
| lap_igpu_chunk4_5cases | ircad02 | liver_vessels_all | 136.9 | 0.52 | webgpu | None | 0 | MATCH (exact) | 0 | 238.3 | 17.4 / 17.0 / 17.1 |
| lap_igpu_chunk4_5cases | ircad05 | total_liver | 64.2 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 119.1 | 8.6 / 8.2 / 8.2 |
| lap_igpu_chunk4_5cases | ircad05 | liver_segments_all | 311.3 | 0.46 | webgpu | None | 0 | DIFFERENT (copy .u8) | 0 | 567.1 | 37.2 / 36.9 / 36.8 |
| lap_igpu_chunk4_5cases | ircad05 | liver_vessels_all | 319.0 | 0.50 | webgpu | None | 0 | MATCH (exact) | 0 | 580.3 | 37.3 / 36.9 / 36.8 |
| lap_igpu_chunk4_5cases | ircad10 | total_liver | 32.1 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 53.6 | 4.8 / 4.5 / 4.3 |
| lap_igpu_chunk4_5cases | ircad10 | liver_segments_all | 106.0 | 0.53 | webgpu | None | 0 | MATCH (exact) | 0 | 176.1 | 13.1 / 12.6 / 12.7 |
| lap_igpu_chunk4_5cases | ircad10 | liver_vessels_all | 106.8 | 0.45 | webgpu | None | 0 | MATCH (exact) | 0 | 175.2 | 13.1 / 12.7 / 12.8 |
| lap_igpu_chunk4_5cases | ircad18 | total_liver | 33.5 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 53.7 | 4.9 / 4.4 / 4.4 |
| lap_igpu_chunk4_5cases | ircad18 | liver_segments_all | 155.2 | 0.38 | webgpu | None | 0 | SAME-AS-DESKTOP-NONEXACT (1 voxels) | 0 | 261.8 | 19.4 / 19.0 / 19.1 |
| lap_igpu_chunk4_5cases | ircad18 | liver_vessels_all | 160.6 | 0.50 | webgpu | None | 0 | MATCH (exact) | 0 | 262.3 | 19.5 / 19.1 / 18.9 |
| lap_igpu_chunk4_r2 | ircad01 | total_liver | 41.8 | 0.68 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk4_r2 | ircad01 | liver_segments_all | 102.9 | 0.42 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk4_r2 | ircad01 | liver_vessels_all | 105.0 | 0.44 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk8_r2 | ircad01 | total_liver | 37.5 | 0.68 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap_igpu_chunk8_r2 | ircad01 | liver_segments_all | 120.5 | 0.46 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap_igpu_chunk8_r2 | ircad01 | liver_vessels_all | 120.4 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap_igpu_chunk0_3tasks | ircad01 | total_liver | 33.0 / 1.2 / 56.0 | 0.65 / 0.00 / 0.00 | cpu (after WebGPU failure),webgpu | None,model 298 returned an all-zero result | 0 | DIFFERENT (copy .u8)  CPU-FALLBACK x1  runs differ among themselves | 4 | 54.8 | 5.7 / 4.3 / 4.3 |
