# ノート PC 20 例の計測（2026-09-30、Ubuntu 22.04、Chrome 142、NVIDIA T1200、前回と同じ書き出し版・ラッパー）

| タグ | 用途 | 説明 |
|---|---|---|
| lap20_chrome_nv_webgpu | 本文に使う | 02:16〜03:09。20 例 × 3 タスク × 3 回。fallback 0。2〜3 回目の差が 3% を超えたのは 2 件（ircad13 肝区域、ircad10 肝臓） |
| lap20_chrome_nv_st_webgpu_r2 | 本文に使う | 09:04〜10:00。静かな状態（直前の負荷は pre_st_r2_load.txt）。差が 3% を超えた件は 0。前回の 5 例と同じ症例での比は中央値 1.002 |
| lap20_chrome_nv_st_webgpu | 記録のみ | 04:01〜04:58。サスペンド後に測り直した回。計測中、ユーザーの Chrome のタブが CPU を約 25% 使っていた。r2 より中央値で約 2%、最大で約 9% 遅い。差が 3% を超えた件は 5 |
| lap20_chrome_nv_st_webgpu_interrupted_suspend | 記録のみ | 03:09〜03:40。ノートのふたが閉じられてサスペンドし、ircad12 で中断した（34/60 件、suspend_journal_excerpt.txt）。以降の計測は systemd-inhibit（sleep:handle-lid-switch）の下で実行 |
| lap20_chrome_wasm | 本文に使う | 04:58〜09:03。20 例 × 3 タスク × 1 回。肝区域 / 肝内血管の時間の比は、ircad03（1.08）と ircad06（1.06）以外は 1.00±0.02 |
| lap20_chrome_wasm_r2_ircad03_06 | 記録（再計測） | 10:01〜10:22。ircad03 と ircad06 だけ再計測した（比は 1.00 / 1.00、元の値より最大 11% 速い）。ハッシュは元と同一 |

- ハッシュ照合: hashes_check_lap20.txt。WebGPU と st は desktop_hashes.json、WASM は desktop_hashes_wasm20.json と照合した。DIFFERENT と NO-DESKTOP-ENTRY はどのタグにもないので、.u8 は同梱していない。
- GPU の記録: lap20_logs/nvsmi_*.csv（10 秒ごと）。ほかに実行スクリプト、計画（plan_laptop20.json）、ログも lap20_logs/ に入れた。
- 旧 5 例の lap_chrome_wasm は、計測中の負荷で ircad01・02・18 が 1.5〜2.2 倍に遅くなっていた。本文では使わない。
