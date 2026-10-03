#include "dicom.h"

#include <algorithm>
#include <cstdlib>
#include <functional>
#include <map>
#include <sstream>

namespace tsc {

namespace {

struct Reader {
    const uint8_t* p;
    size_t len, pos = 0;
    bool explicit_vr = true;
    uint16_t u16(size_t at) const { return (uint16_t)(p[at] | (p[at + 1] << 8)); }
    uint32_t u32(size_t at) const {
        return (uint32_t)p[at] | ((uint32_t)p[at + 1] << 8) | ((uint32_t)p[at + 2] << 16) | ((uint32_t)p[at + 3] << 24);
    }
};

bool is_long_vr(const char* vr) {
    static const char* L[] = {"OB", "OW", "OF", "SQ", "UT", "UN", "OD", "OL", "OV", "UC", "UR", "SV", "UV"};
    for (auto l : L)
        if (vr[0] == l[0] && vr[1] == l[1]) return true;
    return false;
}

bool looks_like_vr(const uint8_t* v) { return v[0] >= 'A' && v[0] <= 'Z' && v[1] >= 'A' && v[1] <= 'Z'; }

std::string trim(std::string s) {
    while (!s.empty() && (s.back() == ' ' || s.back() == '\0')) s.pop_back();
    size_t i = 0;
    while (i < s.size() && s[i] == ' ') ++i;
    return s.substr(i);
}

std::vector<double> parse_ds(const std::string& s) {
    std::vector<double> v;
    std::stringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, '\\')) {
        tok = trim(tok);
        if (!tok.empty()) v.push_back(std::strtod(tok.c_str(), nullptr));
    }
    return v;
}

const uint32_t kUndefined = 0xFFFFFFFFu;

// Skips an element value of undefined length (sequence or encapsulated data)
// starting at r.pos. Returns false on malformed data.
bool skip_undefined(Reader& r, bool explicit_vr);

// Reads one element header at r.pos. Returns false at end.
bool read_header(Reader& r, bool explicit_vr, uint16_t& group, uint16_t& elem, char vr[3], uint32_t& vlen) {
    if (r.pos + 8 > r.len) return false;
    group = r.u16(r.pos);
    elem = r.u16(r.pos + 2);
    vr[0] = vr[1] = vr[2] = 0;
    if (group == 0xFFFE) {  // item / delimiters never carry a VR
        vlen = r.u32(r.pos + 4);
        r.pos += 8;
        return true;
    }
    if (explicit_vr) {
        vr[0] = (char)r.p[r.pos + 4];
        vr[1] = (char)r.p[r.pos + 5];
        if (is_long_vr(vr)) {
            if (r.pos + 12 > r.len) return false;
            vlen = r.u32(r.pos + 8);
            r.pos += 12;
        } else {
            vlen = r.u16(r.pos + 6);
            r.pos += 8;
        }
    } else {
        vlen = r.u32(r.pos + 4);
        r.pos += 8;
    }
    return true;
}

// `n` more bytes are available at r.pos (overflow-safe: size_t is 32 bit on wasm32)
inline bool fits(const Reader& r, uint64_t n) { return r.pos <= r.len && n <= (uint64_t)(r.len - r.pos); }

bool skip_undefined(Reader& r, bool explicit_vr) {
    // content: items (FFFE,E000) until sequence delimiter (FFFE,E0DD)
    int depth_guard = 0;
    while (r.pos + 8 <= r.len) {
        uint16_t g, e;
        char vr[3];
        uint32_t vlen;
        if (!read_header(r, explicit_vr, g, e, vr, vlen)) return false;
        if (g == 0xFFFE && e == 0xE0DD) return true;  // sequence delimiter
        if (g == 0xFFFE && e == 0xE000) {             // item
            if (vlen != kUndefined) {
                if (!fits(r, vlen)) return false;
                r.pos += vlen;
                continue;
            }
            // undefined-length item: nested data set until item delimiter
            for (;;) {
                uint16_t g2, e2;
                char vr2[3];
                uint32_t l2;
                if (!read_header(r, explicit_vr, g2, e2, vr2, l2)) return false;
                if (g2 == 0xFFFE && e2 == 0xE00D) break;
                if (l2 == kUndefined) {
                    if (++depth_guard > 64 || !skip_undefined(r, explicit_vr)) return false;
                    --depth_guard;
                } else {
                    if (!fits(r, l2)) return false;
                    r.pos += l2;
                }
            }
            continue;
        }
        if (g == 0xFFFE && e == 0xE00D) continue;
        return false;
    }
    return false;
}

}  // namespace

bool parse_dicom(const uint8_t* data, size_t len, DicomSlice& out, std::string& err) {
    Reader r{data, len};
    if (len >= 132 && std::memcmp(data + 128, "DICM", 4) == 0) {
        r.pos = 132;
    } else if (len >= 8 && data[0] == 0x02 && data[1] == 0x00) {
        r.pos = 0;  // meta header without preamble
    } else if (len >= 8) {
        r.pos = 0;  // raw data set (no meta)
    } else {
        err = "file too small";
        return false;
    }
    std::string ts = "1.2.840.10008.1.2.1";
    bool have_meta = false;
    // meta group: always explicit VR LE
    while (r.pos + 8 <= len && r.u16(r.pos) == 0x0002) {
        uint16_t g, e;
        char vr[3];
        uint32_t vlen;
        if (!read_header(r, true, g, e, vr, vlen) || vlen == kUndefined || !fits(r, vlen)) {
            err = "bad meta header";
            return false;
        }
        if (e == 0x0010) ts = trim(std::string((const char*)data + r.pos, vlen));
        r.pos += vlen;
        have_meta = true;
    }
    bool explicit_vr;
    if (ts == "1.2.840.10008.1.2") {
        explicit_vr = false;
    } else if (ts == "1.2.840.10008.1.2.1") {
        explicit_vr = true;
    } else if (ts == "1.2.840.10008.1.2.2") {
        err = "big endian transfer syntax not supported";
        return false;
    } else if (ts == "1.2.840.10008.1.2.1.99") {
        err = "deflated transfer syntax not supported";
        return false;
    } else {
        err = "compressed transfer syntax not supported: " + ts;
        return false;
    }
    if (!have_meta && r.pos + 6 <= len) explicit_vr = looks_like_vr(data + r.pos + 4);

    const uint8_t* pixel = nullptr;
    uint32_t pixel_len = 0;
    int bits_stored = -1;
    bool has_rows = false;
    while (r.pos + 8 <= len) {
        uint16_t g, e;
        char vr[3];
        uint32_t vlen;
        if (!read_header(r, explicit_vr, g, e, vr, vlen)) break;
        if (vlen == kUndefined) {
            if (g == 0x7FE0 && e == 0x0010) {
                err = "encapsulated (compressed) pixel data not supported";
                return false;
            }
            if (!skip_undefined(r, explicit_vr)) {
                err = "malformed sequence";
                return false;
            }
            continue;
        }
        if (!fits(r, vlen)) {
            if (g == 0x7FE0 && e == 0x0010) {
                err = "truncated pixel data";
                return false;
            }
            break;
        }
        const uint8_t* v = data + r.pos;
        auto str = [&] { return trim(std::string((const char*)v, vlen)); };
        auto us = [&] { return vlen >= 2 ? (int)r.u16(r.pos) : 0; };
        uint32_t tag = ((uint32_t)g << 16) | e;
        switch (tag) {
            case 0x00080060: out.modality = str(); break;
            case 0x0008103E: out.series_description = str(); break;
            case 0x00080031: out.series_time = str(); break;
            case 0x00180010: out.contrast_agent = str(); break;
            case 0x00200011: out.series_number = std::atoi(str().c_str()); break;
            case 0x00080008: out.localizer = str().find("LOCALIZER") != std::string::npos; break;
            case 0x0020000E: out.series_uid = str(); break;
            case 0x00200013: out.instance_number = std::atoi(str().c_str()); break;
            case 0x00280008: out.number_of_frames = std::max(1, std::atoi(str().c_str())); break;
            case 0x00180050: {
                auto d = parse_ds(str());
                if (!d.empty()) out.slice_thickness = d[0];
                break;
            }
            case 0x00200032: {
                auto d = parse_ds(str());
                if (d.size() >= 3) {
                    for (int i = 0; i < 3; ++i) out.ipp[i] = d[i];
                    out.has_ipp = true;
                }
                break;
            }
            case 0x00200037: {
                auto d = parse_ds(str());
                if (d.size() >= 6) {
                    for (int i = 0; i < 6; ++i) out.iop[i] = d[i];
                    out.has_iop = true;
                }
                break;
            }
            case 0x00280002: out.samples_per_pixel = us(); break;
            case 0x00280010: out.rows = us(); has_rows = true; break;
            case 0x00280011: out.cols = us(); break;
            case 0x00280030: {
                auto d = parse_ds(str());
                if (d.size() >= 2) {
                    out.pixel_spacing[0] = d[0];
                    out.pixel_spacing[1] = d[1];
                }
                break;
            }
            case 0x00280100: out.bits_allocated = us(); break;
            case 0x00280101: bits_stored = us(); break;
            case 0x00280103: out.pixel_representation = us(); break;
            case 0x00281052: { auto d = parse_ds(str()); if (!d.empty()) out.intercept = d[0]; break; }
            case 0x00281053: { auto d = parse_ds(str()); if (!d.empty()) out.slope = d[0]; break; }
            case 0x7FE00010: pixel = v; pixel_len = vlen; break;
            default: break;
        }
        r.pos += vlen;
    }
    if (!pixel || !has_rows || out.rows <= 0 || out.cols <= 0) {
        err = "no image pixel data";
        return false;
    }
    if (out.samples_per_pixel != 1) {
        err = "color images not supported";
        return false;
    }
    if (out.number_of_frames > 1) {
        err = "multi-frame (enhanced) DICOM is not supported";
        return false;
    }
    const size_t n = (size_t)out.rows * out.cols;
    const int bpp = out.bits_allocated / 8;
    if (out.bits_allocated % 8 != 0 || (bpp != 1 && bpp != 2 && bpp != 4)) {
        err = "unsupported BitsAllocated";
        return false;
    }
    if (pixel_len < n * bpp) {
        err = "pixel data too short";
        return false;
    }
    if (bits_stored <= 0) bits_stored = out.bits_allocated;
    out.bits_stored = bits_stored;
    out.raw.assign(pixel, pixel + n * bpp);
    return true;
}

void DicomSlice::decode(float* dst) const {
    const size_t n = (size_t)rows * cols;
    const int bpp = bits_allocated / 8;
    const uint8_t* pixel = raw.data();
    const int pixel_representation = this->pixel_representation;
    for (size_t i = 0; i < n; ++i) {
        int64_t rv;
        if (bpp == 1) {
            rv = pixel[i];
            if (pixel_representation == 1) rv = (int8_t)pixel[i];
        } else if (bpp == 2) {
            uint16_t u = (uint16_t)(pixel[2 * i] | (pixel[2 * i + 1] << 8));
            if (bits_stored < 16) u &= (uint16_t)((1u << bits_stored) - 1);  // unused high bits may hold overlays
            rv = u;
            if (pixel_representation == 1) {
                if (bits_stored < 16) {
                    uint16_t m = (uint16_t)((1u << bits_stored) - 1);
                    u &= m;
                    rv = (u & (1u << (bits_stored - 1))) ? (int64_t)u - (1ll << bits_stored) : (int64_t)u;
                } else {
                    rv = (int16_t)u;
                }
            }
        } else {
            uint32_t u = (uint32_t)pixel[4 * i] | ((uint32_t)pixel[4 * i + 1] << 8) | ((uint32_t)pixel[4 * i + 2] << 16) |
                         ((uint32_t)pixel[4 * i + 3] << 24);
            rv = pixel_representation == 1 ? (int64_t)(int32_t)u : (int64_t)u;
        }
        dst[i] = (float)((double)rv * slope + intercept);
    }
}

namespace {
// the image slices build_volume uses for a series: not localizers, most frequent image size
std::vector<const DicomSlice*> series_slices(const std::vector<DicomSlice>& all, const std::string& uid, int* other = nullptr) {
    std::map<std::pair<int, int>, int> sizes;
    int total = 0;
    for (auto& x : all)
        if (x.series_uid == uid) {
            ++total;
            if (!x.localizer) sizes[{x.rows, x.cols}]++;
        }
    std::pair<int, int> best{0, 0};
    int bn = 0;
    for (auto& kv : sizes)
        if (kv.second > bn) { bn = kv.second; best = kv.first; }
    std::vector<const DicomSlice*> s;
    for (auto& x : all)
        if (x.series_uid == uid && !x.localizer && x.rows == best.first && x.cols == best.second) s.push_back(&x);
    if (other) *other = total - (int)s.size();
    return s;
}
}  // namespace

// all slices share ImageOrientationPatient (within 1e-4)
bool same_orientation(const std::vector<const DicomSlice*>& s) {
    for (auto* x : s)
        for (int i = 0; i < 6; ++i)
            if (std::fabs(x->iop[i] - s[0]->iop[i]) > 1e-4) return false;
    return true;
}

std::vector<DicomSeriesInfo> list_series(const std::vector<DicomSlice>& slices) {
    std::map<std::string, int> seen;
    std::vector<DicomSeriesInfo> r;
    for (auto& x : slices) {
        if (seen.count(x.series_uid)) continue;
        seen[x.series_uid] = 1;
        DicomSeriesInfo e;
        e.series_uid = x.series_uid;
        auto s = series_slices(slices, x.series_uid, &e.num_other);
        const DicomSlice& f = s.empty() ? x : *s[0];
        e.description = f.series_description;
        e.modality = f.modality;
        e.series_time = f.series_time;
        e.contrast_agent = f.contrast_agent;
        e.series_number = f.series_number;
        e.num_slices = (int)s.size();
        e.rows = f.rows;
        e.cols = f.cols;
        e.pixel_spacing[0] = f.pixel_spacing[0];
        e.pixel_spacing[1] = f.pixel_spacing[1];
        if (s.size() >= 2) {
            const double* iop = f.iop;
            const double nrm[3] = {iop[1] * iop[5] - iop[2] * iop[4], iop[2] * iop[3] - iop[0] * iop[5], iop[0] * iop[4] - iop[1] * iop[3]};
            std::vector<double> pos;
            for (auto* p : s)
                if (p->has_ipp) pos.push_back(p->ipp[0] * nrm[0] + p->ipp[1] * nrm[1] + p->ipp[2] * nrm[2]);
            std::sort(pos.begin(), pos.end());
            if (pos.size() >= 2) {
                std::vector<double> d;
                for (size_t i = 1; i < pos.size(); ++i) d.push_back(pos[i] - pos[i - 1]);
                const double dmin = *std::min_element(d.begin(), d.end());
                std::nth_element(d.begin(), d.begin() + d.size() / 2, d.end());
                e.slice_spacing = d[d.size() / 2];
                e.extent_mm = pos.back() - pos.front();
                if (dmin <= 1e-6) e.problem = "duplicate slice positions (several phases in one series?)";
            }
            if (e.problem.empty() && !same_orientation(s)) e.problem = "slices with different orientations";
        }
        if (e.num_slices < 2 && e.problem.empty()) e.problem = e.num_slices == 0 ? "localizer only" : "single image";
        r.push_back(e);
    }
    // default order = build_volume's choice: CT before other modalities, then most slices, then UID
    std::sort(r.begin(), r.end(), [](const DicomSeriesInfo& a, const DicomSeriesInfo& b) {
        const bool pa = a.problem.empty(), pb = b.problem.empty();
        if (pa != pb) return pa;  // buildable series first
        const bool ca = a.modality == "CT", cb = b.modality == "CT";
        if (ca != cb) return ca;
        if (a.num_slices != b.num_slices) return a.num_slices > b.num_slices;
        return a.series_uid < b.series_uid;
    });
    return r;
}

namespace {

// nibabel.as_closest_canonical: which input axis becomes which output axis, flips, new shape and affine
struct CanonicalPlan {
    bool ident = true;
    int in_of_out[3] = {0, 1, 2};
    int out_of_in[3] = {0, 1, 2};
    bool flip[3] = {false, false, false};
    Shape3 shape{0, 0, 0};
    Affine affine{};
};

CanonicalPlan canonical_plan(const Shape3& shape, const Affine& A) {
    // nibabel.orientations.io_orientation (axis selection on the normalised RZS)
    double R[3][3];
    for (int c = 0; c < 3; ++c) {
        double n = 0;
        for (int r = 0; r < 3; ++r) n += A[r * 4 + c] * A[r * 4 + c];
        n = std::sqrt(n);
        if (n == 0) n = 1;
        for (int r = 0; r < 3; ++r) R[r][c] = A[r * 4 + c] / n;
    }
    CanonicalPlan p;
    int out_ax[3];
    for (int in = 0; in < 3; ++in) {
        int best = 0;
        for (int r = 1; r < 3; ++r)
            if (std::fabs(R[r][in]) > std::fabs(R[best][in])) best = r;
        if (std::fabs(R[best][in]) < 1e-6) throw std::runtime_error("degenerate image orientation (affine)");
        out_ax[in] = best;
        p.flip[in] = R[best][in] < 0;
        for (int c = 0; c < 3; ++c) R[best][c] = 0;
    }
    for (int in = 0; in < 3; ++in) {
        p.in_of_out[out_ax[in]] = in;
        p.out_of_in[in] = out_ax[in];
        if (out_ax[in] != in || p.flip[in]) p.ident = false;
    }
    if (p.ident) {
        p.shape = shape;
        p.affine = A;
        return p;
    }
    for (int oa = 0; oa < 3; ++oa) p.shape[oa] = shape[p.in_of_out[oa]];
    // affine: column oa = +-column in; offset shifted for flipped axes
    p.affine = identity_affine();
    for (int r = 0; r < 3; ++r) {
        double off = A[r * 4 + 3];
        for (int in = 0; in < 3; ++in)
            if (p.flip[in]) off += A[r * 4 + in] * (double)(shape[in] - 1);
        p.affine[r * 4 + 3] = off;
        for (int oa = 0; oa < 3; ++oa) {
            int in = p.in_of_out[oa];
            p.affine[r * 4 + oa] = A[r * 4 + in] * (p.flip[in] ? -1.0 : 1.0);
        }
    }
    return p;
}

}  // namespace

template <class T>
Volume<T> as_closest_canonical(const Volume<T>& v) {
    const CanonicalPlan pl = canonical_plan(v.shape, v.affine);
    if (pl.ident) return v;
    Volume<T> o;
    o.shape = pl.shape;
    o.affine = pl.affine;
    o.data.resize(checked_count(numel(o.shape)));
    int64_t in_stride[3] = {v.shape[1] * v.shape[2], v.shape[2], 1};
    parallel_for(o.shape[0], [&](int64_t b, int64_t e, int) {
        for (int64_t i0 = b; i0 < e; ++i0)
            for (int64_t i1 = 0; i1 < o.shape[1]; ++i1)
                for (int64_t i2 = 0; i2 < o.shape[2]; ++i2) {
                    int64_t q[3] = {i0, i1, i2};
                    int64_t src = 0;
                    for (int oa = 0; oa < 3; ++oa) {
                        int in = pl.in_of_out[oa];
                        int64_t id = pl.flip[in] ? v.shape[in] - 1 - q[oa] : q[oa];
                        src += id * in_stride[in];
                    }
                    o.data[(size_t)((i0 * o.shape[1] + i1) * o.shape[2] + i2)] = v.data[(size_t)src];
                }
    });
    return o;
}

template Volume<float> as_closest_canonical(const Volume<float>&);
template Volume<uint8_t> as_closest_canonical(const Volume<uint8_t>&);

Volume<float> build_volume(const std::vector<DicomSlice>& all, const std::string& uid_req, std::string& log,
                           bool explicit_uid, const std::function<void()>& before_alloc) {
    if (all.empty()) throw std::runtime_error("no DICOM images");
    std::string uid = uid_req;
    if (explicit_uid) {
        bool found = false;
        for (auto& x : all) found |= x.series_uid == uid;
        if (!found) throw std::runtime_error("series not found: " + uid);
    } else {
        const auto list = list_series(all);  // default: the first buildable series (largest CT series)
        uid = list.front().series_uid;
        if (!list.front().problem.empty()) throw std::runtime_error("no usable series: " + list.front().problem);
    }
    int other = 0;
    std::vector<const DicomSlice*> s = series_slices(all, uid, &other);
    if (other) log += "WARNING: " + std::to_string(other) + " localizer / other-size image(s) in the series were ignored\n";
    if (s.size() < 2) throw std::runtime_error("series has fewer than 2 slices");
    if (!same_orientation(s)) throw std::runtime_error("slices with different orientations in the series");
    const int rows = s[0]->rows, cols = s[0]->cols;

    const double* iop = s[0]->iop;
    double rd[3] = {iop[0], iop[1], iop[2]}, cd[3] = {iop[3], iop[4], iop[5]};
    double nrm[3] = {rd[1] * cd[2] - rd[2] * cd[1], rd[2] * cd[0] - rd[0] * cd[2], rd[0] * cd[1] - rd[1] * cd[0]};
    bool have_pos = true;
    for (auto* x : s) have_pos &= x->has_ipp;
    if (have_pos) {
        std::stable_sort(s.begin(), s.end(), [&](const DicomSlice* a, const DicomSlice* b) {
            double da = a->ipp[0] * nrm[0] + a->ipp[1] * nrm[1] + a->ipp[2] * nrm[2];
            double db = b->ipp[0] * nrm[0] + b->ipp[1] * nrm[1] + b->ipp[2] * nrm[2];
            return da < db;
        });
    } else {
        std::stable_sort(s.begin(), s.end(), [](const DicomSlice* a, const DicomSlice* b) { return a->instance_number < b->instance_number; });
        log += "WARNING: no ImagePositionPatient, sorted by InstanceNumber\n";
    }
    const int64_t n = (int64_t)s.size();
    double step[3];
    if (have_pos) {
        for (int i = 0; i < 3; ++i) step[i] = (s[n - 1]->ipp[i] - s[0]->ipp[i]) / (double)(n - 1);
        // check spacing consistency
        double d0 = 0, dmax = 0, dmin = 1e30;
        for (int64_t k = 1; k < n; ++k) {
            double d = 0;
            for (int i = 0; i < 3; ++i) d += (s[k]->ipp[i] - s[k - 1]->ipp[i]) * nrm[i];
            dmax = std::max(dmax, d);
            dmin = std::min(dmin, d);
            d0 += d;
        }
        if (dmax - dmin > 0.05 * std::fabs(d0 / (n - 1)) + 1e-3)
            log += "WARNING: non-uniform slice spacing (min " + std::to_string(dmin) + ", max " + std::to_string(dmax) + ")\n";
        if (dmin <= 0) throw std::runtime_error("duplicate slice positions in series (several phases in one series?)");
        // gantry tilt: slices are not stacked along their normal (sheared grid)
        double sl = std::sqrt(step[0] * step[0] + step[1] * step[1] + step[2] * step[2]);
        double cosang = sl > 0 ? std::fabs(step[0] * nrm[0] + step[1] * nrm[1] + step[2] * nrm[2]) / sl : 1;
        if (cosang < std::cos(0.5 * 3.14159265358979 / 180))
            log += "WARNING: gantry tilt (" + std::to_string(std::acos(std::min(1.0, cosang)) * 180 / 3.14159265358979) +
                   " deg): the volume grid is sheared\n";
    } else {
        double th = s[0]->slice_thickness > 0 ? s[0]->slice_thickness : 1.0;
        for (int i = 0; i < 3; ++i) step[i] = nrm[i] * th;
        log += "WARNING: slice spacing taken from SliceThickness (" + std::to_string(th) + " mm)\n";
    }

    // voxel grid (c, r, k): world_LPS = ipp0 + c*dc*rd + r*dr*cd + k*step
    const double dr = s[0]->pixel_spacing[0], dc = s[0]->pixel_spacing[1];
    double A[16] = {0};
    for (int i = 0; i < 3; ++i) {
        A[i * 4 + 0] = rd[i] * dc;
        A[i * 4 + 1] = cd[i] * dr;
        A[i * 4 + 2] = step[i];
        A[i * 4 + 3] = s[0]->ipp[i];
    }
    // LPS -> RAS, then float32 like a NIfTI sform
    for (int c = 0; c < 4; ++c) {
        A[0 * 4 + c] = -A[0 * 4 + c];
        A[1 * 4 + c] = -A[1 * 4 + c];
    }
    Affine aff = identity_affine();
    for (int i = 0; i < 12; ++i) aff[i] = f32(A[i]);
    // written directly in closest-canonical order (same values as building the (c, r, k) volume and then
    // as_closest_canonical, without the intermediate copy); slices are decoded one at a time
    const Shape3 grid{cols, rows, n};
    const CanonicalPlan pl = canonical_plan(grid, aff);
    if (before_alloc) before_alloc();  // all checks passed: the caller may free its previous volume now
    Volume<float> v(pl.shape, pl.affine);
    int64_t ostride[3] = {pl.shape[1] * pl.shape[2], pl.shape[2], 1};
    int64_t step_in[3], base_in[3];  // output offset contribution of input axis `in` at index 0 and per step
    for (int in = 0; in < 3; ++in) {
        const int64_t st = ostride[pl.out_of_in[in]];
        base_in[in] = pl.flip[in] ? (grid[in] - 1) * st : 0;
        step_in[in] = pl.flip[in] ? -st : st;
    }
    parallel_for(n, [&](int64_t b, int64_t e, int) {
        std::vector<float> px((size_t)rows * cols);
        for (int64_t k = b; k < e; ++k) {
            s[k]->decode(px.data());
            const int64_t ok = base_in[2] + k * step_in[2];
            for (int64_t r = 0; r < rows; ++r) {
                const int64_t orr = ok + base_in[1] + r * step_in[1];
                for (int64_t c = 0; c < cols; ++c) v.data[(size_t)(orr + base_in[0] + c * step_in[0])] = px[(size_t)(r * cols + c)];
            }
        }
    });
    log += "series " + uid + ": " + std::to_string(cols) + "x" + std::to_string(rows) + "x" + std::to_string(n) + "\n";
    return v;
}

}  // namespace tsc
