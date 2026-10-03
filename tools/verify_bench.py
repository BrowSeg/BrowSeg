"""Compare a BrowSeg benchmark bundle (downloaded from bench.html?local=1) with the paper's records.

usage: python tools/verify_bench.py <bundle.json> [paper/data/desktop_hashes.json | paper/data/desktop_hashes_wasm20.json]

The bundle holds, for every case x task, the FNV-1a hash of the label map of each run. The paper's records hold the
hash of the same label map produced on the authors' desktop (WebGPU: desktop_hashes.json, tags desk_chrome_webgpu_final
for the three liver tasks and desk_chrome_webgpu_total_20 for the 117 structures; CPU/WebAssembly:
desktop_hashes_wasm20.json, tag desk_chrome_wasm_20, liver tasks only). The hash is computed over the label map on the
original CT grid (uint8, one byte per voxel), so two runs with the same hash produced the same label map voxel for voxel.

Without the second argument every run is compared with the record of the path it ran on (webgpu / cpu), so a run that
lost the GPU and finished on the CPU is compared with the CPU record.
Exit status 0 when every case x task that has a record matches and all repeated runs are identical, 1 otherwise.
"""
import json, sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    bundle = json.load(open(sys.argv[1], encoding="utf-8"))
    results = bundle.get("results", [])
    here = Path(__file__).resolve().parent.parent
    data = here / "paper" / "data"
    # every run is compared with the record of the path it actually used (a run that lost the GPU and finished on the
    # CPU is compared with the CPU record); the optional second argument forces one record file for all runs
    refs = {}
    if len(sys.argv) > 2:
        refs["webgpu"] = refs["cpu"] = json.load(open(sys.argv[2], encoding="utf-8")); refs["webgpu"]["path"] = sys.argv[2]
    else:
        for b, f in (("webgpu", "desktop_hashes.json"), ("cpu", "desktop_hashes_wasm20.json")):
            refs[b] = json.load(open(data / f, encoding="utf-8")); refs[b]["path"] = str(data / f)
    env = bundle.get("environment", {})
    # worker.js labels a run 'webgpu', 'cpu' or 'cpu (after WebGPU failure)'; the record is chosen by the path
    path = lambda b: "cpu" if str(b).startswith("cpu") else "webgpu"
    backends = sorted({path(b) for r in results for b in (r.get("backends") or [r["backend"]])})
    print(f"bundle: {sys.argv[1]}  tag {bundle.get('tag')}  backend {'+'.join(backends) or env.get('backend', '-')}  threads {env.get('threads')}  isolated {env.get('crossOriginIsolated')}")
    print(f"        {env.get('userAgent', '')}")
    print(f"        GPU: {(env.get('gpu') or {}).get('description') or env.get('webglRenderer') or '-'}   version: {env.get('version', '-')}")
    for b, ref in refs.items():
        if b in backends or not backends:
            print(f"record ({b}): {ref['path']}  (tag {ref.get('source_tag')}, {len(ref['entries'])} case x task)")
    print()
    print(f"{'case / task':34} {'runs identical':15} {'paper':10} {'this run':10} result")
    ok = ng = na = notrep = 0
    for r in results:
        hashes = r["hashes"]; same = len(set(hashes)) == 1
        run_backends = [path(b) for b in (r.get("backends") or [r["backend"]] * len(hashes))]
        exps = [refs[b]["entries"].get(r["key"], {}).get("hashes", [None])[0] for b in run_backends]
        compared = sum(1 for e in exps if e)
        if compared == 0:
            res = "no record"; na += 1
        elif all(h == e for h, e in zip(hashes, exps) if e):  # runs without a record are left out of the verdict
            res = "match"; ok += 1
        else:
            res = "DIFFERENT"; ng += 1
        if compared and compared < len(hashes):
            res += f" ({compared} of {len(hashes)} runs have a record)"
        if not same:
            notrep += 1
        shown = exps[0] if len(set(exps)) == 1 else "mixed"
        print(f"{r['key']:34} {'yes' if same else 'NO':15} {shown or '-':10} {hashes[0]:10} {res}   ({' / '.join(f'{s:.2f}' for s in r['seconds'])} s{'; ' + '+'.join(sorted(set(run_backends))) if len(set(run_backends)) > 1 else ''})")
    print()
    print(f"{ok} match, {ng} different, {na} without record; {notrep} case x task with non-identical repeated runs")
    entries = refs["cpu" if backends == ["cpu"] else "webgpu"]["entries"]
    missing = sorted(set(entries) - {r["key"] for r in results})
    if missing:
        print(f"not run here ({len(missing)} of the paper's case x task): {', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}")
    sys.exit(0 if ng == 0 and notrep == 0 else 1)


if __name__ == "__main__":
    main()
