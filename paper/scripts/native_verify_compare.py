"""Compare the native label maps written by native_verify.sh with the Python CPU references and with the browser
CPU-path results (desk_chrome_wasm_20 / desk_chrome_webgpu_total_20), voxel by voxel.

usage: python native_verify_compare.py <out dir>     (ircad env: nibabel, numpy)
"""
import sys, glob, os
from pathlib import Path
import numpy as np, nibabel as nib

ROOT = Path(__file__).resolve().parents[3]
out = Path(sys.argv[1])
B = ROOT / "paper_jiim/paper_benchmarks/data/browser"
bad = 0
for f in sorted(out.glob("*_labels.nii")):
    key = f.name[:-len("_labels.nii")]
    ref = ROOT / "data/bench_refs/ts218_cpu" / f"{key}.npy"
    nat = np.asarray(nib.as_closest_canonical(nib.load(str(f))).dataobj).astype(np.uint8)
    r = np.load(ref)
    assert nat.shape == r.shape, (key, nat.shape, r.shape)
    d_py = int((nat != r).sum())
    tag = "desk_chrome_webgpu_total_20" if key.endswith("total_all") else "desk_chrome_wasm_20"
    u8 = B / tag / f"{key}.u8"
    d_br = int((nat.ravel() != np.fromfile(u8, np.uint8)).sum()) if u8.exists() else None
    flag = "" if (d_br == 0 or (d_br is None)) else "  <-- differs from the measured browser run"
    if flag:
        bad += 1
    print(f"{key:40s} vs python {d_py:5d}   vs browser({tag}) {d_br}{flag}")
print("RESULT:", "identical to the measured browser runs" if not bad else f"{bad} label maps differ")
