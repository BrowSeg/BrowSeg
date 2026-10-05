'use strict';
// BrowSeg: wiring of worker (WASM/WebGPU engine), views, editor.

const $ = (id) => document.getElementById(id);
const TASKS = [
  ['total|liver', t('肝臓 (total, roi_subset=liver)')],
  ['liver_segments|-', t('肝臓 8 区域 (Couinaud)')],
  ['liver_vessels|-', t('肝内血管 (統合)')],
  ['total|liver,spleen,kidney_right,kidney_left,gallbladder,pancreas,stomach,aorta,inferior_vena_cava,portal_vein_and_splenic_vein', t('腹部主要臓器 (roi_subset)')],
  ['total|-', t('全身 117 構造 (total, 5 モデル)')],
];
const BASE_MODELS = [[8, '肝内血管 (liver_vessels, 8)'], [570, '肝区域 (liver_segments, 570)'], [291, '腹部臓器 (organs, 291)'],
                     [293, '心臓・大血管 (cardiac, 293)']];

const App = {
  S: {
    ct: null, lab: null, shape: null, zooms: null, affine: null, cursor: [0, 0, 0],
    window: [50, 400], overlay: true, alpha: 0.45, crosshair: true, active: 0,
    source: null, tasks: [], editedVoxels: 0, counts: new Uint32Array(256),
  },
  labels: new Labels.Registry(),
  tool: 'nav', brushRadius: 3, sphere: false, protect: true, eraseAll: false,
  huRange: { on: false, lo: 100, hi: 400 },
  spaceDown: false, backend: false, customModels: [], dirty: new Set(), meshSeq: 0,
};

// ================================================================= worker (request queue)
// test hooks (?order=, ?threads=, ?gpufail=, ...) are for bench.html / gputest.html; a shared URL must not change results
const workerParams = new URLSearchParams();
for (const k of ['lang', 'cpu']) { const v = new URLSearchParams(location.search).get(k); if (v !== null) workerParams.set(k, v); }
const worker = new Worker('worker.js' + (workerParams.size ? '?' + workerParams : ''));
// ask the browser to keep the downloaded model weights (Cache API) when disk space runs low; harmless if refused
try { if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {}); } catch (e) { /* not available */ }
let pending = null;
const queue = [];
function request(msg, expect, transfer) {
  if (App.engineDead) return Promise.reject(new Error(t('エンジンが停止しています。ページを再読み込みしてください')));
  return new Promise((resolve, reject) => {
    queue.push({ msg, expect, transfer, resolve, reject });
    pump();
  });
}
function pump() {
  if (pending || !queue.length) return;
  pending = queue.shift();
  worker.postMessage(pending.msg, pending.transfer || []);
}
worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === 'progress') return setProgress(m.stage, m.frac);
  if (m.type === 'log') return log(m.text);
  if (m.type === 'warning') { log('WARNING ' + m.text); toast(m.text, 8000); return; }
  if (m.type === 'backend') {
    if (App.engine) App.engine.backend = m.backend;
    setPill('engineStatus', 'warn', t('エンジン {0}（GPU が使えなくなったため切替）', m.backend === 'webgpu' ? 'WebGPU' : 'CPU'));
    return;
  }
  const p = pending;
  if (m.type === 'error') {
    if (!p || (m.request && m.request !== p.msg.type)) { log(`ERROR (${m.request || '?'}): ${m.message}`); return; }
    pending = null; p.reject(new Error(m.message)); pump(); return;
  }
  if (p && m.type === p.expect) { pending = null; p.resolve(m); pump(); }
};
worker.onerror = (e) => {
  e.preventDefault();
  const msg = t('エンジンが停止しました: {0}（ページを再読み込みしてください）', e.message || 'worker error');
  log('ERROR ' + msg); toast(msg, 10000); setPill('engineStatus', 'err', t('エンジン停止'));
  const all = [pending, ...queue.splice(0)].filter(Boolean);
  pending = null;
  App.engineDead = true; App.engine = null; updateButtons();
  for (const p of all) p.reject(new Error(msg));
};
// init goes through the queue: loads dropped before the engine is ready simply wait behind it
request({ type: 'init' }, 'ready').then((m) => {
  App.engine = m;
  setPill('engineStatus', 'ok', t('エンジン {0} / {1} スレッド{2}', m.backend === 'webgpu' ? 'WebGPU' : 'CPU', m.threads, m.build === 'dist-st' ? t('（単一スレッド版）') : ''));
  log(m.version);
  if (m.backend !== 'webgpu' && m.gpuWanted) {  // WebGPU was not available: the CPU works, but say how to enable the GPU
    const hint = t('WebGPU が使えないため CPU で解析します（結果は同じで、時間がかかります）。Linux の Chrome では chrome://flags で「Unsafe WebGPU Support」と「Vulkan」を Enabled にして Chrome を再起動すると GPU を使えます。');
    log(hint); toast(hint, 12000);
  }
  updateButtons();
}).catch((e) => { App.engineDead = true; setPill('engineStatus', 'err', t('エンジン起動失敗')); log('ERROR init: ' + e.message); toast(t('エンジンの起動に失敗しました: {0}', e.message), 8000); });
// HTML escaping for names coming from files / the server
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// ================================================================= small UI helpers
function log(t) { const el = $('log'); el.textContent += t + '\n'; el.scrollTop = el.scrollHeight; }
function toast(t, ms = 2600) { const el = $('toast'); el.textContent = t; el.classList.add('show'); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('show'), ms); }
App.toast = toast;
function setPill(id, state, text) { const el = $(id); el.querySelector('.dot').className = 'dot ' + state; el.querySelector('span:last-child').textContent = text; }
function setProgress(stage, frac) {
  const names = { 'dicom': t('DICOM → ボリューム'), 'resample_6mm': t('6mm へリサンプル'), 'crop_model': t('粗セグメンテーション'),
    'resample_part': t('リサンプル'), 'part_model': t('モデル推論'), 'done': t('完了'), 'mesh': t('メッシュ生成'), 'read DICOM': t('DICOM 読み込み'), };
  const base = Object.keys(names).find((k) => stage.startsWith(k)) || stage;
  $('stage').textContent = `${names[base] || stage}${stage.slice(base.length)} ${Math.round(frac * 100)}%`;
  $('bar').style.width = (100 * frac).toFixed(1) + '%';
}
function download(blob, name) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
function busy(on, text) {
  App.busy = on;
  if (text) setPill('engineStatus', on ? 'busy' : 'ok', text);
  updateButtons();
}
function updateButtons() {
  const ready = !!App.engine && !App.busy, has = !!App.S.ct;
  $('runTask').disabled = !(ready && has);
  for (const id of ['openLabels', 'dlCT', 'dlLabels', 'addLabel', 'updateMeshes']) $(id).disabled = !has || App.busy;
  $('openNifti').disabled = !!App.busy;
  $('switchSeries').hidden = !App.seriesList;
  $('switchSeries').disabled = !!App.busy;
  $('drop').classList.toggle('disabled', !!App.busy);
  $('dlOBJ').disabled = $('dlSTL').disabled = !App.viewer.meshes.size;
  $('renameLabel').disabled = $('deleteLabel').disabled = !App.S.active || !!App.busy;
}

// ================================================================= views
App.views = ['axial', 'coronal', 'sagittal'].map((a) => new SliceView(App, $('v-' + a), a));
App.viewer = new Viewer3D($('v-3d').querySelector('canvas'));
App.viewer.labels = App.labels;
App.editor = new Editor(App);

App.renderViews = () => App.views.forEach((v) => v.render());
App.setCursor = (c) => { App.S.cursor = c.map((v, i) => Math.max(0, Math.min(App.S.shape[i] - 1, Math.round(v)))); App.renderViews(); App.showProbe(App.S.cursor); };
App.setWindow = (level, width) => { App.S.window = [level, width]; App._gray = null; App.renderViews(); };
App.grayLut = () => {
  if (App._gray && App._grayKey === App.S.window.join()) return App._gray;
  const [L, W] = App.S.window, lut = new Uint8Array(65536), lo = L - W / 2;
  for (let i = 0; i < 65536; i++) { const v = ((i - 32768) - lo) / W * 255; lut[i] = v < 0 ? 0 : v > 255 ? 255 : v; }
  App._gray = lut; App._grayKey = App.S.window.join();
  return lut;
};
App.labelLut = () => { if (!App._lut) App._lut = App.labels.lut(); return App._lut; };
App.invalidateLut = () => { App._lut = null; };
App.showProbe = (vox) => {
  const S = App.S;
  if (!vox || !S.ct) { $('probe').textContent = ''; return; }
  const i = (vox[0] * S.shape[1] + vox[1]) * S.shape[2] + vox[2];
  const l = S.lab ? S.lab[i] : 0, L = l ? App.labels.map.get(l) : null;
  $('probe').textContent = `voxel (${vox.join(', ')})   HU ${S.ct[i]}   ${L ? Labels.display(L.name) + ' [' + L.name + ']' : t('背景')}`;
};

// ================================================================= volume loading
function onVolume(v, source) {
  const S = App.S;
  clearTimeout(meshTimer); App.dirty.clear(); App.volGen = (App.volGen || 0) + 1;
  Object.assign(S, { ct: v.ct, shape: v.shape, zooms: v.zooms, affine: v.affine, lab: new Uint8Array(v.ct.length),
                     cursor: v.shape.map((n) => n >> 1), source, tasks: [], editedVoxels: 0, active: 0 });
  S.counts = new Uint32Array(256);
  App.labels.clear(); App.invalidateLut(); App.editor.reset(); App.viewer.clear();
  $('empty').hidden = true;
  $('volInfo').textContent = `${v.shape.join(' × ')} voxels, ${v.zooms.map((z) => z.toFixed(2)).join(' × ')} mm  (${source.name || source.kind}` +
    (source.series_uid ? ` / ${t('シリーズ')} ${source.series_number || ''} ${source.series_description || ''}` : '') + ')';
  if (source.kind !== 'dicom') App.seriesList = null;
  if (v.log) log(v.log.trim());
  recount(); renderLabelList(); App.renderViews(); updateButtons();
}
async function loadDicomFiles(files) {
  files = files.filter((f) => !/\.(txt|json|md|jpg|png|zip|xml|html?|nii|gz)$/i.test(f.name) && f.name !== 'DICOMDIR');
  if (!files.length) { toast(t('DICOM ファイルが見つかりません')); return false; }
  if (App.busy) { toast(t('処理中です。終わってから読み込んでください')); return false; }
  let ok = false;
  busy(true, t('DICOM 読み込み中…'));
  App.seriesList = null; App.seriesFolder = null;  // the engine's slices are replaced by this load
  try {
    const bufs = [];
    for (const f of files) bufs.push(await f.arrayBuffer());
    const sl = await request({ type: 'loadDicom', files: bufs }, 'series', bufs);
    const folder = files[0].webkitRelativePath ? files[0].webkitRelativePath.split('/')[0] : 'DICOM';
    const usable = sl.list.filter((x) => x.slices >= 2 && !x.problem);
    if (!usable.length) throw new Error(t('2 枚以上の画像からなるシリーズがありません'));
    // several series: let the user choose (the slices stay in the engine so the series can be switched later)
    const pick = usable.length === 1 ? usable[0] : await chooseSeries(sl.list);
    if (pick) {
      ok = await buildSeries(pick, { name: folder, files: files.length }, usable.length > 1);
      App.seriesList = usable.length > 1 ? sl.list : null;
      App.seriesFolder = { name: folder, files: files.length };
    } else await request({ type: 'clearDicom' }, 'cleared');  // cancelled: free the slices
  } catch (e) {
    loadFailed(e);
    if (!App.seriesList && !App.engineDead) request({ type: 'clearDicom' }, 'cleared').catch(() => {});
  }
  busy(false, t('エンジン {0}', App.engine ? App.engine.backend : ''));
  return ok;
}
// A failed load: the engine may have dropped its CT (it frees the old one before building the new one to
// save memory) -> then the displayed volume is cleared too, so the UI and the engine stay consistent.
function loadFailed(e) {
  const lost = /\[CT_LOST\]/.test(e.message);
  const msg = e.message.replace('[CT_LOST] ', '');
  toast(t('読み込み失敗: {0}', msg) + (lost && App.S.ct ? t('（表示中の CT も閉じました）') : ''), 6000);
  log('ERROR ' + msg);
  if (lost) clearVolume();
}
function clearVolume() {
  const S = App.S;
  clearTimeout(meshTimer); App.dirty.clear(); App.volGen = (App.volGen || 0) + 1;
  Object.assign(S, { ct: null, lab: null, shape: null, source: null, tasks: [], editedVoxels: 0, active: 0 });
  S.counts = new Uint32Array(256);
  App.labels.clear(); App.invalidateLut(); App.editor.reset(); App.viewer.clear();
  App.seriesList = null;
  $('empty').hidden = false; $('volInfo').textContent = '';
  recount(); renderLabelList(); App.renderViews(); updateButtons();
}

// builds the CT of one DICOM series in the engine and shows it
async function buildSeries(ser, src, keep) {
  const v = await request({ type: 'buildSeries', uid: ser.uid, keep }, 'volume');
  onVolume(v, Object.assign({ kind: 'dicom' }, src, {
    series_uid: ser.uid, series_description: ser.description, series_number: ser.number, series_time: ser.time,
    slice_spacing: ser.sliceSpacing }));
  return true;
}

// ---- series picker
// default suggestion: the engine's choice (largest CT series); a portal-venous phase with (almost) as many
// slices is suggested instead, since the liver vessel tasks need it
function suggestSeries(list) {
  const ok = list.filter((x) => x.slices >= 2 && !x.problem && (x.modality === 'CT' || !x.modality));
  if (!ok.length) return { s: list.find((x) => x.slices >= 2 && !x.problem) || list[0], why: '' };
  const max = Math.max(...ok.map((x) => x.slices));
  const pv = ok.find((x) => /portal|venous|\bpv\b|門脈/i.test(x.description) && x.slices >= 0.8 * max);
  if (pv) return { s: pv, why: t('門脈相（肝血管の抽出向き）') };
  return { s: ok[0], why: t('枚数が最も多い CT シリーズ') };
}
function seriesNote(x) {
  const n = [];
  const why = { 'duplicate slice positions (several phases in one series?)': t('同じ位置のスライスが重複（複数の相が 1 シリーズに混在？）・読み込めません'),
                'slices with different orientations': t('向きの違うスライスが混在・読み込めません') }[x.problem];
  if (why) n.push(why);
  else if (x.slices === 0 && x.other) n.push(t('位置決め画像のみ（読み込めません）'));
  else if (x.slices < 2) n.push(t('画像が 1 枚のみ（読み込めません）'));
  else if (x.other) n.push(t('位置決め画像など {0} 枚は除外', x.other));
  if (x.modality && x.modality !== 'CT') n.push(t('{0}（CT 以外）', x.modality));
  const sp = Math.min(x.spacing[0] || 1, x.spacing[1] || 1);
  if (x.sliceSpacing && x.sliceSpacing / sp > 3) n.push(t('厚いスライス'));
  return n.join(t('、'));
}
function chooseSeries(list, currentUid) {
  return new Promise((resolve) => {
    const dlg = $('seriesDlg'), tb = $('seriesRows'), sug = suggestSeries(list);
    const hhmm = (s) => (s && s.length >= 4 ? `${s.slice(0, 2)}:${s.slice(2, 4)}` : '');  // (not t: that is the translation function)
    tb.innerHTML = '';
    for (const x of list) {
      const tr = document.createElement('tr');
      const dis = x.slices < 2 || !!x.problem;
      const checked = currentUid ? x.uid === currentUid : x === sug.s;
      tr.className = (dis ? 'dis' : '') + (x === sug.s ? ' sug' : '');
      tr.innerHTML = `<td><input type="radio" name="series" value="${esc(x.uid)}" ${dis ? 'disabled' : ''} ${checked ? 'checked' : ''}></td>` +
        `<td>${x.number || ''}</td><td class="desc">${esc(x.description || t('(説明なし)'))}${x === sug.s ? ` <span class="badge">${t('推奨')}</span>` : ''}</td>` +
        `<td>${esc(x.modality)}</td><td class="n">${x.slices}</td><td class="n">${x.cols}×${x.rows}</td>` +
        `<td class="n">${x.spacing[1] ? x.spacing[1].toFixed(2) : '–'}</td><td class="n">${x.sliceSpacing ? x.sliceSpacing.toFixed(2) : '–'}</td>` +
        `<td class="n">${x.extent ? x.extent.toFixed(0) : '–'}</td><td>${esc(hhmm(x.time))}</td><td>${esc(x.contrast)}</td><td class="note">${esc(seriesNote(x))}</td>`;
      if (!dis) tr.onclick = (e) => { if (e.target.tagName !== 'INPUT') tr.querySelector('input').checked = true; };
      tb.appendChild(tr);
    }
    $('seriesInfo').textContent = t('{0} シリーズが見つかりました。推奨: {1}（{2}）', list.length, sug.s.description || sug.s.uid, sug.why) +
      (currentUid ? t('。切り替えると現在のラベルは消えます（必要なら先に保存してください）。') : '');
    const done = (v) => { dlg.onclose = null; dlg.close(); resolve(v); };
    $('seriesOk').onclick = (e) => {
      e.preventDefault();
      const r = tb.querySelector('input:checked');
      done(r ? list.find((x) => x.uid === r.value) : null);
    };
    $('seriesCancel').onclick = (e) => { e.preventDefault(); done(null); };
    dlg.onclose = () => resolve(null);  // Esc
    dlg.showModal();
  });
}
async function switchSeries() {
  if (!App.seriesList || App.busy) return;
  const pick = await chooseSeries(App.seriesList, App.S.source && App.S.source.series_uid);
  if (!pick || (App.S.source && pick.uid === App.S.source.series_uid)) return;
  busy(true, t('シリーズ読み込み中…'));
  try { await buildSeries(pick, App.seriesFolder, true); } catch (e) { loadFailed(e); }
  busy(false, t('エンジン {0}', App.engine ? App.engine.backend : ''));
}

// buf: file contents, or an already parsed NIfTI ({dims, affine, data}); nested: called inside another busy step
async function loadNiftiVolume(buf, name, nested = false) {
  if (App.busy && !nested) { toast(t('処理中です。終わってから読み込んでください')); return false; }
  let ok = false;
  if (!nested) busy(true, t('NIfTI 読み込み中…'));
  try {
    if (App.seriesList) { await request({ type: 'clearDicom' }, 'cleared'); App.seriesList = null; }  // free kept DICOM slices
    const nii = buf instanceof ArrayBuffer ? await Nifti.read(buf) : buf;
    const v = await request({ type: 'loadVolume', data: nii.data, dims: nii.dims, affine: nii.affine }, 'volume', [nii.data.buffer]);
    onVolume(v, { kind: 'nifti', name });
    ok = true;
  } catch (e) {
    if (nested) throw e;
    loadFailed(e);
  }
  if (!nested) busy(false, t('エンジン {0}', App.engine ? App.engine.backend : ''));
  return ok;
}

// shape of a NIfTI volume after reorientation to the canonical grid (same axis rule as canonicalLabels)
function canonicalShape(nii) {
  const A = nii.affine, R = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  for (let c = 0; c < 3; c++) { const n = Math.hypot(A[c], A[4 + c], A[8 + c]) || 1; for (let r = 0; r < 3; r++) R[r][c] = A[r * 4 + c] / n; }
  const inOf = [];
  for (let c = 0; c < 3; c++) {
    let best = 0;
    for (let r = 1; r < 3; r++) if (Math.abs(R[r][c]) > Math.abs(R[best][c])) best = r;
    inOf[best] = c;
    for (let k = 0; k < 3; k++) R[best][k] = 0;
  }
  return [nii.dims[inOf[0]], nii.dims[inOf[1]], nii.dims[inOf[2]]];
}

// label map from NIfTI (+ optional meta.json with label names)
function canonicalLabels(nii) {
  // axis-aligned reorientation to the app's canonical RAS grid (same rule as the C++ side)
  const A = nii.affine, R = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  for (let c = 0; c < 3; c++) { const n = Math.hypot(A[c], A[4 + c], A[8 + c]) || 1; for (let r = 0; r < 3; r++) R[r][c] = A[r * 4 + c] / n; }
  const outAx = [], flip = [];
  for (let c = 0; c < 3; c++) {
    let best = 0;
    for (let r = 1; r < 3; r++) if (Math.abs(R[r][c]) > Math.abs(R[best][c])) best = r;
    outAx[c] = best; flip[c] = R[best][c] < 0;
    for (let k = 0; k < 3; k++) R[best][k] = 0;
  }
  const inOf = []; outAx.forEach((o, i) => { inOf[o] = i; });
  const dims = nii.dims, oshape = [dims[inOf[0]], dims[inOf[1]], dims[inOf[2]]];
  let vmax = 0;
  for (let i = 0; i < nii.data.length; i++) {
    const v = nii.data[i];
    if (v > vmax) vmax = v;
    if (v < 0 || Math.abs(v - Math.round(v)) > 1e-3) throw new Error(t('ラベル値 {0} は 0〜255 の整数ではありません', v));
  }
  if (vmax > 255) throw new Error(t('ラベル値 {0} は 255 を超えています', vmax));
  const out = new Uint8Array(oshape[0] * oshape[1] * oshape[2]);
  const q = [0, 0, 0], p = [0, 0, 0];
  for (q[0] = 0; q[0] < oshape[0]; q[0]++) for (q[1] = 0; q[1] < oshape[1]; q[1]++) for (q[2] = 0; q[2] < oshape[2]; q[2]++) {
    for (let a = 0; a < 3; a++) { const i = inOf[a]; p[i] = flip[i] ? dims[i] - 1 - q[a] : q[a]; }
    out[(q[0] * oshape[1] + q[1]) * oshape[2] + q[2]] = Math.round(nii.data[p[0] + dims[0] * (p[1] + dims[1] * p[2])]);
  }
  return { shape: oshape, data: out };
}
function applyLabelMap(map, names, source, mode) {
  // map: canonical Uint8Array with local label values; names[v] = structure name
  const S = App.S;
  const snap = { lab: S.lab.slice(), reg: App.labels.list().map((l) => ({ ...l })) };
  const lut = new Uint8Array(256), present = new Uint8Array(256);
  for (let i = 0; i < map.length; i++) present[map[i]] = 1;
  try {
    if (mode === 'replace') App.labels.clear();
    for (let v = 1; v < 256; v++) if (present[v]) lut[v] = App.labels.ensure(names[v] || `label_${v}`, source).id;
  } catch (e) {  // e.g. more than 255 labels: restore the registry, leave the map untouched
    App.labels.clear();
    for (const l of snap.reg) App.labels.map.set(l.id, l);
    throw e;
  }
  if (mode === 'replace') S.lab.fill(0);
  if (!App.labels.map.has(S.active)) S.active = 0;
  const lab = S.lab;
  for (let i = 0; i < map.length; i++) { const v = map[i]; if (v && lut[v]) lab[i] = lut[v]; }
  const rec = App.editor.pushSnapshot(snap, 'task');
  App.invalidateLut();
  recount();
  renderLabelList(); App.renderViews();
  // the new labels and every label whose voxels were overwritten (their meshes change too)
  const ids = [...new Set([...lut].filter((x) => x).concat(rec.labels.filter((id) => App.labels.map.has(id))))];
  if (mode === 'replace') App.viewer.clear();
  return ids;
}
async function loadLabelFiles(files) {
  try {
    let meta = null, nii = null;
    for (const f of files) {
      if (/\.json$/i.test(f.name)) meta = JSON.parse(await f.text());
      else nii = await Nifti.read(await f.arrayBuffer());
    }
    if (!nii) return toast(t('ラベル NIfTI を選んでください'));
    applyLabelNifti(nii, meta, files[0].name);
  } catch (e) { toast(t('ラベルを読み込めません: {0}', e.message), 6000); log('ERROR ' + e.message); }
}
// throws on errors; returns the label ids that were applied
function applyLabelNifti(nii, meta, name) {
  const c = canonicalLabels(nii);
  if (c.shape.join() !== App.S.shape.join()) throw new Error(t('格子が CT と違います ({0} vs {1})', c.shape.join('×'), App.S.shape.join('×')));
  const names = [];
  const present = new Set(c.data);
  if (meta && meta.labels) for (const l of meta.labels) names[l.id] = l.name;
  for (const v of present) if (v && !names[v]) names[v] = `label_${v}`;
  const ids = applyLabelMap(c.data, names, 'file:' + name, 'merge');
  if (meta && meta.labels) for (const l of meta.labels) {
    const L = App.labels.byName(l.name);
    if (L) {
      if (Array.isArray(l.color) && l.color.length === 3 && l.color.every((x) => typeof x === 'number' && x >= 0 && x <= 1)) L.color = l.color;
      L.verified = !!l.verified;
      if (typeof l.source === 'string' && l.source) L.source = l.source;  // provenance (total / manual / ...)
    }
  }
  App.invalidateLut(); renderLabelList(); App.renderViews();
  updateMeshes(ids);
  return ids;
}

// ================================================================= tasks
function taskOptions() {
  const sel = $('taskSelect'), cur = sel.value;
  sel.innerHTML = '';
  for (const [v, t] of TASKS) sel.add(new Option(t, v));
  for (const m of App.customModels) sel.add(new Option(t('カスタム: {0} v{1} ({2})', m.name, m.version, m.labels.join(', ')), `custom:${m.id}:${m.crop || '-'}|-`));
  if (cur) sel.value = cur;
}
async function runTask() {
  const [task, roi] = $('taskSelect').value.split('|');
  const taskName = $('taskSelect').selectedOptions[0]?.text || task;  // shown in the log and the completion message
  const mode = document.querySelector('input[name=merge]:checked').value;
  busy(true, t('解析中…'));
  const t0 = performance.now();
  try {
    const custom = {};
    for (const m of App.customModels) custom[m.id] = m.file;
    const r = await request({ type: 'run', task, roi, custom }, 'result');
    log(`${taskName}: ${r.seconds.toFixed(1)} s (${r.backend}) [${task}${roi !== '-' ? ' ' + roi : ''}]`);
    if (r.log) log(r.log.trim().split('\n').slice(-14).join('\n'));
    const ids = applyLabelMap(r.labels, r.names, task, mode);
    App.S.tasks.push({ task, roi, time: new Date().toISOString(), seconds: r.seconds });
    await updateMeshes(ids);
    toast(t('完了: {0}（{1} 秒）', taskName, ((performance.now() - t0) / 1000).toFixed(1)));
  } catch (e) { toast(t('解析失敗（{0}）: {1}', taskName, e.message), 6000); log(`ERROR ${taskName}: ${e.message}`); }
  busy(false, t('エンジン {0} / {1} スレッド{2}', App.engine.backend === 'webgpu' ? 'WebGPU' : 'CPU', App.engine.threads, ''));
}

// ================================================================= meshes
async function updateMeshes(ids) {
  if (!App.S.lab) return;
  const fromDirty = !ids;
  ids = (ids || [...App.dirty]).filter((id) => App.labels.map.has(id));
  if (fromDirty) App.dirty.clear();
  if (!ids.length) return;
  const items = ids.map((id) => ({ id, name: App.labels.map.get(id).name }));
  const first = App.viewer.meshes.size === 0, gen = App.volGen;
  try {
    const lab = App.S.lab.slice();
    const r = await request({ type: 'mesh', labels: lab, items }, 'meshes', [lab.buffer]);
    if (gen !== App.volGen) return;  // a new volume was loaded meanwhile
    for (const it of r.items) {
      if (it.indices.length) App.viewer.setMesh(it.id, it.vertices, it.normals, it.indices);
      else App.viewer.removeMesh(it.id);
      const L = App.labels.map.get(it.id);
      if (L) L.meshMl = it.meshMl;
    }
    for (const id of ids) if (!App.labels.map.has(id)) App.viewer.removeMesh(id);
    if (first) App.viewer.fit(); else App.viewer.draw();
  } catch (e) {
    log('mesh ERROR ' + e.message);
    if (gen === App.volGen) for (const id of ids) App.dirty.add(id);  // retry with the next update
  }
  updateButtons();
}
let meshTimer = null;
App.onEdited = (labelIds, n, kind) => {
  if (!App.labels.map.has(App.S.active)) App.S.active = 0;
  App.S.editedVoxels += Math.abs(n);
  for (const l of labelIds) if (l) App.dirty.add(l);
  App.invalidateLut();
  recount();
  renderLabelList();
  App.renderViews();
  if (kind === 'task' || kind === 'delete') { clearTimeout(meshTimer); updateMeshes(); updateButtons(); }
  else if ($('autoMesh').checked) { clearTimeout(meshTimer); meshTimer = setTimeout(() => updateMeshes(), 800); }
};
App.setActive = (id) => { App.S.active = id; renderLabelList(); updateButtons(); };

function recount() {
  const c = new Uint32Array(256), lab = App.S.lab;
  if (lab) for (let i = 0; i < lab.length; i++) c[lab[i]]++;
  App.S.counts = c;
  const vml = App.S.zooms ? App.S.zooms[0] * App.S.zooms[1] * App.S.zooms[2] / 1000 : 0;
  const n = App.labels.map.size;
  $('summary').textContent = App.S.ct ? t('{0} ラベル   編集 {1} voxels   {2} タスク', n, App.S.editedVoxels.toLocaleString(), App.S.tasks.length) : '';
  App.vml = vml;
}

// ================================================================= label list
function renderLabelList() {
  const f = $('labelFilter').value.trim().toLowerCase();
  const el = $('labelList');
  el.innerHTML = '';
  for (const l of App.labels.list()) {
    const disp = Labels.display(l.name);
    if (f && !l.name.toLowerCase().includes(f) && !disp.includes(f)) continue;
    const row = document.createElement('div');
    row.className = 'lab' + (l.id === App.S.active ? ' active' : '');
    const rgb = `rgb(${l.color.map((c) => Math.round(c * 255)).join(',')})`;
    const ml = (App.S.counts[l.id] * (App.vml || 0)).toFixed(1);
    row.innerHTML = `<input type="checkbox" ${l.visible ? 'checked' : ''} title="${t('表示')}"><span class="sw" style="background:${rgb}" title="${t('色を変更')}"></span>` +
      `<span class="nm" title="${esc(l.name)} (id ${l.id}, ${esc(l.source)})">${esc(disp)}</span><span class="ml">${ml} ml</span><span class="vf">${l.verified ? '✓' : ''}</span>`;
    row.querySelector('input').onclick = (e) => { e.stopPropagation(); l.visible = e.target.checked; App.invalidateLut(); App.renderViews(); App.viewer.draw(); };
    row.querySelector('.sw').onclick = (e) => {
      e.stopPropagation();
      const ci = document.createElement('input'); ci.type = 'color';
      ci.value = '#' + l.color.map((c) => Math.round(c * 255).toString(16).padStart(2, '0')).join('');
      ci.oninput = () => { const h = ci.value; l.color = [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16) / 255); App.invalidateLut(); App.renderViews(); App.viewer.draw(); renderLabelList(); };
      ci.click();
    };
    row.onclick = () => App.setActive(l.id);
    row.ondblclick = () => { // jump to the label's centre slice
      const S = App.S, [X, Y, Z] = S.shape;
      let sx = 0, sy = 0, sz = 0, n = 0;
      for (let i = 0; i < S.lab.length; i += 7) if (S.lab[i] === l.id) { sx += (i / (Y * Z)) | 0; sy += ((i / Z) | 0) % Y; sz += i % Z; n++; }
      if (n) App.setCursor([sx / n, sy / n, sz / n]);
    };
    el.appendChild(row);
  }
  const L = App.labels.map.get(App.S.active);
  $('activeInfo').textContent = L ? `${Labels.display(L.name)}  [${L.name}]  id ${L.id}  ${(App.S.counts[L.id] * (App.vml || 0)).toFixed(1)} ml  ${t('由来: {0}', L.source)}` : t('なし（一覧でクリックして選択）');
  $('activeVerified').checked = !!(L && L.verified);
  $('activeOpacity').value = L && L.opacity !== undefined ? L.opacity : 1;
}

// ================================================================= export / save
function volumeNifti(kind) {
  const S = App.S;
  return Nifti.write({ shape: S.shape, affine: S.affine, zooms: S.zooms, data: kind === 'ct' ? S.ct : S.lab, datatype: kind === 'ct' ? 'int16' : 'uint8' });
}
function caseMeta(extra) {
  const S = App.S;
  return Object.assign({
    app: 'TSC++ Annotator', engine: App.engine && App.engine.version, source: S.source, shape: S.shape, zooms: S.zooms,
    affine: S.affine, labels: App.labels.toJSON().map((l) => ({ ...l, voxels: S.counts[l.id] })), tasks: S.tasks,
    edited_voxels: S.editedVoxels, saved: new Date().toISOString(),
  }, extra || {});
}
function meshOBJ() {
  const parts = ['# TSC++ mesh, RAS mm, one object per label\n'];
  let base = 1;
  for (const [id, m] of App.viewer.meshes) {
    const L = App.labels.map.get(id);
    parts.push(`o ${L ? L.name : id}\n`);
    for (let i = 0; i < m.v.length; i += 3) parts.push(`v ${m.v[i].toFixed(3)} ${m.v[i + 1].toFixed(3)} ${m.v[i + 2].toFixed(3)}\n`);
    for (let i = 0; i < m.ix.length; i += 3) parts.push(`f ${m.ix[i] + base} ${m.ix[i + 1] + base} ${m.ix[i + 2] + base}\n`);
    base += m.v.length / 3;
  }
  return new Blob(parts, { type: 'text/plain' });
}
function meshSTL() {
  let nt = 0;
  for (const m of App.viewer.meshes.values()) nt += m.ix.length / 3;
  const buf = new ArrayBuffer(84 + nt * 50), dv = new DataView(buf);
  dv.setUint32(80, nt, true);
  let o = 84;
  for (const m of App.viewer.meshes.values()) {
    const v = m.v, ix = m.ix;
    for (let t = 0; t < ix.length; t += 3) {
      const a = ix[t] * 3, b = ix[t + 1] * 3, c = ix[t + 2] * 3;
      const ux = v[b] - v[a], uy = v[b + 1] - v[a + 1], uz = v[b + 2] - v[a + 2], wx = v[c] - v[a], wy = v[c + 1] - v[a + 1], wz = v[c + 2] - v[a + 2];
      const nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx, l = Math.hypot(nx, ny, nz) || 1;
      for (const x of [nx / l, ny / l, nz / l]) { dv.setFloat32(o, x, true); o += 4; }
      for (const p of [a, b, c]) for (let d = 0; d < 3; d++) { dv.setFloat32(o, v[p + d], true); o += 4; }
      o += 2;
    }
  }
  return new Blob([buf]);
}

// ================================================================= wiring
document.querySelectorAll('.tabs button').forEach((b) => b.onclick = () => {
  document.querySelectorAll('.tabs button').forEach((x) => x.classList.toggle('on', x === b));
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.id === 'tab-' + b.dataset.tab));
});
async function readEntries(entry, out) {
  if (entry.isFile) out.push(await new Promise((res, rej) => entry.file(res, rej)));
  else if (entry.isDirectory) {
    const reader = entry.createReader();
    for (;;) {
      const batch = await new Promise((res, rej) => reader.readEntries(res, rej));
      if (!batch.length) break;
      for (const e of batch) await readEntries(e, out);
    }
  }
}
async function onDrop(e) {
  e.preventDefault(); $('drop').classList.remove('hover');
  if (App.busy) return toast(t('処理中です。終わってから読み込んでください'));
  const out = [];
  for (const it of e.dataTransfer.items) { const en = it.webkitGetAsEntry && it.webkitGetAsEntry(); if (en) await readEntries(en, out); }
  if (out.length === 1 && /\.nii(\.gz)?$/i.test(out[0].name)) return loadNiftiVolume(await out[0].arrayBuffer(), out[0].name);
  loadDicomFiles(out);
}
$('drop').onclick = () => $('dirInput').click();
$('dirInput').onchange = (e) => { const f = [...e.target.files]; e.target.value = ''; loadDicomFiles(f); };
for (const el of [$('drop'), $('grid')]) {
  el.addEventListener('dragover', (e) => { e.preventDefault(); $('drop').classList.add('hover'); });
  el.addEventListener('dragleave', () => $('drop').classList.remove('hover'));
  el.addEventListener('drop', onDrop);
}
$('openNifti').onclick = () => $('niftiInput').click();
$('switchSeries').onclick = switchSeries;
$('niftiInput').onchange = async (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) loadNiftiVolume(await f.arrayBuffer(), f.name); };
$('openLabels').onclick = () => $('labelsInput').click();
$('labelsInput').onchange = (e) => { const f = [...e.target.files]; e.target.value = ''; loadLabelFiles(f); };
$('runTask').onclick = runTask;
$('dlCT').onclick = async () => download(await volumeNifti('ct'), 'ct.nii.gz');
$('dlLabels').onclick = async () => { download(await volumeNifti('labels'), 'labels.nii.gz'); download(new Blob([JSON.stringify(caseMeta(), null, 1)]), 'labels_meta.json'); };
$('dlOBJ').onclick = () => download(meshOBJ(), 'meshes.obj');
$('dlSTL').onclick = () => download(meshSTL(), 'meshes.stl');

document.querySelectorAll('#tools button').forEach((b) => b.onclick = () => setTool(b.dataset.tool));
function setTool(t) {
  App.tool = t;
  document.querySelectorAll('#tools button').forEach((b) => b.classList.toggle('on', b.dataset.tool === t));
  const cur = { nav: 'crosshair', brush: 'none', erase: 'none', fill: 'cell', relabel: 'pointer', pick: 'copy' }[t];
  App.views.forEach((v) => { v.canvas.style.cursor = cur; v.render(); });
}
$('brushSize').oninput = (e) => { App.brushRadius = +e.target.value; $('brushSizeVal').textContent = e.target.value; };
$('sphere').onchange = (e) => { App.sphere = e.target.checked; };
$('protect').onchange = (e) => { App.protect = e.target.checked; };
$('eraseAll').onchange = (e) => { App.eraseAll = e.target.checked; };
const huSync = () => {
  const a = +$('huLo').value, b = +$('huHi').value;
  App.huRange = { on: $('huOn').checked, lo: Math.min(a, b), hi: Math.max(a, b) };
};
for (const id of ['huOn', 'huLo', 'huHi']) { $(id).onchange = huSync; $(id).oninput = huSync; }
$('undo').onclick = () => { if (!App.busy && !App.editor.stroke) App.editor.undo(); };
$('redo').onclick = () => { if (!App.busy && !App.editor.stroke) App.editor.redo(); };
$('wlPreset').onchange = (e) => { const [l, w] = e.target.value.split(',').map(Number); App.setWindow(l, w); };
$('overlay').onchange = (e) => { App.S.overlay = e.target.checked; App.renderViews(); };
$('alpha').oninput = (e) => { App.S.alpha = +e.target.value; App.renderViews(); };
$('crosshair').onchange = (e) => { App.S.crosshair = e.target.checked; App.renderViews(); };
$('updateMeshes').onclick = () => updateMeshes([...App.labels.map.keys()].filter((id) => App.S.counts[id]));
$('labelFilter').oninput = renderLabelList;
$('showAll').onclick = () => { App.labels.map.forEach((l) => { l.visible = true; }); App.invalidateLut(); renderLabelList(); App.renderViews(); App.viewer.draw(); };
$('hideAll').onclick = () => { App.labels.map.forEach((l) => { l.visible = false; }); App.invalidateLut(); renderLabelList(); App.renderViews(); App.viewer.draw(); };
$('addLabel').onclick = () => {
  const name = $('newLabelName').value.trim().replace(/\s+/g, '_');
  if (!name) return toast(t('名前を入力してください'));
  try {
    const h = $('newLabelColor').value;
    const before = App.labels.list().map((x) => ({ ...x }));
    const l = App.labels.add(name, [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16) / 255), 'manual');
    App.editor.pushRegistry(before, 'add');
    App.invalidateLut(); App.setActive(l.id); $('newLabelName').value = '';
    if (App.tool === 'nav') setTool('brush');
    toast(t('ラベル「{0}」を追加しました。ブラシで塗ってください', name));
  } catch (e) { toast(e.message); }
};
$('activeVerified').onchange = (e) => { const L = App.labels.map.get(App.S.active); if (L) { L.verified = e.target.checked; renderLabelList(); } };
$('activeOpacity').oninput = (e) => { const L = App.labels.map.get(App.S.active); if (L) { L.opacity = +e.target.value; App.viewer.draw(); } };
$('renameLabel').onclick = () => {
  const L = App.labels.map.get(App.S.active), name = $('renameInput').value.trim().replace(/\s+/g, '_');
  if (!L || !name) return toast(t('新しい名前を入力してください'));
  if (App.labels.byName(name)) return toast(t('同じ名前のラベルがあります'));
  const before = App.labels.list().map((x) => ({ ...x }));
  L.name = name; $('renameInput').value = '';
  App.editor.pushRegistry(before, 'rename');
  renderLabelList();
};
$('deleteLabel').onclick = () => {
  const L = App.labels.map.get(App.S.active);
  if (!L) return;
  const snap = { lab: App.S.lab.slice(), reg: App.labels.list().map((l) => ({ ...l })) };
  const lab = App.S.lab;
  for (let i = 0; i < lab.length; i++) if (lab[i] === L.id) lab[i] = 0;
  App.labels.remove(L.id); App.viewer.removeMesh(L.id); App.viewer.draw();
  App.editor.pushSnapshot(snap, 'delete');
  App.S.active = 0; App.invalidateLut(); recount(); renderLabelList(); App.renderViews(); updateButtons();
  toast(t('ラベル「{0}」を削除しました（元に戻せます）', L.name));
};

addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
  if (e.key === ' ') { App.spaceDown = true; e.preventDefault(); }
  const locked = App.busy || App.editor.stroke;  // saving / running, or in the middle of a brush stroke
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); if (locked) return; return e.shiftKey ? App.editor.redo() : App.editor.undo(); }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); if (locked) return; return App.editor.redo(); }
  const map = { n: 'nav', b: 'brush', e: 'erase', f: 'fill', r: 'relabel', i: 'pick' };
  if (!e.ctrlKey && map[e.key.toLowerCase()]) setTool(map[e.key.toLowerCase()]);
  if (e.key === '[' || e.key === ']') {
    const s = $('brushSize'); s.value = Math.max(0.5, Math.min(20, +s.value + (e.key === ']' ? 0.5 : -0.5))); s.oninput({ target: s });
    App.renderViews();
  }
});
addEventListener('keyup', (e) => { if (e.key === ' ') App.spaceDown = false; });

App.log = log;

taskOptions();
updateButtons();
// ?demo=1: load the DICOM series exposed by the server (--demo)
if (new URLSearchParams(location.search).has('demo')) {
  fetch('/demo/list').then((r) => r.json()).then(async (names) => {
    const files = [];
    for (const n of names) files.push(new File([await (await fetch('/demo/' + encodeURIComponent(n))).arrayBuffer()], n));
    const wait = () => (App.engine ? loadDicomFiles(files) : App.engineDead ? null : setTimeout(wait, 300));
    wait();
  });
}
window.App = App;
