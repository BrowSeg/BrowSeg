#!/bin/bash
# Judge one tag: per-run backend/fallback/gpuErrors/seconds, GPU name, kernel lines, hashes.py check.
cd ~/Documents/MyGithubProject2/BrowSeg_v3
TAG=$1; L=~/Documents/MyGithubProject2/BrowSeg_tools/igpu_v3
python3 - "$TAG" <<'PY'
import json,sys,glob,os
tag=sys.argv[1]; d='paper/data/browser/'+tag
e=json.load(open(d+'/environment.json')); print('GPU:', e.get('gpu',{}).get('vendor'), e.get('webglRenderer'), 'backend', e.get('backend'), e.get('engineOptions'))
for f in sorted(glob.glob(d+'/*__*.json')):
  for r in json.load(open(f))['runs']:
    print(f"{os.path.basename(f)[:-5]:32s} {r['backend']:7s} fallback={r.get('fallback')} gpuErrors={r.get('gpuErrors')} seconds={r['seconds']:.1f} model={r.get('modelSeconds')} hash={r['hash']}")
PY
cat $L/time_$TAG.txt | head -3
echo "kernel lines:"; cat $L/kernel_$TAG.txt
python3 paper/scripts/hashes.py check paper/data/browser $TAG paper/data/desktop_hashes.json | tee $L/hashes_$TAG.txt
