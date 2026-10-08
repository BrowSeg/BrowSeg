"""Check of the lower-memory NIfTI loading (tsc_set_volume_raw, 2026-10-08): the new build's WebGPU outputs on LiTS must be
identical to the public build 7ee2d83 (browser_lits_pub/lits_pub_chrome_webgpu), and the WebAssembly heap is compared.
usage: python lits_raw_check_20261008.py <new tag dir> [<new tag dir> ...]
"""
import json, sys
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data"
old = {f.stem: json.loads(f.read_text()) for f in (D / "browser_lits_pub" / "lits_pub_chrome_webgpu").glob("lits_*.json")}
new = {}
for d in sys.argv[1:]:
    for f in sorted(Path(d).glob("lits_*.json")):
        new[f.stem] = json.loads(f.read_text())
same = [k for k in new if k in old and {r["hash"] for r in new[k]["runs"]} == {r["hash"] for r in old[k]["runs"]}]
print(f"identical to 7ee2d83: {len(same)}/{len(new)} (pairs in the old record {len(old)})")
for k in sorted(set(new) - set(same)):
    print("  different:", k, [r["hash"] for r in new[k]["runs"]], sorted({r["hash"] for r in old.get(k, {"runs": []})["runs"]}))
fb = [k for k, d in new.items() for r in d["runs"] if r["backend"] != "webgpu" or r.get("fallback")]
print("backend/fallback:", fb or "none")
for name, rec in (("7ee2d83", old), ("new", new)):
    first = {}
    for k, d in rec.items():   # heap after the first task of each case = memory needed to load the CT and run it alone
        c = d["case"]
        first[c] = max(first.get(c, 0), max(r["heap"] for r in d["runs"]))
    top = sorted(first.items(), key=lambda kv: -kv[1])[:3]
    print(f"{name}: heap max per case (MiB): " + ", ".join(f"{c} {h / 2**20:.0f}" for c, h in top))
