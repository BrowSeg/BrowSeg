"""Label-map fingerprints: build the reference list on the desktop, compare against it on another machine.

The browser benchmark (web/bench.html) stores a FNV-1a hash of every label map in <case>__<task>.json
("runs[].hash"). Where the desktop's output equals the Python reference exactly, that hash identifies the
exact label map, so another machine only has to ship its .json files back; the .u8 label maps are needed
only for runs whose hash differs.

  python hashes.py build <browser dir> <tag>[,<tag2>...] <refs dir> <out.json>
      hashes of the runs in <browser dir>/<tag> whose .u8 equals the reference .npy (exact), plus, for the
      others, the hash and the number of differing voxels. Several tags (comma-separated) are merged, e.g. the
      liver tasks (desk_chrome_webgpu_final) and the 117-structure task (desk_chrome_webgpu_total_20); a key
      present in two tags must have the same hashes
  python hashes.py check <browser dir> <tag> <desktop_hashes.json>
      for every run of <tag>: MATCH (same as an exact desktop map), SAME-AS-DESKTOP-NONEXACT, or DIFFERENT
      (copy that .u8 back); also flags runs that fell back to the CPU
"""
import sys, json
from pathlib import Path
import numpy as np


def build(bdir, tags, rdir, out):
    res = {}
    for tag in tags.split(","):
        for jf in sorted((Path(bdir) / tag).glob("*__*.json")):
            d = json.load(open(jf))
            key = jf.stem
            hashes = sorted({r["hash"] for r in d["runs"]})
            ref = Path(rdir) / f"{key}.npy"
            u8 = jf.with_suffix(".u8")
            diff = int((np.load(ref).ravel() != np.fromfile(u8, np.uint8)).sum()) if ref.exists() and u8.exists() else None
            entry = {"hashes": hashes, "diff_voxels_vs_python": diff, "exact": diff == 0, "tag": tag}
            if key in res and res[key]["hashes"] != hashes:
                raise SystemExit(f"{key}: hashes differ between tags ({res[key]['tag']} {res[key]['hashes']} vs {tag} {hashes})")
            res.setdefault(key, entry)
    json.dump({"source_tag": tags, "entries": res}, open(out, "w"), indent=1)
    print(f"{len(res)} entries, exact: {sum(1 for v in res.values() if v['exact'])} -> {out}")


def check(bdir, tag, listfile):
    ref = json.load(open(listfile))["entries"]
    for jf in sorted((Path(bdir) / tag).glob("*__*.json")):
        d = json.load(open(jf))
        key = jf.stem
        hs = {r["hash"] for r in d["runs"]}
        fb = [r.get("fallback") for r in d["runs"] if r.get("fallback")]
        e = ref.get(key)
        if e is None:
            st = "NO-DESKTOP-ENTRY (copy .u8)"
        elif hs <= set(e["hashes"]):
            st = "MATCH (exact)" if e["exact"] else f"SAME-AS-DESKTOP-NONEXACT ({e['diff_voxels_vs_python']} voxels)"
        else:
            st = "DIFFERENT (copy .u8)"
        print(f"{key:36s} {st}{'  CPU-FALLBACK x' + str(len(fb)) if fb else ''}{'  runs differ among themselves' if len(hs) > 1 else ''}")


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(*sys.argv[2:6])
    else:
        check(*sys.argv[2:5])
