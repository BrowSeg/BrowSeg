"""Voxel-by-voxel comparison of two native_verify.sh output directories (e.g. the build before and after a code
change). usage: python native_before_after.py <dir A> <dir B>
"""
import sys
from pathlib import Path
import numpy as np, nibabel as nib

a, b = Path(sys.argv[1]), Path(sys.argv[2])
n = bad = 0
for fa in sorted(a.glob("*_labels.nii")):
    fb = b / fa.name
    if not fb.exists():
        print(f"{fa.name}: missing in {b}"); bad += 1; continue
    x = np.asarray(nib.load(str(fa)).dataobj); y = np.asarray(nib.load(str(fb)).dataobj)
    d = int((x != y).sum()) if x.shape == y.shape else -1
    n += 1
    if d:
        bad += 1; print(f"{fa.name}: {d} voxels differ")
print(f"compared {n} label maps: {'all identical' if not bad else f'{bad} differ'}")
