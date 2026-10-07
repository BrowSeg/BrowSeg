"""M2: compare the label-map hashes of the re-measurement with the public build 7ee2d83 (data/browser/v3_*) with the
records used in the paper (same case x task), and report repeatability, backends, fallbacks and GPU errors.
Output: analysis/m2_compare_20261007.txt"""
import glob, json, os
PAIRS = [("v3_desk_chrome_webgpu", "desk_chrome_webgpu_final"), ("v3_desk_chrome_webgpu_total", "desk_chrome_webgpu_total_20"),
         ("v3_desk_chrome_webgpu_threads1", "desk_chrome_webgpu_threads1_20"), ("v3_desk_edge_webgpu", "desk_edge_webgpu_20"),
         ("v3_desk_chrome_wasm", "desk_chrome_wasm_20"), ("v3_desk_firefox_wasm", "desk_firefox_wasm_20"),
         ("v3_desk_firefox_webgpu", "desk_chrome_webgpu_final"), ("v3_desk_chrome_webgpu_cold", "desk_chrome_webgpu_cold_final_r2")]
out = []
def load(tag):
    d = {}
    for f in glob.glob(f"data/browser/{tag}/*__*.json"):
        j = json.load(open(f, encoding="utf-8"))
        d[os.path.basename(f)[:-5]] = j
    return d
for new, old in PAIRS:
    a, b = load(new), load(old)
    same = diff = 0; dl = []; rep = 0; backends = set(); fb = 0; ge = 0
    for k, j in a.items():
        hs = [r["hash"] for r in j["runs"]]
        rep += len(set(hs)) == 1
        backends |= {r["backend"] for r in j["runs"]}
        fb += sum(1 for r in j["runs"] if r.get("fallback")); ge += sum(r.get("gpuErrors", 0) for r in j["runs"])
        if k in b:
            if b[k]["runs"][0]["hash"] == hs[0]: same += 1
            else: diff += 1; dl.append(k)
    out.append(f"{new} vs {old}: keys {len(a)}, first-run hash same {same}, different {diff} {dl}; runs identical within the key {rep}/{len(a)}; "
               f"backends {sorted(backends)}; runs with fallback {fb}; gpuErrors {ge}")
open("analysis/m2_compare_20261007.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))

# median times (s): WebGPU = mean of runs 2-3 per case, CPU = the single run; 20 cases (appended)
import statistics
def med(tag):
    d = {}
    for f in glob.glob(f"data/browser/{tag}/*__*.json"):
        j = json.load(open(f, encoding="utf-8"))
        t = j["task"] if j["roi"] == "-" else j["task"] + ":" + j["roi"]
        rs = [r["seconds"] for r in j["runs"]]
        d.setdefault(t, []).append(statistics.mean(rs[1:]) if len(rs) > 1 else rs[0])
    return ", ".join(f"{k} {statistics.median(v):.2f}" for k, v in sorted(d.items()))
ua = json.load(open("data/browser/v3_desk_firefox_webgpu/environment.json", encoding="utf-8"))["userAgent"]
t = [f"median seconds {tag}: {med(tag)}" for tag, _ in PAIRS if tag != "v3_desk_chrome_webgpu_cold"]
t.append(f"v3_desk_firefox_webgpu userAgent: {ua}")
open("analysis/m2_compare_20261007.txt", "a", encoding="utf-8").write("\n".join(t) + "\n")
print("\n".join(t))
