// Minimal DICOM (Part 10) CT series reader. No external dependencies.
// Supports uncompressed transfer syntaxes: Implicit VR LE, Explicit VR LE
// (and files without the 128-byte preamble). Compressed pixel data is rejected.
#pragma once

#include <functional>
#include <string>
#include <vector>

#include "common.h"

namespace tsc {

struct DicomSlice {
    std::string series_uid;
    std::string modality;
    std::string series_description;
    std::string series_time, contrast_agent;  // (0008,0031), (0018,0010)
    int series_number = 0;                    // (0020,0011)
    bool localizer = false;                   // ImageType contains LOCALIZER (scout)
    int instance_number = 0;
    int number_of_frames = 1;
    double slice_thickness = 0;        // (0018,0050), 0 if absent
    int rows = 0, cols = 0;
    double pixel_spacing[2] = {1, 1};  // (row spacing, column spacing)
    double ipp[3] = {0, 0, 0};         // ImagePositionPatient (LPS)
    double iop[6] = {1, 0, 0, 0, 1, 0};
    bool has_ipp = false, has_iop = false;
    double slope = 1.0, intercept = 0.0;
    int bits_allocated = 16, bits_stored = 16, pixel_representation = 0, samples_per_pixel = 1;
    // raw pixel data as stored (rows*cols values of bits_allocated/8 bytes, little endian, row-major (r, c));
    // decoded to HU only when the volume is built (half the memory of float pixels for 16-bit CT)
    std::vector<uint8_t> raw;
    // rescaled (HU) pixel i, as float((double)raw * slope + intercept)
    void decode(float* dst) const;
};

// Parses one DICOM file from memory. Returns false (with err) if unusable.
bool parse_dicom(const uint8_t* data, size_t len, DicomSlice& out, std::string& err);

struct DicomSeriesInfo {
    std::string series_uid, description, modality, series_time, contrast_agent;
    int series_number = 0;
    int num_slices = 0;      // image slices of the main image size (what build_volume would use)
    int num_other = 0;       // localizers / other image sizes in the same series (ignored)
    int rows = 0, cols = 0;
    double pixel_spacing[2] = {0, 0};
    double slice_spacing = 0;  // median distance between slice positions along the normal (mm), 0 if unknown
    double extent_mm = 0;      // first to last slice position (mm)
    std::string problem;       // why the series cannot be built as a volume ("" = fine)
};

// Groups slices by SeriesInstanceUID, keeps the largest CT series (or the
// series given by uid), sorts along the slice normal and builds a volume in
// closest-canonical RAS orientation (like nibabel.as_closest_canonical of the
// dicom2nifti output). Pixel values are HU as float.
// explicit_uid: `uid` names the series (also an empty UID); otherwise the default series is used.
// before_alloc is called once all checks passed, right before the volume is allocated (lets a caller free
// its previous volume only when the new one will be built).
Volume<float> build_volume(const std::vector<DicomSlice>& slices, const std::string& uid, std::string& log,
                           bool explicit_uid = false, const std::function<void()>& before_alloc = {});

// One entry per SeriesInstanceUID, largest CT series first (the default choice of build_volume).
std::vector<DicomSeriesInfo> list_series(const std::vector<DicomSlice>& slices);

// NIfTI voxel data (x fastest, little endian, any of the NIfTI-1 scalar types 2, 4, 8, 16, 64, 256, 512, 768) ->
// float volume in closest-canonical RAS orientation, written directly in canonical order (no float copy of the
// original layout). value = float(raw * slope + inter) evaluated in double, the same as the browser's Nifti.read.
// Same result as building the float volume in the file's layout and calling as_closest_canonical, with about half
// of the peak memory for int16 data.
Volume<float> volume_from_nifti_raw(const uint8_t* raw, int nifti_datatype, double slope, double inter, const Shape3& shape,
                                    const Affine& affine, const std::function<void()>& before_alloc = {});

// Reorients a volume with arbitrary (axis aligned or oblique) affine to the
// closest canonical RAS orientation (nibabel io_orientation + as_reoriented).
template <class T>
Volume<T> as_closest_canonical(const Volume<T>& v);

}  // namespace tsc
