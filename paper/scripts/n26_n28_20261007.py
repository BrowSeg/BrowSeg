"""N26 / N28 (2026-10-07) summary.
N26: Python TotalSegmentator 2.18 on the GPU (RTX 4070), IRCAD 20 cases x 3 liver tasks, conditions
  default (Table 5: fp16 mixed precision + cudnn.benchmark, runs r1-r3), fp32 (autocast and TF32 off), det (mixed precision,
  cudnn.benchmark off + deterministic): voxels differing from the CPU reference, and run-to-run differences.
N28: native BrowSeg (probe build) CPU, input resampling in 32-bit instead of 64-bit vs the same build without the switch.
Output: analysis/n26_n28_20261007.txt. Run from paper_benchmarks with numpy."""
import glob, os, re
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
R = os.path.join(ROOT, "data", "bench_refs")
CASES = [f"ircad{i:02d}" for i in range(1, 21)]
TASKS = ["total_liver", "liver_segments_all", "liver_vessels_all"]
out = []
def load(d, k):
    p = os.path.join(R, d, k + ".npy")
    return np.load(p) if os.path.exists(p) else None
conds = {"default": [f"ts218_gpu_r{r}" for r in (1, 2, 3)],
         "fp32": [f"ts218_gpu_fp32_r{r}" for r in (1, 2, 3)],
         "det": [f"ts218_gpu_det_r{r}" for r in (1, 2, 3)]}
out.append("N26: Python TS 2.18 GPU vs CPU reference (IRCAD 20 x 3 liver tasks)")
for c, dirs in conds.items():
    dirs = [d for d in dirs if os.path.isdir(os.path.join(R, d))]
    for t in TASKS:
        per_run, n_ident, n_runvar, maxd, missing = [], 0, 0, 0, 0
        for case in CASES:
            k = f"{case}__{t}"; ref = load("ts218_cpu", k)
            arrs = [load(d, k) for d in dirs]
            if any(a is None for a in arrs) or not arrs:
                missing += 1; continue
            diffs = [int((a != ref).sum()) for a in arrs]
            per_run.append((case, diffs))
            n_ident += sum(d == 0 for d in diffs)
            maxd = max(maxd, max(diffs))
            if any(int((arrs[0] != a).sum()) for a in arrs[1:]): n_runvar += 1
        n = len(per_run) * len(dirs)
        nz = [d for _, ds in per_run for d in ds if d]
        out.append(f"  {c:8s} {t:20s} runs {len(dirs)} cases {len(per_run)} (missing {missing}): identical to CPU {n_ident}/{n}, "
                   f"diff range {min(nz) if nz else 0}-{maxd}, cases whose runs differ from each other {n_runvar}/{len(per_run)}")
        out.append("           " + "; ".join(f"{c_[5:]}:{'/'.join(map(str, d))}" for c_, d in per_run if any(d)))
for c, dirs in conds.items():
    dirs = [d for d in dirs if os.path.isdir(os.path.join(R, d))]
    tot = [int((load(d, f"{case}__{t}") != load("ts218_cpu", f"{case}__{t}")).sum()) for d in dirs for case in CASES for t in TASKS
           if load(d, f"{case}__{t}") is not None]
    if tot:
        out.append(f"  {c}: all tasks: identical {sum(x == 0 for x in tot)}/{len(tot)} runs, max {max(tot)} voxels")

out.append("")
out.append("N28: native probe build, CPU, input resampling 64-bit (base) vs 32-bit (f32), vs the TS 2.18 CPU reference")
N = os.path.join(ROOT, "data", "n28")
for mode in ("base", "f32"):
    for t in TASKS:
        res = []
        for case in CASES:
            f = os.path.join(N, mode, f"{case}__{t}.txt")
            if not os.path.exists(f): continue
            s = open(f).read()
            m = re.search(r"final\s+(EXACT)?\s*mismatches (\d+) /", s)
            d = re.search(r"worst Dice ([0-9.]+)", s)
            b = re.search(r"bbox canonical (\[.*)", s)
            res.append((case, int(m.group(2)) if m else None, float(d.group(1)) if d else None, b.group(1) if b else ""))
        ok = [r for r in res if r[1] is not None]
        nz = [r[1] for r in ok if r[1]]
        out.append(f"  {mode:4s} {t:20s} cases {len(ok)}/{len(res)}: identical {sum(r[1] == 0 for r in ok)}, diff range "
                   f"{min(nz) if nz else 0}-{max(nz) if nz else 0}, worst Dice {min((r[2] for r in ok if r[2] is not None), default=1):.6f}")
        out.append("           " + "; ".join(f"{c[5:]}:{d}" for c, d, _, _ in ok if d))
# crop boxes base vs f32
nb = 0; nbd = []
for case in CASES:
    for t in TASKS:
        fa, fb = (os.path.join(N, m, f"{case}__{t}.txt") for m in ("base", "f32"))
        if os.path.exists(fa) and os.path.exists(fb):
            ba = re.search(r"bbox canonical (\[.*)", open(fa).read()); bb = re.search(r"bbox canonical (\[.*)", open(fb).read())
            if ba and bb:
                nb += 1
                if ba.group(1) != bb.group(1): nbd.append(f"{case} {t}: {ba.group(1)} -> {bb.group(1)}")
out.append(f"  crop boxes base vs f32: compared {nb}, different {len(nbd)}" + ("; " + "; ".join(nbd) if nbd else ""))
# BrowSeg WebGPU (public build, desktop Chrome; data/browser/v3_desk_chrome_webgpu/*.u8) vs the Python GPU fp32 runs
BW = os.path.join(ROOT, "paper_jiim", "paper_benchmarks", "data", "browser", "v3_desk_chrome_webgpu")
for d in conds["fp32"]:
    if len(glob.glob(os.path.join(R, d, "*.npy"))) < 60: continue
    same, diffs = 0, []
    for case in CASES:
        for t in TASKS:
            k = f"{case}__{t}"; f = load(d, k); ub = os.path.join(BW, k + ".u8")
            if f is None or not os.path.exists(ub): continue
            b = np.fromfile(ub, dtype=np.uint8).reshape(f.shape); n = int((b != f).sum())
            same += n == 0
            if n: diffs.append(f"{k}:{n}")
    out.append(f"BrowSeg WebGPU (v3_desk_chrome_webgpu) vs Python GPU fp32 {d}: identical {same}/60" + ("; " + "; ".join(diffs) if diffs else ""))
open("analysis/n26_n28_20261007.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))

# ---- Table 4 of the manuscript (JP): Python GPU conditions vs the CPU reference -> analysis/table_5_jp.md ({{table:5}})
def dice_min(a, b):
    best = 1.0
    for l in set(np.unique(a)) | set(np.unique(b)):
        if l == 0: continue
        x, y = a == l, b == l
        s = int(x.sum()) + int(y.sum())
        if s: best = min(best, 2.0 * int((x & y).sum()) / s)
    return best
JPT = {"total_liver": "肝臓", "liver_segments_all": "肝区域", "liver_vessels_all": "肝内血管"}
NAME = {"default": "既定（fp16 の混合精度、cuDNN の自動チューニング）", "fp32": "32 ビット（autocast と TF32 を無効。自動チューニングは既定のまま）",
        "det": "混合精度のまま、自動チューニングを無効にし決定的なアルゴリズムを指定"}
rows_t, dmins = [], {}
for c, dirs in conds.items():
    dirs = [d for d in dirs if len(glob.glob(os.path.join(R, d, "*.npy"))) >= 60]  # complete run sets only
    if not dirs: continue
    cells = []
    for t in TASKS:
        n_id = n = 0; diffs = []; var = 0; dm = 1.0
        for case in CASES:
            k = f"{case}__{t}"; ref = load("ts218_cpu", k); arrs = [load(d, k) for d in dirs]
            if any(a is None for a in arrs): continue
            ds = [int((a != ref).sum()) for a in arrs]; n += len(ds); n_id += sum(x == 0 for x in ds); diffs += ds
            var += any(int((arrs[0] != a).sum()) for a in arrs[1:])
            dm = min([dm] + [dice_min(a, ref) for a, x in zip(arrs, ds) if x])
        dmins[(c, t)] = dm
        nz = [x for x in diffs if x]
        rng = (f"各 {min(nz):,}" if min(nz) == max(nz) else f"{min(nz):,}〜{max(nz):,}") if nz else "—"
        cells.append(f"{n_id} / {n}（{rng}）、{var} 例")
    rows_t.append(f"| {NAME[c]}、{len(dirs)} 回 | " + " | ".join(cells) + " |")
tbl = ["| 条件、各症例の実行回数 | 肝臓（total, roi_subset） | 肝区域 | 肝内血管 |", "|---|---|---|---|"] + rows_t
dmd = "、".join(f"{JPT[t]} {dmins[('default', t)]:.4f}" for t in TASKS if ('default', t) in dmins)
note = (f"各欄は「参照と完全に一致した実行 / 実行数（不一致のあった実行の不一致ボクセル数の範囲）、実行間で出力が変わった症例数」。"
        f"既定の条件での構造ごとの Dice 係数の最小値は {dmd}。症例 9 の肝区域の 27,581 ボクセルは、どちらか一方だけがラベルを付けたボクセル（対称差）で、"
        f"約 42 mL（ボクセル 0.873 × 0.873 × 2.0 mm）に当たる。症例ごとの値は公開リポジトリの記録（python_gpu.csv ほか）。")
open("analysis/table_5_jp.md", "w", encoding="utf-8").write("\n".join(tbl) + "\n\n" + note + "\n")
print("\n".join(tbl)); print(note); print({k: round(v, 6) for k, v in dmins.items()})
