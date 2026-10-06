#!/bin/bash
# M4 LiTS (laptop part): Python TotalSegmentator 2.18 (ts218, CPU) intermediates for the 8 LiTS cases whose WebGPU output
# differed from the desktop reference, then the top-2 logits at the differing voxels (tie_check_pair / tie_check_resampled).
L=~/Documents/MyGithubProject2/BrowSeg_tools/m4_lits; D=~/Dropbox/BrowSeg_laptop/m4_lits; PY=~/anaconda3/envs/ts218/bin/python
IN=$L/data/Task03_Liver; OUT=$L/dump; mkdir -p $OUT $D/results
cd ~/Documents/MyGithubProject2/BrowSeg_v6
echo "start $(date '+%F %T')" > $L/run_lits_time.txt
while read -r f key task roi; do
  case "$f" in imagesTs/*) until grep -q '^end' $L/download_time.txt; do sleep 30; done;; esac  # Ts cases come last in the tar
  [ -f $IN/$f ] || { echo "  missing $f" >> $L/run_lits_time.txt; continue; }
  echo "$(date '+%T') $key" >> $L/run_lits_time.txt
  $PY tools/make_reference.py $IN/$f $OUT/$key cpu $task $roi > $L/make_reference_$key.log 2>&1
  echo "  exit $?" >> $L/run_lits_time.txt
done <<LIST
imagesTr/liver_15.nii.gz lits_015_seg liver_segments -
imagesTr/liver_22.nii.gz lits_022_seg liver_segments -
imagesTr/liver_92.nii.gz lits_092_seg liver_segments -
imagesTr/liver_92.nii.gz lits_092_liver total liver
imagesTr/liver_107.nii.gz lits_107_seg liver_segments -
imagesTr/liver_120.nii.gz lits_120_seg liver_segments -
imagesTr/liver_129.nii.gz lits_129_seg liver_segments -
imagesTr/liver_129.nii.gz lits_129_ves liver_vessels -
imagesTs/liver_163.nii.gz lits_163_seg liver_segments -
imagesTs/liver_185.nii.gz lits_185_seg liver_segments -
LIST
echo "dumps end $(date '+%F %T')" >> $L/run_lits_time.txt
cd $D
while read -r js dump model script; do
  $PY $script $js - $OUT/$dump $model > results/tie_laptop_${js%.json}.log 2>&1
  echo "tie $js exit $?" >> $L/run_lits_time.txt
done <<LIST
lits_015__liver_segments_all.json lits_015_seg 570 tie_check_pair.py
lits_022__liver_segments_all.json lits_022_seg 570 tie_check_pair.py
lits_092__liver_segments_all.json lits_092_seg 570 tie_check_pair.py
lits_092__total_liver.json lits_092_liver 291 tie_check_pair.py
lits_107__liver_segments_all.json lits_107_seg 570 tie_check_pair.py
lits_120__liver_segments_all.json lits_120_seg 570 tie_check_pair.py
lits_129__liver_segments_all.json lits_129_seg 570 tie_check_pair.py
lits_129__liver_vessels_all.json lits_129_ves 8 tie_check_resampled.py
lits_163__liver_segments_all.json lits_163_seg 570 tie_check_pair.py
lits_185__liver_segments_all.json lits_185_seg 570 tie_check_pair.py
LIST
echo "end $(date '+%F %T')" >> $L/run_lits_time.txt
echo FINISHED
