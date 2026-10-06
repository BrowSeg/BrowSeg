"""M4: compare the PROBE lines of BrowSeg (tests/probe_wasm_node.mjs, web/dist-probe) and Python (tools/probe_python.py)
at the same network-grid voxels, stage by stage:
  (a) every tile's fp32 network output y (before the Gaussian), and the Gaussian weight g
  (b) the fp16 accumulator after each tile, and the fp16 count
  (c) the final fp16 logits after the division (and the back-resampled crop-grid logits, if probed)
For each voxel it prints the two decisive classes (top 2 of either side's final), the first stage at which the two
implementations differ, and the largest fp32 difference of y in units of the fp32 ulp.

usage: python compare_probes.py <browseg log> <python probe.log> [--voxel z,y,x ...]
"""
import re, sys
from collections import defaultdict
import numpy as np


def parse(path):
    acc = defaultdict(list)   # net -> [(tile, g, n_before, n_after, {c: (y, a_before, a_after)})]
    final, crop = {}, {}
    for line in open(path, encoding="utf-8", errors="replace"):
        if not line.startswith("PROBE "):
            continue
        kind = line.split()[1]
        if kind == "acc":
            net = tuple(int(v) for v in re.search(r"net=\((\d+),(\d+),(\d+)\)", line).groups())
            tile = int(re.search(r"tile=(\d+)", line).group(1))
            g = float(re.search(r" g=(\S+)", line).group(1))
            nb, na = (float(v) for v in re.search(r" n=(\S+)->(\S+)", line).groups())
            cl = {int(c): (float(y), float(b), float(a)) for c, y, b, a in
                  re.findall(r"c(\d+):y=(\S+?),a=(\S+?)->(\S+)", line)}
            acc[net].append((tile, g, nb, na, cl))
        elif kind == "final":
            net = tuple(int(v) for v in re.search(r"net=\((\d+),(\d+),(\d+)\)", line).groups())
            n = float(re.search(r" n=(\S+)", line).group(1))
            final[net] = (n, {int(c): float(v) for c, v in re.findall(r" c(\d+)=(\S+)", line)})
        elif kind == "crop":
            q = tuple(int(v) for v in re.search(r"crop=\((\d+),(\d+),(\d+)\)", line).groups())
            crop[q] = {int(c): float(v) for c, v in re.findall(r" c(\d+)=(\S+)", line)}
    return acc, final, crop


def ulp32(x):
    return float(np.spacing(np.float32(abs(x)) if x != 0 else np.float32(1e-38)))


def h16(x):
    return float(np.spacing(np.float16(abs(x))))


def top2(d):
    o = sorted(d, key=lambda c: (-d[c], c))
    return o[0], o[1]


def main():
    b_acc, b_fin, b_crop = parse(sys.argv[1])
    p_acc, p_fin, p_crop = parse(sys.argv[2])
    only = None
    if "--voxel" in sys.argv:
        only = {tuple(int(v) for v in s.split(",")) for s in sys.argv[sys.argv.index("--voxel") + 1:]}
    nets = sorted(set(b_fin) & set(p_fin))
    print(f"voxels: browseg {len(b_fin)}, python {len(p_fin)}, common {len(nets)}")
    for net in nets:
        if only and net not in only:
            continue
        bn, bf = b_fin[net]
        pn, pf = p_fin[net]
        cls = sorted(set(top2(bf)) | set(top2(pf)))
        bt, pt = top2(bf), top2(pf)
        flip = bt[0] != pt[0] or (bf[bt[0]] == bf[bt[1]]) != (pf[pt[0]] == pf[pt[1]])
        print(f"\nnet (z,y,x)={net}  final argmax: browseg {bt[0]}  python {pt[0]}" + ("   <-- decision differs" if bt[0] != pt[0] else ""))
        for c in cls:
            print(f"  class {c}: final browseg {bf[c]:.9g}  python {pf[c]:.9g}  diff {bf[c] - pf[c]:+.3g} "
                  f"({(bf[c] - pf[c]) / h16(pf[c]) if pf[c] else 0:+.0f} fp16-ulp)")
        print(f"  count n: browseg {bn:.9g} python {pn:.9g}" + ("" if bn == pn else "  <-- differs"))
        bt_ = {t[0]: t for t in b_acc[net]}
        pt_ = {t[0]: t for t in p_acc[net]}
        tiles = sorted(set(bt_) | set(pt_))
        if set(bt_) != set(pt_):
            print(f"  TILES DIFFER: browseg {sorted(bt_)} python {sorted(pt_)}")
        first_acc = None
        for t in tiles:
            if t not in bt_ or t not in pt_:
                continue
            _, bg, bnb, bna, bcl = bt_[t]
            _, pg, pnb, pna, pcl = pt_[t]
            parts = []
            if bg != pg:
                parts.append(f"g {bg:.9g} vs {pg:.9g}")
            for c in cls:
                by, bb, ba = bcl[c]
                py, pb, pa = pcl[c]
                dy = by - py
                same = np.float16(ba) == np.float16(pa)  # accumulators hold fp16 values (logs print 9 digits: JS vs C rounding)
                parts.append(f"c{c} y {by:.9g}/{py:.9g} (d={dy:+.3g}, {dy / ulp32(py):+.1f} fp32-ulp) acc {ba:.9g}/{pa:.9g}"
                             + ("" if same else " *"))
                if not same and first_acc is None:
                    first_acc = t
            print(f"  tile {t:3d}: " + " | ".join(parts))
        print(f"  first tile where the fp16 accumulator of a decisive class differs: {first_acc}")
    for q in sorted(set(b_crop) & set(p_crop)):
        b, p = b_crop[q], p_crop[q]
        bt, pt = top2(b), top2(p)
        print(f"\ncrop (z,y,x)={q}: argmax browseg {bt[0]} python {pt[0]}")
        for c in sorted(set(bt) | set(pt)):
            print(f"  class {c}: browseg {b[c]:.9g} python {p[c]:.9g} diff {b[c] - p[c]:+.3g} ({(b[c] - p[c]) / h16(p[c]):+.0f} fp16-ulp)")


if __name__ == "__main__":
    main()
