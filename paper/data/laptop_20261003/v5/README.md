# ノート PC 計測 v5：117 構造の再挑戦（T1200、2026-10-04）

キットは BrowSeg_v5 です（EXPORT_INFO：TSC++Project 22f94cc。web/dist/tsc.wasm は v4 と同じ ea687569…。違いは worker.js・bench.html・bench_run.mjs）。
**BROWSEG_COMMIT.txt は v5 に入っていませんでした**（v4 にはありました）。重みは 8 本と classmaps.txt で、MANIFEST と一致しました。手編集は bench_run.mjs の Chrome のパスだけです。

## lap_chrome_nv_total_v5_auto：ircad01・ircad02 × total:- × reps=1、既定の設定
| 症例 | backend | gpuErrors | 秒 | 照合 |
|---|---|---|---|---|
| ircad01 | cpu (after WebGPU failure) | 201 | 562.8 | MATCH (exact)、4d27bb47 |
| ircad02 | cpu（最初から CPU。log は空） | 201（ircad01 からの持ち越し） | 1199.5 | MATCH (exact)、582a6be8 |

ircad01 の流れ（`runs/.../ircad01__total_all.json` の log）：
1. 重み 5 本（291–295）を GPU に転送 → model 291 の作業バッファ（plan）で VK_ERROR_OUT_OF_DEVICE_MEMORY。
2. 「WARNING WebGPU ran out of GPU memory …」→ **low-memory mode** に切り替え（ログ「kept in memory (low-memory mode: one model on the GPU at a time)」× 5）。
3. low-memory mode でも、CreateBuffer の VK_ERROR_OUT_OF_DEVICE_MEMORY と、それに続く「WriteBuffer([Invalid Buffer])」の検証エラーが続きました（gpuErrors 201。21 件目以降は記録されていません）。
4. 「WARNING WebGPU failed (…; GPU retry: …)」→ CPU で再計算。
- **「new device」の行はありません。** device lost が起きなかったので、開き直しの経路には入っていません。
- **nvidia-smi**（2 秒ごと、`logs/nvsmi_lap_chrome_nv_total_v5_auto.csv`）：
  - 00:07:03 に 2693 MiB、00:07:11 に 3894 MiB、ピークは 3897 MiB。
  - **00:16:23（ircad01 の終わり）まで約 3.89 GB のまま**でした。
  - つまり、low-memory mode で再試行した時点でも、最初の試行の重み 5 本（と作業バッファ）が GPU から解放されていなかったように見えます。
  - そのあと 41〜72 MiB に下がり、ircad02 は GPU を使っていません。
- カーネル：NVRM/Xid は 0 行です。
- 開始前の状態：load は高め（直前の Firefox の CPU 実行の名残、1 分平均 12）、空き 11 GB、ほかの重い処理なし。

**判定：backend は webgpu にならなかったので、手順 2（lap20_chrome_nv_webgpu_total_lowmem）は流していません。**

## ファイル
`runs/lap_chrome_nv_total_v5_auto/`（.json、environment.json、status.txt）、`logs/`（bench、serve、time、kernel、nvsmi、hashes）、`scripts/`（run_v5.sh、plan_v5_auto.json、chrome_webgpu.sh）。
