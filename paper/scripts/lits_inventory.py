"""Header-only inventory of the local MSD Task03_Liver (LiTS) volumes, to choose extra liver cases and long-range
(chest-abdomen-pelvis) cases. Flags volumes whose shape and spacing equal one of the 20 3D-IRCADb-01 cases already used
(LiTS includes 20 IRCAD volumes). Output: ../analysis/lits_inventory_20261006.csv"""
import csv, glob, json, os
import nibabel as nib
ROOT = "C:/Users/user/Desktop/Deep3DLiver/Task03_Liver/Task03_Liver"
B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/browser/desk_chrome_webgpu_final")
ircad = {}
for f in glob.glob(f"{B}/ircad*__total_liver.json"):
    j = json.load(open(f)); ircad[os.path.basename(f)[:7]] = (tuple(j["load"]["shape"]), tuple(round(z, 3) for z in j["load"]["zooms"]))
rows = []
for split in ("imagesTr", "imagesTs"):
    for f in sorted(glob.glob(f"{ROOT}/{split}/*.nii.gz")):
        if os.path.basename(f).startswith("._"):
            continue
        h = nib.load(f).header
        sh = tuple(int(x) for x in h.get_data_shape()); zo = tuple(round(float(x), 3) for x in h.get_zooms()[:3])
        # LiTS stores the 20 IRCAD volumes (liver_28..47) with a spacing of 1.0 mm on every axis, so match on the shape
        # (same slice count) when the spacing is that placeholder, otherwise on shape and spacing
        match = [c for c, (s2, z2) in ircad.items() if sorted(s2) == sorted(sh) and (sorted(z2) == sorted(zo) or zo == (1.0, 1.0, 1.0))]
        rows.append(dict(case=os.path.basename(f)[:-7], split=split[-2:], nx=sh[0], ny=sh[1], nz=sh[2],
                         dx=zo[0], dy=zo[1], dz=zo[2], z_mm=round(sh[2] * zo[2]), voxels_M=round(sh[0] * sh[1] * sh[2] / 1e6, 1),
                         ircad_match=";".join(match)))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../analysis/lits_inventory_20261006.csv")
with open(out, "w", newline="", encoding="utf-8") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "volumes;", sum(1 for r in rows if r["ircad_match"]), "match an IRCAD case")
