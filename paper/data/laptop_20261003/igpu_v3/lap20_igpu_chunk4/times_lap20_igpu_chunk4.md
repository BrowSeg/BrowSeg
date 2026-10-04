# BrowSeg v3: Intel UHD (TGL GT1) WebGPU with split submission (gpuchunk) - times

seconds per run (reps separated by /); model = modelSeconds; check = hashes.py check vs desktop_hashes.json;
kernel = i915/rcs0/GPU HANG lines in journalctl -k for the run window.

| tag | case | task | seconds | model | backend | fallback | gpuErrors | check | kernel | lap20 wasm (CPU) | lap20 nv webgpu (T1200) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lap20_igpu_chunk4 | ircad01 | total_liver | 40.9 | 0.68 | webgpu | None | 0 | MATCH (exact) | 0 | 54.8 | 5.7 / 4.3 / 4.3 |
| lap20_igpu_chunk4 | ircad01 | liver_segments_all | 121.4 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.2 / 12.9 / 12.6 |
| lap20_igpu_chunk4 | ircad01 | liver_vessels_all | 115.4 | 0.40 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.7 / 12.9 / 12.9 |
| lap20_igpu_chunk4 | ircad02 | total_liver | 64.5 | 0.32 | webgpu | None | 0 | MATCH (exact) | 0 | 110.7 | 9.0 / 8.2 / 8.2 |
| lap20_igpu_chunk4 | ircad02 | liver_segments_all | 137.2 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 238.7 | 17.5 / 17.1 / 17.0 |
| lap20_igpu_chunk4 | ircad02 | liver_vessels_all | 135.7 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 238.3 | 17.4 / 17.0 / 17.1 |
| lap20_igpu_chunk4 | ircad03 | total_liver | 32.7 | 0.32 | webgpu | None | 0 | MATCH (exact) | 0 | 58.7 | 4.7 / 4.3 / 4.3 |
| lap20_igpu_chunk4 | ircad03 | liver_segments_all | 111.3 | 0.38 | webgpu | None | 0 | MATCH (exact) | 0 | 196.6 | 13.0 / 12.6 / 12.6 |
| lap20_igpu_chunk4 | ircad03 | liver_vessels_all | 132.2 | 0.50 | webgpu | None | 0 | MATCH (exact) | 0 | 181.4 | 13.4 / 12.9 / 13.0 |
| lap20_igpu_chunk4 | ircad04 | total_liver | 38.0 | 0.47 | webgpu | None | 0 | MATCH (exact) | 0 | 56.4 | 4.6 / 4.3 / 4.2 |
| lap20_igpu_chunk4 | ircad04 | liver_segments_all | 122.6 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 194.2 | 13.0 / 12.6 / 12.6 |
| lap20_igpu_chunk4 | ircad04 | liver_vessels_all | 102.1 | 0.52 | webgpu | None | 0 | MATCH (exact) | 0 | 190.5 | 13.0 / 12.6 / 12.6 |
| lap20_igpu_chunk4 | ircad05 | total_liver | 64.6 | 0.39 | webgpu | None | 0 | MATCH (exact) | 0 | 119.1 | 8.6 / 8.2 / 8.2 |
| lap20_igpu_chunk4 | ircad05 | liver_segments_all | 320.8 | 0.48 | webgpu | None | 0 | DIFFERENT (copy .u8) | 0 | 567.1 | 37.2 / 36.9 / 36.8 |
| lap20_igpu_chunk4 | ircad05 | liver_vessels_all | 348.2 | 0.51 | webgpu | None | 0 | MATCH (exact) | 0 | 580.3 | 37.3 / 36.9 / 36.8 |
| lap20_igpu_chunk4 | ircad06 | total_liver | 34.8 | 0.33 | webgpu | None | 0 | MATCH (exact) | 0 | 64.0 | 5.0 / 4.7 / 4.8 |
| lap20_igpu_chunk4 | ircad06 | liver_segments_all | 227.3 | 0.48 | webgpu | None | 0 | MATCH (exact) | 0 | 422.2 | 28.4 / 27.9 / 27.9 |
| lap20_igpu_chunk4 | ircad06 | liver_vessels_all | 246.4 | 0.48 | webgpu | None | 0 | MATCH (exact) | 0 | 397.4 | 28.4 / 28.0 / 28.0 |
| lap20_igpu_chunk4 | ircad07 | total_liver | 64.8 | 0.38 | webgpu | None | 0 | MATCH (exact) | 0 | 110.9 | 8.7 / 8.3 / 8.3 |
| lap20_igpu_chunk4 | ircad07 | liver_segments_all | 234.4 | 0.54 | webgpu | None | 0 | MATCH (exact) | 0 | 354.2 | 25.5 / 25.0 / 25.1 |
| lap20_igpu_chunk4 | ircad07 | liver_vessels_all | 204.4 | 0.47 | webgpu | None | 0 | MATCH (exact) | 0 | 357.4 | 25.7 / 25.2 / 25.2 |
| lap20_igpu_chunk4 | ircad08 | total_liver | 32.9 | 0.46 | webgpu | None | 0 | MATCH (exact) | 0 | 54.0 | 4.8 / 4.4 / 4.4 |
| lap20_igpu_chunk4 | ircad08 | liver_segments_all | 204.8 | 0.39 | webgpu | None | 0 | MATCH (exact) | 0 | 349.4 | 25.0 / 24.6 / 24.6 |
| lap20_igpu_chunk4 | ircad08 | liver_vessels_all | 210.4 | 0.50 | webgpu | None | 0 | MATCH (exact) | 0 | 348.1 | 25.3 / 24.9 / 24.9 |
| lap20_igpu_chunk4 | ircad09 | total_liver | 65.5 | 0.42 | webgpu | None | 0 | MATCH (exact) | 0 | 111.0 | 8.8 / 8.3 / 8.3 |
| lap20_igpu_chunk4 | ircad09 | liver_segments_all | 362.4 | 0.52 | webgpu | None | 0 | MATCH (exact) | 0 | 528.0 | 37.4 / 36.9 / 36.8 |
| lap20_igpu_chunk4 | ircad09 | liver_vessels_all | 316.3 | 0.57 | webgpu | None | 0 | MATCH (exact) | 0 | 527.0 | 37.3 / 36.8 / 36.9 |
| lap20_igpu_chunk4 | ircad10 | total_liver | 32.4 | 0.38 | webgpu | None | 0 | MATCH (exact) | 0 | 53.6 | 4.8 / 4.5 / 4.3 |
| lap20_igpu_chunk4 | ircad10 | liver_segments_all | 101.3 | 0.46 | webgpu | None | 0 | MATCH (exact) | 0 | 176.1 | 13.1 / 12.6 / 12.7 |
| lap20_igpu_chunk4 | ircad10 | liver_vessels_all | 101.2 | 0.46 | webgpu | None | 0 | MATCH (exact) | 0 | 175.2 | 13.1 / 12.7 / 12.8 |
| lap20_igpu_chunk4 | ircad11 | total_liver | 32.5 | 0.37 | webgpu | None | 0 | MATCH (exact) | 0 | 53.5 | 4.6 / 4.3 / 4.4 |
| lap20_igpu_chunk4 | ircad11 | liver_segments_all | 103.4 | 0.48 | webgpu | None | 0 | MATCH (exact) | 0 | 175.5 | 13.1 / 12.7 / 12.6 |
| lap20_igpu_chunk4 | ircad11 | liver_vessels_all | 120.6 | 0.54 | webgpu | None | 0 | MATCH (exact) | 0 | 175.9 | 13.1 / 12.8 / 12.8 |
| lap20_igpu_chunk4 | ircad12 | total_liver | 38.6 | 0.49 | webgpu | None | 0 | MATCH (exact) | 0 | 53.6 | 5.0 / 4.4 / 4.4 |
| lap20_igpu_chunk4 | ircad12 | liver_segments_all | 277.5 | 0.50 | webgpu | None | 0 | MATCH (exact) | 0 | 436.4 | 30.8 / 30.5 / 30.6 |
| lap20_igpu_chunk4 | ircad12 | liver_vessels_all | 262.0 | 0.54 | webgpu | None | 0 | MATCH (exact) | 0 | 435.6 | 31.6 / 31.0 / 30.9 |
| lap20_igpu_chunk4 | ircad13 | total_liver | 32.9 | 0.43 | webgpu | None | 0 | MATCH (exact) | 0 | 53.9 | 4.8 / 4.4 / 4.4 |
| lap20_igpu_chunk4 | ircad13 | liver_segments_all | 150.8 | 0.52 | webgpu | None | 0 | MATCH (exact) | 0 | 262.7 | 19.1 / 18.7 / 20.4 |
| lap20_igpu_chunk4 | ircad13 | liver_vessels_all | 152.3 | 0.48 | webgpu | None | 0 | MATCH (exact) | 0 | 261.9 | 18.8 / 18.4 / 18.5 |
| lap20_igpu_chunk4 | ircad14 | total_liver | 17.1 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 27.8 | 2.8 / 2.5 / 2.5 |
| lap20_igpu_chunk4 | ircad14 | liver_segments_all | 151.4 | 0.48 | webgpu | None | 0 | SAME-AS-DESKTOP-NONEXACT (1 voxels) | 0 | 262.4 | 18.7 / 18.4 / 18.4 |
| lap20_igpu_chunk4 | ircad14 | liver_vessels_all | 150.6 | 0.47 | webgpu | None | 0 | MATCH (exact) | 0 | 263.9 | 18.9 / 18.6 / 18.6 |
| lap20_igpu_chunk4 | ircad15 | total_liver | 35.1 | 0.39 | webgpu | None | 0 | MATCH (exact) | 0 | 58.8 | 5.0 / 4.6 / 4.6 |
| lap20_igpu_chunk4 | ircad15 | liver_segments_all | 210.8 | 0.47 | webgpu | None | 0 | MATCH (exact) | 0 | 354.0 | 25.2 / 24.8 / 24.8 |
| lap20_igpu_chunk4 | ircad15 | liver_vessels_all | 227.5 | 0.41 | webgpu | None | 0 | MATCH (exact) | 0 | 354.1 | 25.3 / 24.9 / 25.0 |
| lap20_igpu_chunk4 | ircad16 | total_liver | 62.0 | 0.44 | webgpu | None | 0 | MATCH (exact) | 0 | 105.4 | 8.3 / 8.0 / 7.9 |
| lap20_igpu_chunk4 | ircad16 | liver_segments_all | 317.7 | 0.57 | webgpu | None | 0 | SAME-AS-DESKTOP-NONEXACT (1 voxels) | 0 | 521.8 | 37.1 / 36.9 / 37.0 |
| lap20_igpu_chunk4 | ircad16 | liver_vessels_all | 309.1 | 0.60 | webgpu | None | 0 | MATCH (exact) | 0 | 522.7 | 37.8 / 37.4 / 37.3 |
| lap20_igpu_chunk4 | ircad17 | total_liver | 32.5 | 0.36 | webgpu | None | 0 | MATCH (exact) | 0 | 53.5 | 4.8 / 4.4 / 4.4 |
| lap20_igpu_chunk4 | ircad17 | liver_segments_all | 227.2 | 0.49 | webgpu | None | 0 | MATCH (exact) | 0 | 392.0 | 28.4 / 28.0 / 28.1 |
| lap20_igpu_chunk4 | ircad17 | liver_vessels_all | 224.4 | 0.51 | webgpu | None | 0 | MATCH (exact) | 0 | 392.7 | 28.6 / 28.2 / 28.3 |
| lap20_igpu_chunk4 | ircad18 | total_liver | 32.8 | 0.44 | webgpu | None | 0 | MATCH (exact) | 0 | 53.7 | 4.9 / 4.4 / 4.4 |
| lap20_igpu_chunk4 | ircad18 | liver_segments_all | 150.4 | 0.46 | webgpu | None | 0 | SAME-AS-DESKTOP-NONEXACT (1 voxels) | 0 | 261.8 | 19.4 / 19.0 / 19.1 |
| lap20_igpu_chunk4 | ircad18 | liver_vessels_all | 149.8 | 0.49 | webgpu | None | 0 | MATCH (exact) | 0 | 262.3 | 19.5 / 19.1 / 18.9 |
| lap20_igpu_chunk4 | ircad19 | total_liver | 33.8 | 0.38 | webgpu | None | 0 | MATCH (exact) | 0 | 55.4 | 4.8 / 4.5 / 4.4 |
| lap20_igpu_chunk4 | ircad19 | liver_segments_all | 135.0 | 0.47 | webgpu | None | 0 | MATCH (exact) | 0 | 235.5 | 17.4 / 17.0 / 16.9 |
| lap20_igpu_chunk4 | ircad19 | liver_vessels_all | 135.1 | 0.44 | webgpu | None | 0 | MATCH (exact) | 0 | 234.4 | 17.3 / 16.8 / 16.8 |
| lap20_igpu_chunk4 | ircad20 | total_liver | 68.8 | 0.49 | webgpu | None | 0 | DIFFERENT (copy .u8) | 0 | 117.5 | 9.5 / 8.9 / 8.8 |
| lap20_igpu_chunk4 | ircad20 | liver_segments_all | 306.0 | 0.51 | webgpu | None | 0 | MATCH (exact) | 0 | 546.2 | 38.1 / 37.6 / 37.6 |
| lap20_igpu_chunk4 | ircad20 | liver_vessels_all | 304.8 | 0.38 | webgpu | None | 0 | MATCH (exact) | 0 | 533.8 | 38.1 / 37.6 / 37.7 |
