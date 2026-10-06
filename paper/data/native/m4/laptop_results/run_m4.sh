#!/bin/bash
# Paper M4 (laptop part): dump TotalSegmentator intermediates (tools/make_reference.py, ts218, CPU) for the 4 case x task
# pairs that differed between the laptop and desktop M3 references.
T=~/Documents/MyGithubProject2/BrowSeg_tools/m4
cd ~/Documents/MyGithubProject2/BrowSeg_v6
PY=~/anaconda3/envs/ts218/bin/python
echo "start $(date '+%F %T')" > $T/run_m4_time.txt
for job in "ircad06 liver_segments" "ircad09 liver_segments" "ircad14 liver_segments" "ircad12 liver_vessels"; do
  set -- $job
  echo "$(date '+%T') $1 $2" >> $T/run_m4_time.txt
  $PY tools/make_reference.py ../BrowSeg_cases/cases/$1 $T/dump/$1_$2 cpu $2 - > $T/make_reference_$1_$2.log 2>&1
  echo "  exit $?" >> $T/run_m4_time.txt
done
echo "end $(date '+%F %T')" >> $T/run_m4_time.txt
echo FINISHED
