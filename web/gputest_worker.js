'use strict';
// Worker version of gputest.html (?worker=1): same tests, run inside a Web Worker like the app's engine.
importScripts('gpu_unet.js');
const log = (t) => self.postMessage(t);
function parseNpy(buf) {
  const u8 = new Uint8Array(buf), hl = new DataView(buf).getUint16(8, true);
  const hdr = new TextDecoder().decode(u8.subarray(10, 10 + hl));
  const shape = hdr.match(/\(([^)]*)\)/)[1].split(',').filter((s) => s.trim()).map(Number);
  return { shape, data: new Float32Array(buf.slice(10 + hl)) };
}
async function test(model, dir) {
  const dev = self.dev || (self.dev = await GpuUNet.createDevice());
  const w = new Uint8Array(await (await fetch(`/weights/${model}`)).arrayBuffer());
  const net = new GpuUNet(dev, w);
  const x = parseNpy(await (await fetch(`/ref/${dir}/patch_in.npy`)).arrayBuffer());
  const ref = parseNpy(await (await fetch(`/ref/${dir}/logits.npy`)).arrayBuffer());
  let y;
  const times = [];
  for (let r = 0; r < 4; r++) { const t = performance.now(); y = await net.forward(x.data); times.push(performance.now() - t); }
  const C = ref.shape[1], N = ref.data.length / C;
  let maxd = 0, maxr = 0, dis = 0, s2 = 0, r2 = 0;
  for (let i = 0; i < y.length; i++) { const d = Math.abs(y[i] - ref.data[i]); maxd = Math.max(maxd, d); maxr = Math.max(maxr, Math.abs(ref.data[i])); s2 += d * d; r2 += ref.data[i] ** 2; }
  for (let i = 0; i < N; i++) {
    let a = 0, b = 0;
    for (let c = 1; c < C; c++) { if (y[c * N + i] > y[a * N + i]) a = c; if (ref.data[c * N + i] > ref.data[b * N + i]) b = c; }
    dis += a !== b;
  }
  log(`${model}: forward ms ${times.map((t) => t.toFixed(0)).join(' / ')}  max|diff| ${maxd.toExponential(3)} (max|ref| ${maxr.toFixed(1)}) rel-rms ${Math.sqrt(s2 / r2).toExponential(3)}  argmax disagreement ${dis}/${N}`);
  return { times, maxd, dis };
}
// sliding-window path on one tile: beginVolume (Gaussian = 1) -> forwardAccumulate at origin 0 -> readLogits (fp16),
// compared with forward() of the same patch. Checks the weight / accum / pack shaders and the readback.
function halfToFloat(h) {
  const s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 0x1f, m = h & 0x3ff;
  if (e === 0) return s * m * 2 ** -24;
  if (e === 31) return m ? NaN : s * Infinity;
  return s * (1 + m / 1024) * 2 ** (e - 15);
}
async function testAccumulate(model, dir) {
  const dev = self.dev || (self.dev = await GpuUNet.createDevice());
  const net = new GpuUNet(dev, new Uint8Array(await (await fetch(`/weights/${model}`)).arrayBuffer()));
  const x = parseNpy(await (await fetch(`/ref/${dir}/patch_in.npy`)).arrayBuffer());
  const y = await net.forward(x.data);
  const ps = net.cfg.patch, PP = ps[0] * ps[1] * ps[2];
  await net.beginVolume(new Float32Array(PP).fill(1), ps);
  net.forwardAccumulate(x.data, [0, 0, 0]);
  const h = await net.readLogits();
  await net.popVolumeScopes();
  net.releasePlan();
  let maxd = 0, maxr = 0, zeros = 0;
  for (let i = 0; i < y.length; i++) { const v = halfToFloat(h[i]); maxd = Math.max(maxd, Math.abs(v - y[i])); maxr = Math.max(maxr, Math.abs(y[i])); zeros += v === 0; }
  log(`${model} accumulate path: max|fp16(acc) - forward| ${maxd.toExponential(3)} (max|forward| ${maxr.toFixed(1)}), zero values ${zeros}/${y.length}`);
}
// several tiles into one larger volume (tiles shifted along the last axis, overlapping), expected sum computed in JS
async function testMultiTile(model, dir, ntiles) {
  const dev = self.dev || (self.dev = await GpuUNet.createDevice());
  const net = new GpuUNet(dev, new Uint8Array(await (await fetch(`/weights/${model}`)).arrayBuffer()));
  const x = parseNpy(await (await fetch(`/ref/${dir}/patch_in.npy`)).arrayBuffer());
  const y = await net.forward(x.data);
  const [P0, P1, P2] = net.cfg.patch, PP = P0 * P1 * P2, C = y.length / PP, step = P2 / 2;
  const ps = [P0, P1, P2 + step * (ntiles - 1)], NP = ps[0] * ps[1] * ps[2];
  const exp = new Float32Array(C * NP);
  for (let t = 0; t < ntiles; t++)
    for (let c = 0; c < C; c++) for (let i = 0; i < P0; i++) for (let j = 0; j < P1; j++) for (let k = 0; k < P2; k++)
      exp[((c * ps[0] + i) * ps[1] + j) * ps[2] + k + t * step] += y[((c * P0 + i) * P1 + j) * P2 + k];
  await net.beginVolume(new Float32Array(PP).fill(1), ps);
  for (let t = 0; t < ntiles; t++) net.forwardAccumulate(x.data, [0, 0, t * step]);
  let h, err = '';
  try { h = await net.readLogits(); } catch (e) { err = e.message; }
  net.releasePlan();
  if (!h) { log(`${model} ${ntiles} tiles: ERROR ${err}`); return; }
  let maxd = 0, maxr = 0, bad = 0;
  for (let i = 0; i < exp.length; i++) { const d = Math.abs(halfToFloat(h[i]) - exp[i]); maxd = Math.max(maxd, d); maxr = Math.max(maxr, Math.abs(exp[i])); bad += d > 0.5; }
  log(`${model} ${ntiles} tiles into ${ps.join('x')}: max|diff| ${maxd.toExponential(3)} (max|exp| ${maxr.toFixed(1)}), voxels off by >0.5: ${bad}/${exp.length}`);
}

self.onmessage = async (e) => {
  try {
    if (e.data === 'multi') {
      for (const n of [2, 8]) await testMultiTile('total6mm_298.tsw', 'layers_298', n);
      await testMultiTile('organs_291.tsw', 'layers_291', 4);
    } else {
      await test('total6mm_298.tsw', 'layers_298');
      await test('organs_291.tsw', 'layers_291');
    }
  } catch (err) { log('ERROR ' + err.message); }
  log('DONE');
};
