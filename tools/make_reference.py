"""
Run the original TotalSegmentator (roi_subset=['liver']) and dump every
intermediate stage so the C++ port can be verified stage by stage.

usage: python make_reference.py <dicom_dir> <out_dir> [cpu|gpu] [task] [roi,roi...|-]
       (default task "total" with roi_subset "liver"; roi "-" = no roi_subset)

Dumped files (per nnU-Net model call, prefix = task id, e.g. 298_ / 291_):
  00_converted.nii.gz      DICOM -> NIfTI (dicom2nifti) result
  crop_bbox.json           bbox used by TS crop_to_mask (orig voxel grid)
  {tid}_in.nii.gz          TS-resampled int32 input handed to nnU-Net
  {tid}_props.json         nnU-Net preprocessing properties (nonzero bbox ...)
  {tid}_pre.npy            normalised float32 network input (1,z,y,x)
  {tid}_logits.npy         fp16 sliding-window logits (C,z,y,x)
  {tid}_seg.nii.gz         nnU-Net argmax seg (TS-resampled grid)
  final_liver.nii.gz       final TS output (orig grid, label 5 = liver)
"""
import sys, os, json, shutil, time
from pathlib import Path
import numpy as np
import torch

_r = str(Path.home() / ".totalsegmentator" / "nnunet" / "results")
for _k in ("nnUNet_raw", "nnUNet_preprocessed", "nnUNet_results"):
    os.environ[_k] = _r

def main():
    dicom_dir = Path(sys.argv[1])
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    device = sys.argv[3] if len(sys.argv) > 3 else "cpu"
    task = sys.argv[4] if len(sys.argv) > 4 else "total"
    roi = sys.argv[5] if len(sys.argv) > 5 else ("liver" if task == "total" else "-")
    roi_subset = None if roi == "-" else roi.split(",")
    final_name = "final_liver.nii.gz" if (task == "total" and roi_subset == ["liver"]) else f"final_{task}.nii.gz"

    import totalsegmentator.nnunet as tsn
    from totalsegmentator.python_api import totalsegmentator
    from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
    from nnunetv2.preprocessing.preprocessors.default_preprocessor import DefaultPreprocessor

    global state
    state = {"tid": None}

    # 1) DICOM -> NIfTI
    _orig_dcm = tsn.dcm_to_nifti
    def dcm_to_nifti(inp, outp, *a, **k):
        r = _orig_dcm(inp, outp, *a, **k)
        shutil.copy(outp, out / "00_converted.nii.gz")
        return r
    tsn.dcm_to_nifti = dcm_to_nifti

    # 2) TS crop
    _orig_crop = tsn.crop_to_mask
    def crop_to_mask(img, mask, addon=[0, 0, 0], dtype=None, verbose=False):
        r, bbox = _orig_crop(img, mask, addon=addon, dtype=dtype, verbose=verbose)
        json.dump({"bbox": [[int(a), int(b)] for a, b in bbox], "addon": [float(x) for x in addon]},
                  open(out / "crop_bbox.json", "w"))
        import nibabel as nib
        nib.save(nib.Nifti1Image(np.asarray(mask.dataobj).astype(np.uint8), mask.affine), out / "crop_mask.nii.gz")
        return r, bbox
    tsn.crop_to_mask = crop_to_mask

    # 3) nnU-Net call: copy input / output
    _orig_pred = tsn.nnUNetv2_predict
    def nnUNetv2_predict(dir_in, dir_out, task_id, *a, **k):
        state["tid"] = task_id
        shutil.copy(Path(dir_in) / "s01_0000.nii.gz", out / f"{task_id}_in.nii.gz")
        json.dump({"task_id": task_id, "args": [str(x) for x in a], "kwargs": {kk: str(v) for kk, v in k.items()}},
                  open(out / f"{task_id}_call.json", "w"), indent=1)
        t = time.time()
        r = _orig_pred(dir_in, dir_out, task_id, *a, **k)
        print(f"[ref] task {task_id} nnU-Net took {time.time()-t:.1f}s")
        shutil.copy(Path(dir_out) / "s01.nii.gz", out / f"{task_id}_seg.nii.gz")
        return r
    tsn.nnUNetv2_predict = nnUNetv2_predict

    # 4) force sequential (no worker processes) so patches below apply
    def predict_from_files(self, src, dst, save_probabilities=False, overwrite=True, num_processes_preprocessing=1,
                           num_processes_segmentation_export=1, folder_with_segs_from_prev_stage=None,
                           num_parts=1, part_id=0, **_ignored):
        return self.predict_from_files_sequential(src, dst, save_probabilities, overwrite, folder_with_segs_from_prev_stage)
    nnUNetPredictor.predict_from_files = predict_from_files

    _orig_run_case = DefaultPreprocessor.run_case
    def run_case(self, *a, **k):
        data, seg, props = _orig_run_case(self, *a, **k)
        tid = state["tid"]
        p = {kk: (np.asarray(v).tolist() if isinstance(v, (np.ndarray, tuple, list)) else str(v))
             for kk, v in props.items() if kk != "nibabel_stuff"}
        json.dump(p, open(out / f"{tid}_props.json", "w"), indent=1)
        return data, seg, props
    DefaultPreprocessor.run_case = run_case

    _orig_logits = nnUNetPredictor.predict_logits_from_preprocessed_data
    def predict_logits(self, data):
        tid = state["tid"]
        np.save(out / f"{tid}_pre.npy", data.numpy())
        r = _orig_logits(self, data)
        np.save(out / f"{tid}_logits.npy", r.numpy())
        return r
    nnUNetPredictor.predict_logits_from_preprocessed_data = predict_logits

    t0 = time.time()
    # TS >= 2.15 has resampling_order (default 1 since 2.16); test_task reads it from resampling_order.txt
    import inspect
    if "resampling_order" in inspect.signature(totalsegmentator).parameters:
        (out / "resampling_order.txt").write_text(str(inspect.signature(totalsegmentator).parameters["resampling_order"].default))
    import importlib.metadata
    (out / "ts_version.txt").write_text(importlib.metadata.version("TotalSegmentator"))
    seg = totalsegmentator(dicom_dir, out / final_name, ml=True, task=task, roi_subset=roi_subset, device=device,
                           quiet=False, verbose=True)
    print(f"[ref] total {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
