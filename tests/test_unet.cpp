// Kernel-level verification of the C++ UNet against PyTorch activations
// (tools/make_layer_ref.py).  usage: test_unet <model.tsw> <layer_ref_dir>
#include <chrono>
#include <cstdio>

#include "tsc/npy.h"
#include "tsc/unet.h"

using namespace tsc;

static void compare(const char* name, const Tensor& t, const NpyArray& r) {
    int64_t n = t.data.size();
    if (r.count() != n) {
        std::printf("%-8s size mismatch %lld vs %lld\n", name, (long long)n, (long long)r.count());
        return;
    }
    const float* rp = r.as<float>();
    double maxabs = 0, maxref = 0, sum2 = 0, ref2 = 0;
    for (int64_t i = 0; i < n; ++i) {
        double d = std::fabs((double)t.data[i] - rp[i]);
        maxabs = std::max(maxabs, d);
        maxref = std::max(maxref, (double)std::fabs(rp[i]));
        sum2 += d * d;
        ref2 += (double)rp[i] * rp[i];
    }
    std::printf("%-8s C=%3d %3dx%3dx%3d  max|diff| %.3e  (max|ref| %.2f)  rel-rms %.3e\n", name, t.C, t.D, t.H, t.W,
                maxabs, maxref, std::sqrt(sum2 / (ref2 + 1e-30)));
}

int main(int argc, char** argv) {
    try {
        if (argc < 3) {
            std::printf("usage: test_unet model.tsw layer_dir\n");
            return 2;
        }
        std::string dir = argv[2];
        auto t0 = std::chrono::steady_clock::now();
        ModelWeights w = load_weights_file(argv[1]);
        UNet net(w);
        auto t1 = std::chrono::steady_clock::now();
        NpyArray in = npy_load(dir + "/patch_in.npy");
        Tensor x(1, (int)in.shape[2], (int)in.shape[3], (int)in.shape[4]);
        std::memcpy(x.data.data(), in.bytes.data(), x.data.size() * 4);
        std::vector<Tensor> stages;
        net.forward(x, nullptr);  // warm-up (thread pool, buffers)
        auto t2 = std::chrono::steady_clock::now();
        Tensor y = net.forward(x, &stages);
        auto t3 = std::chrono::steady_clock::now();
        std::printf("load %.0f ms, forward %.0f ms (threads %d)\n",
                    std::chrono::duration<double, std::milli>(t1 - t0).count(),
                    std::chrono::duration<double, std::milli>(t3 - t2).count(), num_threads());
        int S = w.cfg.n_stages;
        for (int s = 0; s < S; ++s) {
            std::string nm = "enc" + std::to_string(s);
            compare(nm.c_str(), stages[s], npy_load(dir + "/" + nm + ".npy"));
        }
        for (int s = 0; s < S - 1; ++s) {
            std::string nm = "dec" + std::to_string(s);
            compare(nm.c_str(), stages[S + s], npy_load(dir + "/" + nm + ".npy"));
        }
        NpyArray ref = npy_load(dir + "/logits.npy");
        compare("logits", y, ref);
        // argmax agreement
        int64_t sp = y.sp(), dis = 0;
        const float* rp = ref.as<float>();
        for (int64_t i = 0; i < sp; ++i) {
            int a = 0, b = 0;
            for (int c = 1; c < y.C; ++c) {
                if (y.ch(c)[i] > y.ch(a)[i]) a = c;
                if (rp[c * sp + i] > rp[b * sp + i]) b = c;
            }
            dis += a != b;
        }
        std::printf("argmax disagreement: %lld / %lld voxels\n", (long long)dis, (long long)sp);
        return 0;
    } catch (const std::exception& e) {
        std::printf("exception: %s\n", e.what());
        return 3;
    }
}
