# LiTS re-measurement with the public build 7ee2d83 (2026-10-08, desktop Chrome)

- WebGPU (lits_pub_chrome_webgpu, 07:59-08:19 JST): 90 case-task pairs x 3 runs, all identical to the 10-06 records (lits_pub_gpu_20261008.txt).
- CPU page p1 (lits_129, 002, 015, 185, 102, 084, 107, 092, 087, 072; 08:19-08:36 JST) stopped with
  "[CT_LOST] std::bad_alloc" while loading the 5th case (lits_102), after 4 cases (12 results) were saved:
  the WebAssembly heap is not released within one page (limitation stated in the Discussion).
  The 6 remaining cases are re-run on new pages, 3 cases per page (plan_lits_pub_cpu_p1rest.json: p1b, p1c).
- Pages p2, p3 (10 + 9 cases) and lits_167 alone (plan_lits_pub_cpu.json).
- 2026-10-08 ~09:20 JST: the CPU re-measurement (p2 in progress) was stopped on purpose: the NIfTI/DICOM loading is being
  changed to lower the peak memory (lits_167 could not be loaded on the laptop), so the paper's version changes and the
  CPU and WebGPU timings are re-measured with the new build. The WebGPU run above stays as evidence that 7ee2d83 gives
  the same outputs as the 10-06 build.
