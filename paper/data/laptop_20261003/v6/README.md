# ノート PC 計測 v6：117 構造を T1200（4 GB）の GPU で（2026-10-04）

キットは BrowSeg_v6（BROWSEG_COMMIT d4a13bb）です。v5 との違いは worker.js と gpu_unet.js だけで、wasm は ea687569（同じ）です。
重みは 8 本と classmaps.txt で、MANIFEST と一致しました。手編集は bench_run.mjs の Chrome のパスだけです。
計測は NVIDIA T1200 Laptop（4 GB、ドライバ 550.144.03）、Chrome 142.0.7444.175 で、systemd-inhibit の下、電源接続で行いました。

## 1. lap_chrome_nv_total_v6_auto（ircad01、既定の設定）：**GPU のまま完走しました**
- backend「webgpu (low-memory mode after out of memory)」、**64.5 秒**（v5・v4 では CPU になり 551〜563 秒）、gpuErrors 0、hash 4d27bb47、**MATCH (exact)**。
- fallback 欄には最初の OOM の文面が残るので、hashes.py は「CPU-FALLBACK x1」と表示します。**実際の計算は GPU（low-memory mode）です。**
- ログの流れ：
  1. 重み 5 本を GPU に転送 → `model 291: GPU memory weights 119 MiB, work buffers 1432 MiB, accumulation 500 MiB` → VK_ERROR_OUT_OF_DEVICE_MEMORY。
  2. `WebGPU device lost (Device was destroyed.); continuing with the CPU (WASM)`（自分で device を閉じたときにも、この文面が出ます）。
  3. `WebGPU: new device opened for the retry`
  4. `WARNING WebGPU ran out of GPU memory …` → `kept in memory (low-memory mode: one model on the GPU at a time)` × 5。
  5. low-memory mode の各モデルの GPU メモリ：

     | モデル | weights（MiB） | work buffers（MiB） |
     |---|---|---|
     | 291 | 119 | 1432 |
     | 292 | 119 | 1464 |
     | 293 | 119 | 1336 |
     | 294 | 119 | 1416 |
     | 295 | 119 | 1464 |
- nvidia-smi（2 秒ごと）：
  - 最初の試行：2709 MiB → 3895 MiB（ピーク、00:40:55）
  - device を閉じた直後：77 MiB（00:40:59）
  - low-memory mode 中：1394〜1466 MiB
  - 終了後：5 MiB
- カーネルに NVRM/Xid の行はありません。

## 2. lap_chrome_nv_total_v6_lowmem（gpulowmem=1、ircad01..20 × total:- × reps=1）
- 実行：00:42:25〜01:10:57（28.5 分）。開始時の load 0.52、空き 11 GB。
- **20/20 が backend webgpu で、fallback なし、gpuErrors 0。** カーネルに NVRM/Xid の行は 0 です。nvidia-smi のピークは **1470 MiB** でした。
- desktop_hashes.json との照合：**MATCH (exact) 17、SAME-AS-DESKTOP-NONEXACT 2**（ircad04・ircad05、各 4 ボクセル。デスクトップ自身と同じ）、**DIFFERENT 1**（ircad07）。
  - ircad07 の hash 7637ac05 は、デスクトップの CPU 記録 desk_chrome_wasm_total_20 と、desk_firefox_webgpu_total_final の hash と同じでした。デスクトップの Chrome WebGPU（8b26ab35、exact）とは違います。
  - デスクトップの .u8 が手元にないので、ボクセル差は数えていません。ノートの .u8 は `runs/lap_chrome_nv_total_v6_lowmem/ircad07__total_all.u8` にあります。
- 時間：合計 28.1 分、1 例あたり平均 84.3 秒です（症例ごとの値は `times_lap_chrome_nv_total_v6_lowmem.md`）。
  - 小さい症例：約 47〜52 秒（デスクトップの WebGPU は約 9 秒、CPU は約 145〜161 秒）
  - 大きい症例：約 98〜101 秒（デスクトップの WebGPU は約 18 秒、CPU は約 323 秒）
  - 最大の症例（ircad19・20）：約 149〜150 秒
  - 時間の大部分は part tiles（GPU）です。modelSeconds は ircad01 だけ 0.75 秒で、ほかはほぼ 0 です。

## ファイル
- `runs/<tag>/`：.json、environment.json、status.txt、ircad07 の .u8
- `logs/`：bench、serve、seq の各ログ、time（開始時の uptime・free・top）、kernel、nvsmi、hashes
- `scripts/`：run_v6.sh、plan_v6_auto.json、plan_v6_lowmem.json、chrome_webgpu.sh

追記（デスクトップ側から）：ircad07 の hash 7637ac05 は CPU の記録と同じで、Python 参照との差は 2 ボクセルです（デスクトップで数えた値）。
