#include "weights.h"

#include <cstdlib>
#include <fstream>
#include <sstream>

namespace tsc {

ModelWeights load_weights(const uint8_t* data, size_t len, bool config_only) {
    if (len < 12 || std::memcmp(data, "TSCPPW01", 8) != 0) throw std::runtime_error("not a .tsw weights file");
    uint32_t hlen;
    std::memcpy(&hlen, data + 8, 4);
    if (12 + (size_t)hlen > len) throw std::runtime_error("truncated .tsw header");
    std::string header((const char*)data + 12, hlen);
    size_t base = (12 + (size_t)hlen + 63) / 64 * 64;

    ModelWeights w;
    ModelConfig& c = w.cfg;
    std::istringstream hs(header);
    std::string line;
    while (std::getline(hs, line)) {
        std::istringstream ls(line);
        std::string key;
        ls >> key;
        if (key == "name") ls >> c.name;
        else if (key == "task_id") ls >> c.task_id;
        else if (key == "patch") ls >> c.patch[0] >> c.patch[1] >> c.patch[2];
        else if (key == "spacing") {
            std::string a, b, d;
            ls >> a >> b >> d;
            c.spacing[0] = std::strtod(a.c_str(), nullptr);
            c.spacing[1] = std::strtod(b.c_str(), nullptr);
            c.spacing[2] = std::strtod(d.c_str(), nullptr);
        } else if (key == "ct_norm") {
            std::string a[4];
            ls >> a[0] >> a[1] >> a[2] >> a[3];
            c.ct_mean = std::strtod(a[0].c_str(), nullptr);
            c.ct_std = std::strtod(a[1].c_str(), nullptr);
            c.ct_p005 = std::strtod(a[2].c_str(), nullptr);
            c.ct_p995 = std::strtod(a[3].c_str(), nullptr);
        } else if (key == "n_stages") ls >> c.n_stages;
        else if (key == "features") { int v; while (ls >> v) c.features.push_back(v); }
        else if (key == "strides" || key == "kernels") {
            std::vector<int> v;
            int x;
            while (ls >> x) v.push_back(x);
            auto& dst = key == "strides" ? c.strides : c.kernels;
            for (size_t i = 0; i + 2 < v.size(); i += 3) dst.push_back({v[i], v[i + 1], v[i + 2]});
        } else if (key == "n_conv_enc") { int v; while (ls >> v) c.n_conv_enc.push_back(v); }
        else if (key == "n_conv_dec") { int v; while (ls >> v) c.n_conv_dec.push_back(v); }
        else if (key == "num_classes") ls >> c.num_classes;
        else if (key == "label") {
            int idx;
            std::string nm;
            ls >> idx >> nm;
            if (!ls || idx < 0 || idx > 255) throw std::runtime_error("weights: bad label index");
            if ((int)c.labels.size() <= idx) c.labels.resize(idx + 1);
            c.labels[idx] = nm;
        } else if (key == "tensor") {
            if (config_only) continue;  // only the header is needed (the network runs elsewhere, e.g. WebGPU)
            std::string nm, dt;
            int nd;
            ls >> nm >> dt >> nd;
            if (!ls || nd < 0 || nd > 5) throw std::runtime_error("bad tensor header " + nm);
            TensorF t;
            t.shape.resize(nd);
            for (int i = 0; i < nd; ++i) {
                ls >> t.shape[i];
                if (!ls || t.shape[i] < 0) throw std::runtime_error("bad tensor shape " + nm);
            }
            uint64_t off, nbytes;
            ls >> off >> nbytes;
            // overflow-safe (size_t is 32 bit on wasm32)
            if (!ls || base > len || off > len - base || nbytes > len - base - off) throw std::runtime_error("truncated tensor " + nm);
            const uint8_t* p = data + base + off;
            int64_t n = t.numel();
            t.data.resize(checked_count<float>(n));
            if (dt == "f32") {
                if ((int64_t)nbytes != n * 4) throw std::runtime_error("bad size " + nm);
                std::memcpy(t.data.data(), p, nbytes);
            } else if (dt == "f16") {
                if ((int64_t)nbytes != n * 2) throw std::runtime_error("bad size " + nm);
                for (int64_t i = 0; i < n; ++i) {
                    uint16_t h;
                    std::memcpy(&h, p + 2 * i, 2);
                    t.data[(size_t)i] = half_to_float(h);
                }
            } else {
                throw std::runtime_error("unknown dtype " + dt);
            }
            w.tensors[nm] = std::move(t);
        } else if (key == "end") {
            break;
        }
    }
    if (c.n_stages <= 0 || (int)c.features.size() != c.n_stages || (int)c.strides.size() != c.n_stages ||
        (int)c.kernels.size() != c.n_stages || (int)c.n_conv_enc.size() != c.n_stages ||
        (int)c.n_conv_dec.size() != c.n_stages - 1 || c.num_classes <= 0 || c.num_classes > 256)
        throw std::runtime_error("bad .tsw config");
    return w;
}

ModelWeights load_weights_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open " + path);
    std::vector<uint8_t> buf((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    return load_weights(buf.data(), buf.size());
}

}  // namespace tsc
