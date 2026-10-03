// Static server with the headers required for SharedArrayBuffer (WASM threads).
// usage: node serve.mjs [port] [dicom_dir]   ->  http://localhost:8080/web/
// With dicom_dir, http://localhost:8080/web/?demo=1 loads that series directly (for testing).
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const root = path.dirname(fileURLToPath(import.meta.url));
const port = +process.argv[2] || 8080;
const types = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.wasm': 'application/wasm', '.css': 'text/css', '.json': 'application/json', '.tsw': 'application/octet-stream',
  '.png': 'image/png', '.svg': 'image/svg+xml',
};
const allowed = ['web', 'weights', 'weights_fp16'];
// --bench <cases dir>: web/bench.html runs every case (sub-folder with DICOM files or one .nii/.nii.gz) and the
// results (timings JSON + label maps) are written to paper_jiim/paper_benchmarks/data/browser/<tag>/
const benchIdx = process.argv.indexOf('--bench');
const benchDir = benchIdx > 0 ? path.resolve(process.argv[benchIdx + 1]) : null;
const outIdx = process.argv.indexOf('--out');
const benchOut = outIdx > 0 && process.argv[outIdx + 1] ? path.resolve(process.argv[outIdx + 1]) : path.join(root, 'paper_jiim', 'paper_benchmarks', 'data', 'browser');
const demoDir = process.argv[3] && !process.argv[3].startsWith('--') ? path.resolve(process.argv[3]) : null;
if (demoDir) allowed.push('ref');  // dev: reference dumps for the test pages
const safe = (s) => String(s).replace(/[^A-Za-z0-9_.-]/g, '_');
const plainName = (s) => /^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(s) && !s.includes('..');  // one path component, no traversal
// writes (/bench/save, /demo/snap) are accepted only from pages served by this server: any other site open in the
// browser could otherwise POST here (no CORS preflight for simple requests)
const sameOrigin = (req) => { const o = req.headers.origin; try { return !!o && new URL(o).host === req.headers.host; } catch (e) { return false; } };
const streamFile = (p, res, hdr, extra = {}) => {
  const s = fs.createReadStream(p);
  s.on('error', () => { if (!res.headersSent) res.writeHead(500); res.end(); });
  s.on('open', () => res.writeHead(200, { ...hdr, ...extra }));
  s.pipe(res);
};
const NO_COI = process.argv.includes('--no-coi');  // test the non-isolated (single-thread) path

http.createServer((req, res) => {
  try { handle(req, res); } catch (e) { console.error(e); if (!res.headersSent) res.writeHead(500); res.end(); }
}).listen(port, '127.0.0.1', () => console.log(`BrowSeg: http://localhost:${port}/web/`));

function handle(req, res) {
  let url;
  try { url = decodeURIComponent(new URL(req.url, 'http://x').pathname); } catch (e) { res.writeHead(400); return res.end('bad url'); }
  if (url === '/') { res.writeHead(302, { Location: '/web/' }); return res.end(); }
  const hdr = NO_COI ? { 'Cache-Control': 'no-cache' }
    : { 'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp', 'Cache-Control': 'no-cache' };
  if (url === '/demo/list') {
    const files = demoDir ? fs.readdirSync(demoDir).filter((f) => fs.statSync(path.join(demoDir, f)).isFile()) : [];
    res.writeHead(200, { ...hdr, 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(files));
  }
  if (url === '/demo/snap' && req.method === 'POST' && demoDir) {  // dev: save a PNG screenshot to out/
    if (!sameOrigin(req)) { res.writeHead(403); return res.end(); }
    const chunks = []; req.on('data', (c) => chunks.push(c));
    req.on('end', () => { fs.mkdirSync(path.join(root, 'out'), { recursive: true });
      fs.writeFileSync(path.join(root, 'out', 'snap.png'), Buffer.concat(chunks)); res.writeHead(200, hdr); res.end('ok'); });
    return;
  }
  if (benchDir && url === '/bench/cases') {
    const cases = fs.readdirSync(benchDir).filter((d) => fs.statSync(path.join(benchDir, d)).isDirectory()).sort()
      .map((d) => ({ name: d, files: fs.readdirSync(path.join(benchDir, d)).filter((f) => fs.statSync(path.join(benchDir, d, f)).isFile()) }));
    res.writeHead(200, { ...hdr, 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(cases));
  }
  if (url.startsWith('/bench/expected/')) {  // the paper's hash records, for bench.html?local=1 (served even without --bench)
    const name = url.slice('/bench/expected/'.length);
    if (!['desktop_hashes.json', 'desktop_hashes_wasm20.json'].includes(name)) { res.writeHead(404); return res.end(); }
    const p = ['paper_jiim/paper_benchmarks/data', 'paper/data'].map((d) => path.join(root, d, name)).find((f) => fs.existsSync(f));
    if (!p) { res.writeHead(404); return res.end(); }
    return streamFile(p, res, hdr, { 'Content-Type': 'application/json' });
  }
  if (benchDir && url.startsWith('/bench/file/')) {
    const [c, f] = url.slice('/bench/file/'.length).split('/');
    if (!c || !f || !plainName(c) || !plainName(f)) { res.writeHead(400); return res.end(); }
    const p = path.join(benchDir, c, f);
    if (!fs.existsSync(p) || !fs.statSync(p).isFile()) { res.writeHead(404); return res.end(); }
    return streamFile(p, res, hdr, { 'Content-Type': 'application/octet-stream' });
  }
  if (benchDir && url === '/bench/save' && req.method === 'POST') {  // ?tag=..&name=.. body = file content
    if (!sameOrigin(req)) { res.writeHead(403); return res.end(); }
    const q = new URL(req.url, 'http://x').searchParams;
    const tag = safe(q.get('tag')), name = safe(q.get('name'));
    if (!plainName(tag) || !plainName(name)) { res.writeHead(400); return res.end('bad tag/name'); }
    const dir = path.join(benchOut, tag);
    const chunks = []; req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      try { fs.mkdirSync(dir, { recursive: true }); fs.writeFileSync(path.join(dir, name), Buffer.concat(chunks)); res.writeHead(200, hdr); res.end('ok'); }
      catch (e) { console.error(e); res.writeHead(500); res.end(); }
    });
    return;
  }
  if (url.startsWith('/demo/') && demoDir) {
    const f = path.join(demoDir, path.basename(url));
    if (!fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); return res.end(); }
    return streamFile(f, res, hdr, { 'Content-Type': 'application/octet-stream' });
  }
  let file = path.normalize(path.join(root, url));
  const rel = path.relative(root, file).split(path.sep);
  if (rel[0] === '..' || !allowed.includes(rel[0])) { res.writeHead(404); return res.end('not found'); }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404); return res.end('not found'); }
    streamFile(file, res, hdr, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Content-Length': st.size });
  });
}
