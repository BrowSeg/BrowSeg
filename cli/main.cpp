// tsc_liver: DICOM folder -> TotalSegmentator task (total / roi_subset / liver_segments) + meshes, no Python.
// usage: tsc_liver <dicom_dir> <weights_dir> <out_prefix> [--task total|liver_segments|liver_vessels] [--roi liver|-] [--threads N]
// writes <out_prefix>_labels.nii (uint8, RAS), <out_prefix>.obj (one object per structure), <out_prefix>.stl
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>

#include "tsc/dicom.h"
#include "tsc/mesh.h"
#include "tsc/pipeline.h"

using namespace tsc;
namespace fs = std::filesystem;

static bool write_nifti_u8(const Volume<uint8_t>& v, const std::string& path) {
    char h[352] = {0};
    auto i32 = [&](int off, int32_t x) { std::memcpy(h + off, &x, 4); };
    auto i16 = [&](int off, int16_t x) { std::memcpy(h + off, &x, 2); };
    auto f32w = [&](int off, float x) { std::memcpy(h + off, &x, 4); };
    i32(0, 348);
    i16(40, 3);
    for (int d = 0; d < 3; ++d) i16(42 + 2 * d, (int16_t)v.shape[d]);
    i16(48, 1); i16(50, 1); i16(52, 1); i16(54, 1);
    i16(70, 2);   // DT_UINT8
    i16(72, 8);   // bitpix
    auto z = zooms_from_affine(v.affine);
    f32w(76, 1.0f);
    for (int d = 0; d < 3; ++d) f32w(80 + 4 * d, (float)z[d]);
    f32w(108, 352.0f);  // vox_offset
    f32w(112, 1.0f);    // scl_slope
    h[123] = 10;        // xyzt_units: mm + s
    i16(252, 0);        // qform_code
    i16(254, 1);        // sform_code: scanner
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 4; ++c) f32w(280 + 16 * r + 4 * c, (float)v.affine[r * 4 + c]);
    std::memcpy(h + 344, "n+1\0", 4);
    std::ofstream f(path, std::ios::binary);
    if (!f) return false;
    f.write(h, 352);
    // NIfTI is Fortran order (i fastest); our arrays are C order (k fastest)
    std::vector<uint8_t> buf((size_t)v.size());
    for (int64_t i = 0; i < v.shape[0]; ++i)
        for (int64_t j = 0; j < v.shape[1]; ++j)
            for (int64_t k = 0; k < v.shape[2]; ++k) buf[(size_t)((k * v.shape[1] + j) * v.shape[0] + i)] = v(i, j, k);
    f.write((const char*)buf.data(), (std::streamsize)buf.size());
    return true;
}

static std::string find_weights(const std::string& dir, int tid) {
    for (auto& e : fs::directory_iterator(dir)) {
        std::string n = e.path().filename().string(), suf = "_" + std::to_string(tid) + ".tsw";
        if (n.size() > suf.size() && n.compare(n.size() - suf.size(), suf.size(), suf) == 0) return e.path().string();
    }
    throw std::runtime_error("no weights for model " + std::to_string(tid) + " in " + dir);
}

int main(int argc, char** argv) {
    if (argc < 4) {
        std::printf("usage: tsc_liver <dicom_dir> <weights_dir> <out_prefix> [--task total|liver_segments|liver_vessels] [--roi liver[,..]|-] [--threads N]\n"
                    "  default: --task total --roi liver (TotalSegmentator roi_subset)\n");
        return 2;
    }
    try {
        std::string task = "total", roi = "liver";
        for (int i = 4; i + 1 < argc; ++i) {
            std::string a = argv[i];
            if (a == "--threads") set_num_threads(std::atoi(argv[i + 1]));
            if (a == "--roi") roi = argv[i + 1];
            if (a == "--resampling_order") set_resampling_order(std::atoi(argv[i + 1]));
            if (a == "--task") {
                task = argv[i + 1];
                if (task != "total") roi = "-";  // roi_subset only exists for total
            }
        }
        std::vector<std::string> rois;
        if (roi != "-") {
            std::stringstream ss(roi);
            std::string t;
            while (std::getline(ss, t, ',')) rois.push_back(t);
        }
        auto t0 = std::chrono::steady_clock::now();
        auto secs = [&] { return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(); };
        std::vector<DicomSlice> slices;
        for (auto& e : fs::recursive_directory_iterator(argv[1])) {
            if (!e.is_regular_file()) continue;
            std::ifstream f(e.path(), std::ios::binary);
            std::vector<uint8_t> buf((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
            DicomSlice s;
            std::string err;
            if (parse_dicom(buf.data(), buf.size(), s, err)) slices.push_back(std::move(s));
        }
        std::string log;
        Volume<float> ct = build_volume(slices, "", log);
        slices.clear();
        std::printf("[%.1fs] %s", secs(), log.c_str());

        const std::string wd = argv[2];
        ClassMaps cm = load_classmaps_file(wd + "/classmaps.txt");
        // load only the models the task needs
        const std::vector<int> need = task_model_ids(task, rois, cm);
        std::map<int, ModelConfig> cfgs;
        std::map<int, std::unique_ptr<UNet>> nets;
        std::map<int, const ModelConfig*> cfgp;
        std::map<int, const UNet*> netp;
        for (int tid : need) {
            ModelWeights w = load_weights_file(find_weights(wd, tid));
            cfgs[tid] = w.cfg;
            nets[tid] = std::make_unique<UNet>(w);
        }
        for (auto& kv : cfgs) cfgp[kv.first] = &kv.second;
        for (auto& kv : nets) netp[kv.first] = kv.second.get();
        std::printf("[%.1fs] task %s, %zu model(s) loaded (%d threads)\n", secs(), task.c_str(), need.size(), num_threads());
        auto prog = [&](const std::string& s, double f) {
            std::printf("\r[%.1fs] %-18s %3.0f%%", secs(), s.c_str(), f * 100);
            std::fflush(stdout);
            if (f >= 1.0) std::printf("\n");
        };
        std::unique_ptr<Runner> runner = make_runner(ct, task, rois, cfgp, cm, prog);
        Volume<uint8_t> seg = run_runner(*runner, netp, prog);
        const std::vector<std::string> labels = runner->labels();
        std::printf("\n%s", runner->timings().c_str());
        const std::string out = argv[3];
        if (!write_nifti_u8(seg, out + "_labels.nii")) throw std::runtime_error("cannot write " + out + "_labels.nii");
        std::vector<int64_t> counts(256, 0);
        for (auto v : seg.data) counts[v]++;
        auto z = zooms_from_affine(seg.affine);
        Mesh all;
        FILE* obj = std::fopen((out + ".obj").c_str(), "w");
        if (!obj) throw std::runtime_error("cannot write " + out + ".obj");
        std::fprintf(obj, "# tsc mesh, RAS mm, one object per structure\n");
        size_t vbase = 1;
        int nlab = 0;
        for (int l = 1; l < 256; ++l) {
            if (!counts[l]) continue;
            ++nlab;
            const std::string name = l < (int)labels.size() ? labels[l] : std::to_string(l);
            Mesh m = mask_to_mesh(seg, l, mesh_options_for(name, false));
            std::printf("  %-28s %9.1f ml  %7zu triangles\n", name.c_str(), counts[l] * z[0] * z[1] * z[2] / 1000.0, m.num_triangles());
            std::fprintf(obj, "o %s\n", name.c_str());
            for (size_t v = 0; v < m.num_vertices(); ++v)
                std::fprintf(obj, "v %.3f %.3f %.3f\n", m.vertices[v * 3], m.vertices[v * 3 + 1], m.vertices[v * 3 + 2]);
            for (size_t t = 0; t < m.indices.size(); t += 3)
                std::fprintf(obj, "f %zu %zu %zu\n", m.indices[t] + vbase, m.indices[t + 1] + vbase, m.indices[t + 2] + vbase);
            const uint32_t off = (uint32_t)all.num_vertices();
            all.vertices.insert(all.vertices.end(), m.vertices.begin(), m.vertices.end());
            for (auto i : m.indices) all.indices.push_back(i + off);
            vbase += m.num_vertices();
        }
        std::fclose(obj);
        write_stl(all, out + ".stl");
        std::printf("[%.1fs] %d structure(s) -> %s_labels.nii, %s.obj, %s.stl\n", secs(), nlab, out.c_str(), out.c_str(), out.c_str());
        return 0;
    } catch (const std::exception& e) {
        std::printf("error: %s\n", e.what());
        return 1;
    }
}
