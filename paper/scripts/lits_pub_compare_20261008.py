"""LiTS re-measurement with the public build 7ee2d83 (2026-10-08) vs the 10-06 records.

Compares, per case x task, the label-map hashes of every run of the new records (data/browser_lits_pub/<tag>/)
with the hashes of the old records (data/browser_lits/<tag>/), and reports backends, fallbacks and timing medians.
usage: python lits_pub_compare_20261008.py gpu|cpu
"""
import json, statistics as st, sys
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data"
A = Path(__file__).resolve().parents[1] / "analysis"
mode = sys.argv[1]
if mode == "gpu":
    new_tags, old_tags = ["lits_pub_chrome_webgpu"], ["lits_chrome_webgpu"]
else:
    new_tags = ["lits_pub_chrome_wasm_p1", "lits_pub_chrome_wasm_p1b", "lits_pub_chrome_wasm_p1c", "lits_pub_chrome_wasm_p2", "lits_pub_chrome_wasm_p3", "lits_pub_chrome_wasm_167"]
    old_tags = ["lits_chrome_wasm", "lits_chrome_wasm_167", "lits_chrome_wasm_rest"]


def load(root, tags):
    out = {}
    for t in tags:
        for f in sorted((D / root / t).glob("lits_*.json")):
            d = json.loads(f.read_text())
            out[f.stem] = d   # later tags override earlier ones (old: the separate 167 / rest pages)
    return out


new, old = load("browser_lits_pub", new_tags), load("browser_lits", old_tags)
lines = [f"LiTS {mode}: public build (browser_lits_pub {new_tags}) vs 10-06 records (browser_lits {old_tags})",
         f"pairs: new {len(new)}, old {len(old)}"]
same, diff, fb, rep_ok = 0, [], [], 0
for k in sorted(old):
    if k not in new:
        lines.append(f"MISSING in new: {k}"); continue
    hn = [r["hash"] for r in new[k]["runs"]]
    ho = {r["hash"] for r in old[k]["runs"]}
    if len(set(hn)) == 1:
        rep_ok += 1
    if set(hn) <= ho and len(ho) == 1:
        same += 1
    else:
        diff.append(f"{k}: new {hn} old {sorted(ho)}")
    b = {r["backend"] for r in new[k]["runs"]}
    if b != ({"webgpu"} if mode == "gpu" else {"cpu"}) or any(r.get("fallback") for r in new[k]["runs"]):
        fb.append(f"{k}: backends {b} fallback {[r.get('fallback') for r in new[k]['runs']]}")
lines.append(f"identical to the 10-06 record (every run): {same}/{len(old)}")
lines.append(f"runs identical within the new record: {rep_ok}/{len(new)}")
lines += ["different: " + d for d in diff] + ["backend/fallback: " + f for f in fb]
for task in ["total", "liver_segments", "liver_vessels"]:
    v = []
    for k, d in new.items():
        if d["task"] != task:
            continue
        s = [r["seconds"] for r in d["runs"]]
        v.append(sum(s[1:]) / len(s[1:]) if len(s) > 1 else s[0])
    if v:
        lines.append(f"time {task}: median {st.median(v):.2f} s, range {min(v):.2f}-{max(v):.2f} (n={len(v)})")
heap = max((r["heap"], k) for k, d in new.items() for r in d["runs"])
lines.append(f"heap max {heap[0] / 2**20:.0f} MiB ({heap[1]})")
(A / f"lits_pub_{mode}_20261008.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
