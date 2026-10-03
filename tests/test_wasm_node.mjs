// Runs the WASM build (CPU path) under Node and compares the label map with the Python reference.
// usage: node tests/test_wasm_node.mjs <dicom_dir> <weights_dir> <ref_final_can.npy> [task] [roi|-]
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const createTSC = require(`../web/${process.env.TSC_DIST || 'dist'}/tsc.js`);  // TSC_DIST=dist-st: single-thread build

const [dicomDir, wdir, refNpy, task = 'total', roi = 'liver'] = process.argv.slice(2);
const M = await createTSC({ onProgress: (s, f) => { if (f === 0 || f === 1) console.log(`  .. ${s} ${Math.round(f * 100)}%`); } });
const mem = () => M.wasmMemory.buffer;
const copyIn = (buf) => { const p = M._malloc(buf.length); new Uint8Array(mem(), p, buf.length).set(buf); return p; };
const str = (s) => { const n = M.lengthBytesUTF8(s) + 1, p = M._malloc(n); M.stringToUTF8(s, p, n); return p; };
const err = () => M.UTF8ToString(M._tsc_result_ptr(5));

if (M._tsc_load_classmaps(str(fs.readFileSync(path.join(wdir, 'classmaps.txt'), 'utf8')))) throw new Error(err());
const out = M._malloc(64);
const n = M._tsc_task_models(str(task), str(roi), out, 16);
if (n < 0) throw new Error(err());
const ids = Array.from(new Int32Array(mem(), out, n));
for (const tid of ids) {
  const f = fs.readdirSync(wdir).find((x) => x.endsWith(`_${tid}.tsw`));
  const b = fs.readFileSync(path.join(wdir, f)); const p = copyIn(b);
  const r = M._tsc_load_weights(p, b.length, 1); M._free(p);
  if (r < 0) throw new Error(err());
  console.log(`model ${r} loaded (${f})`);
}
let ns = 0;
for (const f of fs.readdirSync(dicomDir)) {
  const b = fs.readFileSync(path.join(dicomDir, f)); const p = copyIn(b);
  ns += M._tsc_add_dicom(p, b.length); M._free(p);
}
if (M._tsc_load_dicom_volume()) throw new Error(err());
console.log(`dicom slices: ${ns}, threads: ${M._tsc_result_int(8)}, task ${task}, roi ${roi}`);
const t0 = Date.now();
if (M._tsc_run(str(task), str(roi))) throw new Error(err());
console.log(`run: ${(Date.now() - t0) / 1000}s (seg ${M._tsc_result_double(1).toFixed(2)}s)`);
const shape = [0, 1, 2].map((i) => M._tsc_ct_info(i));
const nvox = shape[0] * shape[1] * shape[2];
const mask = new Uint8Array(mem(), M._tsc_labels_ptr(), nvox).slice();
const names = [];
for (let i = 0; i < M._tsc_num_label_names(); i++) names.push(M.UTF8ToString(M._tsc_label_name(i)));
// mesh every present label through the edit path (tsc_set_labels + tsc_build_meshes)
const present = [...new Set(mask)].filter((v) => v);
const lp = copyIn(mask);
if (M._tsc_set_labels(lp)) throw new Error(err());
M._free(lp);
if (M._tsc_build_meshes(str(present.map((v) => `${v}\t${names[v]}`).join('\n')))) throw new Error(err());
console.log(`meshes: ${M._tsc_result_int(10)} structures, ${M._tsc_result_int(1)} triangles, ${M._tsc_result_double(2).toFixed(2)}s`);
const rb = fs.readFileSync(refNpy); const hl = rb.readUInt16LE(8); const ref = rb.subarray(10 + hl);
let diff = 0;
for (let i = 0; i < nvox; i++) diff += mask[i] !== ref[i];
console.log(`label map vs python: differing voxels ${diff} of ${nvox}`);
process.exit(diff === 0 ? 0 : 1);
