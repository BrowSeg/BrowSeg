# M3 完了報告（ノート PC、2026-10-06）

**状態：完了。** 20 例 × 3 タスク = 60 組すべてそろいました。終了コード 0、カーネルの OOM 行は 0、ログのエラー・警告も 0 です。

## ファイル
| ファイル | 内容 |
|---|---|
| `ts218_cpu_laptop.tar.gz` | 6,303,520 B。SHA-256 `55abce913b6409add3880aa50747dc55e9048550e9da5c0a9417566f600d5f4a`（`ts218_cpu_laptop.tar.gz.sha256` にもあります） |
| tar.gz の中身（131 項目） | `ts218_cpu_laptop/`：`<case>__<task>_<roi>.npy` × 60、`.json` × 60、`times.tsv`（key・秒・ラベル）、run_m3.sh、run_m3.log、run_m3_time.txt（開始・終了・開始時の uptime と free）、run_m3_kernel.txt（OOM 行。空）、laptop_run_environment.txt、laptop_ts218_pip_freeze.txt、laptop_torch_config.txt、laptop_lscpu.txt、weights_sha256_laptop.txt |
| `laptop_run_environment.txt` | 実行環境の記録（下記の要約と同じもの。tar.gz の外にも置きました） |

展開して照合する例：`sha256sum -c ts218_cpu_laptop.tar.gz.sha256 && tar xzf ts218_cpu_laptop.tar.gz`

## 実行
- 時刻：2026-10-06 17:10:22 〜 18:53:06 JST（1 時間 43 分）。計算時間の合計は 102.1 分です。
- 実行の許可：著者が、ノートの画面で「OK」と指示しました（17:10）。デスクトップの GO メッセージ（17:15）は、開始の後に届きました。中身は同じ指示です。
- コマンド（conda 環境 ts218、`BrowSeg_v6/` で実行）：
  `python paper/scripts/make_refs.py ../BrowSeg_cases/cases <out> cpu "total:liver;liver_segments:-;liver_vessels:-"`
- systemd-inhibit の下、AC 電源接続で実行しました。
- 開始時の状態：load 1.03、空きメモリ 9 GB（開始直後に Chrome の BrowSeg タブを閉じたため、9.5 GB まで増えました）、ほかの重い処理はなし。
- GPU：torch は 2.11.0+cpu（CUDA のビルドなし、cuda available False）で、device="cpu" です。GPU の経路はありません。
- send_usage_stats は変えていません（true のまま）。

## 環境（要約）
| 項目 | 値 |
|---|---|
| OS | Linux 6.8.0-138-generic（Ubuntu 22.04.5） |
| CPU | Intel Core i7-11800H（8 コア 16 スレッド、AVX-512：f、cd、bw、dq、vl、ifma、vbmi、vbmi2、vnni、bitalg、vpopcntdq、vp2intersect） |
| Python / TotalSegmentator / nnunetv2 | 3.11.15 / 2.18.0 / 2.7.0 |
| torch / numpy | 2.11.0+cpu / 2.4.4 |
| torch の CPU capability | **AVX512** |
| MKL / oneDNN | **2024.2** / 3.10.2 |
| 並列処理 | OpenMP 4.5（201511）、torch・OMP・MKL とも 8 スレッド。環境変数 OMP_NUM_THREADS・MKL_NUM_THREADS は指定なし（既定のまま） |
| resampling_order | 1（json に記録） |
| 重み | 291・298・570・008 とも SHA-256 がデスクトップと一致（weights_sha256_laptop.txt） |

デスクトップ（AVX2、MKL 2025.3、MSVC の OpenMP）との違いは、AVX-512 だけではありません。MKL・OpenMP・コンパイラも違います。論文では「Linux＋AVX-512 と Windows＋AVX2 の参照の差」と書く方針、と合意済みです。

## 結果の概要（ノート側で見た範囲。ボクセルの照合はデスクトップで）
| タスク | 件数 | 平均（秒） | 最小〜最大（秒） | 出たラベル |
|---|---|---|---|---|
| total roi=liver | 20 | 49.1 | 35.1〜70.4 | 5 |
| liver_segments | 20 | 126.5 | 73.8〜194.2 | 1〜8（全例） |
| liver_vessels | 20 | 130.6 | 75.5〜195.4 | 1・2、または 1 のみ（例ごとに times.tsv を参照） |

liver_vessels でラベル 1 だけ（腫瘍のラベル 2 がない）の症例は、ircad05・ircad11・ircad12・ircad20 の 4 例です。これらはノート側では異常と判断していません。デスクトップの参照と同じかどうかは、照合で確かめてください。

## 追記：デスクトップでの照合結果（デスクトップのセッションから受け取った値）
デスクトップの参照（data/bench_refs/ts218_cpu）とボクセル単位で比べた結果です。
- **60 組中 56 組が完全一致。** 残りの 4 組は 1〜2 ボクセル差：ircad06・09・14 の liver_segments と、ircad12 の liver_vessels。
- liver_vessels で腫瘍（ラベル 2）が 0 の 4 例（ircad05・11・12・20）は、デスクトップでも 0 で、一致しました（モデルの出力）。
- 肝臓の量に問題はありません。M3 は完了です。
