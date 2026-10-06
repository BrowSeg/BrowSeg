"""Smallest image size (in voxels, one axis) at which nnU-Net's sliding-window tile positions differ between step
size 0.5 (BrowSeg before the post-measurement fix) and 0.8 (TotalSegmentator 2.18 for the 6 mm model), patch 64.
Uses nnunetv2's own compute_steps_for_sliding_window (run in the ts218 env). Output: ../analysis/step_threshold_20261006.txt
"""
from importlib.metadata import version
from nnunetv2.inference.sliding_window_prediction import compute_steps_for_sliding_window as steps

first = None
for n in range(64, 400):
    a = steps((n,), (64,), 0.5)[0]
    b = steps((n,), (64,), 0.8)[0]
    if a != b and first is None:
        first = (n, a, b)
print(f"nnunetv2 {version('nnunetv2')}: patch 64, smallest axis size with different tile positions "
      f"(step 0.5 vs 0.8) = {first[0]} voxels; positions {first[1]} vs {first[2]}")
print("largest 6 mm grid axis over the 20 cases = 83 (review_stats_20261006.txt, case 19 z)")
