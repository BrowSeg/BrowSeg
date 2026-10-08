"""Public records for paper-v1.1 (2026-10-08): LiTS in the expected-hash files of the benchmark page, and one CSV.

- data/desktop_hashes.json (WebGPU) and data/desktop_hashes_wasm20.json (CPU): the 90 LiTS case x task pairs measured with
  the paper's build 022925c (data/browser_lits_v11) are added as entries "lits_NNN__<task>" next to the 3D-IRCADb-01
  entries of paper-v1, so bench.html?local=1 compares a reader's LiTS run with the paper's (cases/lits_NNN/liver_N.nii.gz).
- data/lits_v11_summary.csv: one row per path x case x task: hashes, differing voxels vs the reference (TotalSegmentator
  2.18.0, CPU), smallest per-structure Dice, seconds (WebGPU: mean of runs 2-3, CPU: one run), WebAssembly heap (MiB).
Differing voxels and Dice come from lits_summary.csv (10-06 build); the v1.1 label maps are identical to those (checked
here by hash, otherwise the script stops).
"""
import csv, json
from pathlib import Path

B = Path(__file__).resolve().parents[1]
D, A = B / "data", B / "analysis"
V11 = D / "browser_lits_v11"
TAGS = {"webgpu": ["lits_v11_chrome_webgpu"],
        "cpu": ["lits_v11_chrome_wasm_p1", "lits_v11_chrome_wasm_p2", "lits_v11_chrome_wasm_p3", "lits_v11_chrome_wasm_167"]}
OLD = {"webgpu": ["lits_chrome_webgpu"], "cpu": ["lits_chrome_wasm", "lits_chrome_wasm_167", "lits_chrome_wasm_rest"]}
summary = {(r["tag"], r["case"], r["task"]): r for r in csv.DictReader(open(A / "lits_summary.csv", encoding="utf-8"))}


def records(root, tags):
    out = {}
    for t in tags:
        for f in sorted((root / t).glob("lits_*.json")):
            out[f.stem] = (t, json.loads(f.read_text()))
    return out


rows = []
for path, hfile in (("webgpu", "desktop_hashes.json"), ("cpu", "desktop_hashes_wasm20.json")):
    new, old = records(V11, TAGS[path]), records(D / "browser_lits", OLD[path])
    assert len(new) == 90, (path, len(new))
    h = json.loads((D / hfile).read_text(encoding="utf-8"))
    for k, (tag, d) in sorted(new.items()):
        hashes = sorted({r["hash"] for r in d["runs"]})
        otag, od = old[k]
        assert hashes == sorted({r["hash"] for r in od["runs"]}), f"{path} {k}: v1.1 differs from the 10-06 record"
        s = summary[(otag, d["case"], d["task"])]
        dv = int(s["diff_voxels"])
        h["entries"][k] = {"hashes": hashes, "diff_voxels_vs_python": dv, "exact": dv == 0, "tag": tag}
        secs = [r["seconds"] for r in d["runs"]]
        rows.append({"path": path, "case": d["case"], "task": d["task"], "roi": d["roi"], "shape": "x".join(map(str, d["shape"])),
                     "runs": len(secs), "hash": " ".join(hashes), "diff_voxels_vs_reference": dv, "min_dice": s["worst_dice"],
                     "seconds": round(sum(secs[1:]) / len(secs[1:]) if len(secs) > 1 else secs[0], 3),
                     "heap_mib": round(max(r["heap"] for r in d["runs"]) / 2**20), "record": f"browser_lits_v11/{tag}/{k}.json"})
    tags = set(h.get("source_tag", "").split(",")) | set(TAGS[path])
    h["source_tag"] = ",".join(sorted(t for t in tags if t))
    (D / hfile).write_text(json.dumps(h, indent=1), encoding="utf-8")
    print(hfile, len(h["entries"]), "entries")
with open(D / "lits_v11_summary.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print("lits_v11_summary.csv", len(rows), "rows")
