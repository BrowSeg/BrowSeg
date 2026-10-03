// Common types for the TotalSegmentator C++ port.
//
// Array convention: every 3-D array is stored like a C-contiguous numpy array,
// i.e. index(i, j, k) = (i * shape[1] + j) * shape[2] + k (last axis fastest).
// This keeps summation orders identical to the Python reference.
#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace tsc {

using Shape3 = std::array<int64_t, 3>;
using Affine = std::array<double, 16>;  // row-major 4x4, voxel index -> world (RAS mm)

inline int64_t numel(const Shape3& s) { return s[0] * s[1] * s[2]; }

// element count -> size_t, refusing counts that do not fit (wasm32: size_t is 32 bit, silent wrap-around
// would give a too small buffer)
template <class T = uint8_t>
inline size_t checked_count(int64_t n) {
    if (n < 0 || (uint64_t)n > (uint64_t)(SIZE_MAX / sizeof(T))) throw std::length_error("array too large: " + std::to_string(n) + " elements");
    return (size_t)n;
}

inline Affine identity_affine() {
    Affine a{};
    a[0] = a[5] = a[10] = a[15] = 1.0;
    return a;
}

template <class T>
struct Volume {
    Shape3 shape{0, 0, 0};
    std::vector<T> data;
    Affine affine = identity_affine();

    Volume() = default;
    Volume(const Shape3& s, const Affine& a = identity_affine()) : shape(s), data(checked_count<T>(numel(s))), affine(a) {}

    int64_t size() const { return numel(shape); }
    int64_t idx(int64_t i, int64_t j, int64_t k) const { return (i * shape[1] + j) * shape[2] + k; }
    T& operator()(int64_t i, int64_t j, int64_t k) { return data[(size_t)idx(i, j, k)]; }
    const T& operator()(int64_t i, int64_t j, int64_t k) const { return data[(size_t)idx(i, j, k)]; }
};

// nibabel stores zooms in the NIfTI header as float32; TS/nnU-Net read them back
// from there, so every spacing used in the pipeline is float32-rounded.
inline double f32(double v) { return (double)(float)v; }

inline std::array<double, 3> zooms_from_affine(const Affine& a) {
    std::array<double, 3> z{};
    for (int c = 0; c < 3; ++c) {
        double s = 0;
        for (int r = 0; r < 3; ++r) s += a[r * 4 + c] * a[r * 4 + c];
        z[c] = f32(std::sqrt(s));
    }
    return z;
}

// Python's round() (round-half-to-even), as used by scipy/nnU-Net for shapes.
inline int64_t py_round(double v) { return (int64_t)std::nearbyint(v); }

// ---------------------------------------------------------------------------
// IEEE half precision (nnU-Net accumulates sliding-window logits in fp16)
// ---------------------------------------------------------------------------
inline uint16_t float_to_half(float f) {
    uint32_t x;
    std::memcpy(&x, &f, 4);
    uint32_t sign = (x >> 16) & 0x8000u;
    uint32_t mant = x & 0x7fffffu;
    int32_t exp = (int32_t)((x >> 23) & 0xff);
    if (exp == 0xff) return (uint16_t)(sign | 0x7c00u | (mant ? 0x200u : 0));  // inf / nan
    int32_t e = exp - 127 + 15;
    if (e >= 0x1f) return (uint16_t)(sign | 0x7c00u);  // overflow -> inf
    if (e <= 0) {                                     // subnormal / zero
        if (e < -10) return (uint16_t)sign;
        mant |= 0x800000u;
        uint32_t shift = (uint32_t)(14 - e);
        uint32_t h = mant >> shift;
        uint32_t rem = mant & ((1u << shift) - 1);
        uint32_t half = 1u << (shift - 1);
        if (rem > half || (rem == half && (h & 1))) h++;
        return (uint16_t)(sign | h);
    }
    uint32_t h = ((uint32_t)e << 10) | (mant >> 13);
    uint32_t rem = mant & 0x1fffu;
    if (rem > 0x1000u || (rem == 0x1000u && (h & 1))) h++;  // may carry into exponent: correct
    return (uint16_t)(sign | h);
}

inline float half_to_float(uint16_t h) {
    uint32_t sign = (uint32_t)(h & 0x8000u) << 16;
    uint32_t exp = (h >> 10) & 0x1f;
    uint32_t mant = h & 0x3ffu;
    uint32_t x;
    if (exp == 0) {
        if (mant == 0) {
            x = sign;
        } else {  // subnormal
            int e = -1;
            do { mant <<= 1; ++e; } while (!(mant & 0x400u));
            x = sign | ((uint32_t)(127 - 15 - e) << 23) | ((mant & 0x3ffu) << 13);
        }
    } else if (exp == 0x1f) {
        x = sign | 0x7f800000u | (mant << 13);
    } else {
        x = sign | ((exp + 127 - 15) << 23) | (mant << 13);
    }
    float f;
    std::memcpy(&f, &x, 4);
    return f;
}

// Table version of half_to_float (identical results, much faster in hot loops).
inline const float* half_lut() {
    static const std::vector<float> lut = [] {
        std::vector<float> t(65536);
        for (uint32_t i = 0; i < 65536; ++i) t[i] = half_to_float((uint16_t)i);
        return t;
    }();
    return lut.data();
}

// Parallel bounding box of voxels where pred(value) holds; returns false if none.
template <class T, class Pred>
bool bbox_where(const T* data, const Shape3& s, Pred pred, int64_t lo[3], int64_t hi[3]);

// ---------------------------------------------------------------------------
// Threading: a small persistent pool (std::thread works natively and under
// Emscripten with -pthread).
// ---------------------------------------------------------------------------
int num_threads();
void set_num_threads(int n);
// Calls fn(begin, end, thread_id) on contiguous chunks of [0, n).
void parallel_for(int64_t n, const std::function<void(int64_t, int64_t, int)>& fn, int64_t min_chunk = 1);

// Progress / log callback (stage name, fraction 0..1). Optional.
using ProgressFn = std::function<void(const std::string&, double)>;

template <class T, class Pred>
bool bbox_where(const T* data, const Shape3& s, Pred pred, int64_t lo[3], int64_t hi[3]) {
    std::vector<std::array<int64_t, 6>> part((size_t)s[0], {s[0], s[1], s[2], -1, -1, -1});
    parallel_for(s[0], [&](int64_t b, int64_t e, int) {
        for (int64_t i = b; i < e; ++i) {
            auto& r = part[(size_t)i];
            for (int64_t j = 0; j < s[1]; ++j) {
                const T* row = data + (i * s[1] + j) * s[2];
                int64_t kmin = -1, kmax = -1;
                for (int64_t k = 0; k < s[2]; ++k)
                    if (pred(row[k])) {
                        if (kmin < 0) kmin = k;
                        kmax = k;
                    }
                if (kmin < 0) continue;
                r[0] = std::min(r[0], i); r[3] = std::max(r[3], i);
                r[1] = std::min(r[1], j); r[4] = std::max(r[4], j);
                r[2] = std::min(r[2], kmin); r[5] = std::max(r[5], kmax);
            }
        }
    });
    for (int d = 0; d < 3; ++d) { lo[d] = s[d]; hi[d] = -1; }
    for (auto& r : part)
        for (int d = 0; d < 3; ++d) { lo[d] = std::min(lo[d], r[d]); hi[d] = std::max(hi[d], r[3 + d]); }
    return hi[0] >= 0;
}

}  // namespace tsc
