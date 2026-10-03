"""For every voxel where a BrowSeg label map differs from the Python reference, print the Python fp16 logits of
the two best classes at the corresponding network-grid voxel (is it a tie / 1-ulp gap?).

usage: python tie_check.py <case> <task> <roi|-> <browser tag> <ref218 dump dir> <model id>
  needs: data/bench_refs/ts218_cpu/<case>__<task>_<roi>.npy, paper_benchmarks/data/browser/<tag>/<case>__...u8,
         <ref218 dump dir>/{final_*.nii.gz, <model>_in.nii.gz, <model>_logits.npy, <model>_seg.nii.gz} (tools/make_reference.py)
Run with the ts218 env (nibabel).
"""
import sys, glob
from pathlib import Path
import numpy as np, nibabel as nib

case, task, roi, tag, dump, model = sys.argv[1:7]
ROOT = Path(__file__).resolve().parents[3]
key = f"{case}__{task}_{'all' if roi == '-' else roi}"
ref = np.load(ROOT / "data/bench_refs/ts218_cpu" / f"{key}.npy")
b = np.fromfile(ROOT / "paper_jiim/paper_benchmarks/data/browser" / tag / f"{key}.u8", np.uint8).reshape(ref.shape)
diff = np.argwhere(ref != b)
print(f"{key} [{tag}]: {len(diff)} differing voxels (orig grid, canonical x,y,z)")

fin = nib.as_closest_canonical(nib.load(glob.glob(f"{dump}/final_*.nii.gz")[0]))
inn = nib.as_closest_canonical(nib.load(f"{dump}/{model}_in.nii.gz"))
seg = np.asarray(nib.as_closest_canonical(nib.load(f"{dump}/{model}_seg.nii.gz")).dataobj)
lg = np.load(f"{dump}/{model}_logits.npy")  # (C, z, y, x) fp16
assert lg.shape[1:] == seg.shape[::-1], (lg.shape, seg.shape)
inv = np.linalg.inv(inn.affine)
# TS writes the labels back with scipy.ndimage.zoom(order=0, grid_mode=False): crop-grid index c maps to the network-grid
# coordinate c * (n_in - 1) / (n_crop - 1) (end-aligned), whereas the affines are origin-aligned (c * zoom). Recover c from
# the affines and apply the end-aligned factor. n_crop = size of the crop bbox (tools/make_reference.py crop_bbox.json).
import json
bbox = json.load(open(f"{dump}/crop_bbox.json"))["bbox"]
n_crop = np.array([hi - lo for lo, hi in bbox], float)
n_in = np.array(inn.shape, float)
zoom_aff = np.array(fin.header.get_zooms()[:3]) / np.array(inn.header.get_zooms()[:3])
assert np.allclose(np.round(n_crop * zoom_aff), n_in), (n_crop, zoom_aff, n_in)
seen = set()
for v in diff:
    w = fin.affine @ np.array([*v, 1.0])
    g_aff = (inv @ w)[:3]
    g = g_aff / zoom_aff * (n_in - 1) / (n_crop - 1)
    gi = tuple(int(round(c)) for c in g)
    print(f"  orig {tuple(int(c) for c in v)}: python={int(ref[tuple(v)])} browseg={int(b[tuple(v)])} -> network grid {np.round(g, 2)} (affine only: {np.round(g_aff, 2)})")
    if gi in seen:
        continue
    seen.add(gi)
    # the nearest-neighbour write-back may pick either neighbour: report the 2x2x2 neighbourhood
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                x, y, z = int(np.floor(g[0])) + dx, int(np.floor(g[1])) + dy, int(np.floor(g[2])) + dz
                if not (0 <= x < seg.shape[0] and 0 <= y < seg.shape[1] and 0 <= z < seg.shape[2]):
                    continue
                val = lg[:, z, y, x].astype(np.float32)
                o = np.argsort(-val)
                ulp = float(np.spacing(np.float16(val[o[0]])))
                gap = float(val[o[0]] - val[o[1]])
                print(f"    net ({x},{y},{z}) python argmax={o[0]} (seg {int(seg[x, y, z])}) top={val[o[0]]:.4f} "
                      f"2nd={o[1]}:{val[o[1]]:.4f} gap={gap:.4f} = {gap / ulp:.0f} fp16-ulp")
