"""Four-way agreement on 3D-IRCADb-01 (20 cases x 3 liver tasks): desktop reference (Python CPU, Windows), laptop reference
(Python CPU, Ubuntu), BrowSeg WebGPU and BrowSeg CPU (public build, desktop Chrome). Saved outputs only.
Output: analysis/fourway_20261007.txt (rev2 re-review A-M4). Run from paper_benchmarks with numpy."""
import os, itertools, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
R = os.path.join(ROOT, "data", "bench_refs"); B = os.path.join(ROOT, "paper_jiim", "paper_benchmarks", "data", "browser")
TASKS = ["total_liver", "liver_segments_all", "liver_vessels_all"]
def get(src, k, shape=None):
    if src == "desktop": return np.load(os.path.join(R, "ts218_cpu", k + ".npy"))
    if src == "laptop": return np.load(os.path.join(R, "ts218_cpu_laptop_m3", k + ".npy"))
    d = "v3_desk_chrome_webgpu" if src == "browseg_webgpu" else "v3_desk_chrome_wasm"
    return np.fromfile(os.path.join(B, d, k + ".u8"), dtype=np.uint8).reshape(shape)
names = ["desktop", "laptop", "browseg_webgpu", "browseg_cpu"]
same = {p: 0 for p in itertools.combinations(names, 2)}; diffv = {p: 0 for p in same}; detail = {p: [] for p in same}
total_vox = 0
for i in range(1, 21):
    for t in TASKS:
        k = f"ircad{i:02d}__{t}"; ref = get("desktop", k)
        a = {n: (ref if n == "desktop" else get(n, k, ref.shape)) for n in names}
        total_vox += ref.size
        for p in same:
            n = int((a[p[0]] != a[p[1]]).sum()); same[p] += n == 0; diffv[p] += n
            if n: detail[p].append(f"{i:02d}{t[:3]}:{n}")
out = [f"3D-IRCADb-01, 60 case-task pairs, {total_vox:,} voxels compared per source pair"]
for p in same:
    out.append(f"{p[0]} vs {p[1]}: identical {same[p]}/60, differing voxels total {diffv[p]} ({'; '.join(detail[p])})")
open(os.path.join(os.path.dirname(__file__), "..", "analysis", "fourway_20261007.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))
