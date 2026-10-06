# Imported 2026-10-06 from desktop-a8 (Desktop/TS論文チェック/scripts/review_analysis.py); only ROOT changed to a path relative to this file.
# Output: ../analysis/review_stats_20261006.txt (used by Results v4 / Supplement S1.5, S1.7; ledger D61-D65).
# desktop-a8 review analyses (2026-10-06). Inputs: raw label maps (.u8) and Python references (.npy); no analysis CSVs.
# Run: PYTHONIOENCODING=utf-8 C:/Users/user/anaconda3/envs/ircad/python.exe review_analysis.py
import json, glob, os, numpy as np, statistics as st, collections
from scipy.stats import beta
ROOT=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../..")); B=f"{ROOT}/paper_jiim/paper_benchmarks/data/browser"; R=f"{ROOT}/data/bench_refs"
T={"total_liver":"肝臓","liver_segments_all":"肝区域","liver_vessels_all":"肝内血管","total_all":"117構造"}
def cp(k,n,a=0.05):
    lo=0 if k==0 else beta.ppf(a/2,k,n-k+1); hi=1 if k==n else beta.ppf(1-a/2,k+1,n-k); return lo*100,hi*100
# DICOM geometry per case from run JSON load info
geo={}
for f in glob.glob(f"{B}/desk_chrome_webgpu_final/ircad*__total_liver.json"):
    j=json.load(open(f)); c=os.path.basename(f)[:7]; geo[c]=(j["load"]["shape"],j["load"]["zooms"])
print("=== 1. mismatching (case, task) pairs by path ===")
paths={"WebGPU":["desk_chrome_webgpu_final","desk_chrome_webgpu_total_20"],"CPU":["desk_chrome_wasm_20","desk_chrome_wasm_total_20"],"iGPU(Intel)":[]}
mm=collections.defaultdict(dict)
for p,tags in paths.items():
    for tag in tags:
        for u in glob.glob(f"{B}/{tag}/*.u8"):
            k=os.path.basename(u)[:-3]; a=np.load(f"{R}/ts218_cpu/{k}.npy"); b=np.fromfile(u,np.uint8).reshape(a.shape); n=int((a!=b).sum())
            if n:
                sp=geo[k[:7]][1]; vol=n*sp[0]*sp[1]*sp[2]
                mm[k][p]=(n,round(vol,2))
# iGPU via hashes
web=json.load(open(f"{ROOT}/paper_jiim/paper_benchmarks/data/desktop_hashes.json"))["entries"]; cpu=json.load(open(f"{ROOT}/paper_jiim/paper_benchmarks/data/desktop_hashes_wasm20.json"))["entries"]
for f in glob.glob(f"{ROOT}/paper_jiim/paper_benchmarks/data/laptop_20261003/igpu_v3/lap20_igpu_chunk4/run/ircad*.json"):
    k=os.path.basename(f)[:-5]; h=json.load(open(f))["runs"][0]["hash"]
    if h==web[k]["hashes"][0] and not web[k].get("exact",True): mm[k]["iGPU(Intel)"]="=NVIDIA WebGPU"
    elif h!=web[k]["hashes"][0] and h==cpu.get(k,{}).get("hashes",[None])[0]: mm[k]["iGPU(Intel)"]="=CPU path"
for k in sorted(mm): print(f"  {k[:7]} {T[k[9:]]:5} {dict(mm[k])}")
print("  distinct pairs:",len(mm))
print("=== 2. Clopper-Pearson 95% CI ===")
for lab,k,n in [("肝臓 WebGPU",20,20),("肝区域 WebGPU/CPU",17,20),("肝内血管 WebGPU",20,20),("117 WebGPU",18,20),("肝臓/肝内血管 CPU",19,20),("117 CPU",17,20),("WebGPU 全体",75,80),("CPU 3タスク",55,60),("CPU 4タスク",72,80)]:
    lo,hi=cp(k,n); print(f"  {lab:18} {k}/{n} = {100*k/n:.1f}%  95%CI {lo:.1f}–{hi:.1f}%")
print("=== 3. case characteristics ===")
heap=collections.defaultdict(dict)
for tag,key in [("desk_chrome_webgpu_final","gpu3"),("desk_chrome_webgpu_total_20","gpu117"),("desk_chrome_wasm_20","cpu3"),("desk_chrome_wasm_total_20","cpu117")]:
    for f in glob.glob(f"{B}/{tag}/ircad*.json"):
        c=os.path.basename(f)[:7]; heap[c][key]=max(heap[c].get(key,0),max(x.get("heap",0) for x in json.load(open(f))["runs"]))
print("  case slices spacing(xy,z) aniso(z/xy) 6mm-grid 1.5mm-full-grid  heapMiB(gpu3,gpu117,cpu3,cpu117)")
for c in sorted(geo):
    sh,sp=geo[c]; g6=[int(round(s*z/6)) for s,z in zip(sh,sp)]; g15=[int(round(s*z/1.5)) for s,z in zip(sh,sp)]
    print(f"  {c} {sh[2]:4} {sp[0]:.2f}/{sp[2]:.2f} {sp[2]/sp[0]:.1f}{'*' if sp[2]/sp[0]>3 else ' '} {g6} {g15} {[round(heap[c].get(k,0)/2**20) for k in ('gpu3','gpu117','cpu3','cpu117')]}")
print("=== 4. Python GPU case 9: where do the diffs lie? ===")
for task in ("total_liver","liver_segments_all","liver_vessels_all","total_all"):
    k=f"ircad09__{task}"; c=np.load(f"{R}/ts218_cpu/{k}.npy")
    for i in (1,2,3):
        g=np.load(f"{R}/ts218_gpu_r{i}/{k}.npy"); d=np.argwhere(g!=c)
        if len(d)==0: continue
        lab=c>0; 
        # fraction of diff voxels on a label boundary of the CPU map
        from scipy import ndimage
        bnd=lab ^ ndimage.binary_erosion(lab); dil=ndimage.binary_dilation(bnd,iterations=1)
        on=dil[tuple(d.T)].mean()
        # how much of the liver boundary is touched
        frac_b=(dil & (g!=c)).sum()/max(1,dil.sum())
        print(f"  {task:20} r{i}: diff {len(d):6}  on-boundary {on*100:5.1f}%  boundary voxels touched {frac_b*100:5.1f}%  z-range {d[:,2].min()}-{d[:,2].max()}")
print("=== 5. heap: cases where the running maximum increased (cases run in order 01..20 in one page) ===")
for tag in ["desk_chrome_webgpu_final","desk_chrome_webgpu_total_20","desk_chrome_wasm_20","desk_chrome_wasm_total_20"]:
    seq=[]; cur=0
    for c in sorted({os.path.basename(f)[:7] for f in glob.glob(f"{B}/{tag}/ircad*.json")}):
        h=max(max(x.get("heap",0) for x in json.load(open(f))["runs"]) for f in glob.glob(f"{B}/{tag}/{c}__*.json"))
        if h>cur: seq.append(f"{c[-2:]}->{round(h/2**20)}"); cur=h
    print(f"  {tag:30} "+", ".join(seq)+" (MiB)")
