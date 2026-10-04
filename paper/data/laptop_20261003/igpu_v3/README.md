# ノート PC 計測 v3：内蔵 GPU（Intel UHD）での分割送信 — 結果（2026-10-03）

ノート：HP ZBook Studio G8、i7-11800H、Intel UHD Graphics (TGL GT1)、Ubuntu 22.04、kernel 6.8.0-138、Mesa 23.2.1、Chrome 142.0.7444.175。
WebGPU は Intel の Vulkan ICD（`BROWSEG_GPU=intel`）で動かしました。全 run の environment.json で GPU が intel gen-12lp／ANGLE "Mesa Intel(R) UHD Graphics (TGL GT1)" であることを確認済みです。
書き出し版は BrowSeg_v3（c21be14）で、`~/Documents/MyGithubProject2/BrowSeg_v3` に置きました。手編集は bench_run.mjs の Chrome のパスと、指示どおりの plan_laptop_igpu_B.json（N=4）だけです（`scripts/*.diff`）。
実行は 1 項目ずつで、項目の間に計測用 Chrome を閉じました。systemd-inhibit を使い、電源は接続したままです。

## 結論
- **分割送信（gpuchunk）では、Intel UHD で GPU リセットなしに完走しました。** chunk1・chunk1_nowait・chunk4・chunk8・chunk4_5cases・chunk4_r2・chunk8_r2 の計 33 run すべてで、backend webgpu、fallback なし、gpuErrors 0、i915/rcs0 の行 0 でした。
- **分割なし（既定）は非決定的です。** chunk0_control（reps=1、14:48）は正常でした。chunk0_3tasks（reps=3、15:30）ではリセットが起き、さらに**エラーも fallback もないまま誤った出力が 2 回出ました**（下記）。
- 段階 B の N は、デスクトップ側の判断で **4（待機あり）** にしました。N=4 は 3 タスクとも N=8 より速く、r2 でも同じ傾向でした。gpuchunk=8&gpuchunkwait=0 は試していません。

## 各タグ
| タグ | 条件 | 判定 | hashes.py check | カーネル |
|---|---|---|---|---|
| lap_igpu_chunk1_oom_aborted | gpuchunk=1 | **数えない**：13:47:05 に OOM killer が計測用タブを終了（並行の conda-env create ×2、約 9 GB）。GPU の結果ではない | – | OOM のみ |
| lap_igpu_chunk1 | gpuchunk=1 | 完走 | 3/3 MATCH | 0 |
| lap_igpu_chunk1_nowait | gpuchunk=1&gpuchunkwait=0 | 完走 | 3/3 MATCH | 0 |
| lap_igpu_chunk4 | gpuchunk=4 | 完走 | 3/3 MATCH | 0 |
| lap_igpu_chunk8 | gpuchunk=8 | 完走 | 3/3 MATCH | 0 |
| lap_igpu_chunk0_control | 既定、肝臓のみ、reps=1 | 完走（リセットは起きず、予想と違った） | 1/1 MATCH | 0 |
| lap_igpu_chunk4_5cases | gpuchunk=4、5 例 × 3 タスク | 完走 | 13 MATCH、1 SAME-AS-DESKTOP-NONEXACT（ircad18 segments）、1 DIFFERENT（ircad05 segments、下記） | 0 |
| lap_igpu_chunk4_r2 | gpuchunk=4（再） | 完走 | 3/3 MATCH | 0 |
| lap_igpu_chunk8_r2 | gpuchunk=8（再） | 完走 | 3/3 MATCH | 0 |
| lap_igpu_chunk0_3tasks | 既定、ircad01 × 3 タスク × reps=3 | **失敗**：リセットが起きた。指示どおり肝区域 rep1 の途中で停止 | total_liver DIFFERENT、CPU-FALLBACK ×1、run 間で不一致 | Fence timeout、rcs0 リセット、GPU HANG |

MATCH・DIFFERENT の数（全 hashes 出力の合計）：MATCH 32、SAME-AS-DESKTOP-NONEXACT 1、DIFFERENT 2。

### ircad05__liver_segments_all（chunk4_5cases）の DIFFERENT
hash c89697ef は、CPU 版（desk_chrome_wasm_20・lap20_chrome_wasm）と同じ値です。desktop_hashes_wasm20 では diff_voxels_vs_python=1 になっています。
.u8 で比べると、Intel の結果は lap20_chrome_wasm と 0 ボクセル差、T1200 WebGPU（f91b879a、Python と exact）とは 1 ボクセル差でした（index 27651043、Intel/CPU=6、WebGPU=5）。
拮抗したボクセル 1 個が反対側に倒れたものと見ています。GPU の不具合ではありません。.u8 は `runs/lap_igpu_chunk4_5cases/` にあります。

### lap_igpu_chunk0_3tasks（分割なし）の失敗
カーネルログ（開始 15:30:45、load 1.29、ほかの重い処理なし）：
```
15:31:10 kernel: Fence expiration time out i915-0000:00:02.0:chrome[54089]:20!
15:32:32 kernel: i915 0000:00:02.0: [drm] Resetting rcs0 for preemption time out
15:32:32 kernel: i915 0000:00:02.0: [drm] chrome[54089] context reset due to GPU hang
15:32:32 kernel: i915 0000:00:02.0: [drm] GPU HANG: ecode 12:1:8ed9fff2, in chrome [54089]
```
ecode は前回 attempt1 と同じです。total_liver の結果：
| rep | backend | fallback | gpuErrors | 秒 | hash |
|---|---|---|---|---|---|
| 1 | webgpu | なし | 0 | 33.0 | 0f03dec9（誤り） |
| 2 | webgpu | なし | 0 | 1.2 | 5dec9dc5（誤り） |
| 3 | cpu (after WebGPU failure) | model 298 returned an all-zero result | 0 | 56.0 | de14684e（正しい） |

rep1・rep2 は、エラー表示も CPU への切り替えもないまま、誤ったラベルマップを返しました。全ゼロの検出が働いたのは rep3 になってからです。
保存されている .u8 は rep1 のものです（bench.html は rep 0 だけを保存します）。その FNV-1a は 0f03dec9 で、誤った出力そのものです（下の「追加確認」を参照）。

## 時間
全 run の表は `times_table.md` にあります（タグ × 症例 × タスク。seconds、modelSeconds、backend、fallback、gpuErrors、照合結果、カーネル行数のほか、前回の lap20_chrome_wasm と lap20_chrome_nv_webgpu の同じ症例の値も並べています）。
ircad01 の要点（秒）：

| 条件 | total_liver | liver_segments | liver_vessels |
|---|---|---|---|
| chunk1 | 45.9 | 143.5 | 140.2 |
| chunk1_nowait | 43.8 | 124.4 | 133.4 |
| chunk4 / r2 / 5cases | 33.8 / 41.8 / 41.0 | 101.9 / 102.9 / 112.1 | 103.3 / 105.0 / 101.1 |
| chunk8 / r2 | 42.4 / 37.5 | 125.2 / 120.5 | 107.6 / 120.4 |
| chunk0_control | 37.9 | – | – |
| 前回 lap20_chrome_wasm（CPU） | 54.8 | 175.5 | 175.9 |
| 前回 lap20_chrome_nv_webgpu（T1200、3 回） | 5.7 / 4.3 / 4.3 | 13.2 / 12.9 / 12.6 | 13.7 / 12.9 / 12.9 |

待機なしにすると、chunk1 ではやや速くなりました（segments 143.5→124.4、vessels 140.2→133.4）。
Intel UHD に chunk4 を使うと、CPU（WASM）の約 1.3〜1.7 倍の速さです。T1200 と比べると約 8 倍遅くなります。

modelSeconds について。これは「重みをキャッシュかダウンロードから読む時間＋WASM の設定＋GPU への転送」です。計測用プロファイルの Cache API に重みが残ります（`logs/note_weight_cache.txt`）。
- chunk1：total_liver はキャッシュから（OOM で止まった試行のときに入ったもの）、segments と vessels は初回です。
- それ以降のタグ：すべてキャッシュからです。
重みは localhost から来るので、初回でも約 1 秒です。

## 指示書と現物の違い
1. weights/classmaps.txt の SHA-256 が MANIFEST と合いませんでした（改行コードの違い。デスクトップ側で MANIFEST を修正済み）。.tsw 4 本は一致しました。MANIFEST に載っている 292〜295 と fp16 は今回使わないので置いていません。
2. 対照 chunk0（reps=1）ではリセットが起きませんでした。リセットが再現したのは chunk0_3tasks（reps=3）です。分割なしの結果は非決定的です。
3. 最初の chunk1 は、並行して動いていた conda-env create（ユーザーの作業）による OOM で中断し、やり直しました。各タグの開始時の負荷（uptime、free -h、top）は `logs/time_*.txt` にあります。
4. v3 の web/dist/tsc.wasm の版の文字列は「tsc 0.4 (... + portal/hepatic split + custom models, C++/WASM)」です。一方、書き出したソース web/wasm_api.cpp:85 は「BrowSeg 0.1 ...」です。つまり dist は、今の書き出しソースからビルドしたものではありません（ハッシュは EXPORT_INFO と一致）。
5. 段階 B の N は、指示書の「最も大きい N」（8）ではなく、デスクトップ側の判断で 4 にしました。
6. attempt1 の 5 例通し再実行は、デスクトップ側の判断で行いませんでした。

## 中身
- `runs/<tag>/`：各タグの .json、environment.json、status.txt。DIFFERENT の .u8 も入れています。
- `logs/`：bench、serve、seq の各ログ、hashes_*.txt、kernel_*.txt（各 run の時間帯の i915/rcs0/GPU HANG 行）、time_*.txt（開始と終了の時刻、開始時の負荷）、OOM と重みキャッシュの注記。
- `scripts/`：run_igpu_v3.sh（1 項目を実行）、run_igpu_v3_seq.sh（順に実行。メモリが足りないとき・重い処理があるときは保留）、judge_igpu_v3.sh、igpu_v3_table.py、chrome_webgpu.sh、追加の計画（r2、chunk0_extra。extra は index 0 だけ実行）、bench_run.mjs と plan B の差分。
- `env_diff_attempt1_vs_v3.md`：前回 attempt1 との環境の差。

## 追加確認：lap_igpu_chunk0_3tasks（デスクトップ側の依頼 3 点。追加の計測はしていません）
### 1. 「WebGPU device lost」の行
**どこにもありません。** 次のすべてを調べました。
- bench ログ（開始行のみ）、serve ログ、status.txt
- environment.json の initLog（空）
- ircad01__total_liver.json の各 rep の `log` と `engineLog`
rep1・rep2 の log に警告はなく、gpuErrors もすべて 0 です。
唯一の警告は rep3 の「WARNING WebGPU failed (model 298 returned an all-zero result); recomputing on the CPU」です（全ゼロの検出によるもので、device lost ではありません）。

### 時刻の対応
ファイルの更新時刻と各 rep の seconds から組み立てました（JST）。
| 時刻 | 出来事 |
|---|---|
| 15:30:47 頃 | total_liver rep1 開始 |
| 15:31:10 | kernel: Fence expiration time out（chrome[54089]）← **rep1 の途中**（part の tiles 実行中） |
| 15:31:20.9 | rep1 終了（.u8 保存、33.0 秒、hash 0f03dec9） |
| 15:31:21〜22 | rep2（1.2 秒、hash 5dec9dc5） |
| 15:31:22〜15:32:18 | rep3（CPU に切り替え、56.0 秒、hash de14684e） |
| 15:32:18 | liver_segments_all rep1 開始 |
| 15:32:32 | kernel: Resetting rcs0 for preemption time out / context reset / GPU HANG ← **liver_segments の途中** |
| 15:3x | ノート側で計測を停止 |

rcs0 リセットのカーネル行が出たのは liver_segments の途中です。total_liver の rep1〜rep3 の時点で出ていたのは、Fence timeout（15:31:10）だけでした。

### 2. 各 rep の seconds と modelSeconds（engineLog の段階別時間つき）
| rep | seconds | modelSeconds | backend | engineLog の段階 |
|---|---|---|---|---|
| 1 | 33.00 | 0.647 | webgpu | crop tiles 1657 ms、**part tiles 30011 ms**、全段階あり |
| 2 | 1.23 | 0.0002 | webgpu | crop tiles 1130 ms、crop の後で終了（bbox + crop／part の段階なし） |
| 3 | 56.00 | 0.0002 | cpu (after WebGPU failure) | crop tiles 1925 ms、part tiles 52199 ms（CPU） |
| 参考：chunk0_control | 37.92 | 0.62 | webgpu | crop tiles 1845 ms、part tiles 34779 ms |
| 参考：chunk4 | 33.85 | 0.59 | webgpu | crop tiles 1605 ms、part tiles 31026 ms |

- rep2 の hash 5dec9dc5 は、**全ゼロのラベルマップ**（512×512×129 がすべて 0）の FNV-1a と一致しました（計算で確認）。
  - crop モデル（298）の結果に肝臓がなかったので、part モデルを実行せずに空のマップを返したと考えられます。
  - このとき全ゼロの検出（model 298）は働かず、rep3 で初めて働きました。
- rep1 は全段階を実行し、時間も正常な run と同程度です。それでも結果は誤っていました。
  - 保存された .u8 を correct map（chunk4 の de14684e）と比べると、3427 ボクセル差です（全 33,816,576 中）。
  - 差は 129 スライス中 74 スライス（34〜111）に広がっています。
  - 肝臓のボクセル数は、正しい値 2,842,833 に対して 2,841,892 です。
  - 見た目では分かりにくい誤差です。
  - modelSeconds は 2 回目以降はほぼ 0 で、重みは GPU に残ったままです。

### 3. hash の対応表（ircad01__total_liver）
| hash | 意味 | 出た run |
|---|---|---|
| de14684e | 正しい（desktop exact、Python と 0 ボクセル差） | 全分割 run、chunk0_control、chunk0_3tasks rep3（CPU）、前回 CPU と T1200 |
| 0f03dec9 | 誤り：3427 ボクセル差、肝臓 2,841,892 ボクセル | chunk0_3tasks rep1（webgpu、エラーなし） |
| 5dec9dc5 | 誤り：全ゼロ（空のマップ） | chunk0_3tasks rep2（webgpu、エラーなし） |

rep1 の .u8 は `runs/lap_igpu_chunk0_3tasks/ircad01__total_liver.u8` にあります（0f03dec9）。

## 追加：lap20_igpu_chunk4（20 例の本計測）
`lap20_igpu_chunk4/README.md` を見てください。結果は次のとおりです。
- 60/60 が webgpu、fallback 0、gpuErrors 0、i915 の行 0。
- WebGPU の記録との照合：MATCH 55、NONEXACT 3、DIFFERENT 2。DIFFERENT の 2 件は CPU（wasm20）の出力と同一です。
- 平均時間は CPU の約 1.67 倍の速さで、T1200 の約 8.3 倍遅いです。
