'use strict';
// Orthogonal slice views (axial / coronal / sagittal) of the canonical RAS volume.
// Volume index: (x * Y + y) * Z + z. Display convention (radiological): patient right on
// screen left, anterior up (axial), superior up (coronal / sagittal), anterior left (sagittal).

class SliceView {
  constructor(app, container, axis) {
    this.app = app;
    this.axis = axis;  // 'axial' | 'coronal' | 'sagittal'
    this.el = container;
    this.canvas = container.querySelector('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.info = container.querySelector('.vinfo');
    this.zoom = 1;
    this.pan = [0, 0];
    this.off = document.createElement('canvas');
    this.hover = null;
    this.bind();
    new ResizeObserver(() => this.render()).observe(this.canvas);
  }

  // ---------------------------------------------------------------- geometry
  geom() {
    const { shape: [X, Y, Z], zooms: [sx, sy, sz] } = this.app.S;
    const c = this.app.S.cursor;
    if (this.axis === 'axial') return { W: X, H: Y, su: sx, sv: sy, base: ((X - 1) * Y + (Y - 1)) * Z + c[2], du: -Y * Z, dv: -Z, fixed: 2, N: Z };
    if (this.axis === 'coronal') return { W: X, H: Z, su: sx, sv: sz, base: ((X - 1) * Y + c[1]) * Z + (Z - 1), du: -Y * Z, dv: -1, fixed: 1, N: Y };
    return { W: Y, H: Z, su: sy, sv: sz, base: (c[0] * Y + (Y - 1)) * Z + (Z - 1), du: -Z, dv: -1, fixed: 0, N: X };
  }
  uvToVoxel(u, v) {
    const { shape: [X, Y, Z], cursor: c } = this.app.S;
    if (this.axis === 'axial') return [X - 1 - u, Y - 1 - v, c[2]];
    if (this.axis === 'coronal') return [X - 1 - u, c[1], Z - 1 - v];
    return [c[0], Y - 1 - u, Z - 1 - v];
  }
  voxelToUV(x, y, z) {
    const { shape: [X, Y, Z] } = this.app.S;
    if (this.axis === 'axial') return [X - 1 - x, Y - 1 - y];
    if (this.axis === 'coronal') return [X - 1 - x, Z - 1 - z];
    return [Y - 1 - y, Z - 1 - z];
  }
  transform(g) {
    const cw = this.canvas.width, ch = this.canvas.height;
    const s0 = Math.min(cw / (g.W * g.su), ch / (g.H * g.sv)) * 0.96;
    const s = s0 * this.zoom;
    const w = g.W * g.su * s, h = g.H * g.sv * s;
    return { s, ox: (cw - w) / 2 + this.pan[0], oy: (ch - h) / 2 + this.pan[1], pu: g.su * s, pv: g.sv * s };
  }
  eventUV(ev) {
    const r = this.canvas.getBoundingClientRect();
    const px = (ev.clientX - r.left) * devicePixelRatio, py = (ev.clientY - r.top) * devicePixelRatio;
    const g = this.geom(), t = this.transform(g);
    return [(px - t.ox) / t.pu, (py - t.oy) / t.pv, g];
  }
  eventVoxel(ev) {
    const [fu, fv, g] = this.eventUV(ev);
    const u = Math.floor(fu), v = Math.floor(fv);
    if (u < 0 || v < 0 || u >= g.W || v >= g.H) return null;
    return this.uvToVoxel(u, v);
  }

  // ---------------------------------------------------------------- rendering
  render() {
    const S = this.app.S;
    const cv = this.canvas;
    const w = Math.round(cv.clientWidth * devicePixelRatio), h = Math.round(cv.clientHeight * devicePixelRatio);
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    const ctx = this.ctx;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, w, h);
    if (!S.ct) return;
    const g = this.geom();
    if (this.off.width !== g.W || this.off.height !== g.H) { this.off.width = g.W; this.off.height = g.H; }
    const octx = this.off.getContext('2d');
    const img = octx.createImageData(g.W, g.H), d = img.data;
    const ct = S.ct, lab = S.lab, gray = this.app.grayLut(), { rgb, vis } = this.app.labelLut();
    const a = S.overlay ? S.alpha : 0, a1 = 1 - a;
    for (let v = 0; v < g.H; v++) {
      let idx = g.base + v * g.dv, o = v * g.W * 4;
      for (let u = 0; u < g.W; u++, idx += g.du, o += 4) {
        const gv = gray[ct[idx] + 32768];
        const l = lab ? lab[idx] : 0;
        if (l && vis[l] && a > 0) {
          d[o] = gv * a1 + rgb[l * 3] * a; d[o + 1] = gv * a1 + rgb[l * 3 + 1] * a; d[o + 2] = gv * a1 + rgb[l * 3 + 2] * a;
        } else {
          d[o] = d[o + 1] = d[o + 2] = gv;
        }
        d[o + 3] = 255;
      }
    }
    octx.putImageData(img, 0, 0);
    const t = this.transform(g);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.off, t.ox, t.oy, g.W * t.pu, g.H * t.pv);
    // crosshair
    const c = S.cursor;
    const [cu, cvv] = this.voxelToUV(c[0], c[1], c[2]);
    const colors = { axial: '#e0564f', coronal: '#5fb35f', sagittal: '#4f86e0' };
    const others = { axial: ['sagittal', 'coronal'], coronal: ['sagittal', 'axial'], sagittal: ['coronal', 'axial'] }[this.axis];
    if (S.crosshair) {
      ctx.lineWidth = 1 * devicePixelRatio;
      ctx.globalAlpha = 0.7;
      ctx.strokeStyle = colors[others[0]];
      ctx.beginPath(); ctx.moveTo(t.ox + (cu + 0.5) * t.pu, t.oy); ctx.lineTo(t.ox + (cu + 0.5) * t.pu, t.oy + g.H * t.pv); ctx.stroke();
      ctx.strokeStyle = colors[others[1]];
      ctx.beginPath(); ctx.moveTo(t.ox, t.oy + (cvv + 0.5) * t.pv); ctx.lineTo(t.ox + g.W * t.pu, t.oy + (cvv + 0.5) * t.pv); ctx.stroke();
      ctx.globalAlpha = 1;
    }
    if (this.app.sim) this.app.sim.drawOverlay(this, ctx, g, t);
    // brush outline
    const tool = this.app.tool;
    if (this.hover && (tool === 'brush' || tool === 'erase')) {
      const r = this.app.brushRadius;
      ctx.strokeStyle = tool === 'brush' ? '#ffd166' : '#ff6b6b';
      ctx.lineWidth = 1.5 * devicePixelRatio;
      ctx.beginPath();
      ctx.ellipse(this.hover[0], this.hover[1], r * t.s, r * t.s, 0, 0, 2 * Math.PI);
      ctx.stroke();
    }
    this.info.textContent = `${{ axial: 'Axial', coronal: 'Coronal', sagittal: 'Sagittal' }[this.axis]}  ${c[g.fixed] + 1} / ${g.N}`;
    this.el.style.setProperty('--frame', colors[this.axis]);
  }

  // ---------------------------------------------------------------- interaction
  bind() {
    const cv = this.canvas;
    let drag = null;
    cv.addEventListener('contextmenu', (e) => e.preventDefault());
    cv.addEventListener('pointerdown', (e) => {
      if (!this.app.S.ct) return;
      cv.setPointerCapture(e.pointerId);
      const mode = e.button === 2 ? 'wl' : e.button === 1 || (e.button === 0 && this.app.spaceDown) ? 'pan'
        : this.app.tool === 'nav' ? 'nav' : 'tool';
      drag = { mode, x: e.clientX, y: e.clientY, wl: [...this.app.S.window] };
      if (mode === 'nav') this.navTo(e);
      if (mode === 'tool' && this.app.tool.startsWith('sim-')) { drag = null; this.app.sim.onSliceClick(this, e); return; }
      if (mode === 'tool') this.app.editor.begin(this, e);
    });
    cv.addEventListener('pointermove', (e) => {
      const r = cv.getBoundingClientRect();
      this.hover = [(e.clientX - r.left) * devicePixelRatio, (e.clientY - r.top) * devicePixelRatio];
      const vox = this.app.S.ct ? this.eventVoxel(e) : null;
      this.app.showProbe(vox);
      if (!drag) {
        if (this.app.tool === 'brush' || this.app.tool === 'erase') this.render();
        return;
      }
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (drag.mode === 'pan') { this.pan[0] += dx * devicePixelRatio; this.pan[1] += dy * devicePixelRatio; drag.x = e.clientX; drag.y = e.clientY; this.render(); }
      else if (drag.mode === 'wl') { this.app.setWindow(drag.wl[0] - dy * 2, Math.max(1, drag.wl[1] + dx * 4)); }
      else if (drag.mode === 'nav') this.navTo(e);
      else this.app.editor.move(this, e);
    });
    const end = (e) => {
      if (drag && drag.mode === 'tool') this.app.editor.end(this, e);
      drag = null;
    };
    cv.addEventListener('pointerup', end);
    cv.addEventListener('pointercancel', end);
    cv.addEventListener('pointerleave', () => { this.hover = null; this.render(); });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (!this.app.S.ct) return;
      if (e.ctrlKey || e.shiftKey) {
        const f = Math.exp(-e.deltaY * 0.0015);
        this.zoom = Math.max(0.5, Math.min(20, this.zoom * f));
        this.render();
        return;
      }
      const g = this.geom(), c = [...this.app.S.cursor];
      c[g.fixed] = Math.max(0, Math.min(g.N - 1, c[g.fixed] + (e.deltaY > 0 ? -1 : 1)));
      this.app.setCursor(c);
    }, { passive: false });
    cv.addEventListener('dblclick', () => { this.zoom = 1; this.pan = [0, 0]; this.render(); });
  }
  navTo(e) {
    const vox = this.eventVoxel(e);
    if (vox) this.app.setCursor(vox);
  }
}
