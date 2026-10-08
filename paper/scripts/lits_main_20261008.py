"""Main-text numbers and tables for the LiTS-centred manuscript (2026-10-08).

Input : paper_benchmarks/analysis/lits_summary.csv (desktop Chrome, WebGPU 3 runs and CPU 1 run, 30 cases x 3 tasks)
        paper_benchmarks/data/browser_lits_laptop/lap_lits_nv_webgpu/*.json (laptop T1200, if present)
Output: analysis/lits_main_20261008.txt, analysis/table_L1_jp.md (agreement), analysis/table_L2_jp.md (time)
CPU rows: lits_chrome_wasm + lits_chrome_wasm_167 + lits_chrome_wasm_rest (90); lits_022/023 times from the recheck
(another process overlapped the first run, outputs identical). Pilot rows are excluded.
"""
import csv, json, statistics as st
from pathlib import Path

A = Path(__file__).resolve().parents[1] / "analysis"
LAP = Path(__file__).resolve().parents[1] / "data" / "browser_lits_laptop" / "lap_lits_nv_webgpu_rawload"
rows = list(csv.DictReader(open(A / "lits_summary.csv", encoding="utf-8")))
TASKS = [("total", "肝臓"), ("liver_segments", "肝区域"), ("liver_vessels", "肝内血管")]
gpu = [r for r in rows if r["tag"] == "lits_chrome_webgpu"]
cpu = [r for r in rows if r["tag"] in ("lits_chrome_wasm", "lits_chrome_wasm_167", "lits_chrome_wasm_rest")]
recheck = {(r["case"], r["task"]): float(r["t_first"]) for r in rows if r["tag"] == "lits_chrome_wasm_recheck_022_023"}
assert len(gpu) == 90 and len(cpu) == 90, (len(gpu), len(cpu))

out = []
def agree(rs, name):
    cells, n_ok_all, diffs_all, vox = [], 0, [], 0
    for t, _ in TASKS:
        x = [r for r in rs if r["task"] == t]
        ok = sum(int(r["diff_voxels"]) == 0 for r in x)
        bad = sorted(int(r["diff_voxels"]) for r in x if int(r["diff_voxels"]) > 0)
        n_ok_all += ok; diffs_all += bad
        cells.append(f"{ok} / {len(x)}" + (f"（{bad[0]}〜{bad[-1]}）" if len(bad) > 1 and bad[0] != bad[-1] else f"（{bad[0]}）" if bad else ""))
        out.append(f"{name} {t}: exact {ok}/{len(x)}, differing voxels {bad}, min Dice {min(float(r['worst_dice']) for r in x)}")
    for r in rs:
        a, b, c = map(int, r["shape"].split("x"))
        vox += a * b * c
    out.append(f"{name} all: exact {n_ok_all}/{len(rs)}, differing {min(diffs_all)}-{max(diffs_all)} voxels, total differing voxels {sum(diffs_all)}, voxels compared {vox}, min Dice {min(float(r['worst_dice']) for r in rs)}")
    return cells

# Times and memory: the re-measurement with the paper's build 022925c (paper-v1.1; data/browser_lits_v11). Its label maps
# are identical to the 10-06 records for all 90 pairs on both paths (checked below), so the agreement numbers above,
# taken from lits_summary.csv (10-06), hold for 022925c.
V11 = Path(__file__).resolve().parents[1] / "data" / "browser_lits_v11"
V11_TAGS = {"webgpu": ["lits_v11_chrome_webgpu"],
            "cpu": ["lits_v11_chrome_wasm_p1", "lits_v11_chrome_wasm_p2", "lits_v11_chrome_wasm_p3", "lits_v11_chrome_wasm_167"]}
BR = Path(__file__).resolve().parents[1] / "data" / "browser_lits"
OLD_TAGS = {"webgpu": ["lits_chrome_webgpu"], "cpu": ["lits_chrome_wasm", "lits_chrome_wasm_167", "lits_chrome_wasm_rest"]}


def key_of(case, task):
    return f"{case}__total_liver" if task == "total" else f"{case}__{task}_all"


def run_json(backend, case, task):
    for t in V11_TAGS[backend]:
        f = V11 / t / f"{key_of(case, task)}.json"
        if f.exists():
            return json.loads(f.read_text())
    raise FileNotFoundError(key_of(case, task))


def old_json(backend, case, task):
    for t in reversed(OLD_TAGS[backend]):
        f = BR / t / f"{key_of(case, task)}.json"
        if f.exists():
            return json.loads(f.read_text())
    raise FileNotFoundError(key_of(case, task))


def tsec(r):
    """seconds from the v1.1 run JSON: WebGPU = mean of runs 2 and 3, CPU = the single run."""
    s = [x["seconds"] for x in run_json(r["backend"], r["case"], r["task"])["runs"]]
    return sum(s[1:]) / len(s[1:]) if len(s) > 1 else s[0]

def timing(rs, name):
    cells = []
    for t, _ in TASKS:
        v = sorted(tsec(r) for r in rs if r["task"] == t)
        cells.append(f"{st.median(v):.1f}（{v[0]:.1f}〜{v[-1]:.1f}）")
        out.append(f"{name} time {t}: median {st.median(v):.2f} s, range {v[0]:.2f}-{v[-1]:.2f} (n={len(v)})")
    h = [(max(x["heap"] for x in run_json(r["backend"], r["case"], r["task"])["runs"]) / 2**20, r["case"]) for r in rs]
    out.append(f"{name} heap max {max(h)[0]:.0f} MiB ({max(h)[1]}; v1.1, cumulative within a page)")
    same = sum({x["hash"] for x in run_json(r["backend"], r["case"], r["task"])["runs"]} ==
               {x["hash"] for x in old_json(r["backend"], r["case"], r["task"])["runs"]} for r in rs)
    out.append(f"{name} v1.1 label maps identical to the 10-06 record: {same}/{len(rs)}")
    return cells

out.append("WebGPU repeatable (3 runs identical): " + str(sum(r["repeatable"] == "True" for r in gpu)) + "/90")
g_cells, c_cells = agree(gpu, "desktop WebGPU"), agree(cpu, "desktop CPU")
same = sum(int(a["diff_voxels"]) == int(b["diff_voxels"]) for a in gpu for b in cpu if (a["case"], a["task"]) == (b["case"], b["task"]))
out.append(f"same number of differing voxels WebGPU vs CPU: {same}/90")
gt, ct = timing(gpu, "desktop WebGPU"), timing(cpu, "desktop CPU")
from scipy.stats import beta
for t, _ in TASKS:
    k = sum(int(r["diff_voxels"]) == 0 for r in gpu if r["task"] == t); n = 30
    lo = beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0; hi = beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    out.append(f"Clopper-Pearson 95% CI desktop WebGPU {t}: {k}/{n} = {100*lo:.1f}-{100*hi:.1f}%")

lap_cells = ["—"] * 3
if LAP.exists():
    lap = []
    for f in sorted(LAP.glob("lits_*.json")):
        d = json.loads(f.read_text())
        rest = [r["seconds"] for r in d["runs"][1:]]
        lap.append({"task": d["task"], "t": sum(rest) / len(rest) if rest else None,
                    "backend": {r["backend"] for r in d["runs"]}})
    if len(lap) == 90:
        lap_cells = []
        for t, _ in TASKS:
            v = sorted(x["t"] for x in lap if x["task"] == t)
            lap_cells.append(f"{st.median(v):.1f}（{v[0]:.1f}〜{v[-1]:.1f}）")
            out.append(f"laptop WebGPU time {t}: median {st.median(v):.2f} s, range {v[0]:.2f}-{v[-1]:.2f}")

hdr = "| | " + " | ".join(n for _, n in TASKS) + " |\n|---|---|---|---|\n"
(A / "table_L1_jp.md").write_text(hdr + "| WebGPU | " + " | ".join(g_cells) + " |\n| CPU（WebAssembly） | " + " | ".join(c_cells) + " |\n\n"
    "各欄は「参照と完全に一致した症例数 / 症例数（不一致のあった症例の不一致ボクセル数）」。\n", encoding="utf-8")
(A / "table_L2_jp.md").write_text(hdr + "| デスクトップ PC・WebGPU | " + " | ".join(gt) + " |\n| デスクトップ PC・CPU（WebAssembly） | " + " | ".join(ct)
    + " |\n| ノート PC・WebGPU | " + " | ".join(lap_cells) + " |\n\n"
    "値は 30 例の中央値（範囲）。WebGPU は 2・3 回目の平均、CPU は 1 回。\n", encoding="utf-8")
(A / "lits_main_20261008.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
