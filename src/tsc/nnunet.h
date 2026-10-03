// nnU-Net v2 predictor (DefaultPreprocessor + CTNormalization + sliding
// window with Gaussian weighting), reproducing nnUNetPredictor on CPU:
//   * input read like NibabelIOWithReorient (RAS array transposed to z,y,x)
//   * crop to nonzero bbox, CT clip + z-score in float32
//   * pad to patch size, tile steps as compute_steps_for_sliding_window
//   * logits accumulated in fp16 with an fp16 Gaussian importance map
//   * argmax (first max), un-crop, transpose back
#pragma once

#include "unet.h"

namespace tsc {

struct PredictOptions {
    double step_size = 0.5;
    ProgressFn progress;
    std::string stage_name = "predict";
};

struct PredictDebug {
    bool keep = false;
    std::vector<float> pre;  // normalised, cropped network input (z,y,x)
    Shape3 pre_shape{0, 0, 0};
    std::vector<uint16_t> logits;  // fp16 logits after sliding window (C, z,y,x), cropped region
    int bbox[3][2] = {{0, 0}, {0, 0}, {0, 0}};
    int num_tiles = 0;
};

// The predictor split into steps so that the network can run elsewhere
// (e.g. WebGPU): tile_input() -> run network -> accumulate() for every tile,
// then finish(). Holds the padded input and fp16 accumulators.
class SlidingWindow {
public:
    SlidingWindow(const ModelConfig& cfg, const Volume<int32_t>& img, double step_size, PredictDebug* dbg = nullptr);
    const ModelConfig& config() const { return cfg_; }
    int num_tiles() const { return (int)tiles_.size(); }
    int64_t patch_numel() const;
    void tile_input(int t, float* dst) const;    // writes P0*P1*P2 floats
    void accumulate(int t, const float* logits);  // num_classes x P0*P1*P2 fp32 network output
    // For GPU-side accumulation: only the fp16 count map is updated here, the
    // fp16 logits (num_classes x padded volume) are then written via logits_data().
    void accumulate_counts(int t);
    uint16_t* logits_data() { return logits_.data(); }
    const float* gaussian() const { return gauss_f_.data(); }
    const std::array<int64_t, 3>& tile_origin(int t) const { return tiles_[(size_t)t]; }
    const Shape3& padded_shape() const { return ps_; }
    Volume<uint8_t> finish();                     // argmax segmentation (RAS x,y,z)

private:
    ModelConfig cfg_;
    Shape3 img_shape_;
    Affine img_affine_;
    PredictDebug* dbg_;
    int64_t lo_[3] = {0, 0, 0}, pad_lo_[3] = {0, 0, 0};
    Shape3 cs_{0, 0, 0}, ns_{0, 0, 0}, ps_{0, 0, 0};  // cropped, network (resampled), padded grids
    double spacing_t_[3] = {0, 0, 0};                  // input spacing in nnU-Net (z, y, x) order
    std::vector<float> data_, gauss_f_;
    std::vector<std::array<int64_t, 3>> tiles_;
    std::vector<uint16_t> logits_, npred_;
};

// img: int32 volume in RAS voxel order (x,y,z), i.e. what TS writes to
// s01_0000.nii.gz. Its spacing must already equal the model spacing.
Volume<uint8_t> nnunet_predict(const UNet& net, const Volume<int32_t>& img, const PredictOptions& opt,
                               PredictDebug* dbg = nullptr);

}  // namespace tsc
