"""Python TotalSegmentator references (final label maps) for the BrowSeg benchmark.

usage: python make_refs.py <cases_dir> <out_dir> <device> <task:roi>[;<task:roi>...] [case,case,...]
  cases_dir/<case>/  = DICOM files, or one .nii/.nii.gz
  out_dir/<case>__<task>_<roi>.npy   canonical (RAS) uint8 label map, C order (x, y, z)
  out_dir/<case>__<task>_<roi>.json  TS version, resampling order, device, seconds, shape, labels present
Run with the Python of the TS version to compare against (e.g. the ts218 env).
"""
import sys, json, time, tempfile, inspect, importlib.metadata
from pathlib import Path
import numpy as np, nibabel as nib, torch
from totalsegmentator.python_api import totalsegmentator

def main():
    cases_dir, out_dir, device = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    tasks = [(t.split(":")[0], t.split(":")[1] if ":" in t else "-") for t in sys.argv[4].split(";") if t]
    only = set(sys.argv[5].split(",")) if len(sys.argv) > 5 else None
    out_dir.mkdir(parents=True, exist_ok=True)
    sig = inspect.signature(totalsegmentator).parameters
    order = sig["resampling_order"].default if "resampling_order" in sig else 3
    ver = importlib.metadata.version("TotalSegmentator")

    for case in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
        if only and case.name not in only:
            continue
        niis = sorted(case.glob("*.nii*"))
        inp = niis[0] if niis else case
        for task, roi in tasks:
            key = f"{case.name}__{task}_{'all' if roi == '-' else roi.replace(',', '+')}"
            if (out_dir / f"{key}.npy").exists():
                continue
            with tempfile.TemporaryDirectory() as td:
                f = Path(td) / "seg.nii.gz"
                t0 = time.time()
                totalsegmentator(inp, f, ml=True, task=task, roi_subset=None if roi == "-" else roi.split(","),
                                 device=device, quiet=True)
                secs = time.time() - t0
                im = nib.as_closest_canonical(nib.load(f))
                lab = np.ascontiguousarray(np.asarray(im.dataobj).astype(np.uint8))
            np.save(out_dir / f"{key}.npy", lab)
            json.dump({"case": case.name, "task": task, "roi": roi, "ts_version": ver, "resampling_order": order,
                       "device": device, "torch": torch.__version__, "threads": torch.get_num_threads(), "seconds": secs,
                       "shape": list(lab.shape), "labels": [int(x) for x in np.unique(lab) if x]},
                      open(out_dir / f"{key}.json", "w"), indent=1)
            print(f"{key}: {secs:.1f} s, {len(np.unique(lab)) - 1} labels", flush=True)


if __name__ == "__main__":  # Windows: TS uses multiprocessing
    main()
