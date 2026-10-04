# ノート PC 計測 v4（BrowSeg_v4 = 公開版 1592427、2026-10-03）

ノート：i7-11800H、RAM 16 GB、NVIDIA T1200 Laptop（4 GB、ドライバ 550.144.03）、Intel UHD、Ubuntu 22.04、kernel 6.8.0-138。
キットは `~/Documents/MyGithubProject2/BrowSeg_v4` です。web/dist/tsc.wasm は ea687569… で EXPORT_INFO と一致しました。
重みは 8 本（298・291・292・293・294・295・570・8）と classmaps.txt で、いずれも MANIFEST の SHA-256 と一致しました。fp16 は使わないので置いていません。
手編集は bench_run.mjs の Chrome のパスだけです。v4 は Dropbox の同期が終わってから使いました（22:42 の時点では web/ と src/ がまだありませんでした）。

## 1. lap20_chrome_nv_webgpu_total（T1200、total:-、117 構造）— デスクトップ側の指示で ircad02 の後に停止
| 症例 | backend | fallback | gpuErrors | 秒 | modelSeconds | hash 照合 |
|---|---|---|---|---|---|---|
| ircad01 | cpu (after WebGPU failure) | WebGPU plan: vkAllocateMemory failed with VK_ERROR_OUT_OF_DEVICE_MEMORY - While calling [Device].CreateBuffer([BufferDescriptor]). at CheckVkOOMThenSuccessImpl (dawn/native/vulkan/VulkanError.cpp:119); split retry: 同じ | 0 | 551.2 | 4.41 | MATCH (exact)、4d27bb47 |
| ircad02 | cpu（最初から CPU。fallback 欄は空） | – | 0 | 1220.9 | 0.0002 | MATCH (exact)、582a6be8 |

- **失敗した段階**：重み 5 本（291–295、各 125 MB）の GPU への転送と pipeline の作成は成功しました。そのあと「model 291: GPU work buffers (plan)」で作業バッファを確保しようとして失敗し、分割再試行も同じ OOM で失敗しました。
- **nvidia-smi**：失敗した時点で 3888/4096 MiB 使用、ピークは 3897 MiB です。22:55 に 37 MiB へ下がりました（ircad01 の CPU 再計算中に GPU が手放されたと見ています）。記録は `logs/nvsmi_total.csv` にあります。
- ircad02 は CPU で始まり、ログは空でした。ircad01 のあと、ワーカーは CPU のままになっていました。
- カーネルの GPU 関係の行は 1 行だけでした（`nvidia 0000:01:00.0: Using 39-bit DMA addresses`、起動時の通常の行）。NVRM/Xid はありません。
- 開始前の状態：load 1.66、空き 11 GB（`logs/time_lap20_chrome_nv_webgpu_total.txt`）。

## 2. Linux の Firefox の WebGPU
- **版**：Firefox 157.0（snap、BuildID 20260925115621）。計測中に snap が 155.0 から 157.0 へ自動更新されました。
- **about:support**：画面は取れませんでした。headless のスクリーンショットは中身が空で、geckodriver からは about:support を開くことも、特権コンテキスト（snap の geckodriver が -remote-allow-system-access を渡せない）に入ることもできませんでした。代わりに、geckodriver で localhost のページを開き、navigator.gpu を直接調べました（`scripts/ffprobe.py`、結果は `logs/ff_*_probe.json`）。
  - 既定のプロファイル：`navigator.gpu` は無く、WebGPU は無効です。
  - 一時プロファイルで `dom.webgpu.enabled=true`：adapter を取得できました（maxBufferSize 2147483644、adapter.info は空）。
  - `gfx.webgpu.ignore-blocklist` は要りませんでした。
  - snap の中には /usr/share/vulkan/icd.d がありません。NVIDIA の ICD は /var/lib/snapd/lib/vulkan/icd.d/nvidia_icd.json で、VK_ICD_FILENAMES にはこのパスを使います。
  - 計測中は nvidia-smi に firefox のプロセスが出ていたので、T1200 を使っています。
- **起動方法**：bench_run.mjs の Firefox の経路（/tmp のプロファイル、Windows のパス）は、snap 版では使えません（snap は親機の /tmp が見えない）。そこで `scripts/firefox_bench.sh` を使い、$HOME の下に一時プロファイルを作って起動しました（user.js に dom.webgpu.enabled=true）。普段のプロファイルには触れていません。

### lap_firefox_nv_chunk0（分割なし）と lap_firefox_nv_chunk4（gpuchunk=4）：ircad01 × 3 タスク × reps=3
| タグ | タスク | rep 1 / 2 / 3（秒） | backend | gpuErrors | hash 照合 |
|---|---|---|---|---|---|
| chunk0 | total_liver | 64.0 / 56.5 / 55.2 | cpu | 2 | MATCH (exact) |
| chunk0 | liver_segments | 190.2 / 188.0 / 188.6 | cpu | 2 | MATCH (exact) |
| chunk0 | liver_vessels | 190.4 / 185.0 / 185.2 | cpu | 2 | MATCH (exact) |
| chunk4 | total_liver | 66.1 / 59.7 / 59.1 | cpu | 2 | MATCH (exact) |
| chunk4 | liver_segments、liver_vessels | （CPU） | cpu | 2 | MATCH (exact) |

どちらも、最初の total_liver の rep1 で次のログが出ました。
```
WebGPU uncaptured error (GPUOutOfMemoryError): Out of Memory
WebGPU uncaptured error (GPUValidationError): Validation Error / Caused by: In Queue::write_buffer / Buffer with '' label is invalid
WebGPU device lost (Out of memory); continuing with the CPU (WASM)
```
それ以降はすべて CPU です（fallback 欄は空、backend は cpu）。
- **nvidia-smi**：VRAM は 266 MiB のままで、実際に VRAM が尽きたわけではありません。Firefox（wgpu）が確保を断ったものと見ています。
- **カーネル**：両タグとも NVRM/Xid は 0 行です。**ドライバのリセット（Windows のイベント 153／TDR に相当するもの）は起きていません。**
- 分割（gpuchunk=4）でも同じでした。失敗は送信の長さではなく、バッファの確保の段階で起きています。

## ファイル
- `runs/<tag>/`：各タグの .json、environment.json、status.txt。
- `logs/`：bench、serve の各ログ、time_*（開始時の uptime・free・top）、kernel_*、nvsmi_*、hashes_*、Firefox の probe と geckodriver のログ。
- `scripts/`：run_v4.sh、run_ff_v4.sh、firefox_bench.sh、seq_firefox_v4.sh、plan_v4_total.json、chrome_webgpu.sh、ffprobe.py。
