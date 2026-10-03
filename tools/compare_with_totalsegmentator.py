"""Check a BrowSeg label map against your own TotalSegmentator run, voxel by voxel.

BrowSeg (in the browser) -> "export labels (.nii.gz)"        -> browseg_labels.nii.gz
TotalSegmentator (Python) -> TotalSegmentator -i <ct> -o ts.nii.gz --ml --task <task> [--roi_subset liver]
                                                                 -> ts.nii.gz
usage: python compare_with_totalsegmentator.py browseg_labels.nii.gz ts.nii.gz

Both files are reoriented to the same canonical (RAS) axes before comparison, so the orientation of the
NIfTI headers does not matter. Prints the number of differing voxels, the labels involved and the Dice
coefficient per label. Needs numpy and nibabel (pip install numpy nibabel).

Note: run TotalSegmentator on the CPU (--device cpu) for an exact comparison. On a GPU, TotalSegmentator's
own output varies from run to run by a small number of voxels (see the BrowSeg paper).
"""
import sys
import numpy as np
import nibabel as nib


def load_canonical(path):
    img = nib.as_closest_canonical(nib.load(path))
    return np.asarray(img.dataobj).astype(np.uint8), img.header.get_zooms()


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    a, za = load_canonical(sys.argv[1])
    b, zb = load_canonical(sys.argv[2])
    if a.shape != b.shape:
        sys.exit(f"shapes differ: {a.shape} vs {b.shape} (same CT? same task?)")
    diff = a != b
    n = int(diff.sum())
    print(f"voxels: {a.size}, differing: {n} ({100.0 * n / a.size:.6f} %)")
    labels = sorted(set(np.unique(a)) | set(np.unique(b)))
    print(f"{'label':>6} {'BrowSeg':>10} {'TotalSeg':>10} {'Dice':>9}")
    for l in labels:
        if l == 0:
            continue
        x, y = a == l, b == l
        s = int(x.sum()) + int(y.sum())
        dice = 2.0 * int((x & y).sum()) / s if s else 1.0
        print(f"{l:>6} {int(x.sum()):>10} {int(y.sum()):>10} {dice:>9.6f}")
    if n:
        inv = sorted(set(np.unique(a[diff])) | set(np.unique(b[diff])))
        print("labels involved in the differences:", inv)
    else:
        print("IDENTICAL")


if __name__ == "__main__":
    main()
