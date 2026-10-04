"""Voxels where a BrowSeg label map (.u8, original CT grid) differs from the Python reference (.npy).

usage: python diff_voxels.py <label map .u8> <reference .npy> [max listed]
Prints the FNV-1a hash of the .u8 (the hash the benchmark page records), the number of differing voxels, and for up
to <max listed> (default 20) of them the (x, y, z) index in the .npy array order and the reference / BrowSeg labels.
"""
import sys
import numpy as np


def fnv1a(b):
    h = 0x811c9dc5
    for x in b:
        h = ((h ^ x) * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def main():
    u8, npy = sys.argv[1], sys.argv[2]
    nmax = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    ref = np.load(npy)
    lab = np.fromfile(u8, dtype=np.uint8)
    print(f"label map: {u8}")
    print(f"reference: {npy} shape {ref.shape}")
    print(f"fnv1a: {fnv1a(lab.tobytes())}")
    d = np.nonzero(ref.ravel() != lab)[0]
    print(f"differing voxels: {d.size} of {lab.size}")
    for i in d[:nmax]:
        print(f"  index {tuple(int(v) for v in np.unravel_index(i, ref.shape))}: reference {int(ref.ravel()[i])}, BrowSeg {int(lab[i])}")


if __name__ == "__main__":
    main()
