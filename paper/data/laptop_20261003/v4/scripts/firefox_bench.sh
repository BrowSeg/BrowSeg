#!/bin/bash
# Firefox (snap) bench run outside bench_run.mjs: a throw-away profile under $HOME (snap Firefox cannot see the
# host /tmp) with dom.webgpu.enabled, one plan entry, waits for DONE/ERROR in status.txt, then closes that Firefox.
# usage: firefox_bench.sh <tag> <query> <timeoutMin>      (BROWSEG_GPU=nv selects the NVIDIA Vulkan ICD)
cd ~/Documents/MyGithubProject2/BrowSeg_v4
T=~/Documents/MyGithubProject2/BrowSeg_tools; L=$T/v4; mkdir -p $L
TAG=$1; Q=$2; TMO=${3:-60}
P=$(mktemp -d $T/ff_profile_${TAG}_XXXX)  # fresh throw-away profile per run (nothing is deleted)
cat > $P/user.js <<UJS
user_pref("dom.webgpu.enabled", true);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("trailhead.firstrun.didSeeAboutWelcome", true);
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.sessionstore.resume_from_crash", false);
UJS
# BROWSEG_GPU=nv: NVIDIA ICD at the path seen inside the Firefox snap; otherwise leave the snap loader default
if [ "$BROWSEG_GPU" = "nv" ]; then export VK_ICD_FILENAMES=/var/lib/snapd/lib/vulkan/icd.d/nvidia_icd.json; fi
S=paper/data/browser/$TAG/status.txt
echo "$(date -Is) start $TAG (firefox) GPU=$BROWSEG_GPU"
firefox -no-remote -profile $P "http://localhost:8090/web/bench.html?tag=$TAG&$Q" > $L/firefox_$TAG.log 2>&1 &
t0=$(date +%s)
while true; do
  sleep 5
  st=$(cat $S 2>/dev/null)
  if echo "$st" | grep -q -E "DONE|ERROR"; then echo "$(date -Is) $TAG: $st"; break; fi
  if [ $(( $(date +%s) - t0 )) -gt $(( TMO * 60 )) ]; then echo "$TAG: TIMEOUT ($st)"; break; fi
done
for pid in $(ps -eo pid=,args= | awk -v p="$P" 'index($0, p) && /firefox/ && !/awk/ {print $1}'); do kill $pid 2>/dev/null; done
sleep 5
