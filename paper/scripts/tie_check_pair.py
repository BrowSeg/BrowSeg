"""Same as tie_check.py, but for any two label maps (.npy or .u8) of the same case, e.g. the desktop and the laptop
Python references (M3) or a BrowSeg output and a reference. For every differing voxel, print the fp16 logits of the two
best classes at the corresponding network-grid voxel, read from the dump of ONE run (tools/make_reference.py).

usage (map A may also be a differing-voxel list .json, then map B = "-"): python tie_check_pair.py <map A> <map B> <dump dir> <model id>
  map: .npy (bench_refs) or .u8 (browser; reshaped to the shape of map A)
  dump dir: {final_*.nii.gz, <model>_in.nii.gz, <model>_logits.npy, <model>_seg.nii.gz, crop_bbox.json}
Run with the ts218 env (nibabel).
"""
import sys, glob
from pathlib import Path
import numpy as np, nibabel as nib

pa, pb, dump, model = sys.argv[1:5]
if pa.endswith(".json"):  # differing voxels only: {"shape": [x,y,z], "voxels": [[x,y,z,label A,label B], ...]} (map B = "-")
    import json as _json
    _d = _json.load(open(pa))
    ref = np.zeros(_d["shape"], np.uint8); b = np.zeros(_d["shape"], np.uint8)
    for x_, y_, z_, la, lb in _d["voxels"]:
        ref[x_, y_, z_] = la; b[x_, y_, z_] = lb
else:
    ref = np.load(pa)
    b = np.load(pb) if pb.endswith(".npy") else np.fromfile(pb, np.uint8).reshape(ref.shape)
assert ref.shape == b.shape, (ref.shape, b.shape)
diff = np.argwhere(ref != b)
print(f"A={pa} | B={pb} | dump={dump} model {model}: {len(diff)} differing voxels (orig grid, canonical x,y,z)")

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
import os
probe_out = open(os.environ["PROBE_OUT"], "a") if os.environ.get("PROBE_OUT") else None  # M4: spec lines for the probes
seen = set()
for v in diff:
    w = fin.affine @ np.array([*v, 1.0])
    g_aff = (inv @ w)[:3]
    g = g_aff / zoom_aff * (n_in - 1) / (n_crop - 1)
    gi = tuple(int(round(c)) for c in g)
    print(f"  orig {tuple(int(c) for c in v)}: A={int(ref[tuple(v)])} B={int(b[tuple(v)])} -> network grid {np.round(g, 2)} (affine only: {np.round(g_aff, 2)})")
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
                if probe_out: probe_out.write(f"net {model} {z} {y} {x}\n")
                val = lg[:, z, y, x].astype(np.float32)
                o = np.argsort(-val, kind="stable")  # stable: ties list the first index first (= torch.argmax)
                ulp = float(np.spacing(np.float16(val[o[0]])))
                gap = float(val[o[0]] - val[o[1]])
                print(f"    net ({x},{y},{z}) dump argmax={o[0]} (seg {int(seg[x, y, z])}) top={val[o[0]]:.4f} "
                      f"2nd={o[1]}:{val[o[1]]:.4f} gap={gap:.4f} = {gap / ulp:.0f} fp16-ulp")
