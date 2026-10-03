// Peak WASM memory for a large CT: a DICOM series is stacked `reps` times along z (512 x 512 x N*reps),
// handed to the module with tsc_set_volume (NIfTI path) or rebuilt from DICOM copies, then a task is run.
// usage: node tests/mem_probe.mjs <dicom_dir> <weights_dir> <reps> [task] [roi|-] [nifti|dicom]
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const createTSC = require('../web/dist/tsc.js');

const [dicomDir, wdir, repsArg, task = 'total', roi = 'liver', mode = 'dicom'] = process.argv.slice(2);
const reps = +repsArg || 1;
const M = await createTSC({ onProgress: () => {} });
const mem = () => M.wasmMemory.buffer;
const view = (T, p, n) => new T(mem(), p >>> 0, n);
const copyIn = (buf) => { const p = M._malloc(buf.length); view(Uint8Array, p, buf.length).set(buf); return p; };
const str = (s) => { const n = M.lengthBytesUTF8(s) + 1, p = M._malloc(n); M.stringToUTF8(s, p, n); return p; };
const err = () => M.UTF8ToString(M._tsc_result_ptr(5) >>> 0);
const GB = () => (mem().byteLength / 2 ** 30).toFixed(2);
const peak = { v: 0, at: '' };
const note = (what) => { const g = mem().byteLength; if (g > peak.v) { peak.v = g; peak.at = what; } console.log(`  ${what}: heap ${GB()} GB`); };

if (M._tsc_load_classmaps(str(fs.readFileSync(path.join(wdir, 'classmaps.txt'), 'utf8')))) throw new Error(err());
const out = M._malloc(64);
const n = M._tsc_task_models(str(task), str(roi), out, 16);
for (const tid of Array.from(view(Int32Array, out, n))) {
  const f = fs.readdirSync(wdir).find((x) => x.endsWith(`_${tid}.tsw`));
  const b = fs.readFileSync(path.join(wdir, f)), p = copyIn(b);
  if (M._tsc_load_weights(p, b.length, 1) < 0) throw new Error(err());
  M._free(p);
}
note('weights loaded');

const files = fs.readdirSync(dicomDir).map((f) => fs.readFileSync(path.join(dicomDir, f)));
if (mode === 'dicom') {
  // stack by rewriting ImagePositionPatient z (tag 0020,0032) and the SOP instance number is not needed
  M._tsc_clear_dicom();
  let ns = 0;
  for (let r = 0; r < reps; r++) {
    for (const b0 of files) {
      const b = Buffer.from(b0);
      // find (0020,0032) DS value in explicit/implicit little endian: search the tag bytes
      const tag = Buffer.from([0x20, 0x00, 0x32, 0x00]);
      const at = b.indexOf(tag);
      if (at >= 0 && r > 0) {
        const explicit = b.toString('latin1', at + 4, at + 6) === 'DS';
        const len = explicit ? b.readUInt16LE(at + 6) : b.readUInt32LE(at + 4);
        const off = at + (explicit ? 8 : 8);
        const txt = b.toString('latin1', off, off + len);
        const parts = txt.trim().split('\\').map(Number);
        parts[2] -= r * 1000;  // shift each copy by 1 m (non-overlapping; spacing gap is irrelevant for the probe)
        let s = parts.map((x) => x.toFixed(4)).join('\\');
        s = s.length > len ? s.slice(0, len) : s.padEnd(len, ' ');
        b.write(s, off, len, 'latin1');
      }
      const p = copyIn(b);
      ns += M._tsc_add_dicom(p, b.length);
      M._free(p);
    }
  }
  note(`${ns} slices added`);
  if (M._tsc_load_dicom_volume()) throw new Error(err());
} else {
  M._tsc_clear_dicom();
  for (const b of files) { const p = copyIn(b); M._tsc_add_dicom(p, b.length); M._free(p); }
  if (M._tsc_load_dicom_volume()) throw new Error(err());
  const shape = [0, 1, 2].map((i) => M._tsc_ct_info(i));
  const src = view(Float32Array, M._tsc_ct_ptr(), shape[0] * shape[1] * shape[2]).slice();
  const aff = Array.from(view(Float64Array, M._tsc_ct_affine(), 16));
  const [X, Y, Z] = shape, Z2 = Z * reps, f = new Float32Array(X * Y * Z2);
  for (let x = 0; x < X; x++) for (let y = 0; y < Y; y++) for (let z = 0; z < Z2; z++) f[x + X * (y + Y * z)] = src[(x * Y + y) * Z + (z % Z)];
  const p = copyIn(new Uint8Array(f.buffer)), ap = M._malloc(128);
  view(Float64Array, ap, 16).set(aff);
  if (M._tsc_set_volume(p, X, Y, Z2, ap)) throw new Error(err());
  M._free(p); M._free(ap);
}
note(`volume ${[0, 1, 2].map((i) => M._tsc_ct_info(i)).join('x')}`);
const t0 = Date.now();
const r = M._tsc_run(str(task), str(roi));
note(`task ${task} ${r ? 'FAILED: ' + err() : 'ok'} (${((Date.now() - t0) / 1000).toFixed(1)} s)`);
console.log(`PEAK heap ${(peak.v / 2 ** 30).toFixed(2)} GB (${peak.at})`);
process.exit(0);
