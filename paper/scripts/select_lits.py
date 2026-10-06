"""Deterministic selection of 30 LiTS (MSD Task03_Liver) cases for the liver-task exactness check (2026-10-06,
author: "IRCAD に加えて LiTS から基準を決めて選ぶ").
Criteria: exclude the 20 IRCAD volumes (liver_28..47) and liver_191 (implausible spacing); split the remaining 180 by
slice spacing into thin (<= 1.0 mm), medium (1.0-2.5 mm] and thick (> 2.5 mm); in each group sort by slice count
and take 10 evenly spaced cases (first and last included), so small to large scans are covered. No randomness.
Also lists the chest-abdomen-pelvis cases for the 117-structure run check (liver_163, liver_121, liver_22).
Creates hard links (no extra disk space) under TSC++Project/data/bench_cases_lits/<case>/<case>.nii.gz.
Output: ../analysis/lits_selection_20261006.csv"""
import csv, os
SRC = "C:/Users/user/Desktop/Deep3DLiver/Task03_Liver/Task03_Liver"
HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.abspath(os.path.join(HERE, "../../../data/bench_cases_lits"))
rows = [r for r in csv.DictReader(open(os.path.join(HERE, "../analysis/lits_inventory_20261006.csv"), encoding="utf-8"))
        if not r["ircad_match"] and r["case"] != "liver_191"]
groups = {"thin": lambda d: d <= 1.0, "medium": lambda d: 1.0 < d <= 2.5, "thick": lambda d: d > 2.5}
sel = []
for g, f in groups.items():
    s = sorted((r for r in rows if f(float(r["dz"]))), key=lambda r: (int(r["nz"]), r["case"]))
    idx = sorted({round(i * (len(s) - 1) / 9) for i in range(10)})
    assert len(idx) == 10
    for i in idx:
        sel.append(dict(s[i], group=g, purpose="liver3"))
for c in ("liver_163", "liver_121", "liver_22"):
    r = next(r for r in rows if r["case"] == c)
    if not any(x["case"] == c for x in sel):
        sel.append(dict(r, group="cap", purpose="total117"))
    else:
        next(x for x in sel if x["case"] == c)["purpose"] = "liver3+total117"
os.makedirs(DST, exist_ok=True)
for r in sel:
    src = f"{SRC}/images{r['split']}/{r['case']}.nii.gz"
    d = os.path.join(DST, "lits_" + r["case"].split("_")[1].zfill(3)); os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, r["case"] + ".nii.gz")
    if not os.path.exists(dst):
        os.link(src, dst)
    r["bench_case"] = os.path.basename(d)
out = os.path.join(HERE, "../analysis/lits_selection_20261006.csv")
with open(out, "w", newline="", encoding="utf-8") as fo:
    w = csv.DictWriter(fo, fieldnames=list(sel[0])); w.writeheader(); w.writerows(sel)
for r in sel:
    print(r["bench_case"], r["group"], r["purpose"], r["split"], r["nz"], "sl", r["dz"], "mm", r["z_mm"], "mm")
