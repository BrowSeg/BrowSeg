"""Crop box (bbox) of the 6 mm locating model: Python TotalSegmentator (tools/record_bbox.py, data/bbox/python) vs BrowSeg
(native build, tests/test_task "bbox canonical", data/bbox/native), 3D-IRCADb-01 20 cases x 3 liver tasks; the box of
case 9 from repeated GPU runs (data/bbox/python_gpu); and the margin between the reference liver and the box faces.
Output: analysis/bbox_20261007.txt, analysis/table_S7_jp.md (supplement)
Run from paper_benchmarks (any env with numpy)."""
import glob, json, os, re
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PY, NA, GPU = [os.path.join(ROOT, "data", "bbox", d) for d in ("python", "native", "python_gpu")]
REF = os.path.join(ROOT, "data", "bench_refs", "ts218_cpu")
TASKS = [("total", "liver"), ("liver_segments", "all"), ("liver_vessels", "all")]
JP = {"total": "肝臓", "liver_segments": "肝区域", "liver_vessels": "肝内血管"}
out, rows, unclipped_all = [], [], []
same = diff = missing = 0
for i in range(1, 21):
    case = f"ircad{i:02d}"
    ref = np.load(os.path.join(REF, f"{case}__total_liver.npy"))
    liver = np.argwhere(ref == 5)
    lb = [[int(liver[:, d].min()), int(liver[:, d].max()) + 1] for d in range(3)]  # reference liver extent (RAS)
    per_task = []
    for task, roi in TASKS:
        k = f"{case}__{task}_{roi}"
        pj, nt = os.path.join(PY, k + ".bbox.json"), os.path.join(NA, k + ".txt")
        if not (os.path.exists(pj) and os.path.exists(nt)):
            missing += 1; per_task.append((task, None, None, None)); continue
        p = json.load(open(pj))
        m = re.search(r"bbox canonical \[(\d+),(\d+)\) \[(\d+),(\d+)\) \[(\d+),(\d+)\)", open(nt).read())
        nb = [[int(m.group(1)), int(m.group(2))], [int(m.group(3)), int(m.group(4))], [int(m.group(5)), int(m.group(6))]]
        eq = nb == p["bbox_ras"]
        same += eq; diff += not eq
        per_task.append((task, p, nb, eq))
    # margins (mm) from the reference liver to the box faces, using the Python box of the total task (same for all tasks if equal)
    p0 = next((p for _, p, _, _ in per_task if p), None)
    if p0:
        z = p0["zooms"]; b = p0["bbox_ras"]; sh = p0["img_shape"]
        marg = [((lb[d][0] - b[d][0]) * z[d], (b[d][1] - lb[d][1]) * z[d]) for d in range(3)]
        clipped = [b[d][0] == 0 or b[d][1] == sh[d] for d in range(3)]
        mm = min(min(a, c) for a, c in marg)
        # faces cut by the image boundary are not crop margins (the liver reaches the scan end); keep them apart
        cut = [(b[d][0] == 0, b[d][1] == sh[d]) for d in range(3)]
        un = [marg[d][s] for d in range(3) for s in (0, 1) if not cut[d][s]]
        unclipped_all.extend((marg[d][s], case, "xyz"[d], ("lo", "hi")[s]) for d in range(3) for s in (0, 1) if not cut[d][s])
        um = [min([marg[d][s] for s in (0, 1) if not cut[d][s]], default=None) for d in range(3)]
        boxes_equal_across_tasks = len({json.dumps(p["bbox_ras"]) for _, p, _, _ in per_task if p}) == 1
        addons = sorted({tuple(p["addon_mm"]) for _, p, _, _ in per_task if p})
        line = (f"{case}: python box (RAS) {b}, browseg {[nb for _, _, nb, _ in per_task]}, equal {[e for *_, e in per_task]}; "
                f"addon mm {addons}; boxes equal across the 3 tasks {boxes_equal_across_tasks}; reference liver extent {lb}; "
                f"margin liver->box faces (mm) x {marg[0][0]:.1f}/{marg[0][1]:.1f} y {marg[1][0]:.1f}/{marg[1][1]:.1f} z {marg[2][0]:.1f}/{marg[2][1]:.1f}; "
                f"min {mm:.1f}; min over faces not cut by the image boundary {min(un):.1f}; box clipped by the image boundary {clipped}")
        out.append(line)
        rows.append(f"| {i} | {'' if all(e for *_, e in per_task) else '（BrowSeg と異なる）'}{b[0][0]}–{b[0][1]}, {b[1][0]}–{b[1][1]}, {b[2][0]}–{b[2][1]} | " +
                    " / ".join("—" if v is None else f"{v:.1f}" for v in um) + " | " +
                    (", ".join(f"{'xyz'[d]} の{('下', '上')[s]}側" for d in range(3) for s in (0, 1) if cut[d][s]) or "—") + " |")
unclipped_all.sort()
out.insert(0, "smallest margins over faces not cut by the image boundary (mm): " + "; ".join(f"{c} {a} {sd} {m:.1f}" for m, c, a, sd in unclipped_all[:5]))
out.insert(0, f"IRCAD 20 x 3 tasks: box identical (python RAS vs browseg canonical) {same}, different {diff}, missing {missing}")
# case 9 on the GPU
g = sorted(glob.glob(os.path.join(GPU, "ircad09__*.bbox.json")))
gb = {}
for f in g:
    j = json.load(open(f)); gb.setdefault(f"{j['task']}:{j['roi']}", []).append((j["run"], j["bbox_ras"], j["mask_voxels"]))
for k, v in gb.items():
    boxes = {json.dumps(b) for _, b, _ in v}
    out.append(f"ircad09 GPU {k}: runs {len(v)}, distinct boxes {len(boxes)}: " + "; ".join(f"{r} {b} (mask voxels {n})" for r, b, n in v))
if os.path.exists(os.path.join(PY, "ircad09__total_liver.bbox.json")):
    cpu9 = json.load(open(os.path.join(PY, "ircad09__total_liver.bbox.json")))
    out.append(f"ircad09 CPU total:liver box {cpu9['bbox_ras']} (mask voxels {cpu9['mask_voxels']})")
open("analysis/bbox_20261007.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
tbl = ["| 症例 | 範囲（x, y, z、RAS のボクセル） | 肝臓から箱の面までの最小の余裕（mm、x / y / z。画像の端で切られた面を除く） | 画像の端で切られた面 |",
       "|---|---|---|---|"] + rows
open("analysis/table_S7_jp.md", "w", encoding="utf-8").write("\n".join(tbl) + "\n")
print("\n".join(out))

# self-consistency: the recorded Python boxes (TS grid, exclusive ends) must equal the crop_bbox.json that tools/make_reference.py
# dumped in the earlier full runs (same TotalSegmentator code path); and the CPU box of case 9 from that dump vs the GPU runs
chk = []
for d in sorted(glob.glob(os.path.join(ROOT, "data", "ref218", "ircad*_*"))):
    cj = os.path.join(d, "crop_bbox.json")
    if not os.path.isdir(d) or not os.path.exists(cj):
        continue
    name = os.path.basename(d)  # ircadNN_<task>
    case, task = name.split("_", 1)
    key = f"{case}__{task}_{'liver' if task == 'total' else 'all'}"
    pj = os.path.join(PY, key + ".bbox.json")
    if os.path.exists(pj):
        chk.append(f"{key}: recorded {json.load(open(pj))['bbox']} vs make_reference dump {json.load(open(cj))['bbox']} -> "
                   f"{'same' if json.load(open(pj))['bbox'] == json.load(open(cj))['bbox'] else 'DIFFERENT'}")
d9 = os.path.join(ROOT, "data", "ref218", "ircad09_liver_segments", "crop_bbox.json")
if os.path.exists(d9):
    b = json.load(open(d9))["bbox"]; n = 512
    chk.append(f"ircad09 CPU box from the make_reference dump (TS grid LAS) {b} -> RAS [[{n - b[0][1]}, {n - b[0][0]}], {b[1]}, {b[2]}]")
chk.append("ends: TotalSegmentator get_bbox_from_mask uses max+1 (exclusive); test_task prints [lo,hi) with hi = max+1+addon (exclusive); RAS flip lo' = n - hi, hi' = n - lo")
open("analysis/bbox_20261007.txt", "a", encoding="utf-8").write("\n".join(chk) + "\n")
print("\n".join(chk))
