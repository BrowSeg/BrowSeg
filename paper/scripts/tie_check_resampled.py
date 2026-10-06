"""tie_check_pair.py for tasks where nnU-Net resamples internally (liver_vessels, model 8): TS hands nnU-Net the crop at the
ORIGINAL spacing, nnU-Net resamples to the plans spacing, predicts, and resamples the logits back with
resampling_fn_probabilities before the argmax. So the tie must be looked at in the logits AFTER that back-resampling, on
the crop grid (which maps to the original grid by an integer shift, no grid-ratio formula needed).

This script calls nnU-Net's own resampling function (plans of the model) on the dumped logits, checks that its argmax
reproduces the dumped nnU-Net segmentation exactly, and prints the top-2 values at every voxel where map A and map B differ.

usage (map A may also be a differing-voxel list .json, then map B = "-"): python tie_check_resampled.py <map A> <map B> <dump dir> <model id>
  map: .npy (bench_refs) or .u8 (browser; reshaped to the shape of map A), canonical orientation (x,y,z)
  dump dir: tools/make_reference.py output ({model}_in.nii.gz, {model}_logits.npy, {model}_props.json, {model}_seg.nii.gz,
            final_*.nii.gz)
Run with the ts218 env.
"""
import sys, glob, json
from pathlib import Path
import numpy as np, nibabel as nib, torch

pa, pb, dump, model = sys.argv[1:5]
if pa.endswith(".json"):  # differing voxels only: {"shape": [x,y,z], "voxels": [[x,y,z,label A,label B], ...]} (map B = "-")
    import json as _json
    _d = _json.load(open(pa))
    A = np.zeros(_d["shape"], np.uint8); B = np.zeros(_d["shape"], np.uint8)
    for x_, y_, z_, la, lb in _d["voxels"]:
        A[x_, y_, z_] = la; B[x_, y_, z_] = lb
else:
    A = np.load(pa)
    B = np.load(pb) if pb.endswith(".npy") else np.fromfile(pb, np.uint8).reshape(A.shape)
assert A.shape == B.shape, (A.shape, B.shape)
diff = np.argwhere(A != B)
print(f"A={pa} | B={pb} | dump={dump} model {model}: {len(diff)} differing voxels (orig grid, canonical x,y,z)")

from nnunetv2.utilities.plans_handling.plans_handler import PlansManager
res = Path.home() / ".totalsegmentator" / "nnunet" / "results"
plans_file = sorted(res.glob(f"Dataset{int(model):03d}_*/*__nnUNetPlans__3d_fullres/plans.json"))[0]
pm = PlansManager(str(plans_file))
cm = pm.get_configuration("3d_fullres")
props = json.load(open(f"{dump}/{model}_props.json"))
assert pm.transpose_forward == [0, 1, 2], pm.transpose_forward
assert props["bbox_used_for_cropping"] == [[0, s] for s in props["shape_before_cropping"]], "nonzero crop not handled"

lg = np.load(f"{dump}/{model}_logits.npy")  # (C, z, y, x) on the plans grid
spacing = props["spacing"]
cur = cm.spacing if len(cm.spacing) == len(props["shape_after_cropping_and_before_resampling"]) else [spacing[0], *cm.spacing]
print(f"plans {plans_file.parent.name}: logits {lg.shape} {lg.dtype} spacing {cur} -> {props['shape_after_cropping_and_before_resampling']} spacing {spacing}")
print(f"resampling_fn_probabilities kwargs: {pm.plans['configurations']['3d_fullres'].get('resampling_fn_probabilities_kwargs')}")
r = cm.resampling_fn_probabilities(torch.from_numpy(lg), props["shape_after_cropping_and_before_resampling"], cur, spacing)
r = r.numpy() if isinstance(r, torch.Tensor) else np.asarray(r)
print(f"back-resampled logits {r.shape} {r.dtype}")

# nnU-Net array (z,y,x) = canonical (RAS) image of {model}_in transposed (NibabelIOWithReorient)
inn = nib.as_closest_canonical(nib.load(f"{dump}/{model}_in.nii.gz"))
seg = np.asarray(nib.as_closest_canonical(nib.load(f"{dump}/{model}_seg.nii.gz")).dataobj)
am = r.argmax(0).transpose(2, 1, 0)
nmis = int((am != seg).sum())
print(f"consistency: argmax(back-resampled) vs {model}_seg.nii.gz: {nmis} differing voxels" + ("" if nmis == 0 else "  <-- NOT REPRODUCED"))

fin = nib.as_closest_canonical(nib.load(glob.glob(f"{dump}/final_*.nii.gz")[0]))
inv = np.linalg.inv(inn.affine)
import os
probe_out = open(os.environ["PROBE_OUT"], "a") if os.environ.get("PROBE_OUT") else None  # M4: spec lines for the probes
crop_shape = props["shape_after_cropping_and_before_resampling"]
for v in diff:
    g = (inv @ (fin.affine @ np.array([*v, 1.0])))[:3]
    gi = np.round(g).astype(int)
    ok = np.allclose(g, gi, atol=1e-3)
    x, y, z = gi
    if probe_out:
        probe_out.write(f"crop {model} {z} {y} {x}\n")
        # network-grid voxels that can enter the back-resampling of this voxel (generous: +-1 around the scaled position)
        c = [int(np.floor(q * n / m)) for q, n, m in zip((z, y, x), lg.shape[1:], crop_shape)]
        for dz in (-1, 0, 1):
            for dy in (-1, 0, 1, 2):
                for dx in (-1, 0, 1, 2):
                    probe_out.write(f"net {model} {c[0] + dz} {c[1] + dy} {c[2] + dx}\n")
    val = r[:, z, y, x].astype(np.float64)
    o = np.argsort(-val, kind="stable")  # stable: ties list the first index first (= torch.argmax)
    top = np.asarray(r[o[0], z, y, x])
    ulp = float(np.spacing(top))
    gap = float(val[o[0]] - val[o[1]])
    print(f"  orig {tuple(int(c) for c in v)}: A={int(A[tuple(v)])} B={int(B[tuple(v)])} -> crop grid {tuple(int(c) for c in gi)}"
          f"{'' if ok else ' (NOT integer: ' + str(np.round(g, 3)) + ')'} seg={int(seg[x, y, z])} argmax={o[0]} "
          f"top={val[o[0]]:.6f} 2nd={o[1]}:{val[o[1]]:.6f} gap={gap:.6g} = {gap / ulp:.1f} ulp({r.dtype})")
