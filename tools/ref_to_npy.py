"""Convert reference NIfTIs to canonical (RAS) npy arrays for the C++ tests.

  ct_can.npy / ct_can.json      DICOM->NIfTI result, canonical
  <tid>_in.npy, <tid>_seg.npy   nnU-Net input / output (TS already works in RAS there)
  final_*_can.npy, crop_mask_can.npy   original-grid results, canonical
"""
import sys, json, glob
from pathlib import Path
import numpy as np, nibabel as nib

d = Path(sys.argv[1])
ct = nib.load(d / "00_converted.nii.gz")
print("converted dtype", ct.get_data_dtype(), "shape", ct.shape, "zooms", ct.header.get_zooms())
can = nib.as_closest_canonical(ct)
np.save(d / "ct_can.npy", np.ascontiguousarray(np.asarray(can.dataobj)))
json.dump({"affine": can.affine.tolist(), "zooms": [float(z) for z in can.header.get_zooms()],
           "orig_affine": ct.affine.tolist(),
           "ornt": nib.orientations.io_orientation(ct.affine).tolist()}, open(d / "ct_can.json", "w"), indent=1)
for f in sorted(glob.glob(str(d / "*_in.nii.gz")) + glob.glob(str(d / "*_seg.nii.gz"))):
    f = Path(f)
    im = nib.load(f)
    assert nib.aff2axcodes(im.affine) == ("R", "A", "S"), (f, nib.aff2axcodes(im.affine))
    np.save(str(f).replace(".nii.gz", ".npy"), np.ascontiguousarray(np.asarray(im.dataobj)))
    print(f.name, im.shape, im.get_data_dtype(), im.header.get_zooms())
for f in sorted(glob.glob(str(d / "final_*.nii.gz")) + glob.glob(str(d / "crop_mask.nii.gz"))):
    f = Path(f)
    im = nib.as_closest_canonical(nib.load(f))
    np.save(str(f).replace(".nii.gz", "_can.npy"), np.ascontiguousarray(np.asarray(im.dataobj).astype(np.uint8)))
    print(f.name, "labels:", len(np.unique(np.asarray(im.dataobj))) - 1)
