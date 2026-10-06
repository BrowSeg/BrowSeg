"""Smallest per-structure Dice among the liver-task runs that differ from the reference (main text after the
2026-10-06 refocus). Reads analysis_summary.csv (analyze.py). Output: analysis/min_dice_liver3_20261006.txt"""
import csv
TAGS = {"desk_chrome_webgpu_final", "desk_chrome_wasm_20", "desk_firefox_wasm_20", "desk_edge_webgpu_20",
        "desk_chrome_webgpu_threads1_20", "lap20_chrome_nv_webgpu", "lap20_chrome_nv_st_webgpu_r2", "lap20_chrome_wasm"}
rows = [r for r in csv.DictReader(open("analysis_summary.csv", encoding="utf-8"))
        if r["tag"] in TAGS and r["task"] in ("total", "liver_segments", "liver_vessels") and r["roi"] in ("liver", "-")
        and not (r["task"] == "total" and r["roi"] == "-") and r["diff_voxels"] not in ("", "0") and r["worst_dice"]]
m = min(rows, key=lambda r: float(r["worst_dice"]))
print(f"liver tasks, runs with differences: {len(rows)}; smallest per-structure Dice {float(m['worst_dice']):.7f} "
      f"({m['tag']} {m['case']} {m['task']} {m['roi']}, {m['diff_voxels']} voxels)")
