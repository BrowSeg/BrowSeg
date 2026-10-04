#!/bin/bash
# Runs entries of a plan one after another (PLAN env, default stage A); skips the rest if memory is short or another big job runs.
T=~/Documents/MyGithubProject2/BrowSeg_tools
for i in "$@"; do
  av=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
  big=$(ps -eo rss=,comm= | awk '$1>3000000 && $2!="chrome"{print $2}' | head -1)
  if [ "$av" -lt 8 ] || [ -n "$big" ]; then echo "HOLD before index $i: avail ${av}GB big=$big"; exit 2; fi
  cd ~/Documents/MyGithubProject2/BrowSeg_v3
  $T/run_igpu_v3.sh ${PLAN:-paper/scripts/plan_laptop_igpu_A.json} $i
  TAG=$(python3 -c "import json; print(json.load(open('${PLAN:-paper/scripts/plan_laptop_igpu_A.json}'))[$i]['tag'])")
  $T/judge_igpu_v3.sh $TAG
done
echo ALLDONE
