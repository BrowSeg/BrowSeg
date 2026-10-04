"""Python TotalSegmentator CPU run times and the repeatability of the reference, from the reference dumps.

usage: python python_cpu_timing.py <refs dir> <earlier refs dir> <out dir>
  e.g. python python_cpu_timing.py data/bench_refs/ts218_cpu_rerun data/bench_refs/ts218_cpu paper_jiim/paper_benchmarks/analysis

Writes
  python_cpu_timing.csv  per task: cases, threads, median / min / max of `seconds` (one run per case), note
  python_cpu_repro.csv   per case x task: voxels that differ between <refs dir> and <earlier refs dir> (label maps .npy)
Every number comes from <refs dir>/<case>__<task>_<roi>.json (seconds, threads, ts_version) and the .npy label maps.
"""
import sys, json, csv, statistics
from pathlib import Path
import numpy as np

TASKS = {"total_liver": "total:liver", "liver_segments_all": "liver_segments:-", "liver_vessels_all": "liver_vessels:-",
         "total_all": "total:-"}


def main():
    rdir, edir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    secs, threads, versions = {}, set(), set()
    repro = []
    for jf in sorted(rdir.glob("*__*.json")):
        j = json.load(open(jf, encoding="utf-8"))
        case, key = jf.stem.split("__", 1)
        task = TASKS[key]
        secs.setdefault(task, []).append(j["seconds"])
        threads.add(j.get("threads"))
        versions.add(j.get("ts_version"))
        a, b = np.load(rdir / f"{jf.stem}.npy"), np.load(edir / f"{jf.stem}.npy")
        repro.append((case, task, a.shape == b.shape, int((a != b).sum()) if a.shape == b.shape else -1))
    note = f"TS {'/'.join(sorted(v for v in versions if v))} CPU, i7-13700KF, default PyTorch threads, no other jobs; reference dir {rdir.name}"
    with open(out / "python_cpu_timing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["task", "cases", "threads", "median_s", "min_s", "max_s", "note"])
        for task in ["liver_segments:-", "liver_vessels:-", "total:-", "total:liver"]:
            v = secs[task]
            w.writerow([task, len(v), "/".join(str(t) for t in sorted(threads)), f"{statistics.median(v):.3f}",
                        f"{min(v):.3f}", f"{max(v):.3f}", note])
    with open(out / "python_cpu_repro.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "task", "same_shape", "differing_voxels", "earlier_dir", "rerun_dir"])
        for r in repro:
            w.writerow([*r, edir.name, rdir.name])
    same = sum(1 for r in repro if r[2] and r[3] == 0)
    print(f"timing: {', '.join(f'{t} {statistics.median(v):.1f}' for t, v in secs.items())}; threads {sorted(threads)}")
    print(f"repeatability: {same} of {len(repro)} label maps identical to {edir.name}")


if __name__ == "__main__":
    main()
