"""Stress test inputs (2026-10-08): how many slices BrowSeg can load and segment. Takes the largest LiTS case
(liver_167, 512 x 512 x 1026, int16) and resamples it along z to N slices with the same z extent (linear interpolation,
slice spacing scaled by 1026 / N), so only the number of slices (memory) changes, not the anatomy.
Output: <out>/stress_<N>/stress_<N>.nii.gz (int16, gzip level 1). Not used for the agreement numbers.
usage (ts218 env): python make_stress_cases_20261008.py <liver_167.nii.gz> <out dir> N [N ...]
"""
import gzip, sys
from pathlib import Path
import numpy as np
import nibabel as nib
from scipy import ndimage

src, out = Path(sys.argv[1]), Path(sys.argv[2])
img = nib.load(src)
data = np.asarray(img.dataobj)
nz = data.shape[2]
for n in map(int, sys.argv[3:]):
    z = np.linspace(0, nz - 1, n)
    vol = np.empty(data.shape[:2] + (n,), np.int16)
    for k, zk in enumerate(z):   # slice by slice: memory stays at one output volume
        lo = int(np.floor(zk)); hi = min(lo + 1, nz - 1); w = zk - lo
        vol[:, :, k] = np.round((1 - w) * data[:, :, lo] + w * data[:, :, hi]).astype(np.int16)
    aff = img.affine.copy()
    aff[:3, 2] *= (nz - 1) / (n - 1)
    hdr = img.header.copy(); hdr.set_data_dtype(np.int16)
    new = nib.Nifti1Image(vol, aff, hdr); new.set_sform(aff, code=1); new.set_qform(aff, code=1)
    d = out / f"stress_{n}"; d.mkdir(parents=True, exist_ok=True)
    raw = d / f"stress_{n}.nii"
    nib.save(new, raw)
    with open(raw, "rb") as fi, gzip.open(str(raw) + ".gz", "wb", compresslevel=1) as fo:
        while b := fi.read(1 << 24):
            fo.write(b)
    raw.unlink()
    print(n, vol.shape, f"spacing z {abs(aff[2, 2]):.4f}", f"{vol.nbytes / 2**20:.0f} MiB int16", flush=True)
