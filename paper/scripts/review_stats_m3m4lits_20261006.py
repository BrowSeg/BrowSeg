"""Numbers for the manuscript from the M3 / M4 / LiTS records of 2026-10-06 (output: analysis/review_stats_m3m4lits_20261006.txt).
  M3  : TS 2.18 CPU references, laptop (Linux, AVX-512) vs desktop (Windows, AVX2), IRCAD 20 x 3 liver tasks
  M4  : probe comparison BrowSeg (CPU / WebGPU) vs Python at the voxels where BrowSeg differs from the reference
  LiTS: BrowSeg WebGPU vs reference, 30 cases x 3 liver tasks, and the 117-structure runs
Run from paper_benchmarks with the ircad env:  python scripts/review_stats_m3m4lits_20261006.py
"""
import csv, glob, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from compare_probes import parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REF = os.path.join(ROOT, "data", "bench_refs")
M4 = "data/native/m4"
out = []
p = out.append

# ---------------- M3
lap, desk = os.path.join(REF, "ts218_cpu_laptop_m3"), os.path.join(REF, "ts218_cpu")
same, diffs = 0, []
for f in sorted(glob.glob(os.path.join(lap, "*.npy"))):
    k = os.path.basename(f)[:-4]
    a, b = np.load(f), np.load(os.path.join(desk, k + ".npy"))
    d = int((a != b).sum())
    if d == 0:
        same += 1
    else:
        diffs.append((k, d))
p(f"M3 laptop vs desktop TS 2.18 CPU references: identical {same}/{same + len(diffs)}; differing: " +
  ", ".join(f"{k} {d}" for k, d in diffs))
p(f"M3 differing voxels per pair: min {min(d for _, d in diffs)} max {max(d for _, d in diffs)}, total {sum(d for _, d in diffs)}")
gaps = []
for f in sorted(glob.glob(f"{M4}/tie_desktop_*.log")) + sorted(glob.glob(f"{M4}/laptop_results/tie_laptop_*.log")):
    if "resampled" not in f and "ircad12" in f and "laptop" in f:
        continue  # the first laptop ircad12 run stopped (grid mapping); the resampled log replaces it
    txt = open(f, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"orig \(([^)]*)\):.*?\n((?:    net .*\n)+)", txt):
        g = [int(x) for x in re.findall(r"= (\d+) fp16-ulp", m.group(2))]
        gaps.append((os.path.basename(f), m.group(1), min(g)))
    for m in re.finditer(r"orig \(([^)]*)\):.*gap=\S+ = ([\d.]+) ulp", txt):
        gaps.append((os.path.basename(f), m.group(1), float(m.group(2))))
p(f"M3 top-2 fp16 gap at the differing voxels (smallest in the 2x2x2 neighbourhood / at the crop voxel): " +
  "; ".join(f"{f} {v} {g:g}" for f, v, g in gaps))
p(f"M3 largest of these gaps: {max(g for *_, g in gaps):g} fp16-ulp over {len(gaps)} (log, voxel) entries")

# ---------------- M4
pairs = [("cpu", "ircad05_seg"), ("webgpu", "ircad14_seg"), ("cpu", "ircad14_seg"), ("cpu", "ircad16_seg"), ("webgpu", "ircad16_seg"),
         ("cpu", "ircad18_seg"), ("webgpu", "ircad18_seg"), ("cpu", "ircad20_liver"), ("cpu", "ircad12_ves")]
for path, name in pairs:
    b_acc, b_fin, b_crop = parse(f"{M4}/browseg_probe_{path}_{name}.log")
    p_acc, p_fin, p_crop = parse(f"{M4}/python_probe_{name}.log")
    comp = open(f"{M4}/browseg_probe_{path}_{name}.log", encoding="utf-8", errors="replace").read()
    rec = re.findall(r"COMPARE (\S+): differing voxels (\d+)", comp)
    if path == "webgpu":  # the browser log has no COMPARE lines: compare the saved label maps
        case = name.split("_")[0]
        key = f"{case}__liver_segments_all"
        u = np.fromfile(f"data/browser_m4probe/m4probe_webgpu_{case}/{key}.u8", np.uint8)
        rec = [("record", int((u != np.fromfile(f"data/browser/desk_chrome_webgpu_final/{key}.u8", np.uint8)).sum())),
               ("reference", int((u != np.load(os.path.join(desk, key + ".npy")).ravel()).sum()))]
    pyc = re.search(r"python probe final vs ref: differing voxels (\d+)", open(f"{M4}/python_probe_{name}.log", encoding="utf-8").read()).group(1)
    nets = sorted(set(b_fin) & set(p_fin))
    differing_final = [q for q in nets if b_fin[q][1] != p_fin[q][1]]
    line = (f"M4 {path} {name}: probe output vs benchmark record {rec[0][1]} voxels, vs reference {rec[1][1]}; python probe vs reference {pyc}; "
            f"probed net voxels {len(nets)}, with any differing final logit {len(differing_final)}")
    for q in differing_final:
        bf, pf = b_fin[q][1], p_fin[q][1]
        cls = [c for c in bf if bf[c] != pf[c]]
        bt = {t[0]: t for t in b_acc[q]}
        pt = {t[0]: t for t in p_acc[q]}
        first = None
        for t in sorted(set(bt) & set(pt)):
            if any(np.float16(bt[t][4][c][2]) != np.float16(pt[t][4][c][2]) for c in cls):
                first = t
                break
        ntiles = len(bt)
        ydiff = max(abs(bt[t][4][c][0] - pt[t][4][c][0]) / float(np.spacing(np.float32(abs(pt[t][4][c][0]))))
                    for t in set(bt) & set(pt) for c in bt[t][4])
        yabs = max(abs(bt[t][4][c][0] - pt[t][4][c][0]) for t in set(bt) & set(pt) for c in bt[t][4])
        acc_ulp = {c: (np.float16(bt[first][4][c][2]) - np.float16(pt[first][4][c][2])) / np.spacing(np.float16(abs(pt[first][4][c][2])))
                   for c in cls} if first is not None else {}
        line += (f"; net {q}: classes {cls} final browseg " + ",".join(f"c{c}={bf[c]:.9g}" for c in cls) +
                 " python " + ",".join(f"c{c}={pf[c]:.9g}" for c in cls) +
                 f", tiles covering {ntiles}, first tile with a differing fp16 accumulator {first} (" +
                 ",".join(f"c{c} {v:+.0f} ulp" for c, v in acc_ulp.items()) + f"), largest fp32 output difference {ydiff:.0f} fp32-ulp (absolute {yabs:.3g})")
    for q, b in b_crop.items():
        line += f"; crop {q}: browseg " + ",".join(f"c{c}={v:.9g}" for c, v in b.items())
    p(line)

# ---------------- LiTS
rows = [x for x in csv.DictReader(open("analysis/lits_summary.csv", encoding="utf-8"))]
w = [x for x in rows if x["tag"] == "lits_chrome_webgpu"]
by = {}
for x in w:
    by.setdefault(x["task"], []).append(x)
p(f"LiTS WebGPU liver 3 tasks: identical {sum(x['diff_voxels'] == '0' for x in w)}/{len(w)}; " +
  ", ".join(f"{t} {sum(x['diff_voxels'] == '0' for x in v)}/{len(v)}" for t, v in sorted(by.items())))
nz = [x for x in w if x["diff_voxels"] != "0"]
p("LiTS WebGPU differing: " + ", ".join(f"{x['case']} {x['task']} {x['diff_voxels']}" for x in nz))
p(f"LiTS WebGPU differing voxels min {min(int(x['diff_voxels']) for x in nz)} max {max(int(x['diff_voxels']) for x in nz)}; "
  f"smallest per-structure Dice {min(float(x['worst_dice']) for x in w):.6f}; runs per case/task {set(x['runs'] for x in w)}, "
  f"repeatable all {all(x['repeatable'] == 'True' for x in w)}")
p(f"LiTS WebGPU heap max {max(int(x['heap_mib']) for x in w)} MiB; slices min {min(int(x['shape'].split('x')[2]) for x in w)} max {max(int(x['shape'].split('x')[2]) for x in w)}")
for x in rows:
    if "total117" in x["tag"]:
        p(f"LiTS 117 structures WebGPU {x['case']}: differing voxels {x['diff_voxels']}, structures differing {x['labels_diff']}, "
          f"smallest Dice {x['worst_dice']}, heap {x['heap_mib']} MiB, seconds {x['t_first']}")
open("analysis/review_stats_m3m4lits_20261006.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))

# ---------------- LiTS selection (appended)
inv = list(csv.DictReader(open("analysis/lits_inventory_20261006.csv", encoding="utf-8")))
rest = [r for r in inv if not r["ircad_match"] and r["case"] != "liver_191"]
grp = {"thin": lambda d: d <= 1.0, "medium": lambda d: 1.0 < d <= 2.5, "thick": lambda d: d > 2.5}
sel = [r for r in csv.DictReader(open("analysis/lits_selection_20261006.csv", encoding="utf-8")) if "liver3" in r["purpose"]]
extra = [
    f"LiTS inventory: {len(inv)} volumes, IRCAD-matching {sum(bool(r['ircad_match']) for r in inv)}, remaining after excluding IRCAD and liver_191: {len(rest)}; "
    + ", ".join(f"{g} {sum(f(float(r['dz'])) for r in rest)}" for g, f in grp.items()),
    f"LiTS selected for the liver tasks: {len(sel)}; slice spacing {min(float(r['dz']) for r in sel):g}-{max(float(r['dz']) for r in sel):g} mm; "
    f"slices {min(int(r['nz']) for r in sel)}-{max(int(r['nz']) for r in sel)}; in-plane {min(float(r['dx']) for r in sel):g}-{max(float(r['dx']) for r in sel):g} mm",
]
open("analysis/review_stats_m3m4lits_20261006.txt", "a", encoding="utf-8").write("\n".join(extra) + "\n")
print("\n".join(extra))

# ---------------- M4 overall (appended): probed points, points with a differing final logit, size of those differences
tot_pts, diff_pts, ulps, decisive = 0, set(), [], []
seen_pts = set()
for path, name in pairs:
    b_acc, b_fin, _ = parse(f"{M4}/browseg_probe_{path}_{name}.log")
    p_acc, p_fin, _ = parse(f"{M4}/python_probe_{name}.log")
    for q in set(b_fin) & set(p_fin):
        if (name, q) not in seen_pts:
            seen_pts.add((name, q))
        bf, pf = b_fin[q][1], p_fin[q][1]
        for c in bf:
            if bf[c] != pf[c]:
                diff_pts.add((path, name, q))
                u = abs(float(np.float16(bf[c])) - float(np.float16(pf[c]))) / float(np.spacing(np.float16(max(abs(bf[c]), abs(pf[c])))))
                ulps.append((path, name, q, c, round(u, 2)))
extra = [f"M4 overall: probed (case, net voxel) {len(seen_pts)}; (path, case, voxel) with any differing final logit {len(diff_pts)} "
         f"(distinct (case, voxel) {len({(n, q) for _, n, q in diff_pts})}); per differing class: " +
         ", ".join(f"{p_} {n} {q} c{c} {u:g} ulp" for p_, n, q, c, u in ulps) +
         f"; ulp range {min(u for *_, u in ulps):g}-{max(u for *_, u in ulps):g}; classes differing per voxel always 1: "
         f"{all(sum(1 for x in ulps if x[:3] == d) == 1 for d in diff_pts)}"]
open("analysis/review_stats_m3m4lits_20261006.txt", "a", encoding="utf-8").write("\n".join(extra) + "\n")
print("\n".join(extra))

# ---------------- BrowSeg CPU / WebGPU vs the laptop reference (appended)
res = []
for tag in ("desk_chrome_wasm_20", "desk_chrome_webgpu_final"):
    n_same = 0; tot = 0; d_list = []
    for f in sorted(glob.glob(os.path.join(lap, "*.npy"))):
        k = os.path.basename(f)[:-4]
        u = f"data/browser/{tag}/{k}.u8"
        if not os.path.exists(u):
            continue
        d = int((np.fromfile(u, np.uint8) != np.load(f).ravel()).sum()); tot += 1
        n_same += d == 0
        if d: d_list.append(f"{k} {d}")
    res.append(f"BrowSeg {tag} vs laptop reference: identical {n_same}/{tot}; differing: " + ", ".join(d_list))
open("analysis/review_stats_m3m4lits_20261006.txt", "a", encoding="utf-8").write("\n".join(res) + "\n")
print("\n".join(res))

# ---------------- LiTS CPU path (appended after the CPU run): main page + lits_167 alone + 3 remaining cases;
# times of lits_022 / lits_023 from the recheck page (the main run overlapped a short low-priority job, 20:55 JST)
rows = list(csv.DictReader(open("analysis/lits_summary.csv", encoding="utf-8")))
main = {(x["case"], x["task"]): x for x in rows if x["tag"] == "lits_chrome_wasm"}
for t in ("lits_chrome_wasm_167", "lits_chrome_wasm_rest"):
    for x in rows:
        if x["tag"] == t:
            main[(x["case"], x["task"])] = x
rc = {(x["case"], x["task"]): x for x in rows if x["tag"] == "lits_chrome_wasm_recheck_022_023"}
cpu = list(main.values())
gpu = {(x["case"], x["task"]): x for x in rows if x["tag"] == "lits_chrome_webgpu"}
byt = {}
for x in cpu:
    byt.setdefault(x["task"], []).append(x)
nz = [x for x in cpu if x["diff_voxels"] != "0"]
extra = [
    f"LiTS CPU liver 3 tasks: identical {sum(x['diff_voxels'] == '0' for x in cpu)}/{len(cpu)}; " +
    ", ".join(f"{t} {sum(x['diff_voxels'] == '0' for x in v)}/{len(v)}" for t, v in sorted(byt.items())),
    "LiTS CPU differing: " + ", ".join(f"{x['case']} {x['task']} {x['diff_voxels']}" for x in sorted(nz, key=lambda r: (r['case'], r['task']))),
    f"LiTS CPU differing voxels min {min(int(x['diff_voxels']) for x in nz)} max {max(int(x['diff_voxels']) for x in nz)}; smallest per-structure Dice {min(float(x['worst_dice']) for x in cpu):.6f}",
    f"LiTS CPU vs WebGPU: same number of differing voxels {sum(gpu[k]['diff_voxels'] == x['diff_voxels'] for k, x in main.items())}/{len(main)}; "
    "differing only on CPU: " + ", ".join(f"{k[0]} {k[1]}" for k, x in sorted(main.items()) if x['diff_voxels'] != '0' and gpu[k]['diff_voxels'] == '0') +
    "; differing only on WebGPU: " + ", ".join(f"{k[0]} {k[1]}" for k, x in sorted(main.items()) if x['diff_voxels'] == '0' and gpu[k]['diff_voxels'] != '0'),
    f"LiTS CPU lits_167 alone: heap {max(int(x['heap_mib']) for x in rows if x['tag'] == 'lits_chrome_wasm_167')} MiB; the main page stopped at lits_167 with std::bad_alloc "
    f"(data/browser_lits/lits_chrome_wasm/error.txt); main page heap before it {max(int(x['heap_mib']) for x in rows if x['tag'] == 'lits_chrome_wasm')} MiB",
    "LiTS CPU timing check lits_022/023 (main vs recheck, s): " + ", ".join(
        f"{k[0]} {k[1]} {main[k]['t_first']}/{rc[k]['t_first']}" for k in sorted(rc)),
]
import statistics
tm = {}
for k, x in main.items():
    tm.setdefault(k[1], []).append(float((rc.get(k) or x)["t_first"]))
extra.append("LiTS CPU time median (s, 30 cases, lits_022/023 from the recheck): " + ", ".join(f"{t} {statistics.median(v):.1f} (n={len(v)})" for t, v in sorted(tm.items())))
tg = {}
for x in gpu.values():
    tg.setdefault(x["task"], []).append(float(x["t_median_rest"]))
extra.append("LiTS WebGPU time median (s, mean of runs 2-3 per case): " + ", ".join(f"{t} {statistics.median(v):.2f}" for t, v in sorted(tg.items())))
open("analysis/review_stats_m3m4lits_20261006.txt", "a", encoding="utf-8").write("\n".join(extra) + "\n")
print("\n".join(extra))

# ---------------- LiTS mismatches, laptop Python logits (appended; logs from the laptop session, data/native/m4/lits_laptop)
L = "data/native/m4/lits_laptop"
res = []
allg = []
for f in sorted(glob.glob(f"{L}/tie_laptop_lits_*.log")):
    txt = open(f, encoding="utf-8", errors="replace").read()
    g = []
    for m in re.finditer(r"orig \(([^)]*)\):.*?\n((?:    net .*\n)+)", txt):
        g.append(min(int(x) for x in re.findall(r"= (\d+) fp16-ulp", m.group(2))))
    for m in re.finditer(r"orig \(([^)]*)\):.*gap=\S+ = ([\d.]+) ulp", txt):
        g.append(float(m.group(2)))
    n = int(re.search(r": (\d+) differing voxels", txt).group(1))
    res.append(f"{os.path.basename(f)[11:-4]} {n} voxels, smallest top-2 gap per distinct grid point {g}")
    allg += g
hc = open(f"{L}/hash_check_desktop.txt", encoding="utf-8").read()
done_md = open(f"{L}/M4_LITS_LAPTOP_DONE.md", encoding="utf-8").read()
sec = done_md[done_md.index("SHA-256（A-4"):]
sides = ""
for n_, side in re.findall(r"^\| lits_\d+ [^|]+\| (\d+) \| ([^|]+) \|", sec, re.M):
    sides += "B" * int(n_) if "×" in side else "".join(re.findall(r"[AB]", side))
out2 = ["LiTS laptop Python logits at the WebGPU mismatches (gaps listed once per distinct network-grid point): " + "; ".join(res),
        f"LiTS laptop: distinct grid points {len(allg)}, largest of the smallest top-2 gaps {max(allg):g} fp16-ulp; "
        f"laptop final on the desktop-reference side {sides.count('A')} / on the BrowSeg side {sides.count('B')} of {len(sides)} voxels; "
        f"laptop final = desktop reference except the listed voxels: {hc.count('MATCHES')}/10"]
open("analysis/review_stats_m3m4lits_20261006.txt", "a", encoding="utf-8").write("\n".join(out2) + "\n")
print("\n".join(out2))
