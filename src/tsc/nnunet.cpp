#include "nnunet.h"
#include "resample.h"

#include <algorithm>
#include <chrono>
#include <cmath>

namespace tsc {

namespace {

// numpy pairwise summation (float64, contiguous) as used by ndarray.sum()
double pairwise_sum(const double* a, int64_t n) {
    if (n < 8) {
        double res = 0.;
        for (int64_t i = 0; i < n; ++i) res += a[i];
        return res;
    } else if (n <= 128) {
        double r[8];
        for (int j = 0; j < 8; ++j) r[j] = a[j];
        int64_t i;
        for (i = 8; i < n - (n % 8); i += 8)
            for (int j = 0; j < 8; ++j) r[j] += a[i + j];
        double res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; ++i) res += a[i];
        return res;
    } else {
        int64_t n2 = n / 2;
        n2 -= n2 % 8;
        return pairwise_sum(a, n2) + pairwise_sum(a + n2, n - n2);
    }
}

// scipy.ndimage._gaussian_kernel1d(sigma, 0, radius)
std::vector<double> gaussian_kernel1d(double sigma, int radius) {
    const double sigma2 = sigma * sigma;
    std::vector<double> phi(2 * radius + 1);
    for (int i = -radius; i <= radius; ++i) phi[i + radius] = std::exp(-0.5 / sigma2 * (double)(i * i));
    const double s = pairwise_sum(phi.data(), (int64_t)phi.size());
    for (auto& v : phi) v = v / s;
    return phi;
}

// numpy astype(float16) from float64 rounds directly (used for the exported logits in finish()).
// torch's .half() on a float64 tensor goes through float32 (c10::Half(float)): that path is float_to_half((float)d).
uint16_t double_to_half(double d) {
    float f = (float)d;
    uint16_t h = float_to_half(f);
    // correct potential double rounding: compare distances in double
    float lo = half_to_float(h);
    uint16_t alt = (double)lo < d ? (uint16_t)(h + 1) : (uint16_t)(h - 1);
    double dl = std::fabs((double)lo - d), da = std::fabs((double)half_to_float(alt) - d);
    if (da < dl || (da == dl && (alt & 1) == 0)) return alt;
    return h;
}

// nnunetv2 compute_gaussian(tile, sigma_scale=1/8, value_scaling_factor=10) as fp16
std::vector<uint16_t> compute_gaussian(const int P[3]) {
    std::vector<double> w[3];
    for (int d = 0; d < 3; ++d) {
        const double sigma = P[d] * (1. / 8);
        const int radius = (int)(4.0 * sigma + 0.5);
        auto k = gaussian_kernel1d(sigma, radius);
        const int c = P[d] / 2;
        w[d].assign(P[d], 0.0);
        for (int i = 0; i < P[d]; ++i) {
            const int off = i - c;
            if (off >= -radius && off <= radius) w[d][i] = k[off + radius];
        }
    }
    const int64_t n = (int64_t)P[0] * P[1] * P[2];
    std::vector<double> g((size_t)n);
    double mx = 0;
    for (int i = 0; i < P[0]; ++i)
        for (int j = 0; j < P[1]; ++j)
            for (int k = 0; k < P[2]; ++k) {
                double v = w[0][i];
                v = w[1][j] * v;
                v = w[2][k] * v;
                g[((size_t)i * P[1] + j) * P[2] + k] = v;
                mx = std::max(mx, v);
            }
    const double div = mx / 10.0;
    std::vector<uint16_t> h((size_t)n);
    uint16_t minnz = 0x7bff;
    for (int64_t i = 0; i < n; ++i) {
        h[i] = float_to_half((float)(g[i] / div));  // torch.from_numpy(float64).half(): float64 -> float32 -> float16
        if (h[i] != 0 && half_to_float(h[i]) < half_to_float(minnz)) minnz = h[i];
    }
    for (auto& v : h)
        if (v == 0) v = minnz;
    return h;
}

std::vector<int64_t> compute_steps(int64_t image, int tile, double step_size) {
    const double target = tile * step_size;
    const int64_t num = (int64_t)std::ceil((double)(image - tile) / target) + 1;
    const int64_t maxv = image - tile;
    const double actual = num > 1 ? (double)maxv / (double)(num - 1) : 99999999999.0;
    std::vector<int64_t> s;
    for (int64_t i = 0; i < num; ++i) s.push_back((int64_t)std::nearbyint(actual * (double)i));
    return s;
}

}  // namespace

SlidingWindow::SlidingWindow(const ModelConfig& cfg, const Volume<int32_t>& img, double step_size, PredictDebug* dbg)
    : cfg_(cfg), img_shape_(img.shape), img_affine_(img.affine), dbg_(dbg) {
    // --- NibabelIOWithReorient: array transposed to (z, y, x), spacing reversed
    const Shape3 ts{img.shape[2], img.shape[1], img.shape[0]};
    auto zooms = zooms_from_affine(img.affine);
    const double spacing_t[3] = {zooms[2], zooms[1], zooms[0]};
    for (int d = 0; d < 3; ++d) spacing_t_[d] = spacing_t[d];
    auto T = [&](int64_t z, int64_t y, int64_t x) { return img.data[(size_t)((x * img.shape[1] + y) * img.shape[2] + z)]; };

    // --- crop_to_nonzero (bbox of data != 0; hole filling does not change the bbox)
    // computed on the (x,y,z) array and transposed to (z,y,x)
    int64_t hi[3] = {-1, -1, -1};
    {
        int64_t l3[3], h3[3];
        if (bbox_where(img.data.data(), img.shape, [](int32_t v) { return v != 0; }, l3, h3)) {
            for (int d = 0; d < 3; ++d) { lo_[d] = l3[2 - d]; hi[d] = h3[2 - d]; }
        } else {
            for (int d = 0; d < 3; ++d) { lo_[d] = 0; hi[d] = ts[d] - 1; }
        }
    }
    cs_ = Shape3{hi[0] - lo_[0] + 1, hi[1] - lo_[1] + 1, hi[2] - lo_[2] + 1};
    const Shape3 cs = cs_;

    // --- CTNormalization (float32 arithmetic, as numpy with weak python scalars)
    const float lb = (float)cfg.ct_p005, ub = (float)cfg.ct_p995;
    const float mean = (float)cfg.ct_mean, stdv = (float)std::max(cfg.ct_std, 1e-8);
    std::vector<float> pre(checked_count(numel(cs)));
    parallel_for(cs[0], [&](int64_t b, int64_t e, int) {
        for (int64_t z = b; z < e; ++z)
            for (int64_t y = 0; y < cs[1]; ++y)
                for (int64_t x = 0; x < cs[2]; ++x) {
                    float v = (float)T(z + lo_[0], y + lo_[1], x + lo_[2]);
                    v = std::min(std::max(v, lb), ub);
                    v -= mean;
                    v /= stdv;
                    pre[(size_t)((z * cs[1] + y) * cs[2] + x)] = v;
                }
    });
    // new_shape = round(old_spacing / new_spacing * shape) on the cropped array
    for (int d = 0; d < 3; ++d) ns_[d] = py_round(spacing_t_[d] / cfg.spacing[d] * (double)cs[d]);
    if (ns_ != cs) {
        // resample_data_or_seg: astype(float64) -> skimage resize(order 3, mode edge, no anti-aliasing,
        // clip to input range) -> stored as float32. Anisotropic spacing (> 3): per slice in 2-D, then
        // nearest neighbour along the low-resolution axis (order_z 0).
        std::vector<double> d(pre.begin(), pre.end());
        std::vector<float>().swap(pre);  // not needed any more (the float64 copy is the input)
        const int zaxis = nnunet_separate_z_axis(spacing_t_, cfg.spacing);
        std::vector<double> r;
        if (zaxis >= 0) {
            r = nnunet_resample_separate_z(d.data(), cs, ns_, zaxis, 3);
            pre.resize(r.size());
            for (size_t i = 0; i < r.size(); ++i) pre[i] = (float)r[i];
        } else {
            double mn = d[0], mx = d[0];
            for (double v : d) { mn = std::min(mn, v); mx = std::max(mx, v); }
            r = scipy_zoom_grid(d.data(), cs, ns_, 3);
            pre.resize(r.size());
            for (size_t i = 0; i < r.size(); ++i) pre[i] = (float)std::min(std::max(r[i], mn), mx);
        }
    }
    const Shape3 ns = ns_;
    if (dbg && dbg->keep) {
        dbg->pre = pre;
        dbg->pre_shape = ns;
    }
    if (dbg)
        for (int d = 0; d < 3; ++d) { dbg->bbox[d][0] = (int)lo_[d]; dbg->bbox[d][1] = (int)hi[d] + 1; }

    // --- pad to patch size (constant 0, content centred)
    const int* P = cfg.patch;
    for (int d = 0; d < 3; ++d) {
        ps_[d] = std::max<int64_t>(ns[d], P[d]);
        pad_lo_[d] = (ps_[d] - ns[d]) / 2;
    }
    data_.assign(checked_count(numel(ps_)), 0.f);
    for (int64_t z = 0; z < ns[0]; ++z)
        for (int64_t y = 0; y < ns[1]; ++y)
            std::memcpy(&data_[(size_t)(((z + pad_lo_[0]) * ps_[1] + y + pad_lo_[1]) * ps_[2] + pad_lo_[2])],
                        &pre[(size_t)((z * ns[1] + y) * ns[2])], (size_t)ns[2] * 4);

    // --- sliding window tiles (same order as nnU-Net: x, y, z nested)
    std::vector<int64_t> steps[3];
    for (int d = 0; d < 3; ++d) steps[d] = compute_steps(ps_[d], P[d], step_size);
    for (int64_t sx : steps[0])
        for (int64_t sy : steps[1])
            for (int64_t sz : steps[2]) tiles_.push_back({sx, sy, sz});
    const std::vector<uint16_t> gauss = compute_gaussian(P);
    gauss_f_.resize(gauss.size());
    for (size_t i = 0; i < gauss.size(); ++i) gauss_f_[i] = half_to_float(gauss[i]);
    logits_.assign(checked_count((int64_t)cfg.num_classes * numel(ps_)), 0);
    npred_.assign(checked_count(numel(ps_)), 0);
    if (dbg) dbg->num_tiles = (int)tiles_.size();
}

int64_t SlidingWindow::patch_numel() const { return (int64_t)cfg_.patch[0] * cfg_.patch[1] * cfg_.patch[2]; }

void SlidingWindow::tile_input(int t, float* dst) const {
    const int* P = cfg_.patch;
    const auto& s = tiles_[(size_t)t];
    for (int i = 0; i < P[0]; ++i)
        for (int j = 0; j < P[1]; ++j)
            std::memcpy(&dst[((size_t)i * P[1] + j) * P[2]], &data_[(size_t)(((s[0] + i) * ps_[1] + s[1] + j) * ps_[2] + s[2])],
                        (size_t)P[2] * 4);
}

void SlidingWindow::accumulate(int t, const float* y) {
    // prediction *= gaussian (fp32 * fp16 -> fp32); logits(fp16) += prediction; n(fp16) += gaussian
    const int* P = cfg_.patch;
    const int C = cfg_.num_classes;
    const int64_t NP = numel(ps_), PP = patch_numel();
    const auto& s = tiles_[(size_t)t];
    const float* h2f = half_lut();
    parallel_for(P[0], [&](int64_t b, int64_t e, int) {
        for (int64_t i = b; i < e; ++i)
            for (int j = 0; j < P[1]; ++j) {
                const int64_t pbase = ((int64_t)i * P[1] + j) * P[2];
                const int64_t vbase = ((s[0] + i) * ps_[1] + s[1] + j) * ps_[2] + s[2];
                for (int c = 0; c < C; ++c) {
                    const float* yp = y + (size_t)c * PP + pbase;
                    uint16_t* lp = &logits_[(size_t)c * NP + vbase];
                    for (int k = 0; k < P[2]; ++k) {
                        const float v = yp[k] * gauss_f_[pbase + k];
                        lp[k] = float_to_half(h2f[lp[k]] + v);
                    }
                }
                uint16_t* np_ = &npred_[(size_t)vbase];
                for (int k = 0; k < P[2]; ++k) np_[k] = float_to_half(half_to_float(np_[k]) + gauss_f_[pbase + k]);
            }
    });
}

void SlidingWindow::accumulate_counts(int t) {
    const int* P = cfg_.patch;
    const auto& s = tiles_[(size_t)t];
    parallel_for(P[0], [&](int64_t b, int64_t e, int) {
        for (int64_t i = b; i < e; ++i)
            for (int j = 0; j < P[1]; ++j) {
                const int64_t pbase = ((int64_t)i * P[1] + j) * P[2];
                uint16_t* np_ = &npred_[(size_t)(((s[0] + i) * ps_[1] + s[1] + j) * ps_[2] + s[2])];
                for (int k = 0; k < P[2]; ++k) np_[k] = float_to_half(half_to_float(np_[k]) + gauss_f_[pbase + k]);
            }
    });
}

Volume<uint8_t> SlidingWindow::finish() {
    const int C = cfg_.num_classes;
    const int64_t NP = numel(ps_);
    const float* h2f = half_lut();
    // logits /= n (fp16 in, computed in float, fp16 out)
    parallel_for(NP, [&](int64_t b, int64_t e, int) {
        for (int64_t i = b; i < e; ++i) {
            const float n = h2f[npred_[i]];
            for (int c = 0; c < C; ++c) {
                uint16_t& l = logits_[(size_t)c * NP + i];
                l = float_to_half(h2f[l] / n);
            }
        }
    }, 4096);
    npred_.clear();
    data_.clear();
    data_.shrink_to_fit();

    // --- revert padding (network grid), optional resampling of the logits back to the
    //     cropped grid (export: order 1, stored as fp16), argmax, un-crop, transpose back
    PredictDebug* dbg = dbg_;
    const Shape3 cs = cs_, ns = ns_;
    const int64_t NN = numel(ns), NC = numel(cs);
    auto padded_index = [&](int64_t z, int64_t y, int64_t x) {
        return ((z + pad_lo_[0]) * ps_[1] + y + pad_lo_[1]) * ps_[2] + x + pad_lo_[2];
    };
    if (dbg && dbg->keep) {
        dbg->logits.assign(checked_count((int64_t)C * NN), 0);
        parallel_for(ns[0], [&](int64_t b, int64_t e, int) {
            for (int64_t z = b; z < e; ++z)
                for (int64_t y = 0; y < ns[1]; ++y)
                    for (int64_t x = 0; x < ns[2]; ++x)
                        for (int c = 0; c < C; ++c)
                            dbg->logits[(size_t)c * NN + (z * ns[1] + y) * ns[2] + x] = logits_[(size_t)c * NP + padded_index(z, y, x)];
        });
    }
    // fp16 logits on the cropped grid (C x cs)
    std::vector<uint16_t> lc;
    const uint16_t* L;
    int64_t LS;  // class stride
    if (ns != cs) {
        // export: current spacing = the model's, new spacing = the image's (same rule as above)
        const int zaxis = nnunet_separate_z_axis(cfg_.spacing, spacing_t_);
        lc.resize(checked_count((int64_t)C * NC));
        std::vector<double> ch(checked_count(NN));
        for (int c = 0; c < C; ++c) {
            // resample_data_or_seg: astype(float64) -> resize(order 1, edge, clip) -> float16
            parallel_for(ns[0], [&](int64_t b, int64_t e, int) {
                for (int64_t z = b; z < e; ++z)
                    for (int64_t y = 0; y < ns[1]; ++y)
                        for (int64_t x = 0; x < ns[2]; ++x)
                            ch[(size_t)((z * ns[1] + y) * ns[2] + x)] = h2f[logits_[(size_t)c * NP + padded_index(z, y, x)]];
            });
            std::vector<double> r;
            double mn = -INFINITY, mx = INFINITY;  // separate z: already clipped per slice
            if (zaxis >= 0) {
                r = nnunet_resample_separate_z(ch.data(), ns, cs, zaxis, 1);
            } else {
                mn = ch[0], mx = ch[0];
                for (double v : ch) { mn = std::min(mn, v); mx = std::max(mx, v); }
                r = scipy_zoom_grid(ch.data(), ns, cs, 1);
            }
            uint16_t* dst = lc.data() + (size_t)c * NC;
            parallel_for((int64_t)r.size(), [&](int64_t b, int64_t e, int) {
                for (int64_t i = b; i < e; ++i) dst[i] = double_to_half(std::min(std::max(r[(size_t)i], mn), mx));
            }, 1 << 14);
        }
        L = lc.data();
        LS = NC;
    } else {
        L = nullptr;
        LS = NP;
    }
    Volume<uint8_t> out(img_shape_, img_affine_);
    parallel_for(cs[0], [&](int64_t b, int64_t e, int) {
        for (int64_t z = b; z < e; ++z)
            for (int64_t y = 0; y < cs[1]; ++y)
                for (int64_t x = 0; x < cs[2]; ++x) {
                    const int64_t pi = L ? (z * cs[1] + y) * cs[2] + x : padded_index(z, y, x);
                    const uint16_t* base = L ? L : logits_.data();
                    int best = 0;
                    float bv = h2f[base[(size_t)pi]];
                    for (int c = 1; c < C; ++c) {
                        const float v = h2f[base[(size_t)c * LS + pi]];
                        if (v > bv) { bv = v; best = c; }
                    }
                    const int64_t Z = z + lo_[0], Y = y + lo_[1], X = x + lo_[2];
                    out.data[(size_t)((X * img_shape_[1] + Y) * img_shape_[2] + Z)] = (uint8_t)best;
                }
    });
    logits_.clear();
    logits_.shrink_to_fit();
    return out;
}

Volume<uint8_t> nnunet_predict(const UNet& net, const Volume<int32_t>& img, const PredictOptions& opt, PredictDebug* dbg) {
    SlidingWindow sw(net.config(), img, opt.step_size, dbg);
    const int* P = net.config().patch;
    for (int t = 0; t < sw.num_tiles(); ++t) {
        if (opt.progress) opt.progress(opt.stage_name, (double)t / sw.num_tiles());
        Tensor x(1, P[0], P[1], P[2]);
        sw.tile_input(t, x.data.data());
        Tensor y = net.forward(x);
        sw.accumulate(t, y.data.data());
    }
    if (opt.progress) opt.progress(opt.stage_name, 1.0);
    return sw.finish();
}

}  // namespace tsc
