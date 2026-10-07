# M2 ノート側 完了報告（2026-10-07）

## 版と環境
- キット：公開リポジトリ 7ee2d83（bundle の main、タグ paper-v1-candidate）を BrowSeg_public で checkout。tsc.wasm は ea68756971adc3c2…、dist-st は 054fd0f419398aad…。
- 重み：8 本と classmaps.txt を v6 から入れ、MANIFEST の SHA-256 とすべて一致。手編集は bench_run.mjs の 13 行目、Chrome のパスだけ。
- 計測の条件：Chrome 142.0.7444.175（apt）。uaFull は fullVersionList に記録されるが、Linux では platformVersion が空。
- ノートの環境：kernel 6.8.0-138、NVIDIA T1200（550.144.03）、Intel UHD（Mesa 23.2.1、i915 は preempt 7500 ms・heartbeat 2500 ms）。
- 電源と省電力：AC、power profile balanced、governor powersave、systemd-inhibit（sleep:handle-lid-switch）。各 run の env.txt に記録。
- 実行：`BrowSeg_tools/run_m2.sh <キット> plan_v3_laptop.json`（各タグの env.txt・nvsmi.csv（2 秒ごと）・kernel.txt・bench.log・serve.log を記録）。

## 結果
| タグ | 時刻 | run 数 | backend | fallback / gpuErrors | kernel の行 | 照合 |
|---|---|---|---|---|---|---|
| v3_lap_nv_webgpu_cold | 00:14 | 1 | webgpu（turing） | 0 / 0 | 0 | MATCH（de14684e）、6.0 秒 |
| v3_lap_nv_webgpu | 00:14〜01:07 | 180 | webgpu（turing） | 0 / 0 | 0 | desktop_hashes：MATCH 57、NONEXACT 3（ircad14・16・18 の seg） |
| v3_lap_nv_st_webgpu | 01:07〜02:03 | 180 | webgpu（turing、dist-st、1 スレッド） | 0 / 0 | 0 | MATCH 57、NONEXACT 3（同じ 3 件） |
| v3_lap_wasm | 02:03〜06:07 | 60 | cpu | 0 / – | 0 | desktop_hashes_wasm20：MATCH 55、NONEXACT 5（05 seg、12 ves、16 seg、18 seg、20 liver） |
| v3_lap_igpu_webgpu | 06:07〜08:30 | 60 | webgpu（gen-12lp、「network submitted in parts of 4 steps」） | 0 / 0 | 0（i915 のリセットなし） | desktop_hashes：MATCH 55、NONEXACT 3、DIFFERENT 2（ircad05 seg＝c89697ef、ircad20 liver＝54816bfc。どちらも desktop_hashes_wasm20 の CPU の hash と、前回の lap20_igpu_chunk4 と同一） |
| v3_lap_wasm_r2_ircad05_06 | 08:30〜09:06 | 6 | cpu | 0 / – | 0 | wasm20：MATCH 5、NONEXACT 1（05 seg） |

**出力は、すべてのタグで前回のノートの計測と同じ型でした。** 照合で一致・不一致になった組が同じで、DIFFERENT の hash も同一です。

## wasm の時間の乱れの確認（区域と血管の時間の比）
| 症例 | v3_lap_wasm（区域 / 血管、比） | 取り直し r2 | 参考：lap20_chrome_wasm（9/30） | 参考：lap20 r2 |
|---|---|---|---|---|
| ircad05 | 544.5 / 532.4、1.023 | 530.6 / **577.5、0.919** | 567.1 / 580.3、0.977 | – |
| ircad06 | 417.9 / 401.8、1.040 | 419.6 / 422.9、**0.992** | 422.2 / 397.4、1.062 | 397.3 / 398.1、0.998 |
- ircad06：取り直しで比が 0.992 になり、乱れは解消しました。取り直しの値を使ってください。
- ircad05：取り直しでは血管が 577.5 秒と長くなり、比が 0.919 と、逆向きに外れました。ircad05 は 3 回の計測で、区域が 530〜567 秒、血管が 532〜580 秒とばらつきます。この症例はもともと時間が安定しない可能性があります（理由は未確認）。
- 取り直しの実行中に、ノートで行った操作は進み具合の確認（短いコマンド）だけで、ほかの重い処理はありませんでした。ircad05 の扱い（どちらの値を使うか、もう 1 回取るか）は、そちらで判断してください。

## ファイル（results/<tag>/）
- 各ケースの .json、environment.json、status.txt
- env.txt、kernel.txt、nvsmi.csv、bench.log、serve.log、hashes.txt
- `<tag>_u8.tar.gz`（そのタグの .u8 すべて）と `<tag>_u8.tar.gz.sha256`
- 直下：run_m2.sh、plan_v3_laptop.json、plan_v3_lap_wasm_r2.json
