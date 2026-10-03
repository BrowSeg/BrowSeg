'use strict';
// WebGL2 viewer: one mesh (colour / visibility from the label registry) per label, plus "extras"
// (body surface, instruments, ports) with their own style, an optional laparoscope view
// (picture-in-picture or full), ray picking and fixed-size capture.

class Viewer3D {
  constructor(canvas) {
    this.cv = canvas;
    const gl = (this.gl = canvas.getContext('webgl2', { antialias: true, preserveDrawingBuffer: true }));
    this.meshes = new Map();  // label id -> {vao, count, lo, hi, v, n, ix}
    this.extras = new Map();  // key -> mesh + style {color, opacity, visible, scopeHide, scopeColor}
    this.scope = null;        // {eye, dir, up, fov, pip, full, size}
    this.yaw = 0; this.pitch = 0; this.dist = 3; this.pan = [0, 0];
    this.center = [0, 0, 0]; this.radius = 100;
    if (!gl) return;
    const vs = `#version 300 es
      in vec3 p; in vec3 n; uniform mat4 mvp, mv; out vec3 vn; out vec3 vp;
      void main(){ vn = mat3(mv) * n; vp = (mv * vec4(p,1.)).xyz; gl_Position = mvp * vec4(p,1.); }`;
    const fs = `#version 300 es
      precision highp float; in vec3 vn; in vec3 vp; uniform vec3 base; uniform float alpha; uniform int scope; uniform vec4 vpr; out vec4 o;
      void main(){ vec3 N = normalize(vn); if(!gl_FrontFacing) N = -N; vec3 V = normalize(-vp);
        if (scope == 1) {  // laparoscope: light at the scope tip, distance fall-off, circular vignette
          float dist = length(vp), fall = 1. / (1. + pow(dist / 110., 2.));
          float d = max(dot(N, V), 0.), s = pow(d, 60.) * .55;
          vec2 q = (gl_FragCoord.xy - vpr.xy - vpr.zw * .5) / (min(vpr.z, vpr.w) * .5);
          float vig = smoothstep(1.02, .82, length(q));
          vec3 c = base * (.12 + 1.05 * d) * fall * 1.5 + vec3(s) * fall * .7;
          c = c * 1.25 / (1. + .55 * c);  // soft highlight roll-off
          o = vec4(c * vig, 1.); return; }
        vec3 L1 = normalize(vec3(.4,.6,1.)), L2 = normalize(vec3(-.6,-.2,.6));
        float d = max(dot(N,L1),0.)*.75 + max(dot(N,L2),0.)*.3;
        float s = pow(max(dot(N, normalize(L1+V)),0.), 40.)*.3;
        float rim = pow(1.-max(dot(N,V),0.), 3.)*.2;
        o = vec4(base*(.25+d) + vec3(s) + base*rim, alpha); }`;
    const sh = (t, s) => { const x = gl.createShader(t); gl.shaderSource(x, s); gl.compileShader(x); if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw gl.getShaderInfoLog(x); return x; };
    this.prog = gl.createProgram();
    gl.attachShader(this.prog, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(this.prog, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(this.prog);
    this.u = {};
    for (const k of ['mvp', 'mv', 'base', 'alpha', 'scope', 'vpr']) this.u[k] = gl.getUniformLocation(this.prog, k);
    this.bind();
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  // ---------------------------------------------------------------- meshes
  upload(v, n, ix) {
    const gl = this.gl;
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const bufs = [];
    const buf = (data, name) => { const b = gl.createBuffer(); bufs.push(b); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW); const loc = gl.getAttribLocation(this.prog, name); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, 0, 0); };
    buf(v, 'p'); buf(n, 'n');
    const eb = gl.createBuffer(); bufs.push(eb);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, eb); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, ix, gl.STATIC_DRAW);
    gl.bindVertexArray(null);
    const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    for (let i = 0; i < v.length; i += 3) for (let d = 0; d < 3; d++) { lo[d] = Math.min(lo[d], v[i + d]); hi[d] = Math.max(hi[d], v[i + d]); }
    return { vao, bufs, count: ix.length, lo, hi, v, n, ix };
  }
  release(m) { this.gl.deleteVertexArray(m.vao); for (const b of m.bufs) this.gl.deleteBuffer(b); }
  setMesh(id, v, n, ix) {
    if (!this.gl) return;
    this.removeMesh(id);
    if (!ix.length) return;
    this.meshes.set(id, this.upload(v, n, ix));
  }
  removeMesh(id) {
    const m = this.meshes.get(id);
    if (!m) return;
    this.release(m);
    this.meshes.delete(id);
  }
  setExtra(key, v, n, ix, style) {
    if (!this.gl) return;
    const old = this.extras.get(key);
    if (old && old.ix === ix && old.v.length === v.length) {  // same topology (deformed wall): update positions only
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, old.bufs[0]); gl.bufferSubData(gl.ARRAY_BUFFER, 0, v);
      gl.bindBuffer(gl.ARRAY_BUFFER, old.bufs[1]); gl.bufferSubData(gl.ARRAY_BUFFER, 0, n);
      old.v = v; old.n = n; old.style = Object.assign(old.style, style || {});
      for (let d = 0; d < 3; d++) { old.lo[d] = Infinity; old.hi[d] = -Infinity; }
      for (let i = 0; i < v.length; i += 3) for (let d = 0; d < 3; d++) { if (v[i + d] < old.lo[d]) old.lo[d] = v[i + d]; if (v[i + d] > old.hi[d]) old.hi[d] = v[i + d]; }
      return;
    }
    this.removeExtra(key);
    const m = this.upload(v, n, ix);
    m.style = style || {};
    this.extras.set(key, m);
  }
  removeExtra(key) {
    const m = this.extras.get(key);
    if (!m) return;
    this.release(m);
    this.extras.delete(key);
  }
  clear() { for (const id of [...this.meshes.keys()]) this.removeMesh(id); this.draw(); }
  fit() {
    const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    let any = false;
    for (const [id, m] of this.meshes) {
      const l = this.labels && this.labels.map.get(id);
      if (l && !l.visible) continue;
      any = true;
      for (let d = 0; d < 3; d++) { lo[d] = Math.min(lo[d], m.lo[d]); hi[d] = Math.max(hi[d], m.hi[d]); }
    }
    const skin = this.extras.get('skin');
    if (skin && skin.style.visible !== false) { any = true; for (let d = 0; d < 3; d++) { lo[d] = Math.min(lo[d], skin.lo[d]); hi[d] = Math.max(hi[d], skin.hi[d]); } }
    if (!any) return;
    this.center = lo.map((l, d) => (l + hi[d]) / 2);
    this.radius = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2 || 1;
    this.yaw = 0; this.pitch = 0; this.dist = 3; this.pan = [0, 0];
    this.draw();
  }

  // ---------------------------------------------------------------- matrices (column-major 4x4)
  static mul(a, b) { const r = new Float32Array(16); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k]; r[i * 4 + j] = s; } return r; }
  static persp(f, a, n, fa) { const t = 1 / Math.tan(f / 2); return new Float32Array([t / a, 0, 0, 0, 0, t, 0, 0, 0, 0, (fa + n) / (n - fa), -1, 0, 0, 2 * fa * n / (n - fa), 0]); }
  static nrm(a) { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  static crs(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  static lookAt(eye, dir, up) {
    const f = Viewer3D.nrm(dir), s = Viewer3D.nrm(Viewer3D.crs(f, up)), u = Viewer3D.crs(s, f);
    return new Float32Array([s[0], u[0], -f[0], 0, s[1], u[1], -f[1], 0, s[2], u[2], -f[2], 0,
      -(s[0] * eye[0] + s[1] * eye[1] + s[2] * eye[2]), -(u[0] * eye[0] + u[1] * eye[1] + u[2] * eye[2]), f[0] * eye[0] + f[1] * eye[1] + f[2] * eye[2], 1]);
  }
  orbitMV() {
    const M = Viewer3D.mul;
    const rotX = (a) => { const c = Math.cos(a), s = Math.sin(a); return new Float32Array([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]); };
    const rotY = (a) => { const c = Math.cos(a), s = Math.sin(a); return new Float32Array([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]); };
    const trans = (x, y, z) => new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]);
    const scale = (s) => new Float32Array([s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0, 0, 0, 1]);
    const rasToView = new Float32Array([-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1]);  // anterior view
    let mv = M(scale(1 / this.radius), trans(-this.center[0], -this.center[1], -this.center[2]));
    mv = M(rasToView, mv); mv = M(rotY(this.yaw), mv); mv = M(rotX(this.pitch), mv); mv = M(trans(this.pan[0], this.pan[1], -this.dist), mv);
    return mv;
  }

  // ---------------------------------------------------------------- drawing
  draw() {
    const gl = this.gl, cv = this.cv;
    if (!gl) return;
    const w = this.forceSize ? this.forceSize[0] : Math.round(cv.clientWidth * devicePixelRatio);
    const h = this.forceSize ? this.forceSize[1] : Math.round(cv.clientHeight * devicePixelRatio);
    if (!w || !h) return;
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    gl.disable(gl.SCISSOR_TEST);
    gl.viewport(0, 0, w, h);
    gl.clearColor(0.03, 0.035, 0.045, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!this.meshes.size && !this.extras.size) return;
    const sc = this.scope;
    this.pickViews = [];  // [{mvp, vp}] in drawing order; the last one containing the pointer is picked
    if (sc && sc.full) { gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); this.drawScope([0, 0, w, h]); return; }
    const mv = this.orbitMV();
    const P = Viewer3D.persp(0.7, w / h, 0.05, 50);
    this.lastMVP = Viewer3D.mul(P, mv);
    this.pickViews.push({ mvp: this.lastMVP, vp: [0, 0, w, h] });
    this.drawScene(mv, P, false, [0, 0, w, h]);
    if (sc && sc.pip) {
      const s = Math.round(Math.min(w, h) * (sc.size || 0.46)), m = Math.round(8 * devicePixelRatio);
      const vp = [w - s - m, m, s, s];
      gl.enable(gl.SCISSOR_TEST);
      gl.scissor(vp[0] - 2, vp[1] - 2, s + 4, s + 4); gl.clearColor(0.45, 0.47, 0.5, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.scissor(...vp); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      this.drawScope(vp);
      gl.disable(gl.SCISSOR_TEST);
    }
  }
  drawScope(vp) {
    const gl = this.gl, sc = this.scope;
    gl.viewport(...vp);
    const mv = Viewer3D.lookAt(sc.eye, sc.dir, sc.up);
    const P = Viewer3D.persp((sc.fov || 70) * Math.PI / 180, vp[2] / vp[3], 1, 600);
    if (this.pickViews) this.pickViews.push({ mvp: Viewer3D.mul(P, mv), vp: vp.slice(), scope: true });
    this.drawScene(mv, P, true, vp);
    gl.viewport(0, 0, this.cv.width, this.cv.height);
  }
  drawScene(mv, P, scope, vp) {
    const gl = this.gl;
    gl.enable(gl.DEPTH_TEST);
    gl.useProgram(this.prog);
    gl.uniformMatrix4fv(this.u.mv, false, mv);
    gl.uniformMatrix4fv(this.u.mvp, false, Viewer3D.mul(P, mv));
    gl.uniform1i(this.u.scope, scope ? 1 : 0);
    gl.uniform4fv(this.u.vpr, vp);
    const items = [];
    for (const [id, m] of this.meshes) {
      const l = this.labels && this.labels.map.get(id);
      if (scope && this.scopeHideIds && this.scopeHideIds.has(id)) continue;
      items.push({ m, visible: !l || l.visible, color: l ? l.color : [0.7, 0.7, 0.7], alpha: l && l.opacity !== undefined ? l.opacity : 1 });
    }
    for (const m of this.extras.values()) {
      const st = m.style;
      if (scope && st.scopeHide) continue;
      items.push({ m, visible: st.visible !== false || (scope && st.scopeColor), color: scope && st.scopeColor ? st.scopeColor : st.color || [0.7, 0.7, 0.7],
                   alpha: st.opacity !== undefined ? st.opacity : 1 });
    }
    // opaque first, then translucent (liver, skin) without depth writes; the scope view is all opaque
    for (const pass of [0, 1]) {
      for (const it of items) {
        if (!it.visible) continue;
        const alpha = scope ? 1 : it.alpha;
        if ((alpha < 1) !== (pass === 1)) continue;
        if (pass === 1) { gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); }
        gl.uniform3fv(this.u.base, it.color);
        gl.uniform1f(this.u.alpha, alpha);
        gl.bindVertexArray(it.m.vao);
        gl.drawElements(gl.TRIANGLES, it.m.count, gl.UNSIGNED_INT, 0);
      }
    }
    gl.disable(gl.BLEND); gl.depthMask(true);
    gl.bindVertexArray(null);
  }
  // PNG data URL of the view at a fixed size (also works while the page is hidden)
  capture(w, h) {
    this.forceSize = [w, h];
    this.draw();
    const url = this.cv.toDataURL('image/png');
    this.forceSize = null;
    this.draw();
    return url;
  }

  // ---------------------------------------------------------------- picking
  // -> {p: world point, id: label id (number) or extra key (string)} or null
  pick(ev, keys) {
    if (!this.pickViews || !this.pickViews.length) return null;
    const r = this.cv.getBoundingClientRect();
    const px = (ev.clientX - r.left) / r.width * this.cv.width, py = (1 - (ev.clientY - r.top) / r.height) * this.cv.height;
    let view = null;
    for (const pv of this.pickViews) if (px >= pv.vp[0] && px < pv.vp[0] + pv.vp[2] && py >= pv.vp[1] && py < pv.vp[1] + pv.vp[3]) view = pv;
    if (!view) return null;
    const x = (px - view.vp[0]) / view.vp[2] * 2 - 1, y = (py - view.vp[1]) / view.vp[3] * 2 - 1;
    const inv = Viewer3D.invert(view.mvp);
    const un = (z) => { const p = [0, 1, 2, 3].map((i) => inv[i] * x + inv[4 + i] * y + inv[8 + i] * z + inv[12 + i]); return [p[0] / p[3], p[1] / p[3], p[2] / p[3]]; };
    const o = un(-1), far = un(1), d = Viewer3D.nrm([far[0] - o[0], far[1] - o[1], far[2] - o[2]]);
    // what this view draws: in the scope view, hidden ids (retracted liver) and scopeHide extras are skipped
    const hide = view.scope ? this.scopeHideIds : null;
    const list = keys ? keys.map((k) => [k, this.extras.get(k)]).filter(([, m]) => m && !(view.scope && m.style.scopeHide))
      : [...this.meshes.entries()].filter(([id]) => { const l = this.labels && this.labels.map.get(id); return (!l || l.visible) && !(hide && hide.has(id)); });
    let best = Infinity, bestId = null;
    for (const [mid, m] of list) {
      const v = m.v, ix = m.ix;
      for (let t = 0; t < ix.length; t += 3) {
        const a = ix[t] * 3, b = ix[t + 1] * 3, c = ix[t + 2] * 3;
        const e1 = [v[b] - v[a], v[b + 1] - v[a + 1], v[b + 2] - v[a + 2]], e2 = [v[c] - v[a], v[c + 1] - v[a + 1], v[c + 2] - v[a + 2]];
        const p = Viewer3D.crs(d, e2), det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2];
        if (Math.abs(det) < 1e-12) continue;
        const s = [o[0] - v[a], o[1] - v[a + 1], o[2] - v[a + 2]], u = (s[0] * p[0] + s[1] * p[1] + s[2] * p[2]) / det;
        if (u < 0 || u > 1) continue;
        const q = Viewer3D.crs(s, e1), w = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) / det;
        if (w < 0 || u + w > 1) continue;
        const tt = (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) / det;
        if (tt > 0 && tt < best) { best = tt; bestId = mid; }
      }
    }
    return best < Infinity ? { p: [o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best], id: bestId } : null;
  }
  static invert(m) {
    // general 4x4 inverse (column-major in, column-major out) via Gauss-Jordan
    const a = [];
    for (let r = 0; r < 4; r++) { a.push([]); for (let c = 0; c < 4; c++) a[r].push(m[c * 4 + r]); for (let c = 0; c < 4; c++) a[r].push(r === c ? 1 : 0); }
    for (let c = 0; c < 4; c++) {
      let p = c;
      for (let r = c + 1; r < 4; r++) if (Math.abs(a[r][c]) > Math.abs(a[p][c])) p = r;
      [a[c], a[p]] = [a[p], a[c]];
      const d = a[c][c];
      for (let k = 0; k < 8; k++) a[c][k] /= d;
      for (let r = 0; r < 4; r++) if (r !== c) { const f = a[r][c]; for (let k = 0; k < 8; k++) a[r][k] -= f * a[c][k]; }
    }
    const out = new Float64Array(16);
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) out[c * 4 + r] = a[r][4 + c];
    return out;
  }

  // ---------------------------------------------------------------- interaction
  bind() {
    const cv = this.cv;
    let drag = null;
    cv.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, b: e.button }; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
      if (this.scope && this.scope.full) return;
      if (drag.b === 2 || e.shiftKey) { this.pan[0] += dx * this.dist / cv.clientHeight; this.pan[1] -= dy * this.dist / cv.clientHeight; }
      else { this.yaw += dx * 0.01; this.pitch = Math.max(-1.57, Math.min(1.57, this.pitch + dy * 0.01)); }
      this.draw();
    });
    cv.addEventListener('pointerup', (e) => {
      if (drag && drag.b === 0 && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 4 && this.onClick) this.onClick(e);
      drag = null;
    });
    cv.addEventListener('contextmenu', (e) => e.preventDefault());
    cv.addEventListener('wheel', (e) => { e.preventDefault(); this.dist = Math.max(0.5, Math.min(20, this.dist * Math.exp(e.deltaY * 0.001))); this.draw(); }, { passive: false });
    cv.addEventListener('dblclick', () => this.fit());
  }
}
