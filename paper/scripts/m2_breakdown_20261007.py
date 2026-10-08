"""Time breakdown of a BrowSeg run from the engine timings recorded with every run (run["engineLog"], "timings:" block of
src/tsc/pipeline.cpp mark()): network (all "tiles (net+accum)" steps: the patches through the network and the
accumulation of their outputs), pre/post-processing (every other step: resampling, normalisation, crop, argmax, merge,
back to the original grid), model loading (run["modelSeconds"]: weights from the browser cache to WebAssembly / GPU),
and the rest (run["seconds"] minus the above: hand-over between the worker and the page, label map copy).
Public build 7ee2d83 (M2 records, data/browser/v3_*). WebGPU: runs 2-3 (per case: mean), CPU: the single run; median of
the 20 cases. Output: analysis/m2_breakdown_20261007.txt"""
import glob, json, re, statistics

TAGS = ["v3_desk_chrome_webgpu", "v3_desk_chrome_wasm", "v3_lap_nv_webgpu", "v3_lap_nv_st_webgpu", "v3_lap_wasm", "v3_lap_igpu_webgpu"]
TASKS = [("total", "liver"), ("liver_segments", "-"), ("liver_vessels", "-")]
out = []


def parse(el):
    net = pre = 0.0
    for name, ms in re.findall(r"^\s+(.+?)\s{2,}(\d+) ms$", el or "", re.M):
        if "tiles (net+accum)" in name:
            net += int(ms) / 1000
        else:
            pre += int(ms) / 1000
    return net, pre


for tag in TAGS:
    for task, roi in TASKS:
        per = []
        for f in sorted(glob.glob(f"data/browser/{tag}/ircad*__{task}_{'all' if roi == '-' else roi}.json")):
            runs = json.load(open(f, encoding="utf-8"))["runs"]
            use = runs[1:] if len(runs) > 1 else runs
            vals = []
            for r in use:
                net, pre = parse(r.get("engineLog"))
                ml = r.get("modelSeconds") or 0.0
                vals.append((r["seconds"], net, pre, ml, r["seconds"] - net - pre - ml))
            per.append(tuple(statistics.mean(v[i] for v in vals) for i in range(5)))
        if not per:
            continue
        med = [statistics.median(p[i] for p in per) for i in range(5)]
        share = statistics.median(p[1] / p[0] for p in per)
        out.append(f"{tag} {task}:{roi} (n={len(per)}): total {med[0]:.3f} s; network {med[1]:.3f}; pre/post {med[2]:.3f}; "
                   f"model load {med[3]:.3f}; rest {med[4]:.3f}; network share of total {share:.3f}")
open("analysis/m2_breakdown_20261007.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))
