// Stage-by-stage comparison of a C++ TotalSegmentator task with the Python reference
// (tools/make_reference.py + tools/ref_to_npy.py).
// usage: test_task <task> <roi|-> <dicom_dir> <weights_dir> <ref_dir> [final_npy_name]
//   e.g. test_task total liver  <dicom> weights ref/case1_cpu final_liver_can.npy
//        test_task total -      <dicom> weights ref/case1_total_cpu
//        test_task liver_segments - <dicom> weights ref/case1_segments_cpu
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <memory>
#include <sstream>

#include "tsc/dicom.h"
#include "tsc/mesh.h"
#include "tsc/npy.h"
#include "tsc/pipeline.h"

using namespace tsc;
namespace fs = std::filesystem;

static bool g_all_exact = true;

template <class T>
static void cmp_exact(const std::string& name, const T* a, int64_t n, const std::string& path, bool must_match = true) {
    if (!fs::exists(path)) {
        std::printf("  %-22s (no reference file)\n", name.c_str());
        return;
    }
    NpyArray r = npy_load(path);
    if (r.count() != n) {
        std::printf("  %-22s SIZE MISMATCH %lld vs %lld\n", name.c_str(), (long long)n, (long long)r.count());
        g_all_exact = false;
        return;
    }
    int64_t diff = 0;
    for (int64_t i = 0; i < n; ++i) diff += (double)a[i] != r.get(i);
    std::printf("  %-22s %s  mismatches %lld / %lld (%.5f%%)\n", name.c_str(), diff == 0 ? "EXACT" : "     ", (long long)diff,
                (long long)n, 100.0 * diff / n);
    if (diff && must_match) g_all_exact = false;
}

static void cmp_half(const std::string& name, const std::vector<uint16_t>& a, const std::string& path) {
    if (!fs::exists(path)) return;
    NpyArray r = npy_load(path);
    if (r.count() != (int64_t)a.size()) {
        std::printf("  %-22s SIZE MISMATCH\n", name.c_str());
        return;
    }
    const uint16_t* rp = r.as<uint16_t>();
    int64_t diff = 0;
    double maxabs = 0;
    for (size_t i = 0; i < a.size(); ++i)
        if (a[i] != rp[i]) {
            ++diff;
            maxabs = std::max(maxabs, (double)std::fabs(half_to_float(a[i]) - half_to_float(rp[i])));
        }
    std::printf("  %-22s fp16 mismatches %lld / %lld (%.4f%%)  max|diff| %.4g  (summation order; informational)\n", name.c_str(),
                (long long)diff, (long long)a.size(), 100.0 * diff / a.size(), maxabs);
}

static std::string find_weights(const std::string& dir, int tid) {
    for (auto& e : fs::directory_iterator(dir)) {
        std::string n = e.path().filename().string();
        std::string suf = "_" + std::to_string(tid) + ".tsw";
        if (n.size() > suf.size() && n.compare(n.size() - suf.size(), suf.size(), suf) == 0) return e.path().string();
    }
    throw std::runtime_error("no weights for task id " + std::to_string(tid) + " in " + dir);
}

int main(int argc, char** argv) {
    try {
        if (argc < 6) {
            std::printf("usage: test_task <task> <roi|-> <dicom_dir> <weights_dir> <ref_dir> [final_npy]\n");
            return 2;
        }
        const std::string task = argv[1], roi = argv[2], wd = argv[4], ref = argv[5];
        const std::string final_name = argc > 6 ? argv[6] : "final_" + task + "_can.npy";
        {   // references made with TS <= 2.15 (no resampling_order.txt) used spline order 3
            std::ifstream ro(ref + "/resampling_order.txt");
            int order = 3;
            if (ro) ro >> order;
            set_resampling_order(order);
            std::printf("input resampling order %d\n", order);
        }
        std::vector<std::string> rois;
        if (roi != "-") {
            std::stringstream ss(roi);
            std::string t;
            while (std::getline(ss, t, ',')) rois.push_back(t);
        }
        // ---- DICOM
        std::vector<DicomSlice> slices;
        for (auto& e : fs::directory_iterator(argv[3])) {
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
        std::printf("DICOM: %s", log.c_str());
        std::printf("[stage 0] DICOM -> canonical volume\n");
        cmp_exact("ct_can", ct.data.data(), ct.size(), ref + "/ct_can.npy");

        // ---- models needed by the task
        ClassMaps cm = load_classmaps_file(wd + "/classmaps.txt");
        std::map<int, std::unique_ptr<ModelWeights>> weights;
        std::map<int, ModelConfig> cfg_store;  // outlives the weights (TaskSpec points into it)
        std::map<int, const ModelConfig*> cfgs;
        for (int tid : {298, 291, 292, 293, 294, 295, 570, 8}) {
            try {
                weights[tid] = std::make_unique<ModelWeights>(load_weights_file(find_weights(wd, tid)));
                cfg_store[tid] = weights[tid]->cfg;
                cfgs[tid] = &cfg_store[tid];
            } catch (const std::exception&) {
            }
        }
        TaskSpec spec = make_task(task, rois, cfgs, cm);
        std::map<int, std::unique_ptr<UNet>> nets;
        std::map<int, const UNet*> netp;
        if (spec.crop_cfg) nets[298] = std::make_unique<UNet>(*weights[298]);
        for (auto& m : spec.models) nets[m.task_id] = std::make_unique<UNet>(*weights[m.task_id]);
        for (auto& kv : nets) netp[kv.first] = kv.second.get();
        weights.clear();
        std::printf("task %s, roi_subset [%s], models:", task.c_str(), roi.c_str());
        for (auto& m : spec.models) std::printf(" %d", m.task_id);
        std::printf("%s, spacing %.4f %.4f %.4f, step %.1f\n", spec.crop_cfg ? " (+298 crop)" : "", spec.spacing[0], spec.spacing[1],
                    spec.spacing[2], spec.step_size);

        PipelineDebug dbg;
        dbg.keep = true;
        auto t0 = std::chrono::steady_clock::now();
        Volume<uint8_t> seg = run_task(ct, spec, netp, [](const std::string& s, double f) {
            static std::string last;
            if (s != last) { std::printf("    .. %s\n", s.c_str()); std::fflush(stdout); last = s; }
        }, &dbg);
        std::printf("pipeline %.1f s\n%s", std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(), dbg.timings.c_str());

        if (spec.crop_cfg) {
            std::printf("[crop] 6mm rough segmentation\n");
            cmp_exact("298_in", dbg.crop_in.data.data(), dbg.crop_in.size(), ref + "/298_in.npy");
            cmp_exact("298_pre", dbg.crop_pred.pre.data(), (int64_t)dbg.crop_pred.pre.size(), ref + "/298_pre.npy");
            cmp_half("298_logits", dbg.crop_pred.logits, ref + "/298_logits.npy");
            cmp_exact("298_seg", dbg.crop_seg.data.data(), dbg.crop_seg.size(), ref + "/298_seg.npy", false);
            cmp_exact("crop_mask", dbg.crop_mask.data.data(), dbg.crop_mask.size(), ref + "/crop_mask_can.npy");
            std::printf("  bbox canonical [%d,%d) [%d,%d) [%d,%d)\n", dbg.bbox[0][0], dbg.bbox[0][1], dbg.bbox[1][0], dbg.bbox[1][1],
                        dbg.bbox[2][0], dbg.bbox[2][1]);
        }
        std::printf("[resample] task spacing input\n");
        const std::string t0s = std::to_string(spec.models[0].task_id);
        cmp_exact(t0s + "_in", dbg.part_in.data.data(), dbg.part_in.size(), ref + "/" + t0s + "_in.npy");
        for (size_t i = 0; i < spec.models.size(); ++i) {
            const std::string ts = std::to_string(spec.models[i].task_id);
            std::printf("[model %s] %d tiles\n", ts.c_str(), dbg.part_pred[i].num_tiles);
            cmp_exact(ts + "_pre", dbg.part_pred[i].pre.data(), (int64_t)dbg.part_pred[i].pre.size(), ref + "/" + ts + "_pre.npy");
            cmp_half(ts + "_logits", dbg.part_pred[i].logits, ref + "/" + ts + "_logits.npy");
            cmp_exact(ts + "_seg", dbg.part_seg[i].data.data(), dbg.part_seg[i].size(), ref + "/" + ts + "_seg.npy", false);
        }
        std::printf("[final] %s\n", final_name.c_str());
        const std::string fp = ref + "/" + final_name;
        cmp_exact("final", seg.data.data(), seg.size(), fp);
        // per-label summary
        NpyArray fin = npy_load(fp);
        std::vector<int64_t> na(256, 0), nb(256, 0), inter(256, 0);
        for (int64_t i = 0; i < seg.size(); ++i) {
            const int a = seg.data[i], b = (int)fin.get(i);
            na[a]++;
            nb[b]++;
            if (a == b) inter[a]++;
        }
        int labels = 0, labels_exact = 0;
        double worst = 1.0;
        std::string worst_name;
        for (int l = 1; l < 256; ++l) {
            if (!na[l] && !nb[l]) continue;
            ++labels;
            const double d = 2.0 * inter[l] / (double)(na[l] + nb[l]);
            if (na[l] == nb[l] && inter[l] == na[l]) ++labels_exact;
            if (d < worst) {
                worst = d;
                worst_name = l < (int)spec.labels.size() ? spec.labels[l] : std::to_string(l);
            }
        }
        std::printf("  labels present: %d, identical: %d, worst Dice %.6f (%s)\n", labels, labels_exact, worst, worst_name.c_str());
        std::printf("RESULT: %s\n", g_all_exact ? "ALL CHECKED STAGES IDENTICAL" : "DIFFERENCES FOUND");
        return g_all_exact ? 0 : 1;
    } catch (const std::exception& e) {
        std::printf("exception: %s\n", e.what());
        return 3;
    }
}
