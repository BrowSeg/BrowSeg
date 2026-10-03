// nnU-Net v2 PlainConvUNet inference (fp32), built generically from a .tsw
// model description: Conv3d -> InstanceNorm3d(affine, eps 1e-5) -> LeakyReLU(0.01)
// stages, strided-conv downsampling, ConvTranspose3d upsampling, 1x1x1 head.
#pragma once

#include <memory>

#include "weights.h"

namespace tsc {

struct Tensor {
    int C = 0, D = 0, H = 0, W = 0;
    std::vector<float> data;
    Tensor() = default;
    Tensor(int c, int d, int h, int w) : C(c), D(d), H(h), W(w), data((size_t)c * d * h * w) {}
    int64_t sp() const { return (int64_t)D * H * W; }
    float* ch(int c) { return data.data() + (size_t)c * sp(); }
    const float* ch(int c) const { return data.data() + (size_t)c * sp(); }
};

class UNet {
public:
    explicit UNet(const ModelWeights& w);
    ~UNet();
    const ModelConfig& config() const { return cfg_; }
    // input: 1 x D x H x W (D,H,W = patch size). Returns num_classes x D x H x W logits.
    Tensor forward(const Tensor& input, std::vector<Tensor>* stage_outputs = nullptr) const;

    struct Impl;

private:
    ModelConfig cfg_;
    std::unique_ptr<Impl> impl_;
};

}  // namespace tsc
