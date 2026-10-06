# M4 LiTS（不一致 10 件の Python 版ロジット確認）ノート側 完了報告 — 2026-10-06

## データ（A-1）
- MSD Task03_Liver：https://msd-for-monai.s3-us-west-2.amazonaws.com/Task03_Liver.tar（28,925,891,584 B、Last-Modified 2020-08-14）。
- tar は保存せずに流しながら、8 例だけを取り出しました（ノートの空き容量のため。転送は 28.9 GB）。20:57:15〜22:13:12、curl・tar とも終了コード 0。
- 8 例とも、バイト数がデスクトップと一致しました（liver_15 208342476、22 67855809、92 267170369、107 239400185、120 140209744、129 135981386、163 173029778、185 208071903）。
- 入力ファイルの SHA-256 は results/lits_inputs_sha256.txt にあります。

## 途中出力（A-2）
- conda ts218、CPU、BrowSeg_v6/ で tools/make_reference.py に NIfTI をそのまま渡しました。NIfTI の入力で問題なく動きました。
- 10 本すべて終了コード 0。21:57:04〜22:22:04（各本の時刻は results/run_lits_time.txt）。
- 環境：
```
torch 2.11.0+cpu | cuda available False | threads 8 | cpu capability AVX512 | TotalSegmentator 2.18.0 | nnunetv2 2.7.0
['Intel(R) oneAPI Math Kernel Library Version 2024.2-Product Build 20240605 for Intel(R) 64 architecture applications']
```
  OMP_NUM_THREADS・MKL_NUM_THREADS は指定なし。GPU は使っていません。send_usage_stats は変えていません。
- 途中出力（ロジットを含む）はノートの BrowSeg_tools/m4_lits/dump/ に残してあります（送っていません）。

## ロジットの確認（A-3、ログは results/tie_laptop_<key>.log）
A＝デスクトップの TS 2.18 CPU の参照、B＝BrowSeg WebGPU（デスクトップの Chrome）。ロジットはノートの Python 版（fp16）です。
| key | 不一致ボクセル | 近くの格子点で最も小さい上位 2 つの差 |
|---|---|---|
| lits_015 liver_segments | 3 | (61,155,89) で 2 対 1 が 1 ulp。(215,197,89) で 4 対 8 が **0 ulp**（3 つ目のボクセルも同じ格子点の近く） |
| lits_022 liver_segments | 1 | (183,186,81) と (184,187,81) で 4 対 8 が 1 ulp |
| lits_092 liver_segments | 2 | (120,183,103) で 2 対 0 が 1 ulp（2 つ目のボクセルも同じ格子点の近く） |
| lits_092 total（liver、model 291） | 8（2×2×2 の塊） | (81,80,76) で 0 対 5 が **0 ulp**（8 ボクセルとも格子点 80〜81 × 79〜80 × 75〜76 の範囲） |
| lits_107 liver_segments | 2 | (51,180,111) で 2 対 0 が 1 ulp |
| lits_120 liver_segments | 2 | (183,56,132) で 0 対 7 が **0 ulp** |
| lits_129 liver_segments | 2 | (231,217,78) で 4 対 8 が **0 ulp** |
| lits_129 liver_vessels（model 8、tie_check_resampled） | 1 | consistency 0 ボクセル（再現できた）。crop (115,261,111) で 2 = 2.910156 対 0 = 2.908203、**1 ulp** |
| lits_163 liver_segments | 1 | (156,130,74) で 0 対 1 が **0 ulp** |
| lits_185 liver_segments | 2 | (286,28,73) で 0 対 7 が **0 ulp** |

**10 件・24 ボクセルとも、対応する格子点の近傍に、上位 2 構造の差が 0〜1 fp16-ulp の点がありました。** IRCAD の M3・M4 と同じ見え方です。

## ノートの Python 版はどちら側か、と final の SHA-256（A-4、results/side_and_sha256_laptop.txt）
| key | ボクセル | ノートの final が同じ側 | final（canonical uint8）の SHA-256 |
|---|---|---|---|
| lits_015 liver_segments | 3 | A A A | a0cdb4c9ec1c893d211d3a3250597259195f593fb19d464b4a55ca0d04b38fa3 |
| lits_022 liver_segments | 1 | A | e6d358f5cededc050ca1689f7c844f99c1f931c33f6f8476b1d591f455835c60 |
| lits_092 liver_segments | 2 | A A | e9e0bab06bafb9226327245930b069a69930dbbae332a48df2cf76670f9d2b68 |
| lits_092 total liver | 8 | **B** × 8 | 13c6f917d49b60b87f3a843c228ccb068704f6119eb3f7fbb29522f95d44fa0f |
| lits_107 liver_segments | 2 | **B B** | 27c2ec24a85becad605429be01a24d05a8d9e106dbf6f3b5b83cc22b2f62e591 |
| lits_120 liver_segments | 2 | **B B** | 0cd96cf68c34c2c32778d341b07ccf51ac96c3145bd221b1887005dda2cc51e0 |
| lits_129 liver_segments | 2 | **B B** | 26fd833aa78bd1f8b4c3585f9a1e98e135ccdca6463fe2a73f4744277e15ebc1 |
| lits_129 liver_vessels | 1 | **B** | 9a7746b64b4d2fbbe6acc7012cfe3ae1a887ad91c10cd7c24e76bfae2ac95826 |
| lits_163 liver_segments | 1 | A | 8fa9d840fcba0303e57d441ad98b08480b3b8317de21ff31acc5353d689477d5 |
| lits_185 liver_segments | 2 | **B B** | 4ab238133b596a33be7bed10c7abef60bf233c7834824e8094897fc23bc0fb46 |

計：24 ボクセル中、ノートの Python 版はデスクトップの参照（A）と同じ側が 7、BrowSeg WebGPU（B）と同じ側が 17、どちらでもないものは 0。
6 件（lits_092 total、107、120、129 ×2、185）では、**ノートの Python 版自身がデスクトップの Python 版と違い、WebGPU と同じ側**になっています。差は同点の点の向きだけで、Python 版どうしでも、0〜1 ulp の点はどちらにも倒れるということです。
final の全体の SHA-256 は、デスクトップの参照と照合するためのものです（ここで違う key は、上の B 側のボクセルの分だけ違うはず）。
