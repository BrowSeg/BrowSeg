# M4（ロジット追跡）ノート側 完了報告 — 2026-10-06

## 実行
- 時刻：2026-10-06 19:21:23 〜 19:31:14 JST（途中出力の取得、4 組。各組の時刻は results/run_m4_time.txt）。tie_check_pair.py はそのあとに実行しました。
- 環境（conda ts218、CPU、BrowSeg_v6/ で tools/make_reference.py）：
```
torch 2.11.0+cpu | cuda available False | threads 8 | cpu capability AVX512
TotalSegmentator 2.18.0 | nnunetv2 2.7.0
['OpenMP 201511 (a.k.a. OpenMP 4.5)', 'Intel(R) oneAPI Math Kernel Library Version 2024.2-Product Build 20240605 for Intel(R) 64 architecture applications']
```
- OMP_NUM_THREADS・MKL_NUM_THREADS は指定なし（既定のまま）。GPU は使っていません（torch は +cpu）。send_usage_stats は変えていません。
- 入力は M3 と同じ DICOM のフォルダ（BrowSeg_cases/cases/<case>）です。
- 途中出力（ロジットの .npy など）は、ノートの BrowSeg_tools/m4/dump/ に残してあります（送っていません）。

## 一貫性の確認（手順 2）
各 final_*.nii.gz を canonical にした配列は、M3 の ts218_cpu_laptop/<key>.npy と **4 組とも完全一致（IDENTICAL）** でした。

## 追跡の結果（手順 3、ログは results/tie_laptop_<case>_<task>.log）
A＝デスクトップの参照、B＝ノートの M3。ロジットはノートの途中出力（fp16）です。
| 症例・タスク | 差のあるボクセル（orig、canonical） | A→B | 近くの格子点のノートのロジット |
|---|---|---|---|
| ircad06 liver_segments | (422,182,100) | 0→7 | 格子 [233.87, 54.42, 79.82]。近傍 8 点のうち (234,54,80) が **差 0.0078 = 1 fp16-ulp**（7 対 0）。ほかは 132〜1076 ulp |
| ircad09 liver_segments | (399,250,56) | 8→5 | 格子 [235.73, 125.85, 75.01]。(236,126,75) が **差 0 = 0 ulp**（5 対 8 が同点）。z=75 の層は 5 が最大（54〜62 ulp）、z=76 の層は 8 が最大（669〜713 ulp） |
| ircad14 liver_segments | (295,267,65) | 0→1 | 格子 [168.99, 128.87, 69.64]。(169,129,70) が **1 ulp**（1 対 0）、(169,129,69) が 37 ulp |
| ircad14 liver_segments | (389,160,53) | 6→0 | 格子 [253.04, 33.11, 56.79]。(253,33,57) が **0 ulp**（0 対 6 が同点）、(254,34,56) が 8 ulp |
| ircad12 liver_vessels | 1 ボクセル（座標は出る前に停止） | – | **未解析**。下記 |

肝区域の 3 例（差 4 ボクセル）は、どれも対応する格子点の近傍に、上位 2 つの差が 0〜1 fp16-ulp の点がありました。デスクトップ側の ircad14 の結果（0 ulp と 1 ulp）と同じ傾向です。

## ircad12 liver_vessels（モデル 8）：格子が合わず未解析
tie_check_pair.py が次で止まりました：`AssertionError: ((3, 164, 225, 294), (345, 265, 246))`（ロジット (C,z,y,x) と 8_seg の形が対応しない）。指示どおり、直さずに情報だけ記録します。
- 8_in.nii.gz：形 (345, 265, 246)、zooms (0.6797, 0.6797, 1.0) mm。TS はこのタスクでは、nnU-Net に入れる前にモデルの spacing へ再サンプリングしていません。crop_bbox は [[48,393],[137,402],[14,260]]、addon 20。
- 8_props.json：spacing [1.0, 0.6797, 0.6797]（z,y,x）、shape_after_cropping_and_before_resampling [246, 265, 345]。
- plans（Dataset008、3d_fullres）：spacing [1.5, 0.7988, 0.7988]、resampling_fn_data_kwargs {order 3, order_z 0, force_separate_z None}。
- ロジットの形 (164, 225, 294) は、nnU-Net の中でモデルの spacing に再サンプリングした格子（246×1.0/1.5＝164、265×0.6797/0.7988≒225.5、345×0.6797/0.7988≒293.6）と一致します。
- このため 8_seg は、ロジットの argmax を元の格子へ戻したもの（予測は xy order 3・z order 0 で補間）です。1 つのロジットの格子点と対応づけるには、nnU-Net の逆再サンプリングを再現する必要があります。tie_check_pair.py の対応式（crop の格子と格子の比）は、このタスクには当てはまりません。

## 追記：ircad12 liver_vessels（モデル 8）— tie_check_resampled.py（19:34）
ログ：`results/tie_laptop_ircad12_liver_vessels_resampled.log`
- nnU-Net 自身の resampling_fn_probabilities（plans：order 1、order_z 0、force_separate_z None）で、ロジット (3,164,225,294) fp16 を crop 格子 (246,265,345) に戻しました。
- **consistency：argmax(back-resampled) と 8_seg.nii.gz の差は 0 ボクセル**（再現できた）。
- 差のあるボクセル：orig (370,234,219)、A（デスクトップ）=1、B（ノート）=0 → crop 格子 (251,97,205)。整数の格子点に写りました。
  - ノート：**背景（0）= 3.423828、ラベル 1 = 3.423828、差 0（0 ulp、fp16 で同点）**。argmax は 0（同点のときは先頭の背景が選ばれる）で、seg も 0。
  - デスクトップ（受け取った値）：ラベル 1 = 3.423828、背景 = 3.421875、差 1 ulp。
  - つまり、同じ格子点で、デスクトップは 1 ulp の差でラベル 1、ノートは 0 ulp の同点で背景になりました。上位 2 つが 0〜1 ulp で入れ替わったものです。
- 補足：plans の読み込みのとき、nnU-Net が「Detected old nnU-Net plans format」の警告を出しました（計算には影響なし。consistency は 0）。

## まとめ（4 組・5 ボクセル）
ノートとデスクトップで違った 5 ボクセルは、すべて上位 2 つのロジットが 0〜1 fp16-ulp の点で起きていました（肝区域 4 ボクセルはノートとデスクトップの両方で確認、肝内血管 1 ボクセルは逆再サンプリング後の crop 格子で確認）。
