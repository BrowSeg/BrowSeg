'use strict';
// NIfTI-1 read/write (.nii / .nii.gz) for the browser. gzip via the native
// DecompressionStream / CompressionStream.

const Nifti = (() => {
  async function gunzipIfNeeded(buf) {
    const u8 = new Uint8Array(buf);
    if (u8[0] === 0x1f && u8[1] === 0x8b) {
      const ds = new DecompressionStream('gzip');
      return await new Response(new Blob([u8]).stream().pipeThrough(ds)).arrayBuffer();
    }
    return buf;
  }

  async function gzip(parts) {
    const cs = new CompressionStream('gzip');
    return await new Response(new Blob(parts).stream().pipeThrough(cs)).blob();
  }

  // -> { dims:[nx,ny,nz], pixdim:[sx,sy,sz], affine:[16] row-major, data: Float32Array (x fastest), datatype }
  async function read(buf) {
    buf = await gunzipIfNeeded(buf);
    let dv = new DataView(buf);
    let le = true;
    if (dv.getInt32(0, true) !== 348) {
      if (dv.getInt32(0, false) === 348) le = false;
      else throw new Error('not a NIfTI-1 file');
    }
    const i16 = (o) => dv.getInt16(o, le), f32 = (o) => dv.getFloat32(o, le);
    const ndim = i16(40);
    const dims = [i16(42), i16(44), Math.max(1, i16(46))];
    if (ndim > 3 && i16(48) > 1) console.warn('NIfTI: only the first volume is used');
    const datatype = i16(70), bitpix = i16(72);
    const pixdim = [f32(80), f32(84), f32(88)];
    const voxOffset = Math.max(352, Math.round(f32(108)));
    let slope = f32(112), inter = f32(116);
    if (!slope) { slope = 1; inter = 0; }
    const qform = i16(252), sform = i16(254);
    let affine;
    if (sform > 0) {
      affine = [];
      for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) affine.push(f32(280 + 16 * r + 4 * c));
      affine.push(0, 0, 0, 1);
    } else if (qform > 0) {
      const b = f32(256), c = f32(260), d = f32(264);
      const a = Math.sqrt(Math.max(0, 1 - b * b - c * c - d * d));
      const qfac = f32(76) < 0 ? -1 : 1;
      const R = [a * a + b * b - c * c - d * d, 2 * b * c - 2 * a * d, 2 * b * d + 2 * a * c,
                 2 * b * c + 2 * a * d, a * a + c * c - b * b - d * d, 2 * c * d - 2 * a * b,
                 2 * b * d - 2 * a * c, 2 * c * d + 2 * a * b, a * a + d * d - c * c - b * b];
      const s = [pixdim[0], pixdim[1], pixdim[2] * qfac], o = [f32(268), f32(272), f32(276)];
      affine = [];
      for (let r = 0; r < 3; r++) { for (let k = 0; k < 3; k++) affine.push(R[r * 3 + k] * s[k]); affine.push(o[r]); }
      affine.push(0, 0, 0, 1);
    } else {
      affine = [pixdim[0], 0, 0, 0, 0, pixdim[1], 0, 0, 0, 0, pixdim[2], 0, 0, 0, 0, 1];
    }
    const n = dims[0] * dims[1] * dims[2];
    const readers = {
      2: [1, (o) => dv.getUint8(o)], 256: [1, (o) => dv.getInt8(o)], 4: [2, (o) => dv.getInt16(o, le)],
      512: [2, (o) => dv.getUint16(o, le)], 8: [4, (o) => dv.getInt32(o, le)], 768: [4, (o) => dv.getUint32(o, le)],
      16: [4, (o) => dv.getFloat32(o, le)], 64: [8, (o) => dv.getFloat64(o, le)],
    };
    const rd = readers[datatype];
    if (!rd) throw new Error(`NIfTI datatype ${datatype} not supported`);
    const data = new Float32Array(n);
    const [bytes, get] = rd;
    for (let i = 0; i < n; i++) data[i] = get(voxOffset + i * bytes) * slope + inter;
    void bitpix;
    return { dims, pixdim, affine, data, datatype };
  }

  // canonical C-order array (x,y,z; z fastest) -> NIfTI (x fastest), gzip-compressed Blob
  async function write({ shape, affine, zooms, data, datatype }) {
    const [X, Y, Z] = shape;
    const bytes = datatype === 'uint8' ? 1 : 2;
    const h = new ArrayBuffer(352), dv = new DataView(h);
    dv.setInt32(0, 348, true);
    dv.setInt16(40, 3, true); dv.setInt16(42, X, true); dv.setInt16(44, Y, true); dv.setInt16(46, Z, true);
    for (let i = 48; i <= 54; i += 2) dv.setInt16(i, 1, true);
    dv.setInt16(70, datatype === 'uint8' ? 2 : 4, true); dv.setInt16(72, bytes * 8, true);
    dv.setFloat32(76, 1, true);
    zooms.forEach((z, i) => dv.setFloat32(80 + 4 * i, z, true));
    dv.setFloat32(108, 352, true); dv.setFloat32(112, 1, true); dv.setFloat32(116, 0, true);
    dv.setUint8(123, 10);                // mm, s
    dv.setInt16(252, 0, true); dv.setInt16(254, 1, true);  // sform (scanner)
    for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) dv.setFloat32(280 + 16 * r + 4 * c, affine[r * 4 + c], true);
    new Uint8Array(h, 344, 4).set([0x6e, 0x2b, 0x31, 0]);  // "n+1"
    const out = datatype === 'uint8' ? new Uint8Array(X * Y * Z) : new Int16Array(X * Y * Z);
    for (let x = 0; x < X; x++) for (let y = 0; y < Y; y++) {
      const b = (x * Y + y) * Z;
      for (let z = 0; z < Z; z++) out[(z * Y + y) * X + x] = data[b + z];
    }
    return gzip([h, out]);
  }

  // NIfTI order (x fastest) volume -> canonical C-order is done in C++ (tsc_set_volume);
  // for label maps loaded onto an existing canonical CT we reorient here.
  function toCOrder(nii) {
    const [X, Y, Z] = nii.dims, out = new Uint8Array(X * Y * Z);
    for (let x = 0; x < X; x++) for (let y = 0; y < Y; y++) {
      const b = (x * Y + y) * Z;
      for (let z = 0; z < Z; z++) out[b + z] = nii.data[(z * Y + y) * X + x];
    }
    return out;
  }

  return { read, write, gzip, toCOrder };
})();
