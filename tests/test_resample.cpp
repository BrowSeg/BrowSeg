// Verifies tsc::scipy_zoom against scipy outputs.
// usage: test_resample <in.npy> <ref.npy> <order> [truncate_int32]
//   in.npy : float64/int array, ref.npy : scipy.ndimage.zoom result (same shape as output)
#include <chrono>
#include <cstdio>

#include "tsc/npy.h"
#include "tsc/resample.h"

using namespace tsc;

int run(int argc, char** argv) {
    if (argc < 4) {
        std::printf("usage: test_resample in.npy ref.npy order [trunc]\n");
        return 2;
    }
    NpyArray in = npy_load(argv[1]);
    NpyArray ref = npy_load(argv[2]);
    int order = std::atoi(argv[3]);
    bool trunc = argc > 4 && std::atoi(argv[4]) != 0;
    bool grid = argc > 5 && std::atoi(argv[5]) != 0;
    Shape3 s{in.shape[0], in.shape[1], in.shape[2]};
    Shape3 os{ref.shape[0], ref.shape[1], ref.shape[2]};
    auto d = in.to_double();
    auto t0 = std::chrono::steady_clock::now();
    auto out = grid ? scipy_zoom_grid(d.data(), s, os, order) : scipy_zoom(d.data(), s, os, order);
    double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    int64_t n = numel(os), ndiff = 0;
    double maxabs = 0;
    for (int64_t i = 0; i < n; ++i) {
        double v = out[i];
        if (trunc) v = (double)(int32_t)v;  // numpy astype(int32) truncates toward zero
        double r = ref.get(i);
        double e = std::fabs(v - r);
        if (e > maxabs) maxabs = e;
        if (v != r) ++ndiff;
    }
    std::printf("zoom order %d: %lld x %lld x %lld -> %lld x %lld x %lld  %.1f ms  mismatches %lld / %lld  max|diff| %.3g\n",
                order, (long long)s[0], (long long)s[1], (long long)s[2], (long long)os[0], (long long)os[1],
                (long long)os[2], ms, (long long)ndiff, (long long)n, maxabs);
    return ndiff == 0 ? 0 : 1;
}

int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& e) {
        std::printf("exception: %s\n", e.what());
        return 3;
    }
}
