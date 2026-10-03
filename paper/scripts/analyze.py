"""Tables of the paper from the benchmark records.

usage: python analyze.py <browser records dir> <python refs dir> <python gpu dirs prefix> <out dir>
  e.g. python analyze.py paper_jiim/paper_benchmarks/data/browser data/bench_refs/ts218_cpu data/bench_refs/ts218_gpu_r paper_jiim/paper_benchmarks/analysis

Writes (CSV + Markdown):
  exactness.csv   per tag x task: cases, cases with 0 differing voxels, max differing voxels, repeatability
  timing.csv      per tag x task: median / min / max of the run times (first run and later runs separately), heap
  python_gpu.csv  Python TotalSegmentator on the GPU: run-to-run and GPU-vs-CPU differing voxels per case x task
  tables.md       the same as Markdown tables
Every number here can be traced to a file: browser/<tag>/<case>__<task>.json (+ .u8), refs/<case>__<task>.npy.
"""
import sys, json, csv, statistics, glob, os
from pathlib import Path
from collections import defaultdict
import numpy as np


def main():
    bdir, rdir, gpre, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    refs = {}

    def ref(key):
        if key not in refs:
            p = rdir / f"{key}.npy"
            refs[key] = np.load(p).ravel() if p.exists() else None
        return refs[key]

    # label maps recorded on another machine come back as hashes only (paper/scripts/hashes.py): a hash equal to
    # a desktop map that was exact means 0 differing voxels; equal to a non-exact desktop map means that map's count
    # desktop_hashes.json (WebGPU final) and desktop_hashes_wasm20.json (CPU path): key -> [(hash set, diff), ...]
    dh = defaultdict(list)
    for name in ("desktop_hashes.json", "desktop_hashes_wasm20.json"):
        hl = bdir / name
        if not hl.exists():
            hl = bdir.parent / name
        if hl.exists():
            for k, e in json.load(open(hl))["entries"].items():
                dh[k].append((set(e["hashes"]), e["diff_voxels_vs_python"]))

    ex, tm = defaultdict(list), defaultdict(list)
    for tagdir in sorted(p for p in bdir.iterdir() if p.is_dir() and (p.name.startswith("desk_") or p.name.startswith("lap_") or p.name.startswith("lap20_"))):
        env = json.load(open(tagdir / "environment.json")) if (tagdir / "environment.json").exists() else {}
        for jf in sorted(tagdir.glob("*__*.json")):
            d = json.load(open(jf))
            key = jf.stem
            r = ref(key)
            u8 = tagdir / f"{key}.u8"
            runs = d["runs"]
            if r is not None and u8.exists():
                diff = int((r != np.fromfile(u8, np.uint8)).sum())
            elif any({x["hash"] for x in runs} <= hs for hs, _ in dh.get(key, [])):
                diff = next(d for hs, d in dh[key] if {x["hash"] for x in runs} <= hs)  # identical map to a desktop map (verified by hash)
            else:
                diff = None
            k = (tagdir.name, f"{d['task']}:{d['roi']}")
            ex[k].append({"case": d["case"], "diff": diff, "runs": runs, "repeatable": (len({x["hash"] for x in runs}) == 1) if len(runs) >= 2 else None,  # None = single run (not assessable)
                          "fallback": any(x.get("fallback") for x in runs), "backend": runs[0]["backend"]})
            tm[k].append({"case": d["case"], "first": runs[0]["seconds"], "rest": [x["seconds"] for x in runs[1:]],
                          "heap": max(x["heap"] for x in runs) >> 20, "load": d["load"]["loadS"], "shape": d["shape"]})

    rows_e, rows_t = [], []
    for k in sorted(ex):
        v = ex[k]
        diffs = [x["diff"] for x in v if x["diff"] is not None]
        rows_e.append({"tag": k[0], "task": k[1], "backend": v[0]["backend"], "cases": len(v), "compared": len(diffs),
                       "exact_cases": sum(1 for x in diffs if x == 0), "max_diff_voxels": max(diffs) if diffs else "",
                       "cases_with_diff": ",".join(f"{x['case']}:{x['diff']}" for x in v if x["diff"]),
                       "all_repeatable": ("single_run" if any(x["repeatable"] is None for x in v) else all(x["repeatable"] for x in v)),
                       "runs_min": min(len(x["runs"]) for x in v), "cpu_fallbacks": sum(1 for x in v if x["fallback"])})
        t = tm[k]
        # per case: median of runs 2..n; the table shows the median and range of these per-case values over the cases
        rest = [statistics.median(x["rest"]) for x in t if x["rest"]]
        rows_t.append({"tag": k[0], "task": k[1], "cases": len(t), "first_median_s": round(statistics.median([x["first"] for x in t]), 2),
                       "first_min_s": round(min(x["first"] for x in t), 2), "first_max_s": round(max(x["first"] for x in t), 2),
                       "rest_median_s": round(statistics.median(rest), 2) if rest else "", "rest_min_s": round(min(rest), 2) if rest else "",
                       "rest_max_s": round(max(rest), 2) if rest else "", "n_rest_runs": sum(len(x["rest"]) for x in t),
                       "heap_max_mib": max(x["heap"] for x in t), "load_median_s": round(statistics.median([x["load"] for x in t]), 2)})

    # Python TotalSegmentator on the GPU: run-to-run and vs CPU
    rows_g = []
    gdirs = sorted(d for d in glob.glob(gpre + "*") if Path(d).is_dir())
    if gdirs:
        for f in sorted(Path(gdirs[0]).glob("*.npy")):
            key = f.stem
            runs = [np.load(Path(g) / f.name).ravel() for g in gdirs if (Path(g) / f.name).exists()]
            secs = [json.load(open(Path(g) / f"{key}.json"))["seconds"] for g in gdirs if (Path(g) / f"{key}.json").exists()]
            r = ref(key)
            pair = [int((runs[i] != runs[j]).sum()) for i in range(len(runs)) for j in range(i + 1, len(runs))]
            rows_g.append({"key": key, "gpu_runs": len(runs), "run_to_run_min": min(pair) if pair else "", "run_to_run_max": max(pair) if pair else "",
                           "vs_cpu_min": min(int((x != r).sum()) for x in runs) if r is not None else "",
                           "vs_cpu_max": max(int((x != r).sum()) for x in runs) if r is not None else "",
                           "gpu_seconds_median": round(statistics.median(secs), 1) if secs else "", "voxels": int(runs[0].size)})

    def write(name, rows):
        if not rows:
            return
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    write("exactness.csv", rows_e); write("timing.csv", rows_t); write("python_gpu.csv", rows_g)
    md = ["# Benchmark tables (generated by analyze.py)", ""]
    for title, rows in [("Exactness vs Python TotalSegmentator 2.18 (CPU)", rows_e), ("Run time (s)", rows_t), ("Python TotalSegmentator on the GPU", rows_g)]:
        if not rows:
            continue
        md += [f"## {title}", "", "| " + " | ".join(rows[0].keys()) + " |", "|" + "---|" * len(rows[0])]
        md += ["| " + " | ".join(str(v) for v in r.values()) + " |" for r in rows]
        md.append("")
    (out / "tables.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
