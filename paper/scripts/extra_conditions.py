"""Summaries of the conditions measured on 2026-10-03/04 that are reported in the text, not in the tables.

usage: python extra_conditions.py <paper_benchmarks dir> <public repo paper/data dir with the expected hashes>
  e.g. python extra_conditions.py paper_jiim/paper_benchmarks ../BrowSeg_public/paper/data

Writes <paper_benchmarks>/analysis/extra_conditions.csv, one row per condition x task:
  condition, tag, task, cases, runs, run_used (first | all | rest), median_s, min_s, max_s, backends,
  python_exact (output identical to the Python reference), same_as_gpu_record_nonexact, same_as_cpu_record,
  other (identical to none of these), note
Classification of an output hash: python_exact if it equals an exact entry of desktop_hashes.json or
desktop_hashes_wasm20.json; same_as_gpu_record_nonexact if it equals a non-exact entry of desktop_hashes.json;
same_as_cpu_record if it equals a non-exact entry of desktop_hashes_wasm20.json or the desktop Chrome CPU
117-structure output (browser/desk_chrome_wasm_total_20, which desktop_hashes_wasm20.json does not contain).
"""
import sys, json, csv, statistics, glob, os
from pathlib import Path


def runs_of(paths):
    out = {}
    for f in paths:
        d = json.load(open(f, encoding="utf-8"))
        key = os.path.basename(f)[:-5]                      # ircadNN__task_roi
        out[key] = d["runs"]
    return out


def main():
    pb, exp = Path(sys.argv[1]), Path(sys.argv[2])
    gpu = json.load(open(exp / "desktop_hashes.json", encoding="utf-8"))["entries"]
    cpu = json.load(open(exp / "desktop_hashes_wasm20.json", encoding="utf-8"))["entries"]
    cpu117 = {k: [r["hash"] for r in v] for k, v in runs_of(glob.glob(str(pb / "data/browser/desk_chrome_wasm_total_20/ircad*.json"))).items()}

    def classify(key, h):
        for rec in (gpu, cpu):
            e = rec.get(key)
            if e and h in e["hashes"] and e.get("exact"):
                return "python_exact"
        e = gpu.get(key)
        if e and h in e["hashes"]:
            return "same_as_gpu_record_nonexact"
        e = cpu.get(key)
        if (e and h in e["hashes"]) or h in cpu117.get(key, []):
            return "same_as_cpu_record"
        return "other"

    L = pb / "data/laptop_20261003"
    B = pb / "data/browser"
    conds = [  # (condition, tag, files, run_used, note)
        ("laptop Intel UHD WebGPU, gpuchunk=4", "lap20_igpu_chunk4", glob.glob(str(L / "igpu_v3/lap20_igpu_chunk4/**/ircad*.json"), recursive=True), "first", "one run per case"),
        ("laptop CPU (WebAssembly, 16 threads)", "lap20_chrome_wasm", glob.glob(str(B / "lap20_chrome_wasm/ircad*.json")), "first", "one run per case"),
        ("laptop T1200 WebGPU, first run", "lap20_chrome_nv_webgpu", glob.glob(str(B / "lap20_chrome_nv_webgpu/ircad*.json")), "first", "run 1 of 3"),
        ("laptop T1200 WebGPU, 117 structures, low-memory mode", "lap_chrome_nv_total_v6_lowmem", glob.glob(str(L / "v6/runs/lap_chrome_nv_total_v6_lowmem/**/ircad*.json"), recursive=True), "first", "gpulowmem=1, kit v6"),
        ("desktop Firefox 156 CPU (WebAssembly)", "desk_firefox_wasm_20", glob.glob(str(B / "desk_firefox_wasm_20/ircad01__*.json")), "first", "case 1 only"),
        ("desktop Firefox 156 WebGPU, single submission", "desk_firefox_webgpu_tdr_chunk0", glob.glob(str(B / "desk_firefox_webgpu_tdr_chunk0/ircad*.json")), "all", "case 1, 3 runs"),
        ("desktop Firefox 156 WebGPU, gpuchunk=4", "desk_firefox_webgpu_tdr_chunk4", glob.glob(str(B / "desk_firefox_webgpu_tdr_chunk4/ircad*.json")), "all", "case 1, 3 runs"),
        ("desktop Firefox 156 WebGPU, gpuchunk=1", "desk_firefox_webgpu_tdr_chunk1", glob.glob(str(B / "desk_firefox_webgpu_tdr_chunk1/ircad*.json")), "all", "case 1, 3 runs"),
        ("desktop Firefox 156 WebGPU, 20 cases x 3 runs", "desk_firefox_webgpu_final", glob.glob(str(B / "desk_firefox_webgpu_final/ircad*.json")), "all", "after a failure the session continued on the CPU"),
        ("desktop Chrome cold start (weights downloaded)", "desk_chrome_webgpu_cold_final_r2", glob.glob(str(B / "desk_chrome_webgpu_cold_final_r2/ircad*.json")), "first", "case 1"),
    ]
    rows = []
    for cond, tag, files, used, note in conds:
        by_task = {}
        for key, runs in runs_of(files).items():
            task = key.split("__", 1)[1]
            sel = runs[:1] if used == "first" else runs
            for r in sel:
                by_task.setdefault(task, []).append((key, r))
        for task, items in sorted(by_task.items()):
            secs = [r["seconds"] for _, r in items]
            cls = [classify(k, r["hash"]) for k, r in items]
            backends = {}
            for _, r in items:
                b = r["backend"] if not r["backend"].startswith("cpu (") else "cpu (after WebGPU failure)"
                backends[b] = backends.get(b, 0) + 1
            rows.append([cond, tag, task, len({k for k, _ in items}), len(items), used,
                         f"{statistics.median(secs):.1f}", f"{min(secs):.1f}", f"{max(secs):.1f}",
                         "; ".join(f"{b}={n}" for b, n in sorted(backends.items())),
                         cls.count("python_exact"), cls.count("same_as_gpu_record_nonexact"), cls.count("same_as_cpu_record"),
                         cls.count("other"), note])
    out = pb / "analysis/extra_conditions.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["condition", "tag", "task", "cases", "runs", "run_used", "median_s", "min_s", "max_s", "backends",
                    "python_exact", "same_as_gpu_record_nonexact", "same_as_cpu_record", "other", "note"])
        w.writerows(rows)
    for r in rows:
        print(",".join(str(x) for x in r))


if __name__ == "__main__":
    main()
