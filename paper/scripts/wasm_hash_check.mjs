// Runs a BrowSeg WebAssembly build (CPU path) under Node on IRCAD cases and compares the FNV-1a hash of each label map
// with the paper's CPU record (desktop_hashes_wasm20.json), the same fingerprint the benchmark page records.
// usage: node wasm_hash_check.mjs <repo dir> <cases dir> <weights dir> <case:task:roi> ...
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
const [repo, casesDir, wdir, ...jobs] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const createTSC = require(path.join(repo, 'web', process.env.TSC_DIST || 'dist', 'tsc.js'));
const rec = JSON.parse(fs.readFileSync(path.join(repo, 'paper/data/desktop_hashes_wasm20.json'), 'utf8')).entries;
const M = await createTSC({});
const mem = () => M.wasmMemory.buffer;
const copyIn = (b) => { const p = M._malloc(b.length); new Uint8Array(mem(), p, b.length).set(b); return p; };
const str = (s) => { const n = M.lengthBytesUTF8(s) + 1, p = M._malloc(n); M.stringToUTF8(s, p, n); return p; };
const err = () => M.UTF8ToString(M._tsc_result_ptr(5));
const fnv1a = (u8) => { let h = 0x811c9dc5; for (let i = 0; i < u8.length; i++) { h ^= u8[i]; h = Math.imul(h, 0x01000193); } return (h >>> 0).toString(16).padStart(8, '0'); };
console.log('version', M.UTF8ToString(M._tsc_version()));
if (M._tsc_load_classmaps(str(fs.readFileSync(path.join(wdir, 'classmaps.txt'), 'utf8')))) throw new Error(err());
const loaded = new Set();
let current = null, bad = 0;
for (const job of jobs) {
  const [c, task, roi] = job.split(':');
  const out = M._malloc(64);
  const n = M._tsc_task_models(str(task), str(roi), out, 16);
  const ids = Array.from(new Int32Array(mem(), out, n));
  for (const tid of ids) if (!loaded.has(tid)) {
    const f = fs.readdirSync(wdir).find((x) => x.endsWith(`_${tid}.tsw`));
    const b = fs.readFileSync(path.join(wdir, f)); const p = copyIn(b);
    if (M._tsc_load_weights(p, b.length, 1) < 0) throw new Error(err());
    M._free(p); loaded.add(tid);
  }
  if (current !== c) {
    M._tsc_clear_dicom();
    const dir = path.join(casesDir, c);
    for (const f of fs.readdirSync(dir)) { const b = fs.readFileSync(path.join(dir, f)); const p = copyIn(b); M._tsc_add_dicom(p, b.length); M._free(p); }
    if (M._tsc_load_dicom_volume()) throw new Error(err());
    current = c;
  }
  const t0 = Date.now();
  if (M._tsc_run(str(task), str(roi))) throw new Error(err());
  const shape = [0, 1, 2].map((i) => M._tsc_ct_info(i));
  const h = fnv1a(new Uint8Array(mem(), M._tsc_labels_ptr(), shape[0] * shape[1] * shape[2]));
  const key = `${c}__${task}_${roi === '-' ? 'all' : roi}`;
  const want = rec[key] ? rec[key].hashes : [];
  const ok = want.includes(h);
  bad += !ok;
  console.log(`${key}\t${h}\t${ok ? 'MATCH CPU record' : 'DIFFERENT (record ' + want.join(',') + ')'}\t${((Date.now() - t0) / 1000).toFixed(1)} s`);
}
console.log(bad ? `${bad} DIFFERENT` : 'all match');
process.exit(bad ? 1 : 0);
