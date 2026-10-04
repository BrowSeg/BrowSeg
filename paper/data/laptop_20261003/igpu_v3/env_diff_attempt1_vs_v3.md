# Environment: attempt1 (2026-09-29, i915 reset) vs v3 (2026-10-03, chunk0 control without reset)

| Item | attempt1 (lap_chrome_webgpu_attempt1_i915hang) | v3 (lap_igpu_*) |
|---|---|---|
| Chrome | 142.0.7444.175 (laptop_environment.json) | 142.0.7444.175 |
| Mesa (mesa-vulkan-drivers) | 23.2.1-1ubuntu3.1~22.04.4 | 23.2.1-1ubuntu3.1~22.04.4 |
| Kernel | 6.8.0-138-generic | 6.8.0-138-generic (no apt installs/upgrades since 2026-09-28) |
| Boot | up 31 days (booted 2026-08-30) | rebooted 2026-09-30 13:05 (up 3 days) |
| i915 rcs0 preempt_timeout_ms | 7500 (driver default; not changed, per the session notes) | 7500 |
| i915 rcs0 heartbeat_interval_ms | 2500 (default, not changed) | 2500 |
| Kernel cmdline / i915 modprobe options | default, none | default, none (quiet splash only) |
| WebGPU adapter | intel gen-12lp, ANGLE "Mesa Intel(R) UHD Graphics (TGL GT1)" | same |
| GPU limits (maxBufferSize / maxStorageBufferBindingSize) | 4294967296 / 4294967292 | same; adapter feature list identical |
| Build | BrowSeg f94295b, web/dist from TSC++Project 5e3a982; version string "BrowSeg 0.1 (TotalSegmentator 2.13/2.18 tasks, C++/WASM)" | BrowSeg_v3 c21be14, web/dist from TSC++Project f85acc7 (EXPORT_INFO hashes match); version string "tsc 0.4 (TotalSegmentator 2.13/2.18 tasks + portal/hepatic split + custom models, C++/WASM)" |
| Query | 5 cases x 3 tasks x reps=3, no gpuchunk | control: ircad01 total:liver x reps=1, no gpuchunk |
| Run context | first Intel WebGPU run of the session; kernel had "Fence expiration time out" lines for chrome from 22:32 JST, then "Resetting rcs0 for preemption time out" at 22:37 | earlier runs that day (chunk1..chunk8) passed; no i915 lines |
| Result | total_liver all 3 reps: all-zero output from model 291/298, CPU fallback; then "map::at: key not found" | webgpu, no fallback, 37.9 s, MATCH |

Note: the version string compiled into v3's tsc.wasm ("tsc 0.4 ...") does not match BrowSeg_v3/web/wasm_api.cpp line 85 ("BrowSeg 0.1 ..."), so the shipped web/dist was not built from the exported wasm_api.cpp as it stands.

Update 15:32: in v3, with the same environment and no gpuchunk, lap_igpu_chunk0_3tasks (ircad01, reps=3) reproduced the reset ("Resetting rcs0 for preemption time out", GPU HANG ecode 12:1:8ed9fff2, the same ecode as attempt1). So the reset is not tied to the old build or the 31-day uptime: the unsplit submission passes sometimes (control, reps=1) and fails at other times.
