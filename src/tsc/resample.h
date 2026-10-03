// Bit-faithful re-implementation of scipy.ndimage.zoom(input, zoom, order,
// mode='nearest', grid_mode=False, prefilter=True) for 3-D float64 input,
// following scipy 1.17 ni_splines.c / ni_interpolation.c operation order.
#pragma once

#include "common.h"

namespace tsc {

// Output shape as scipy computes it: round(in_shape * zoom) (round-half-even).
Shape3 zoom_output_shape(const Shape3& in_shape, const std::array<double, 3>& zoom);

// in: C-order double array of shape in_shape. order must be 0 or 3.
// Returns double array of shape out_shape.
std::vector<double> scipy_zoom(const double* in, const Shape3& in_shape, const Shape3& out_shape, int order);

// Same for other input types (values converted to double exactly, as numpy would).
std::vector<double> scipy_zoom(const float* in, const Shape3& in_shape, const Shape3& out_shape, int order);
std::vector<double> scipy_zoom(const int32_t* in, const Shape3& in_shape, const Shape3& out_shape, int order);
std::vector<double> scipy_zoom(const uint8_t* in, const Shape3& in_shape, const Shape3& out_shape, int order);

// scipy.ndimage.zoom(..., grid_mode=True) as used by skimage.transform.resize (nnU-Net's
// internal resampling). order 0, 1 or 3; output shape given explicitly.
std::vector<double> scipy_zoom_grid(const double* in, const Shape3& in_shape, const Shape3& out_shape, int order);

// scipy.ndimage.zoom(..., grid_mode=True, mode='nearest') of a 2-D C-order array (h x w -> oh x ow), as
// skimage.transform.resize does for one slice in nnU-Net's separate-z resampling. order 1 or 3.
// Runs on the calling thread (callers parallelise over slices).
std::vector<double> scipy_zoom_grid_2d(const double* in, int64_t h, int64_t w, int64_t oh, int64_t ow, int order);

// nnU-Net resample_data_or_seg(..., do_separate_z=True, order_z=0) for one channel (not a segmentation):
// every slice along `axis` is resized in 2-D (skimage resize, order `order`, mode edge, clipped to that
// slice's value range), then the result is resampled along `axis` with map_coordinates(order 0, 'nearest').
std::vector<double> nnunet_resample_separate_z(const double* in, const Shape3& s, const Shape3& ns, int axis, int order);

// nnU-Net determine_do_sep_z_and_axis(force_separate_z=None, threshold 3): index of the low-resolution
// axis if the resampling must be done separately along it, else -1.
int nnunet_separate_z_axis(const double* current_spacing, const double* new_spacing);

// order-0 zoom of a label map, returned directly as uint8 (identical values).
std::vector<uint8_t> scipy_zoom_nearest_u8(const uint8_t* in, const Shape3& in_shape, const Shape3& out_shape);

}  // namespace tsc
