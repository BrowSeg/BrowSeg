#!/bin/bash
# M2 (re-measurement with the public version) on the laptop: runs plan entries one at a time with the kit's bench_run.mjs.
# GPU per entry: tag containing "igpu" -> Intel UHD, otherwise NVIDIA T1200 (BROWSEG_GPU, see chrome_webgpu.sh).
# Per run, BrowSeg_tools/m2/<tag>/ gets: env.txt (versions, power settings, load), nvsmi.csv (2 s), kernel.txt
# (journalctl -k GPU/OOM lines for the run window), bench.log, serve.log, and a copy of the result folder.
# usage: run_m2.sh <kit dir> <plan.json> [index ...]   (no index = all entries; run under systemd-inhibit)
KIT=$(realpath "$1"); PLAN=$(realpath "$2"); shift 2
T=~/Documents/MyGithubProject2/BrowSeg_tools; CASES=~/Documents/MyGithubProject2/BrowSeg_cases/cases
N=$(python3 -c "import json; print(len(json.load(open('$PLAN'))))")
IDX=${@:-$(seq 0 $((N-1)))}
cd "$KIT"
for i in $IDX; do
  TAG=$(python3 -c "import json; print(json.load(open('$PLAN'))[$i]['tag'])")
  L=$T/m2/$TAG; mkdir -p $L
  case "$TAG" in *igpu*) GPU=intel;; *) GPU=nv;; esac
  python3 -c "import json; json.dump([json.load(open('$PLAN'))[$i]], open('$L/one.json','w'))"
  {
    echo "tag $TAG  gpu $GPU  kit $KIT ($(git -C "$KIT" log -1 --format='%h %ci' 2>/dev/null))"
    echo "tsc.wasm sha256 $(sha256sum web/dist/tsc.wasm | cut -c1-64)"
    echo "chrome: $(google-chrome --version)"; echo "uname: $(uname -r)"
    echo "nvidia: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader)"
    echo "mesa: $(dpkg-query -W -f='${Version}' mesa-vulkan-drivers)"
    echo "i915 rcs0 preempt_timeout_ms $(cat /sys/class/drm/card*/engine/rcs0/preempt_timeout_ms) heartbeat_interval_ms $(cat /sys/class/drm/card*/engine/rcs0/heartbeat_interval_ms)"
    echo "AC online: $(cat /sys/class/power_supply/A*/online)  power profile: $(powerprofilesctl get 2>/dev/null)  governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
    echo "gnome sleep-inactive-ac: $(gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 2>/dev/null) after $(gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 2>/dev/null) s; idle-delay $(gsettings get org.gnome.desktop.session idle-delay 2>/dev/null)"
    echo "inhibitors:"; systemd-inhibit --list --no-pager 2>/dev/null | grep -i -E "browseg|sleep|lid" | head -5
    echo "load at start:"; uptime; free -h; top -bn1 -o %CPU | sed -n 7,12p
  } > $L/env.txt 2>&1
  node serve.mjs 8090 --bench "$CASES" --out paper/data/browser > $L/serve.log 2>&1 & SRV=$!; sleep 2
  nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total,clocks.sm,power.draw,temperature.gpu,clocks_throttle_reasons.active --format=csv -l 2 > $L/nvsmi.csv 2>&1 & NV=$!
  START=$(date '+%Y-%m-%d %H:%M:%S'); echo "start $START" >> $L/env.txt
  BROWSEG_GPU=$GPU node paper/scripts/bench_run.mjs paper/data/browser $L/one.json 2>&1 | tee $L/bench.log
  echo "end $(date '+%Y-%m-%d %H:%M:%S')" >> $L/env.txt
  pkill -f browseg_bench_profiles; sleep 5
  kill $SRV $NV 2>/dev/null
  journalctl -k --since "$START" --until "$(date '+%Y-%m-%d %H:%M:%S')" | grep -i -E "i915|rcs0|GPU HANG|NVRM|Xid|oom|killed process" > $L/kernel.txt
  cp -a paper/data/browser/$TAG $L/result 2>/dev/null
  echo "FINISHED $TAG (kernel lines: $(wc -l < $L/kernel.txt))"
done
echo ALLDONE
