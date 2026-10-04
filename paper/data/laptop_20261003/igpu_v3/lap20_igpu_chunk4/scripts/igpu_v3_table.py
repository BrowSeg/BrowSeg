"""Time table for the v3 iGPU runs: tag x case x task (seconds, modelSeconds, backend, hash check),
next to the previous laptop runs lap20_chrome_wasm (CPU) and lap20_chrome_nv_webgpu (T1200)."""
import json, glob, os, sys
B = os.path.expanduser('~/Documents/MyGithubProject2/BrowSeg_v3/paper/data/browser')
L = os.path.expanduser('~/Documents/MyGithubProject2/BrowSeg_tools/igpu_v3')
TAGS = ['lap_igpu_chunk1', 'lap_igpu_chunk1_nowait', 'lap_igpu_chunk4', 'lap_igpu_chunk8', 'lap_igpu_chunk0_control',
        'lap_igpu_chunk4_5cases', 'lap_igpu_chunk4_r2', 'lap_igpu_chunk8_r2', 'lap_igpu_chunk0_3tasks']
TAGS = sys.argv[2].split(',') if len(sys.argv) > 2 else TAGS
REF = ['lap20_chrome_wasm', 'lap20_chrome_nv_webgpu']
TASKS = ['total_liver', 'liver_segments_all', 'liver_vessels_all']
def runs(tag, key):
    f = f'{B}/{tag}/{key}.json'
    return json.load(open(f))['runs'] if os.path.exists(f) else None
def check(tag):
    f = f'{L}/hashes_{tag}.txt'
    return dict(l.split(None, 1) for l in open(f).read().splitlines() if l.strip()) if os.path.exists(f) else {}
def kern(tag):
    f = f'{L}/kernel_{tag}.txt'
    return sum(1 for _ in open(f)) if os.path.exists(f) else None
out = ['# BrowSeg v3: Intel UHD (TGL GT1) WebGPU with split submission (gpuchunk) - times', '',
       'seconds per run (reps separated by /); model = modelSeconds; check = hashes.py check vs desktop_hashes.json;',
       'kernel = i915/rcs0/GPU HANG lines in journalctl -k for the run window.', '',
       '| tag | case | task | seconds | model | backend | fallback | gpuErrors | check | kernel | lap20 wasm (CPU) | lap20 nv webgpu (T1200) |',
       '|---|---|---|---|---|---|---|---|---|---|---|---|']
for tag in TAGS:
    if not os.path.isdir(f'{B}/{tag}'): continue
    ck, kn = check(tag), kern(tag)
    keys = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{B}/{tag}/*__*.json'))
    keys.sort(key=lambda k: (k.split('__')[0], TASKS.index(k.split('__')[1]) if k.split('__')[1] in TASKS else 9))
    for k in keys:
        r = runs(tag, k); case, task = k.split('__')
        refs = []
        for t in REF:
            rr = runs(t, k)
            refs.append(' / '.join('%.1f' % x['seconds'] for x in rr) if rr else '-')
        secs = ' / '.join('%.1f' % x['seconds'] for x in r)
        mod = ' / '.join('%.2f' % (x.get('modelSeconds') or 0) for x in r)
        be = ','.join(sorted({x['backend'] for x in r}))
        fb = ','.join(sorted({str(x.get('fallback')) for x in r}))
        ge = sum(x.get('gpuErrors') or 0 for x in r)
        out.append(f"| {tag} | {case} | {task} | {secs} | {mod} | {be} | {fb} | {ge} | {ck.get(k, '-')} | {kn} | {refs[0]} | {refs[1]} |")
pass
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
