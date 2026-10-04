"""Which voxels of the original CT grid one voxel of the network grid (1.5 mm, `total`) is written back to.

usage: python grid_backmap.py <DICOM folder of the case> <rows> <cols> <slices> <x> <y> <z>
TotalSegmentator `total` resamples the whole CT to 1.5 mm (no crop) and changes the spacing of the label map back with
scipy.ndimage.zoom(order=0, mode="nearest"). This script builds the network grid from the DICOM spacing, puts one voxel
at (x, y, z) of the network grid and zooms it back the same way, then lists the original-grid voxels it lands on.
"""
import sys, glob
import numpy as np
import pydicom
from scipy import ndimage


def main():
    d = pydicom.dcmread(sorted(glob.glob(sys.argv[1] + "/*"))[0], stop_before_pixels=True)
    shape = tuple(int(v) for v in sys.argv[2:5])
    vox = tuple(int(v) for v in sys.argv[5:8])
    sp = [float(d.PixelSpacing[0]), float(d.PixelSpacing[1]), float(d.SliceThickness)]
    grid = tuple(int(round(s * p / 1.5)) for s, p in zip(shape, sp))
    a = np.zeros(grid, np.uint8)
    a[vox] = 1
    b = ndimage.zoom(a, [s / n for s, n in zip(shape, grid)], order=0, mode="nearest")
    print(f"spacing {sp}, original grid {shape}, network grid {grid}")
    print(f"network voxel {vox} -> original voxels {[tuple(int(x) for x in v) for v in np.argwhere(b == 1)]}")


if __name__ == "__main__":
    main()
