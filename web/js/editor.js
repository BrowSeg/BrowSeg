'use strict';
// Manual label editing: brush / eraser (disc or sphere, optional HU window, label protection),
// 2-D flood fill, 3-D connected-component relabel, label picker; undo / redo.

class Editor {
  constructor(app) {
    this.app = app;
    this.undoStack = [];
    this.redoStack = [];
    this.stroke = null;
    this.last = null;
  }

  // ---------------------------------------------------------------- strokes
  // unique: the caller guarantees each voxel is set at most once (3-D relabel), so no `seen` set is needed
  // (a JS Set is limited to ~16.7 M entries)
  newStroke(kind, unique = false) {
    return { kind, idx: [], old: [], nv: [], seen: unique ? null : new Set(), labels: new Set() };
  }
  set(st, i, v) {
    const lab = this.app.S.lab;
    if (lab[i] === v || (st.seen && st.seen.has(i))) return;
    if (st.seen) st.seen.add(i);
    st.idx.push(i); st.old.push(lab[i]); st.nv.push(v);
    st.labels.add(lab[i]); st.labels.add(v);
    lab[i] = v;
  }
  commit(st) {
    if (!st || !st.idx.length) return;
    const rec = { kind: st.kind, idx: Int32Array.from(st.idx), old: Uint8Array.from(st.old), nv: Uint8Array.from(st.nv),
                  labels: [...st.labels].filter((l) => l > 0) };
    rec.bytes = rec.idx.length * 6;
    this.push(rec);
    this.app.onEdited(rec.labels, rec.idx.length, rec.kind);
  }
  // undo history bounded by count (50) and memory (~600 MB)
  push(rec) {
    this.undoStack.push(rec);
    this.redoStack.length = 0;
    let bytes = this.undoStack.reduce((s, r) => s + (r.bytes || 0), 0);
    while (this.undoStack.length > 1 && (this.undoStack.length > 50 || bytes > 600e6)) bytes -= this.undoStack.shift().bytes || 0;
  }
  // Whole-map change (task runs, label deletion). `before` = {lab: copy of the map, reg: registry copy} taken
  // before the change, called after it. Few changes: sparse (index + old + new, 6 B each); many changes
  // (> 1/6 of the voxels): dense XOR of old and new map (1 B per voxel, applied the same way both directions).
  pushSnapshot(before, kind) {
    const lab = this.app.S.lab, N = lab.length, touched = new Uint8Array(256);
    let n = 0;
    for (let i = 0; i < N; i++) if (lab[i] !== before.lab[i]) { n++; touched[lab[i]] = 1; touched[before.lab[i]] = 1; }
    const rec = { kind, snapshot: true, regOld: before.reg, regNew: this.app.labels.list().map((l) => ({ ...l })),
                  labels: [...touched.keys()].filter((l) => l && touched[l]) };
    if (n * 6 > N) {
      rec.xor = new Uint8Array(N);
      for (let i = 0; i < N; i++) rec.xor[i] = lab[i] ^ before.lab[i];
      rec.bytes = N;
    } else {
      rec.idx = new Int32Array(n); rec.old = new Uint8Array(n); rec.nv = new Uint8Array(n);
      for (let i = 0, k = 0; i < N; i++) if (lab[i] !== before.lab[i]) { rec.idx[k] = i; rec.old[k] = before.lab[i]; rec.nv[k++] = lab[i]; }
      rec.bytes = n * 6;
    }
    this.push(rec);
    return rec;
  }
  // registry-only step (label added / renamed): undo / redo switch just the registry
  pushRegistry(regBefore, kind) {
    this.push({ kind, snapshot: true, idx: new Int32Array(0), old: new Uint8Array(0), nv: new Uint8Array(0),
                regOld: regBefore, regNew: this.app.labels.list().map((l) => ({ ...l })), labels: [], bytes: 0 });
  }
  swapSnapshot(r, undo) {
    const app = this.app, lab = app.S.lab;
    if (r.xor) for (let i = 0; i < lab.length; i++) lab[i] ^= r.xor[i];
    else { const vals = undo ? r.old : r.nv; for (let k = 0; k < r.idx.length; k++) lab[r.idx[k]] = vals[k]; }
    // registry: only what this step changed is switched; labels added / edited later are kept
    const target = new Map((undo ? r.regOld : r.regNew).map((l) => [l.id, l]));
    const other = new Map((undo ? r.regNew : r.regOld).map((l) => [l.id, l]));
    for (const [id, o] of other) {
      const t = target.get(id);
      if (!t) { app.labels.map.delete(id); app.viewer.removeMesh(id); }        // created by this step
      else if (t.name !== o.name) app.labels.map.set(id, { ...t });             // id re-used by this step
    }
    for (const [id, t] of target) if (!other.has(id)) app.labels.map.set(id, { ...t });  // removed by this step
    app.onEdited(r.labels.filter((id) => app.labels.map.has(id)), 0, r.kind);
  }
  undo() {
    const r = this.undoStack.pop();
    if (!r) return;
    if (r.snapshot) { this.swapSnapshot(r, true); this.redoStack.push(r); return; }
    const lab = this.app.S.lab;
    for (let k = r.idx.length - 1; k >= 0; k--) lab[r.idx[k]] = r.old[k];
    this.redoStack.push(r);
    this.app.onEdited(r.labels, -r.idx.length, 'undo');
  }
  redo() {
    const r = this.redoStack.pop();
    if (!r) return;
    if (r.snapshot) { this.swapSnapshot(r, false); this.undoStack.push(r); return; }
    const lab = this.app.S.lab;
    for (let k = 0; k < r.idx.length; k++) lab[r.idx[k]] = r.nv[k];
    this.undoStack.push(r);
    this.app.onEdited(r.labels, r.idx.length, 'redo');
  }
  reset() { this.undoStack.length = 0; this.redoStack.length = 0; }

  // ---------------------------------------------------------------- pointer events from SliceView
  begin(view, ev) {
    const app = this.app, S = app.S;
    if (app.busy) { app.toast(t('処理中は編集できません')); return; }
    const vox = view.eventVoxel(ev);
    if (!vox || !S.lab) return;
    if (app.tool === 'pick' || ev.altKey) {
      const l = S.lab[this.index(vox)];
      if (l) app.setActive(l);
      return;
    }
    if ((app.tool === 'brush' || app.tool === 'fill' || app.tool === 'relabel') && !app.S.active) {
      app.toast(t('先に編集するラベルを選択してください（ラベル一覧でクリック）'));
      return;
    }
    if (app.tool === 'brush' || app.tool === 'erase') {
      this.stroke = this.newStroke(app.tool);
      this.last = vox;
      this.stamp(view, vox);
      app.renderViews();
    } else if (app.tool === 'fill') {
      const st = this.newStroke('fill');
      this.fill2d(view, vox, st);
      this.commit(st);
    } else if (app.tool === 'relabel') {
      const st = this.newStroke('relabel', true);
      this.relabel3d(vox, st);
      this.commit(st);
    }
  }
  move(view, ev) {
    if (!this.stroke) return;
    const vox = view.eventVoxel(ev);
    if (!vox) return;
    // interpolate between the last and the current position (half-radius steps)
    const S = this.app.S, sp = S.zooms;
    const d = [0, 1, 2].map((k) => (vox[k] - this.last[k]) * sp[k]);
    const len = Math.hypot(...d);
    const step = Math.max(0.3, this.app.brushRadius / 2);
    const n = Math.max(1, Math.ceil(len / step));
    for (let i = 1; i <= n; i++) {
      const p = [0, 1, 2].map((k) => Math.round(this.last[k] + (vox[k] - this.last[k]) * i / n));
      this.stamp(view, p);
    }
    this.last = vox;
    this.app.renderViews();
  }
  end() {
    if (this.stroke) this.commit(this.stroke);
    this.stroke = null;
  }

  index([x, y, z]) {
    const [, Y, Z] = this.app.S.shape;
    return (x * Y + y) * Z + z;
  }
  allowed(i, hu) {
    const app = this.app;
    if (app.huRange.on && (hu < app.huRange.lo || hu > app.huRange.hi)) return false;
    return true;
  }

  // brush / eraser stamp: disc in the view plane (or sphere) with radius in mm
  stamp(view, c) {
    const app = this.app, S = app.S, [X, Y, Z] = S.shape, sp = S.zooms;
    const r = app.brushRadius;
    const fixed = view.geom().fixed;
    const rad = [0, 1, 2].map((k) => (k === fixed && !app.sphere ? 0 : Math.floor(r / sp[k])));
    const active = S.active, lab = S.lab, ct = S.ct, st = this.stroke;
    for (let dx = -rad[0]; dx <= rad[0]; dx++) {
      const x = c[0] + dx;
      if (x < 0 || x >= X) continue;
      for (let dy = -rad[1]; dy <= rad[1]; dy++) {
        const y = c[1] + dy;
        if (y < 0 || y >= Y) continue;
        for (let dz = -rad[2]; dz <= rad[2]; dz++) {
          const z = c[2] + dz;
          if (z < 0 || z >= Z) continue;
          const d2 = (dx * sp[0]) ** 2 + (dy * sp[1]) ** 2 + (dz * sp[2]) ** 2;
          if (d2 > r * r) continue;
          const i = (x * Y + y) * Z + z;
          if (!this.allowed(i, ct[i])) continue;
          const cur = lab[i];
          if (st.kind === 'brush') {
            if (app.protect && cur !== 0 && cur !== active) continue;
            this.set(st, i, active);
          } else {
            if (cur === 0) continue;
            if (!app.eraseAll && cur !== active) continue;
            this.set(st, i, 0);
          }
        }
      }
    }
  }

  // 2-D flood fill in the view plane: region of the clicked label (incl. background) -> active label
  fill2d(view, vox, st) {
    const app = this.app, S = app.S, lab = S.lab, ct = S.ct;
    const g = view.geom();
    const [u0, v0] = view.voxelToUV(...vox);
    const target = lab[this.index(vox)];
    if (target === S.active) return;
    const seen = new Uint8Array(g.W * g.H);
    const stack = [u0 + v0 * g.W];
    seen[stack[0]] = 1;
    let count = 0;
    while (stack.length) {
      const p = stack.pop();
      const u = p % g.W, v = (p / g.W) | 0;
      const i = g.base + u * g.du + v * g.dv;
      if (lab[i] !== target || !this.allowed(i, ct[i])) continue;
      this.set(st, i, S.active);
      if (++count > 4e6) break;
      if (u > 0 && !seen[p - 1]) { seen[p - 1] = 1; stack.push(p - 1); }
      if (u < g.W - 1 && !seen[p + 1]) { seen[p + 1] = 1; stack.push(p + 1); }
      if (v > 0 && !seen[p - g.W]) { seen[p - g.W] = 1; stack.push(p - g.W); }
      if (v < g.H - 1 && !seen[p + g.W]) { seen[p + g.W] = 1; stack.push(p + g.W); }
    }
    if (target === 0 && count > 0.5 * g.W * g.H) app.toast(t('塗りつぶし範囲が断面の半分を超えました。CT値範囲の制限を使うと安全です'));
  }

  // 3-D connected component (26-neighbourhood) of the clicked label -> active label
  relabel3d(vox, st) {
    const app = this.app, S = app.S, lab = S.lab, [X, Y, Z] = S.shape;
    const i0 = this.index(vox), L = lab[i0];
    if (!L) { app.toast(t('背景ではなくラベルのある場所をクリックしてください')); return; }
    if (L === S.active) { app.toast(t('クリックした領域は既に選択中のラベルです')); return; }
    const stack = [i0];
    const mark = new Uint8Array(X * Y * Z);  // visited
    mark[i0] = 1;
    while (stack.length) {
      const i = stack.pop();
      this.set(st, i, S.active);
      const x = (i / (Y * Z)) | 0, y = ((i / Z) | 0) % Y, z = i % Z;
      for (let dx = -1; dx <= 1; dx++) {
        const xx = x + dx; if (xx < 0 || xx >= X) continue;
        for (let dy = -1; dy <= 1; dy++) {
          const yy = y + dy; if (yy < 0 || yy >= Y) continue;
          for (let dz = -1; dz <= 1; dz++) {
            const zz = z + dz; if (zz < 0 || zz >= Z) continue;
            const j = (xx * Y + yy) * Z + zz;
            if (!mark[j] && lab[j] === L) { mark[j] = 1; stack.push(j); }
          }
        }
      }
    }
    app.toast(t('{0} ボクセルを付け替えました', st.idx.length.toLocaleString()));
  }
}
