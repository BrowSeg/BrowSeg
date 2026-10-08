// NOTE: this file must be compiled without floating point contraction
// (no FMA fusion) to reproduce scipy's rounding: -ffp-contract=off / MSVC /fp:precise.
#include "resample.h"

#include <algorithm>
#include <cmath>

namespace tsc {

namespace {

constexpr int kNPad = 12;  // scipy _prepad_for_spline_filter for mode='nearest'
constexpr double kPole3 = -0.267949192431122706472553658494127633;  // sqrt(3) - 2

// scipy apply_filter() for order 3 with NI_EXTEND_NEAREST (reflect init).
void apply_filter_nearest(double* c, int64_t n) {
    const double z = kPole3;
    double gain = 1.0;
    gain *= (1.0 - z) * (1.0 - 1.0 / z);
    for (int64_t i = 0; i < n; ++i) c[i] *= gain;

    // _init_causal_reflect
    {
        double z_i = z;
        const double z_n = std::pow(z, (double)n);
        const double c0 = c[0];
        c[0] = c[0] + z_n * c[n - 1];
        for (int64_t i = 1; i < n; ++i) {
            c[0] += z_i * (c[i] + z_n * c[n - 1 - i]);
            z_i *= z;
        }
        c[0] *= z / (1 - z_n * z_n);
        c[0] += c0;
    }
    for (int64_t i = 1; i < n; ++i) c[i] += z * c[i - 1];
    // _init_anticausal_reflect
    c[n - 1] *= z / (z - 1);
    for (int64_t i = n - 2; i >= 0; --i) c[i] = z * (c[i + 1] - c[i]);
}

// Same as apply_filter_nearest, for `nl` lines at once: element i of line l is
// base[i * stride + l]. Every line sees exactly the same sequence of operations,
// the lines are only interleaved so that memory is accessed contiguously.
constexpr int kLineBlock = 64;
void apply_filter_nearest_multi(double* base, int64_t n, int64_t stride, int nl) {
    const double z = kPole3;
    double gain = 1.0;
    gain *= (1.0 - z) * (1.0 - 1.0 / z);
    for (int64_t i = 0; i < n; ++i) {
        double* r = base + i * stride;
        for (int l = 0; l < nl; ++l) r[l] *= gain;
    }
    const double z_n = std::pow(z, (double)n);
    double* r0 = base;
    double* rl = base + (n - 1) * stride;
    double c0[kLineBlock];
    for (int l = 0; l < nl; ++l) {
        c0[l] = r0[l];
        r0[l] = r0[l] + z_n * rl[l];
    }
    double z_i = z;
    for (int64_t i = 1; i < n; ++i) {
        const double* ri = base + i * stride;
        const double* rm = base + (n - 1 - i) * stride;
        for (int l = 0; l < nl; ++l) r0[l] += z_i * (ri[l] + z_n * rm[l]);
        z_i *= z;
    }
    for (int l = 0; l < nl; ++l) {
        r0[l] *= z / (1 - z_n * z_n);
        r0[l] += c0[l];
    }
    for (int64_t i = 1; i < n; ++i) {
        double* ri = base + i * stride;
        const double* rp = ri - stride;
        for (int l = 0; l < nl; ++l) ri[l] += z * rp[l];
    }
    for (int l = 0; l < nl; ++l) rl[l] *= z / (z - 1);
    for (int64_t i = n - 2; i >= 0; --i) {
        double* ri = base + i * stride;
        const double* rn = ri + stride;
        for (int l = 0; l < nl; ++l) ri[l] = z * (rn[l] - ri[l]);
    }
}

std::vector<int64_t> unique_indices(const std::vector<int64_t>& v) {
    std::vector<int64_t> u(v);
    std::sort(u.begin(), u.end());
    u.erase(std::unique(u.begin(), u.end()), u.end());
    return u;
}

void spline_weights3(double x, double* w) {
    x -= std::floor(x);
    double y = x, z = 1.0 - x;
    w[1] = (y * y * (y - 2.0) * 3.0 + 4.0) / 6.0;
    w[2] = (z * z * (z - 2.0) * 3.0 + 4.0) / 6.0;
    w[0] = z * z * z / 6.0;
    w[3] = 1.0;
    for (int i = 0; i < 3; ++i) w[3] -= w[i];
}

inline int64_t clamp_idx(int64_t v, int64_t len) { return v < 0 ? 0 : (v > len - 1 ? len - 1 : v); }

struct AxisTable {
    std::vector<int64_t> idx;  // (order+1) indices per output position (already mapped)
    std::vector<double> w;     // (order+1) weights per output position
};

AxisTable make_axis(int64_t in_len_orig, int64_t in_len_padded, int64_t out_len, int order, int npad, bool grid_mode = false) {
    AxisTable t;
    const int n = order + 1;
    t.idx.resize((size_t)(out_len * n));
    t.w.resize((size_t)(out_len * n));
    // zoom = (in-1)/(out-1) (grid_mode: in/out), or 1 if the divisor is 0 (np.divide(..., where=zoom_div != 0))
    const int64_t div = grid_mode ? out_len : out_len - 1;
    const double zf = div != 0 ? (double)(grid_mode ? in_len_orig : in_len_orig - 1) / (double)div : 1.0;
    for (int64_t kk = 0; kk < out_len; ++kk) {
        double cc = (double)kk;
        if (grid_mode) {
            cc += 0.5;
            cc *= zf;
            cc -= 0.5;
        } else {
            cc *= zf;
        }
        cc += (double)npad;
        int64_t start = (order & 1) ? (int64_t)std::floor(cc) - order / 2 : (int64_t)std::floor(cc + 0.5) - order / 2;
        for (int h = 0; h < n; ++h) t.idx[(size_t)(kk * n + h)] = clamp_idx(start + h, in_len_padded);
        if (order == 3) {
            spline_weights3(cc, &t.w[(size_t)(kk * n)]);
        } else if (order == 1) {
            double x = cc - std::floor(cc);
            double* w = &t.w[(size_t)(kk * n)];
            w[0] = 1.0 - x;
            w[1] = 1.0;
            w[1] -= w[0];
        } else {
            t.w[(size_t)(kk * n)] = 1.0;
        }
    }
    return t;
}

}  // namespace

Shape3 zoom_output_shape(const Shape3& in_shape, const std::array<double, 3>& zoom) {
    Shape3 o;
    for (int d = 0; d < 3; ++d) o[d] = py_round((double)in_shape[d] * zoom[d]);
    return o;
}

// NI_ZoomShift inner loop: t = sum over the (order+1)^3 taps of c * w0 * w1 * w2 (last axis fastest)
template <int N, class S>
void interpolate(const S* src, const Shape3& ss, const AxisTable* ax, const Shape3& os, double* out) {
    const int64_t P1 = ss[1], P2 = ss[2];
    parallel_for(os[0], [&](int64_t b, int64_t e, int) {
        for (int64_t i = b; i < e; ++i) {
            const int64_t* ii = &ax[0].idx[(size_t)(i * N)];
            const double* wi = &ax[0].w[(size_t)(i * N)];
            for (int64_t j = 0; j < os[1]; ++j) {
                const int64_t* jj = &ax[1].idx[(size_t)(j * N)];
                const double* wj = &ax[1].w[(size_t)(j * N)];
                double* o = out + (i * os[1] + j) * os[2];
                for (int64_t k = 0; k < os[2]; ++k) {
                    const int64_t* kx = &ax[2].idx[(size_t)(k * N)];
                    const double* wk = &ax[2].w[(size_t)(k * N)];
                    double t = 0.0;
                    for (int a = 0; a < N; ++a) {
                        const S* pa = src + ii[a] * P1 * P2;
                        for (int bb = 0; bb < N; ++bb) {
                            const S* pb = pa + jj[bb] * P2;
                            for (int c = 0; c < N; ++c) {
                                double coeff = (double)pb[kx[c]];
                                coeff *= wi[a];
                                coeff *= wj[bb];
                                coeff *= wk[c];
                                t += coeff;
                            }
                        }
                    }
                    o[k] = t;
                }
            }
        }
    });
}


template <class T>
std::vector<double> zoom_impl(const T* in, const Shape3& s, const Shape3& os, int order, bool grid_mode = false) {
    if (order != 0 && order != 1 && order != 3) throw std::runtime_error("scipy_zoom: only order 0, 1 and 3 supported");
    std::vector<double> out(checked_count(numel(os)));
    if (order == 1) {
        AxisTable ax[3];
        for (int d = 0; d < 3; ++d) ax[d] = make_axis(s[d], s[d], os[d], 1, 0, grid_mode);
        interpolate<2>(in, s, ax, os, out.data());
        return out;
    }
    if (order == 0) {
        AxisTable ax[3];
        for (int d = 0; d < 3; ++d) ax[d] = make_axis(s[d], s[d], os[d], 0, 0, grid_mode);
        parallel_for(os[0], [&](int64_t b, int64_t e, int) {
            for (int64_t i = b; i < e; ++i)
                for (int64_t j = 0; j < os[1]; ++j) {
                    const T* row = in + (ax[0].idx[i] * s[1] + ax[1].idx[j]) * s[2];
                    double* o = out.data() + (i * os[1] + j) * os[2];
                    for (int64_t k = 0; k < os[2]; ++k) {
                        double t = 0.0;
                        t += (double)row[ax[2].idx[k]];
                        o[k] = t;
                    }
                }
        });
        return out;
    }

    // order 3: scipy pads by 12 (edge), spline-filters the padded array along axis 0, 1, 2 and interpolates.
    // The padded array is never materialised (it was the largest allocation: 8 bytes x (s + 24)^3): the input
    // is read line by line with clamped indices, the axis-0 filter keeps only the planes the interpolation
    // reads (need0), the axis-1 filter only the rows need1 of those planes, the axis-2 filter runs on those
    // rows. Every filtered line sees exactly the same operations as before, so the values are identical.
    const Shape3 ps{s[0] + 2 * kNPad, s[1] + 2 * kNPad, s[2] + 2 * kNPad};
    AxisTable ax[3];
    for (int d = 0; d < 3; ++d) ax[d] = make_axis(s[d], ps[d], os[d], 3, kNPad, grid_mode);
    const std::vector<int64_t> need0 = unique_indices(ax[0].idx), need1 = unique_indices(ax[1].idx);
    const int64_t P0 = ps[0], P1 = ps[1], P2 = ps[2], n0 = (int64_t)need0.size(), n1 = (int64_t)need1.size();
    std::vector<double> F(checked_count(n0 * n1 * P2));  // filtered values at (need0, need1, all k)
    {
        constexpr int64_t KB = 32;                         // columns (axis 2) per block (bounds G)
        std::vector<double> G(checked_count(n0 * P1 * KB));  // axis-0 filtered planes need0, all rows, one column block
        for (int64_t k0 = 0; k0 < P2; k0 += KB) {
            const int64_t nb = std::min<int64_t>(KB, P2 - k0);
            int64_t kin[KB];
            for (int64_t l = 0; l < nb; ++l) kin[l] = clamp_idx(k0 + l - kNPad, s[2]);
            // axis 0: for every row j, the nb lines (j, k0 + l) along i
            parallel_for(P1, [&](int64_t b, int64_t e, int) {
                std::vector<double> L((size_t)(P0 * nb));
                for (int64_t j = b; j < e; ++j) {
                    const int64_t sj = clamp_idx(j - kNPad, s[1]);
                    for (int64_t i = 0; i < P0; ++i) {
                        const T* row = in + (clamp_idx(i - kNPad, s[0]) * s[1] + sj) * s[2];
                        double* dst = L.data() + i * nb;
                        for (int64_t l = 0; l < nb; ++l) dst[l] = (double)row[kin[l]];
                    }
                    apply_filter_nearest_multi(L.data(), P0, nb, (int)nb);
                    for (int64_t q = 0; q < n0; ++q)
                        std::copy(L.data() + need0[(size_t)q] * nb, L.data() + need0[(size_t)q] * nb + nb, G.data() + (q * P1 + j) * nb);
                }
            }, 8);
            // axis 1: lines along j in each kept plane; keep the rows need1
            parallel_for(n0, [&](int64_t b, int64_t e, int) {
                for (int64_t q = b; q < e; ++q) {
                    double* plane = G.data() + q * P1 * nb;
                    apply_filter_nearest_multi(plane, P1, nb, (int)nb);
                    for (int64_t r = 0; r < n1; ++r)
                        std::copy(plane + need1[(size_t)r] * nb, plane + need1[(size_t)r] * nb + nb, F.data() + (q * n1 + r) * P2 + k0);
                }
            }, 1);
        }
    }
    // axis 2 on the kept rows
    parallel_for(n0 * n1, [&](int64_t b, int64_t e, int) {
        for (int64_t r = b; r < e; ++r) apply_filter_nearest(F.data() + r * P2, P2);
    }, 4);
    // interpolate from the compact array (indices of axes 0 / 1 remapped)
    std::vector<int64_t> pos0((size_t)P0, -1), pos1((size_t)P1, -1);
    for (int64_t q = 0; q < n0; ++q) pos0[(size_t)need0[(size_t)q]] = q;
    for (int64_t r = 0; r < n1; ++r) pos1[(size_t)need1[(size_t)r]] = r;
    for (auto& v : ax[0].idx) v = pos0[(size_t)v];
    for (auto& v : ax[1].idx) v = pos1[(size_t)v];
    interpolate<4>(F.data(), Shape3{n0, n1, P2}, ax, os, out.data());
    return out;
}

std::vector<double> scipy_zoom(const double* in, const Shape3& s, const Shape3& os, int order) {
    return zoom_impl(in, s, os, order);
}

std::vector<double> scipy_zoom_grid(const double* in, const Shape3& s, const Shape3& os, int order) {
    if (s == os) return std::vector<double>(in, in + numel(s));  // zoom factors exactly 1: scipy early exit
    return zoom_impl(in, s, os, order, true);
}

std::vector<double> scipy_zoom_grid_2d(const double* in, int64_t h, int64_t w, int64_t oh, int64_t ow, int order) {
    if (order != 1 && order != 3) throw std::runtime_error("scipy_zoom_grid_2d: only order 1 and 3 supported");
    // skimage passes zoom = 1 / (in / out) = exactly 1 for an unchanged shape: scipy.ndimage.zoom then returns
    // a copy of the input (early exit) instead of interpolating
    if (h == oh && w == ow) return std::vector<double>(in, in + h * w);
    std::vector<double> out(checked_count(oh * ow));
    if (order == 1) {
        const AxisTable a0 = make_axis(h, h, oh, 1, 0, true), a1 = make_axis(w, w, ow, 1, 0, true);
        for (int64_t i = 0; i < oh; ++i)
            for (int64_t j = 0; j < ow; ++j) {
                double t = 0.0;
                for (int a = 0; a < 2; ++a)
                    for (int b = 0; b < 2; ++b) {
                        double coeff = in[a0.idx[(size_t)(i * 2 + a)] * w + a1.idx[(size_t)(j * 2 + b)]];
                        coeff *= a0.w[(size_t)(i * 2 + a)];
                        coeff *= a1.w[(size_t)(j * 2 + b)];
                        t += coeff;
                    }
                out[(size_t)(i * ow + j)] = t;
            }
        return out;
    }
    // order 3: edge-pad by 12 on both axes, spline_filter1d along axis 0 then axis 1, interpolate (4x4 taps)
    const int64_t ph = h + 2 * kNPad, pw = w + 2 * kNPad;
    std::vector<double> p(checked_count(ph * pw));
    for (int64_t i = 0; i < ph; ++i) {
        const double* src = in + clamp_idx(i - kNPad, h) * w;
        double* dst = p.data() + i * pw;
        for (int64_t j = 0; j < pw; ++j) dst[j] = src[clamp_idx(j - kNPad, w)];
    }
    for (int64_t k0 = 0; k0 < pw; k0 += kLineBlock)
        apply_filter_nearest_multi(p.data() + k0, ph, pw, (int)std::min<int64_t>(kLineBlock, pw - k0));
    for (int64_t i = 0; i < ph; ++i) apply_filter_nearest(p.data() + i * pw, pw);
    const AxisTable a0 = make_axis(h, ph, oh, 3, kNPad, true), a1 = make_axis(w, pw, ow, 3, kNPad, true);
    for (int64_t i = 0; i < oh; ++i)
        for (int64_t j = 0; j < ow; ++j) {
            double t = 0.0;
            for (int a = 0; a < 4; ++a) {
                const double* row = p.data() + a0.idx[(size_t)(i * 4 + a)] * pw;
                for (int b = 0; b < 4; ++b) {
                    double coeff = row[a1.idx[(size_t)(j * 4 + b)]];
                    coeff *= a0.w[(size_t)(i * 4 + a)];
                    coeff *= a1.w[(size_t)(j * 4 + b)];
                    t += coeff;
                }
            }
            out[(size_t)(i * ow + j)] = t;
        }
    return out;
}

std::vector<double> nnunet_resample_separate_z(const double* in, const Shape3& s, const Shape3& ns, int axis, int order) {
    if (axis < 0 || axis > 2) throw std::runtime_error("separate-z: bad axis");
    const int a1 = axis == 0 ? 1 : 0, a2 = axis == 2 ? 1 : 2;  // the two in-plane axes, in array order
    const int64_t st[3] = {s[1] * s[2], s[2], 1};
    Shape3 ts = ns;
    ts[axis] = s[axis];  // in-plane resized, original number of slices
    const int64_t tst[3] = {ts[1] * ts[2], ts[2], 1};
    std::vector<double> here(checked_count(numel(ts)));
    parallel_for(s[axis], [&](int64_t b, int64_t e, int) {
        std::vector<double> sl(checked_count(s[a1] * s[a2]));
        for (int64_t k = b; k < e; ++k) {
            for (int64_t i = 0; i < s[a1]; ++i)
                for (int64_t j = 0; j < s[a2]; ++j) sl[(size_t)(i * s[a2] + j)] = in[k * st[axis] + i * st[a1] + j * st[a2]];
            double mn = sl[0], mx = sl[0];  // skimage resize clips to the range of its (2-D) input
            for (double v : sl) { mn = std::min(mn, v); mx = std::max(mx, v); }
            std::vector<double> r = scipy_zoom_grid_2d(sl.data(), s[a1], s[a2], ns[a1], ns[a2], order);
            for (int64_t i = 0; i < ns[a1]; ++i)
                for (int64_t j = 0; j < ns[a2]; ++j)
                    here[(size_t)(k * tst[axis] + i * tst[a1] + j * tst[a2])] = std::min(std::max(r[(size_t)(i * ns[a2] + j)], mn), mx);
        }
    }, 1);
    if (s[axis] == ns[axis]) return here;
    // map_coordinates(order=0, mode='nearest') with coordinates scale * (k + 0.5) - 0.5 along `axis`
    // (the in-plane coordinates are the integers themselves): start = floor(cc + 0.5), clamped
    const double scale = (double)s[axis] / (double)ns[axis];
    std::vector<int64_t> src((size_t)ns[axis]);
    for (int64_t k = 0; k < ns[axis]; ++k) {
        double cc = (double)k + 0.5;
        cc = scale * cc;
        cc -= 0.5;
        src[(size_t)k] = clamp_idx((int64_t)std::floor(cc + 0.5), s[axis]);
    }
    std::vector<double> out(checked_count(numel(ns)));
    const int64_t ost[3] = {ns[1] * ns[2], ns[2], 1};
    parallel_for(ns[0], [&](int64_t b, int64_t e, int) {
        for (int64_t z = b; z < e; ++z)
            for (int64_t y = 0; y < ns[1]; ++y)
                for (int64_t x = 0; x < ns[2]; ++x) {
                    int64_t q[3] = {z, y, x};
                    q[axis] = src[(size_t)q[axis]];
                    out[(size_t)(z * ost[0] + y * ost[1] + x)] = here[(size_t)(q[0] * tst[0] + q[1] * tst[1] + q[2])];
                }
    });
    return out;
}

int nnunet_separate_z_axis(const double* cur, const double* nw) {
    auto aniso = [](const double* sp) { return std::max({sp[0], sp[1], sp[2]}) / std::min({sp[0], sp[1], sp[2]}) > 3.0; };
    const double* sp = aniso(cur) ? cur : aniso(nw) ? nw : nullptr;
    if (!sp) return -1;
    const double mx = std::max({sp[0], sp[1], sp[2]});
    int n = 0, axis = -1;
    for (int d = 0; d < 3; ++d)
        if (mx / sp[d] == 1.0) { ++n; axis = d; }  // get_lowres_axis: max(spacing) / spacing == 1
    return n == 1 ? axis : -1;  // 2 or 3 equal maxima: no separate z
}

std::vector<uint8_t> scipy_zoom_nearest_u8(const uint8_t* in, const Shape3& s, const Shape3& os) {
    AxisTable ax[3];
    for (int d = 0; d < 3; ++d) ax[d] = make_axis(s[d], s[d], os[d], 0, 0);
    std::vector<uint8_t> out(checked_count(numel(os)));
    parallel_for(os[0], [&](int64_t b, int64_t e, int) {
        for (int64_t i = b; i < e; ++i)
            for (int64_t j = 0; j < os[1]; ++j) {
                const uint8_t* row = in + (ax[0].idx[i] * s[1] + ax[1].idx[j]) * s[2];
                uint8_t* o = out.data() + (i * os[1] + j) * os[2];
                for (int64_t k = 0; k < os[2]; ++k) o[k] = row[ax[2].idx[k]];
            }
    });
    return out;
}

std::vector<double> scipy_zoom(const float* in, const Shape3& s, const Shape3& os, int order) {
    return zoom_impl(in, s, os, order);
}

std::vector<double> scipy_zoom(const int32_t* in, const Shape3& s, const Shape3& os, int order) {
    return zoom_impl(in, s, os, order);
}

std::vector<double> scipy_zoom(const uint8_t* in, const Shape3& s, const Shape3& os, int order) {
    return zoom_impl(in, s, os, order);
}

}  // namespace tsc
