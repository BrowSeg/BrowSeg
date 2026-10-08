"""DICOM loading check on LiTS (2026-10-08): writes each selected Task03_Liver NIfTI as an uncompressed CT DICOM series
(SimpleITK, one file per slice, int16 with RescaleSlope 1 / Intercept 0, Explicit VR Little Endian), then compares
  BrowSeg  : build/Release/dump_dicom_volume.exe (parse_dicom + build_volume, closest-canonical RAS)
  TS 2.18  : totalsegmentator.dicom_io.dcm_to_nifti -> nib.load -> get_fdata -> as_closest_canonical
on the same DICOM series (shape, every voxel value, affine). Also reports the difference of each to the source NIfTI
(canonical), for information.
usage (ts218 env): python lits_to_dicom_20261008.py <cases_dir> <dicom_out_dir> <out_txt>
cases_dir/<lits_NNN>/liver_N.nii.gz as in data/bench_cases_lits; cases = the 30 of lits_selection_20261006.csv (liver3).
"""
import csv, json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import nibabel as nib
import SimpleITK as sitk
from totalsegmentator.dicom_io import dcm_to_nifti
from totalsegmentator.alignment import as_closest_canonical

HERE = Path(__file__).resolve()
EXE = HERE.parents[3] / "build" / "Release" / "dump_dicom_volume.exe"
SEL = HERE.parents[1] / "analysis" / "lits_selection_20261006.csv"
cases_dir, dcm_root, out_txt = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
cases = [r["bench_case"] for r in csv.DictReader(open(SEL, encoding="utf-8")) if "liver3" in r["purpose"]]


def write_series(nii, out):
    img = sitk.ReadImage(str(nii))
    img = sitk.Cast(sitk.Round(img), sitk.sitkInt16) if img.GetPixelID() != sitk.sitkInt16 else img
    out.mkdir(parents=True, exist_ok=True)
    w = sitk.ImageFileWriter(); w.KeepOriginalImageUIDOn()
    uid = "1.2.826.0.1.3680043.2.1125." + str(abs(hash(nii.name)) % 10**12)
    direction = img.GetDirection()
    for k in range(img.GetDepth()):
        s = img[:, :, k]
        pos = img.TransformIndexToPhysicalPoint((0, 0, k))
        tags = {"0008|0060": "CT", "0020|000e": uid, "0020|000d": uid + ".1", "0008|0016": "1.2.840.10008.5.1.4.1.1.2",
                "0020|0032": "\\".join(f"{v:.6f}" for v in pos),
                "0020|0037": "\\".join(f"{v:.6f}" for v in direction[0:7:3] + direction[1:8:3]),
                "0020|0013": str(k + 1), "0028|1052": "0", "0028|1053": "1", "0018|0050": f"{img.GetSpacing()[2]:.6f}"}
        for t, v in tags.items():
            s.SetMetaData(t, v)
        w.SetFileName(str(out / f"slice_{k:04d}.dcm")); w.Execute(s)
    return img.GetDepth()


lines = ["DICOM loading check on LiTS: NIfTI -> uncompressed DICOM series (SimpleITK " + sitk.Version.VersionString()
         + "), BrowSeg dump_dicom_volume vs TotalSegmentator dcm_to_nifti + as_closest_canonical on the same series",
         "case\tslices\tshape\tvoxels\tdiff_voxels_bs_vs_ts\tmax_abs_affine_bs_vs_ts\tdiff_voxels_ts_vs_nifti\tmax_abs_affine_ts_vs_nifti\tidentical"]
ok = 0
for c in cases:
    nii = next((cases_dir / c).glob("*.nii*"))
    d = dcm_root / c
    n = write_series(nii, d) if not d.exists() else len(list(d.glob("*.dcm")))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); (td / "dcm").mkdir()
        conv = td / "dcm" / "converted_dcm.nii.gz"
        dcm_to_nifti(d, conv, td)
        im = nib.load(conv)
        tsi = as_closest_canonical(nib.Nifti1Image(im.get_fdata(), im.affine))
        ts, aff_ts = np.asarray(tsi.dataobj, dtype=np.float64), tsi.affine
        r = subprocess.run([str(EXE), str(d), str(td / "bs")], capture_output=True, text=True)
        if r.returncode:
            lines.append(f"{c}\tERROR {r.stderr.strip()}"); continue
        meta = json.loads((td / "bs.json").read_text())
        bs = np.fromfile(td / "bs.f32", dtype=np.float32).reshape(meta["shape"]).astype(np.float64)
        aff_bs = np.array(meta["affine"]).reshape(4, 4)
    src = nib.as_closest_canonical(nib.load(nii))
    sv = np.asarray(src.dataobj, dtype=np.float64)
    same = ts.shape == bs.shape
    nd = int((ts != bs).sum()) if same else -1
    ab = float(np.abs(aff_ts - aff_bs).max())
    nd_src = int((ts != sv).sum()) if ts.shape == sv.shape else -1
    ab_src = float(np.abs(aff_ts - src.affine).max())
    good = same and nd == 0 and ab < 1e-4
    ok += good
    lines.append(f"{c}\t{n}\t{ts.shape}\t{ts.size}\t{nd}\t{ab:.3g}\t{nd_src}\t{ab_src:.3g}\t{'yes' if good else 'NO'}")
    print(lines[-1], flush=True)
lines.append(f"identical BrowSeg vs TotalSegmentator (shape, all voxel values, affine within 1e-4 mm): {ok}/{len(cases)}")
out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(lines[-1])
