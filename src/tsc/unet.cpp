#include "unet.h"

#include <algorithm>
#include <cmath>

#if defined(__AVX2__)
#include <immintrin.h>
#define TSC_AVX2 1
#elif defined(__wasm_simd128__)
#include <wasm_simd128.h>
#define TSC_WASM 1
#endif

namespace tsc {

namespace {

#if TSC_AVX2
constexpr int MR = 6, NR = 16;
#elif TSC_WASM
constexpr int MR = 6, NR = 8;
#else
constexpr int MR = 4, NR = 8;
#endif
constexpr int NT = 128;  // output positions per tile (multiple of NR)
constexpr int KC = 256;  // reduction block

// ---------------------------------------------------------------------------
// micro kernel: C[MR x NR] (+)= sum_p A[p][0..MR) * B[p][0..NR)
// A: kc x MR (packed), B: kc x NR (packed), C row stride ldc
// ---------------------------------------------------------------------------
#if TSC_AVX2
inline void micro(int kc, const float* A, const float* B, float* C, int ldc, bool acc) {
    __m256 c00, c01, c10, c11, c20, c21, c30, c31, c40, c41, c50, c51;
    if (acc) {
        c00 = _mm256_loadu_ps(C + 0 * ldc); c01 = _mm256_loadu_ps(C + 0 * ldc + 8);
        c10 = _mm256_loadu_ps(C + 1 * ldc); c11 = _mm256_loadu_ps(C + 1 * ldc + 8);
        c20 = _mm256_loadu_ps(C + 2 * ldc); c21 = _mm256_loadu_ps(C + 2 * ldc + 8);
        c30 = _mm256_loadu_ps(C + 3 * ldc); c31 = _mm256_loadu_ps(C + 3 * ldc + 8);
        c40 = _mm256_loadu_ps(C + 4 * ldc); c41 = _mm256_loadu_ps(C + 4 * ldc + 8);
        c50 = _mm256_loadu_ps(C + 5 * ldc); c51 = _mm256_loadu_ps(C + 5 * ldc + 8);
    } else {
        c00 = c01 = c10 = c11 = c20 = c21 = c30 = c31 = c40 = c41 = c50 = c51 = _mm256_setzero_ps();
    }
    for (int p = 0; p < kc; ++p) {
        const __m256 b0 = _mm256_loadu_ps(B), b1 = _mm256_loadu_ps(B + 8);
        __m256 a;
        a = _mm256_broadcast_ss(A + 0); c00 = _mm256_fmadd_ps(a, b0, c00); c01 = _mm256_fmadd_ps(a, b1, c01);
        a = _mm256_broadcast_ss(A + 1); c10 = _mm256_fmadd_ps(a, b0, c10); c11 = _mm256_fmadd_ps(a, b1, c11);
        a = _mm256_broadcast_ss(A + 2); c20 = _mm256_fmadd_ps(a, b0, c20); c21 = _mm256_fmadd_ps(a, b1, c21);
        a = _mm256_broadcast_ss(A + 3); c30 = _mm256_fmadd_ps(a, b0, c30); c31 = _mm256_fmadd_ps(a, b1, c31);
        a = _mm256_broadcast_ss(A + 4); c40 = _mm256_fmadd_ps(a, b0, c40); c41 = _mm256_fmadd_ps(a, b1, c41);
        a = _mm256_broadcast_ss(A + 5); c50 = _mm256_fmadd_ps(a, b0, c50); c51 = _mm256_fmadd_ps(a, b1, c51);
        A += MR;
        B += NR;
    }
    _mm256_storeu_ps(C + 0 * ldc, c00); _mm256_storeu_ps(C + 0 * ldc + 8, c01);
    _mm256_storeu_ps(C + 1 * ldc, c10); _mm256_storeu_ps(C + 1 * ldc + 8, c11);
    _mm256_storeu_ps(C + 2 * ldc, c20); _mm256_storeu_ps(C + 2 * ldc + 8, c21);
    _mm256_storeu_ps(C + 3 * ldc, c30); _mm256_storeu_ps(C + 3 * ldc + 8, c31);
    _mm256_storeu_ps(C + 4 * ldc, c40); _mm256_storeu_ps(C + 4 * ldc + 8, c41);
    _mm256_storeu_ps(C + 5 * ldc, c50); _mm256_storeu_ps(C + 5 * ldc + 8, c51);
}
#elif TSC_WASM
inline void micro(int kc, const float* A, const float* B, float* C, int ldc, bool acc) {
    v128_t c[MR][2];
    for (int r = 0; r < MR; ++r) {
        if (acc) {
            c[r][0] = wasm_v128_load(C + r * ldc);
            c[r][1] = wasm_v128_load(C + r * ldc + 4);
        } else {
            c[r][0] = c[r][1] = wasm_f32x4_splat(0.f);
        }
    }
    for (int p = 0; p < kc; ++p) {
        const v128_t b0 = wasm_v128_load(B), b1 = wasm_v128_load(B + 4);
#pragma clang loop unroll(full)
        for (int r = 0; r < MR; ++r) {
            const v128_t a = wasm_v128_load32_splat(A + r);
            c[r][0] = wasm_f32x4_add(c[r][0], wasm_f32x4_mul(a, b0));
            c[r][1] = wasm_f32x4_add(c[r][1], wasm_f32x4_mul(a, b1));
        }
        A += MR;
        B += NR;
    }
    for (int r = 0; r < MR; ++r) {
        wasm_v128_store(C + r * ldc, c[r][0]);
        wasm_v128_store(C + r * ldc + 4, c[r][1]);
    }
}
#else
inline void micro(int kc, const float* A, const float* B, float* C, int ldc, bool acc) {
    float c[MR][NR];
    for (int r = 0; r < MR; ++r)
        for (int j = 0; j < NR; ++j) c[r][j] = acc ? C[r * ldc + j] : 0.f;
    for (int p = 0; p < kc; ++p) {
        for (int r = 0; r < MR; ++r)
            for (int j = 0; j < NR; ++j) c[r][j] += A[r] * B[j];
        A += MR;
        B += NR;
    }
    for (int r = 0; r < MR; ++r)
        for (int j = 0; j < NR; ++j) C[r * ldc + j] = c[r][j];
}
#endif

struct PackedA {
    int M = 0, K = 0, panels = 0;
    std::vector<float> data;  // [panel][K][MR]
};

template <class Get>
PackedA pack_a(int M, int K, Get get) {
    PackedA a;
    a.M = M;
    a.K = K;
    a.panels = (M + MR - 1) / MR;
    a.data.assign((size_t)a.panels * K * MR, 0.f);
    for (int m = 0; m < M; ++m) {
        int p = m / MR, r = m % MR;
        for (int k = 0; k < K; ++k) a.data[((size_t)p * K + k) * MR + r] = get(m, k);
    }
    return a;
}

thread_local std::vector<float> tl_bpack, tl_cbuf;

// Tiled GEMM driver. packB(n0, nlen, k0, kc, dst) must write ceil(nlen/NR)
// panels of [kc][NR] (zero padded). store(m0, m1, n0, nlen, C, ldc) consumes rows [m0,m1).
template <class PackB, class Store>
void gemm(const PackedA& A, int64_t N, PackB&& packB, Store&& store) {
    const int64_t tiles = (N + NT - 1) / NT;
    const int nth = num_threads();
    int mchunks = 1;
    if (tiles < 2 * nth) mchunks = std::min<int>(A.panels, (int)((2 * nth + tiles - 1) / tiles));
    const int ppc = (A.panels + mchunks - 1) / mchunks;
    mchunks = (A.panels + ppc - 1) / ppc;
    const int K = A.K;
    parallel_for(tiles * mchunks, [&](int64_t b, int64_t e, int) {
        tl_bpack.resize((size_t)KC * NT);
        tl_cbuf.resize((size_t)ppc * MR * NT);
        float* Bp = tl_bpack.data();
        float* Cb = tl_cbuf.data();
        for (int64_t it = b; it < e; ++it) {
            const int64_t tile = it / mchunks;
            const int mc = (int)(it % mchunks);
            const int64_t n0 = tile * NT;
            const int nlen = (int)std::min<int64_t>(NT, N - n0);
            const int npan = (nlen + NR - 1) / NR;
            const int mp0 = mc * ppc, mp1 = std::min(A.panels, mp0 + ppc);
            for (int k0 = 0; k0 < K; k0 += KC) {
                const int kc = std::min(KC, K - k0);
                packB(n0, nlen, k0, kc, Bp);
                for (int mp = mp0; mp < mp1; ++mp) {
                    const float* Ap = A.data.data() + ((size_t)mp * K + k0) * MR;
                    float* Cp = Cb + (size_t)(mp - mp0) * MR * NT;
                    for (int j = 0; j < npan; ++j) micro(kc, Ap, Bp + (size_t)j * kc * NR, Cp + j * NR, NT, k0 > 0);
                }
            }
            store(mp0 * MR, std::min(A.M, mp1 * MR), n0, nlen, Cb, NT);
        }
    });
}

struct Conv {
    int cin = 0, cout = 0, k[3] = {3, 3, 3}, s[3] = {1, 1, 1}, p[3] = {1, 1, 1};
    PackedA A;
    std::vector<float> bias, nw, nb;
};

struct TConv {
    int cin = 0, cout = 0, s[3] = {2, 2, 2};
    std::vector<PackedA> A;  // one per kernel offset
    std::vector<float> bias;
};

Conv make_conv(const ModelWeights& w, const std::string& pre, const std::array<int, 3>& kernel,
               const std::array<int, 3>& stride, bool norm) {
    Conv c;
    const TensorF& W = w.get(pre + ".w");
    c.cout = (int)W.shape[0];
    c.cin = (int)W.shape[1];
    for (int d = 0; d < 3; ++d) {
        c.k[d] = (int)W.shape[2 + d];
        c.s[d] = stride[d];
        c.p[d] = c.k[d] / 2;
        if (c.k[d] != kernel[d]) throw std::runtime_error("kernel mismatch in " + pre);
    }
    const int K = c.cin * c.k[0] * c.k[1] * c.k[2];
    c.A = pack_a(c.cout, K, [&](int m, int kk) { return W.data[(size_t)m * K + kk]; });
    c.bias = w.get(pre + ".b").data;
    if (norm) {
        c.nw = w.get(pre + ".nw").data;
        c.nb = w.get(pre + ".nb").data;
    }
    return c;
}

TConv make_tconv(const ModelWeights& w, const std::string& pre) {
    TConv t;
    const TensorF& W = w.get(pre + ".w");  // [cin][cout][sd][sh][sw]
    t.cin = (int)W.shape[0];
    t.cout = (int)W.shape[1];
    for (int d = 0; d < 3; ++d) t.s[d] = (int)W.shape[2 + d];
    const int KV = t.s[0] * t.s[1] * t.s[2];
    for (int o = 0; o < KV; ++o)
        t.A.push_back(pack_a(t.cout, t.cin, [&](int m, int k) { return W.data[((size_t)k * t.cout + m) * KV + o]; }));
    t.bias = w.get(pre + ".b").data;
    return t;
}

// Conv over the channel-concatenation of `ins` (all same spatial size).
Tensor conv_forward(const Conv& c, const std::vector<const Tensor*>& ins) {
    const int D = ins[0]->D, H = ins[0]->H, W = ins[0]->W;
    std::vector<const float*> chan;
    for (auto* t : ins)
        for (int ci = 0; ci < t->C; ++ci) chan.push_back(t->ch(ci));
    if ((int)chan.size() != c.cin) throw std::runtime_error("conv input channel mismatch");
    const int OD = (D + 2 * c.p[0] - c.k[0]) / c.s[0] + 1;
    const int OH = (H + 2 * c.p[1] - c.k[1]) / c.s[1] + 1;
    const int OW = (W + 2 * c.p[2] - c.k[2]) / c.s[2] + 1;
    Tensor out(c.cout, OD, OH, OW);
    const int64_t N = out.sp();
    const int kh = c.k[1], kw = c.k[2], KV = c.k[0] * kh * kw;
    const int64_t HW = (int64_t)H * W;

    auto packB = [&](int64_t n0, int nlen, int k0, int kc, float* dst) {
        int iz[NT], iy[NT], ix[NT];
        const int npos = (nlen + NR - 1) / NR * NR;
        for (int n = 0; n < npos; ++n) {
            if (n < nlen) {
                int64_t q = n0 + n;
                int ow = (int)(q % OW);
                q /= OW;
                int oh = (int)(q % OH);
                int od = (int)(q / OH);
                iz[n] = od * c.s[0] - c.p[0];
                iy[n] = oh * c.s[1] - c.p[1];
                ix[n] = ow * c.s[2] - c.p[2];
            } else {
                iz[n] = -1000000;  // forces zero
                iy[n] = ix[n] = 0;
            }
        }
        for (int kk = 0; kk < kc; ++kk) {
            const int k = k0 + kk;
            const int ci = k / KV, t = k % KV;
            const int a = t / (kh * kw), bb = (t / kw) % kh, cc = t % kw;
            const float* src = chan[ci];
            float* d = dst + (size_t)kk * NR;
            for (int n = 0; n < npos; ++n) {
                const int z = iz[n] + a, y = iy[n] + bb, x = ix[n] + cc;
                float v = 0.f;
                if ((unsigned)z < (unsigned)D && (unsigned)y < (unsigned)H && (unsigned)x < (unsigned)W)
                    v = src[z * HW + (int64_t)y * W + x];
                d[(size_t)(n / NR) * kc * NR + (n % NR)] = v;
            }
        }
    };
    auto store = [&](int m0, int m1, int64_t n0, int nlen, const float* C, int ldc) {
        for (int m = m0; m < m1; ++m) {
            const float* src = C + (size_t)(m - m0) * ldc;
            float* dst = out.ch(m) + n0;
            const float b = c.bias[m];
            for (int n = 0; n < nlen; ++n) dst[n] = src[n] + b;
        }
    };
    gemm(c.A, N, packB, store);
    return out;
}

Tensor tconv_forward(const TConv& t, const Tensor& in) {
    Tensor out(t.cout, in.D * t.s[0], in.H * t.s[1], in.W * t.s[2]);
    const int64_t N = in.sp();
    int o = 0;
    for (int a = 0; a < t.s[0]; ++a)
        for (int b = 0; b < t.s[1]; ++b)
            for (int c = 0; c < t.s[2]; ++c, ++o) {
                auto packB = [&](int64_t n0, int nlen, int k0, int kc, float* dst) {
                    const int npos = (nlen + NR - 1) / NR * NR;
                    for (int kk = 0; kk < kc; ++kk) {
                        const float* src = in.ch(k0 + kk) + n0;
                        float* d = dst + (size_t)kk * NR;
                        for (int n = 0; n < npos; ++n) d[(size_t)(n / NR) * kc * NR + (n % NR)] = n < nlen ? src[n] : 0.f;
                    }
                };
                auto store = [&](int m0, int m1, int64_t n0, int nlen, const float* C, int ldc) {
                    for (int n = 0; n < nlen; ++n) {
                        int64_t q = n0 + n;
                        const int w = (int)(q % in.W);
                        q /= in.W;
                        const int h = (int)(q % in.H);
                        const int d = (int)(q / in.H);
                        const int64_t oidx = ((int64_t)(d * t.s[0] + a) * out.H + (h * t.s[1] + b)) * out.W + (w * t.s[2] + c);
                        for (int m = m0; m < m1; ++m) out.ch(m)[oidx] = C[(size_t)(m - m0) * ldc + n] + t.bias[m];
                    }
                };
                gemm(t.A[o], N, packB, store);
            }
    return out;
}

void instnorm_lrelu(Tensor& x, const std::vector<float>& g, const std::vector<float>& b) {
    const int64_t n = x.sp();
    parallel_for(x.C, [&](int64_t c0, int64_t c1, int) {
        for (int64_t c = c0; c < c1; ++c) {
            float* p = x.ch((int)c);
            double s = 0;
            for (int64_t i = 0; i < n; ++i) s += p[i];
            const double mean = s / (double)n;
            double v = 0;
            for (int64_t i = 0; i < n; ++i) {
                const double d = p[i] - mean;
                v += d * d;
            }
            const double var = v / (double)n;
            const float invstd = (float)(1.0 / std::sqrt(var + 1e-5));
            const float alpha = invstd * g[c];
            const float beta = b[c] - (float)mean * alpha;
            for (int64_t i = 0; i < n; ++i) {
                const float y = p[i] * alpha + beta;
                p[i] = y < 0.f ? y * 0.01f : y;
            }
        }
    });
}

}  // namespace

struct UNet::Impl {
    std::vector<std::vector<Conv>> enc, dec;
    std::vector<TConv> up;
    Conv seg;
};

UNet::UNet(const ModelWeights& w) : cfg_(w.cfg), impl_(std::make_unique<Impl>()) {
    const int S = cfg_.n_stages;
    impl_->enc.resize(S);
    for (int s = 0; s < S; ++s)
        for (int c = 0; c < cfg_.n_conv_enc[s]; ++c) {
            std::array<int, 3> st = c == 0 ? cfg_.strides[s] : std::array<int, 3>{1, 1, 1};
            impl_->enc[s].push_back(make_conv(w, "enc." + std::to_string(s) + "." + std::to_string(c), cfg_.kernels[s], st, true));
        }
    impl_->dec.resize(S - 1);
    for (int s = 0; s < S - 1; ++s) {
        impl_->up.push_back(make_tconv(w, "up." + std::to_string(s)));
        const auto& ker = cfg_.kernels[S - 2 - s];
        for (int c = 0; c < cfg_.n_conv_dec[s]; ++c)
            impl_->dec[s].push_back(make_conv(w, "dec." + std::to_string(s) + "." + std::to_string(c), ker, {1, 1, 1}, true));
    }
    impl_->seg = make_conv(w, "seg", {1, 1, 1}, {1, 1, 1}, false);
}

UNet::~UNet() = default;

Tensor UNet::forward(const Tensor& input, std::vector<Tensor>* stage_outputs) const {
    const int S = cfg_.n_stages;
    std::vector<Tensor> skips;
    skips.reserve(S);  // `cur` points into skips: no reallocation allowed
    const Tensor* cur = &input;
    for (int s = 0; s < S; ++s) {
        const auto& convs = impl_->enc[s];
        Tensor x = conv_forward(convs[0], {cur});
        instnorm_lrelu(x, convs[0].nw, convs[0].nb);
        for (size_t c = 1; c < convs.size(); ++c) {
            Tensor y = conv_forward(convs[c], {&x});
            instnorm_lrelu(y, convs[c].nw, convs[c].nb);
            x = std::move(y);
        }
        skips.push_back(std::move(x));
        cur = &skips.back();
        if (stage_outputs) stage_outputs->push_back(skips.back());
    }
    // decoder
    Tensor lres = std::move(skips.back());
    skips.pop_back();
    for (int s = 0; s < S - 1; ++s) {
        Tensor upx = tconv_forward(impl_->up[s], lres);
        lres = Tensor();
        Tensor skip = std::move(skips.back());
        skips.pop_back();
        Tensor x = conv_forward(impl_->dec[s][0], {&upx, &skip});
        instnorm_lrelu(x, impl_->dec[s][0].nw, impl_->dec[s][0].nb);
        upx = Tensor();
        skip = Tensor();
        for (size_t c = 1; c < impl_->dec[s].size(); ++c) {
            Tensor y = conv_forward(impl_->dec[s][c], {&x});
            instnorm_lrelu(y, impl_->dec[s][c].nw, impl_->dec[s][c].nb);
            x = std::move(y);
        }
        if (stage_outputs) stage_outputs->push_back(x);
        lres = std::move(x);
    }
    return conv_forward(impl_->seg, {&lres});
}

}  // namespace tsc
