"""Numbers of the M2 re-measurement (public build 7ee2d83, tags v3_*) quoted in the manuscript, from analysis/timing.csv
and analysis/exactness.csv (analyze.py). Values are printed unrounded (2-3 decimals) so that the manuscript rounds once.
Output: analysis/m2_numbers_20261007.txt"""
import csv
T = {(r["tag"], r["task"]): r for r in csv.DictReader(open("analysis/timing.csv", encoding="utf-8"))}
E = {(r["tag"], r["task"]): r for r in csv.DictReader(open("analysis/exactness.csv", encoding="utf-8"))}
tasks = ["total:liver", "liver_segments:-", "liver_vessels:-"]
out = []


def med(tag, kind):
    return ", ".join(f"{t} {float(T[(tag, t)][kind + '_median_s']):.3f}" for t in tasks if (tag, t) in T)


for tag in ("v3_desk_chrome_webgpu", "v3_desk_edge_webgpu", "v3_desk_chrome_webgpu_threads1", "v3_lap_nv_webgpu", "v3_lap_nv_st_webgpu"):
    out.append(f"{tag} median of runs 2-3 (s): {med(tag, 'rest')}; first run: {med(tag, 'first')}; heap max {max(int(T[(tag, t)]['heap_max_mib']) for t in tasks)} MiB")
for tag in ("v3_desk_chrome_wasm", "v3_desk_firefox_wasm", "v3_lap_wasm", "v3_lap_igpu_webgpu"):
    out.append(f"{tag} median of the single run (s): {med(tag, 'first')}; heap max {max(int(T[(tag, t)]['heap_max_mib']) for t in tasks)} MiB")
for tag in ("v3_desk_chrome_webgpu_cold", "v3_lap_nv_webgpu_cold"):
    out.append(f"{tag} cold start ircad01 liver (s): {float(T[(tag, 'total:liver')]['first_median_s']):.3f}")
r = T[("v3_desk_chrome_webgpu_total", "total:-")]
out.append(f"v3_desk_chrome_webgpu_total 117 structures (s, 1 run per case): median {float(r['first_median_s']):.3f} range {float(r['first_min_s']):.3f}-{float(r['first_max_s']):.3f}; heap max {r['heap_max_mib']} MiB")
ig = {t: float(T[("v3_lap_igpu_webgpu", t)]["first_median_s"]) for t in tasks}
cpu = {t: float(T[("v3_lap_wasm", t)]["first_median_s"]) for t in tasks}
nv1 = {t: float(T[("v3_lap_nv_webgpu", t)]["first_median_s"]) for t in tasks}
out.append("laptop iGPU vs laptop CPU, speed-up (CPU/iGPU): " + ", ".join(f"{t} {cpu[t] / ig[t]:.3f}" for t in tasks))
out.append("laptop iGPU vs T1200 first run, ratio (iGPU/T1200): " + ", ".join(f"{t} {ig[t] / nv1[t]:.3f}" for t in tasks))
st = {t: float(T[("v3_lap_nv_st_webgpu", t)]["rest_median_s"]) for t in tasks}
mt = {t: float(T[("v3_lap_nv_webgpu", t)]["rest_median_s"]) for t in tasks}
out.append("laptop single-thread minus multi-thread build, median of runs 2-3 (s): " + ", ".join(f"{t} {st[t] - mt[t]:.3f}" for t in tasks))
e = [E[("v3_lap_igpu_webgpu", t)] for t in tasks]
out.append("v3_lap_igpu_webgpu exact: " + ", ".join(f"{x['task']} {x['exact_cases']}/{x['cases']} ({x['cases_with_diff']})" for x in e) +
           f"; total exact {sum(int(x['exact_cases']) for x in e)}/{sum(int(x['cases']) for x in e)}")
open("analysis/m2_numbers_20261007.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))

# where the CPU-path memory maximum was first reached (the WebAssembly memory only grows within a page; appended)
import json
order = [(c, t) for c in range(1, 21) for t in ("total_liver", "liver_segments_all", "liver_vessels_all")]
for tag in ("v3_desk_chrome_wasm", "v3_desk_chrome_webgpu"):
    hs = [(c, t, max(r["heap"] for r in json.load(open(f"data/browser/{tag}/ircad{c:02d}__{t}.json"))["runs"])) for c, t in order]
    mx = max(h for *_, h in hs)
    c, t, h = next(x for x in hs if x[2] == mx)
    line = f"{tag} memory maximum {mx >> 20} MiB = {mx / 2 ** 30:.3f} GiB, first reached at ircad{c:02d} {t}"
    open("analysis/m2_numbers_20261007.txt", "a", encoding="utf-8").write(line + "\n")
    print(line)
