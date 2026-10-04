# lap20_igpu_chunk4：Intel UHD（TGL GT1）WebGPU、gpuchunk=4、20 例 × 3 タスク × 1 回（2026-10-03）

- **キット**：BrowSeg_v3（c21be14）。`BROWSEG_GPU=intel`。environment.json の GPU は intel gen-12lp／ANGLE "Mesa Intel(R) UHD Graphics (TGL GT1)" です。
- **クエリ**：cases=ircad01..ircad20&tasks=total:liver;liver_segments:-;liver_vessels:-&reps=1&gpuchunk=4、timeoutMin 360（`scripts/plan_lap20_igpu.json`）。
- **実行**：15:50:58〜18:17:56（2 時間 27 分）。systemd-inhibit の下、電源接続、窓は表示したまま。
- **開始前の状態**：load 0.45、空き 11 GB、スワップ 1.0 GB 使用。conda や runSofa などの重い処理はありませんでした（`logs/time_lap20_igpu_chunk4.txt`）。

## 判定
| 項目 | 結果 |
|---|---|
| run 数 | 60（20 例 × 3 タスク） |
| backend | 60/60 webgpu |
| fallback | 0 |
| gpuErrors | 合計 0 |
| journalctl -k の i915/rcs0/GPU HANG/Fence/OOM | 0 行（run の時間帯全体。`logs/kernel_lap20_igpu_chunk4_wide.txt`） |
| GPU リセット | 0 |

各 run の backend、fallback、gpuErrors は `times_lap20_igpu_chunk4.md` の表にあります。

## 照合
**desktop_hashes.json（WebGPU）と比べた結果**（`logs/hashes_lap20_igpu_chunk4.txt`）：
- MATCH (exact)：55
- SAME-AS-DESKTOP-NONEXACT：3（ircad14・16・18 の liver_segments、それぞれ Python と 1 ボクセル差。デスクトップの WebGPU 自身と同じ）
- DIFFERENT：2

**DIFFERENT の 2 件を desktop_hashes_wasm20.json（CPU）と比べた結果**（`logs/hashes_lap20_igpu_chunk4_vs_wasm20.txt`）：
| key | Intel の hash | WebGPU（desktop） | CPU（desktop wasm20） | .u8 の比較 |
|---|---|---|---|---|
| ircad05__liver_segments_all | c89697ef | f91b879a（exact） | **c89697ef**（Python と 1 ボクセル差） | lap20_chrome_wasm と 0 差、T1200 WebGPU と 1 差（idx 27651043：6 対 5） |
| ircad20__total_liver | 54816bfc | 9c0e6cbc（exact） | **54816bfc**（Python と 4 ボクセル差） | lap20_chrome_wasm と 0 差、T1200 WebGPU と 4 差（4 ボクセルとも Intel/CPU=0、WebGPU=5） |

2 件とも、CPU 版の出力と完全に同じでした。拮抗したボクセルが、CPU と同じ側に倒れたものと見ています。
**60 件すべてが、デスクトップの WebGPU か CPU のどちらかの記録と同一です。** Python 参照と比べると、exact が 55、1〜4 ボクセル差が 5 です。.u8 は `run/` にあります。

参考：CPU（wasm20）と比べた場合、全体では MATCH 54、NONEXACT 4、DIFFERENT 2（ircad12 vessels、ircad14 segments）になります。この 2 件は WebGPU 側の記録と一致しています。

## 時間（秒、タスク別の 20 例平均）
| 条件 | total_liver | liver_segments | liver_vessels | 合計 |
|---|---|---|---|---|
| Intel UHD、gpuchunk=4（今回） | 42.9 | 198.7 | 197.4 | 146.3 分 |
| lap20_chrome_wasm（CPU、1 回） | 71.3 | 332.5 | 330.5 | 244.8 分 |
| lap20_chrome_nv_webgpu（T1200、3 回のうち 1 回目） | 6.0 | 23.5 | 23.7 | 17.7 分 |

Intel UHD に gpuchunk=4 を使うと、CPU の約 1.67 倍の速さです。T1200 と比べると約 8.3 倍遅くなります。
症例ごとの値（前回の 2 条件を並べたもの）は `times_lap20_igpu_chunk4.md` にあります。T1200 の列には 3 回分を / で区切って載せています。
modelSeconds は 0.4〜0.7 秒です（重みはプロファイルのキャッシュから読んでいます）。
