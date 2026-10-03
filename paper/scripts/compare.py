"""Compare browser label maps with the Python TotalSegmentator references and summarise timings.

usage: python compare.py <browser_out_dir> <refs_dir> <summary.csv>
  browser_out_dir/<tag>/<case>__<task>_<roi>.u8 + .json   (web/bench.html)
  refs_dir/<case>__<task>_<roi>.npy                       (make_refs.py)
One row per (tag, case, task): differing voxels, labels with differences, worst Dice over labels present,
repeatability (same fingerprint in every run), run times (first, median of the rest), heap.
"""
import sys, json, csv, statistics
from pathlib import Path
import numpy as np

bdir, rdir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rows = []
for tagdir in sorted(p for p in bdir.iterdir() if p.is_dir()):
    env = json.load(open(tagdir / "environment.json")) if (tagdir / "environment.json").exists() else {}
    for jf in sorted(tagdir.glob("*__*.json")):
        d = json.load(open(jf))
        key = jf.stem
        runs = d["runs"]
        secs = [r["seconds"] for r in runs]
        row = {"tag": tagdir.name, "case": d["case"], "task": d["task"], "roi": d["roi"], "backend": runs[0]["backend"],
               "browser": env.get("userAgent", "")[-30:], "gpu": env.get("webglRenderer", ""),
               "shape": "x".join(map(str, d["shape"])), "runs": len(runs),
               "repeatable": (len({r["hash"] for r in runs}) == 1) if len(runs) >= 2 else "",  # not assessable from one run
               "t_first": round(secs[0], 2), "t_median_rest": round(statistics.median(secs[1:]), 2) if len(secs) > 1 else "",
               "heap_mib": max(r["heap"] for r in runs) >> 20, "load_s": round(d["load"]["loadS"], 2)}
        ref = rdir / f"{key}.npy"
        if ref.exists() and (tagdir / f"{key}.u8").exists():  # label maps from another machine come back as hashes only
            a = np.load(ref).ravel()
            b = np.fromfile(tagdir / f"{key}.u8", np.uint8)
            assert a.size == b.size, key
            diff = a != b
            row["diff_voxels"] = int(diff.sum())
            row["labels_diff"] = len((set(np.unique(a[diff])) | set(np.unique(b[diff]))) - {0}) if row["diff_voxels"] else 0  # labels (other than background) involved
            worst = 1.0
            for l in set(np.unique(a)) | set(np.unique(b)):
                if l == 0: continue
                x, y = a == l, b == l
                s = x.sum() + y.sum()
                worst = min(worst, 2 * (x & y).sum() / s if s else 1.0)
            row["worst_dice"] = round(float(worst), 6)
            row["n_labels"] = int(len(np.unique(a)) - 1)
        else:
            row["diff_voxels"] = "no ref" if not ref.exists() else "no u8 (hash only)"
        rows.append(row)
        print(row["tag"], key, row.get("diff_voxels"), row["t_first"], row["t_median_rest"], flush=True)
keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0].keys()).index(k) if k in rows[0] else 99)
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
print("->", out)
