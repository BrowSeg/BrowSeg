// Loader for .tsw files written by tools/export_weights.py.
#pragma once

#include <map>
#include <string>
#include <vector>

#include "common.h"

namespace tsc {

struct ModelConfig {
    std::string name;
    int task_id = 0;
    int patch[3] = {0, 0, 0};
    double spacing[3] = {0, 0, 0};
    double ct_mean = 0, ct_std = 1, ct_p005 = 0, ct_p995 = 0;
    int n_stages = 0;
    std::vector<int> features;
    std::vector<std::array<int, 3>> strides, kernels;
    std::vector<int> n_conv_enc, n_conv_dec;
    int num_classes = 0;
    std::vector<std::string> labels;  // index -> name
    int label_index(const std::string& n) const {
        for (size_t i = 0; i < labels.size(); ++i)
            if (labels[i] == n) return (int)i;
        return -1;
    }
};

struct TensorF {
    std::vector<int64_t> shape;
    std::vector<float> data;
    int64_t numel() const {
        int64_t n = 1;
        for (auto s : shape) n *= s;
        return n;
    }
};

struct ModelWeights {
    ModelConfig cfg;
    std::map<std::string, TensorF> tensors;
    const TensorF& get(const std::string& n) const {
        auto it = tensors.find(n);
        if (it == tensors.end()) throw std::runtime_error("missing tensor " + n);
        return it->second;
    }
};

// Parses a .tsw file from memory (f32 or f16 tensors; f16 is widened to f32).
// config_only: parse the header only (no tensors; `data` may then hold just the first 12 + header_len bytes)
ModelWeights load_weights(const uint8_t* data, size_t len, bool config_only = false);
ModelWeights load_weights_file(const std::string& path);

}  // namespace tsc
