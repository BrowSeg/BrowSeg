'use strict';
// Label registry: app-level label ids (1..255) keyed by structure name, so results of
// different tasks (and manual labels) can live in one label map.

const Labels = (() => {
  const JA = {
    liver: '肝臓', spleen: '脾臓', kidney_right: '右腎', kidney_left: '左腎', gallbladder: '胆嚢', stomach: '胃',
    pancreas: '膵臓', adrenal_gland_right: '右副腎', adrenal_gland_left: '左副腎', esophagus: '食道', trachea: '気管',
    small_bowel: '小腸', duodenum: '十二指腸', colon: '大腸', urinary_bladder: '膀胱', prostate: '前立腺', heart: '心臓',
    aorta: '大動脈', inferior_vena_cava: '下大静脈', portal_vein_and_splenic_vein: '門脈・脾静脈',
    portal_vein_intrahepatic: '肝内門脈', hepatic_veins: '肝静脈', liver_vessels: '肝内血管', liver_tumor: '肝腫瘍',
    lung_upper_lobe_left: '左肺上葉', lung_lower_lobe_left: '左肺下葉', lung_upper_lobe_right: '右肺上葉',
    lung_middle_lobe_right: '右肺中葉', lung_lower_lobe_right: '右肺下葉', spinal_cord: '脊髄', sacrum: '仙骨',
    sternum: '胸骨', costal_cartilages: '肋軟骨', brain: '脳', skull: '頭蓋骨',
  };
  const NAMED_COLORS = {
    liver: [0.70, 0.33, 0.25], portal_vein_intrahepatic: [0.36, 0.42, 0.95], portal_vein_and_splenic_vein: [0.22, 0.25, 0.80],
    hepatic_veins: [0.25, 0.85, 0.95], inferior_vena_cava: [0.15, 0.60, 0.78], liver_tumor: [0.95, 0.85, 0.30],
    liver_vessels: [0.45, 0.55, 0.95], aorta: [0.90, 0.25, 0.25], gallbladder: [0.40, 0.75, 0.35],
    spleen: [0.65, 0.30, 0.55], kidney_right: [0.85, 0.55, 0.35], kidney_left: [0.85, 0.55, 0.35],
    stomach: [0.88, 0.68, 0.62], duodenum: [0.90, 0.72, 0.55], small_bowel: [0.93, 0.76, 0.62], colon: [0.80, 0.62, 0.45],
    pancreas: [0.93, 0.80, 0.45],
  };
  function display(name) {
    const en = typeof LANG !== 'undefined' && LANG === 'en';
    const names = en ? I18N_EN_LABELS : JA;
    if (names[name]) return names[name];
    const m = /^liver_segment_(\d)$/.exec(name);
    if (m) return en ? `Liver segment S${m[1]}` : `肝区域 S${m[1]}`;
    const v = /^vertebrae_(\w+)$/.exec(name);
    if (v) return en ? `Vertebra ${v[1]}` : `椎体 ${v[1]}`;
    const r = /^rib_(left|right)_(\d+)$/.exec(name);
    if (r) return en ? `${r[1] === 'left' ? 'Left' : 'Right'} rib ${r[2]}` : `${r[1] === 'left' ? '左' : '右'}第${r[2]}肋骨`;
    return name;
  }
  function autoColor(id, name) {
    if (NAMED_COLORS[name]) return NAMED_COLORS[name].slice();
    const h = (id * 137.508) % 360 / 360, s = 0.6, l = 0.55;
    const f = (k) => { const t = (k + h * 12) % 12; return l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(t - 3, 9 - t, 1)); };
    return [f(0), f(8), f(4)];
  }

  class Registry {
    constructor() { this.map = new Map(); }  // id -> {id, name, color, visible, source, verified}
    clear() { this.map.clear(); }
    byName(name) { for (const l of this.map.values()) if (l.name === name) return l; return null; }
    freeId() { for (let i = 1; i < 256; i++) if (!this.map.has(i)) return i; throw new Error(t('ラベル数の上限 (255) です')); }
    ensure(name, source) {
      let l = this.byName(name);
      if (!l) {
        const id = this.freeId();
        l = { id, name, color: autoColor(id, name), visible: true, source, verified: false };
        this.map.set(id, l);
      }
      return l;
    }
    add(name, color, source = 'manual') {
      if (this.byName(name)) throw new Error(t('ラベル「{0}」は既にあります', name));
      const id = this.freeId();
      const l = { id, name, color: color || autoColor(id, name), visible: true, source, verified: false };
      this.map.set(id, l);
      return l;
    }
    remove(id) { this.map.delete(id); }
    list() { return [...this.map.values()].sort((a, b) => a.id - b.id); }
    toJSON() { return this.list().map(({ id, name, color, source, verified }) => ({ id, name, color, source, verified })); }
    // 256-entry RGB table (0..255 ints) + visibility for fast overlay rendering
    lut() {
      const rgb = new Uint8Array(256 * 3), vis = new Uint8Array(256);
      for (const l of this.map.values()) {
        rgb.set(l.color.map((c) => Math.round(c * 255)), l.id * 3);
        vis[l.id] = l.visible ? 1 : 0;
      }
      return { rgb, vis };
    }
  }
  return { Registry, display, autoColor };
})();
