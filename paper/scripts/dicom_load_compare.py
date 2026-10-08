"""DICOM loading check: BrowSeg's DICOM reader vs TotalSegmentator 2.18.0's own conversion.

For each case, TotalSegmentator's path is reproduced exactly (totalsegmentator.dicom_io.dcm_to_nifti ->
nib.load -> get_fdata -> totalsegmentator.alignment.as_closest_canonical), and compared with the volume
written by build/Release/dump_dicom_volume.exe (parse_dicom + build_volume). Reports shape, voxel values
(max abs difference, number of differing voxels) and the affine (max abs difference).

Run with the ts218 env python:
  python dicom_load_compare.py <cases_root> <case,case,...> <out_txt> [dump_exe] [label]
cases_root/<case>/ holds the DICOM files (searched recursively).
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import nibabel as nib
from totalsegmentator.dicom_io import dcm_to_nifti
from totalsegmentator.alignment import as_closest_canonical
import totalsegmentator

root, cases, out_txt = Path(sys.argv[1]), sys.argv[2].split(","), Path(sys.argv[3])
exe = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(__file__).resolve().parents[3] / "build/Release/dump_dicom_volume.exe"
label = sys.argv[5] if len(sys.argv) > 5 else ""

lines = [f"DICOM loading check {label}: BrowSeg dump_dicom_volume vs TotalSegmentator {totalsegmentator.__version__ if hasattr(totalsegmentator, '__version__') else ''} dcm_to_nifti + as_closest_canonical",
         f"root={root}", "case\tshape_ts\tshape_bs\tvoxels\tdiff_voxels\tmax_abs_value_diff\tmax_abs_affine_diff\tidentical"]
n_ok = 0
for c in cases:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "dcm").mkdir()
        nii = td / "dcm" / "converted_dcm.nii.gz"
        dcm_to_nifti(root / c, nii, td)
        img = as_closest_canonical(nib.Nifti1Image(nib.load(nii).get_fdata(), nib.load(nii).affine))
        ts = np.asarray(img.dataobj, dtype=np.float64)
        aff_ts = img.affine
        r = subprocess.run([str(exe), str(root / c), str(td / "bs")], capture_output=True, text=True)
        if r.returncode != 0:
            lines.append(f"{c}\tERROR {r.stderr.strip()}")
            continue
        meta = json.loads((td / "bs.json").read_text())
        bs = np.fromfile(td / "bs.f32", dtype=np.float32).reshape(meta["shape"]).astype(np.float64)
        aff_bs = np.array(meta["affine"]).reshape(4, 4)
    same_shape = tuple(ts.shape) == tuple(bs.shape)
    if same_shape:
        d = np.abs(ts - bs)
        ndiff, vmax = int((d > 0).sum()), float(d.max())
    else:
        ndiff, vmax = -1, float("nan")
    amax = float(np.abs(aff_ts - aff_bs).max())
    ok = same_shape and ndiff == 0 and amax < 1e-4
    n_ok += ok
    lines.append(f"{c}\t{tuple(ts.shape)}\t{tuple(bs.shape)}\t{ts.size}\t{ndiff}\t{vmax:g}\t{amax:.3g}\t{'yes' if ok else 'NO'}")
    print(lines[-1], flush=True)
lines.append(f"identical (shape, all voxel values, affine within 1e-4 mm): {n_ok}/{len(cases)}")
out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(lines[-1])
