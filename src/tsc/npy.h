// Minimal .npy reader/writer (little endian, C order) used by tests and CLI dumps.
#pragma once

#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "common.h"

namespace tsc {

struct NpyArray {
    std::string descr;  // e.g. "<f4", "<i4", "|u1", "<f2", "<f8", "<i2"
    std::vector<int64_t> shape;
    std::vector<char> bytes;
    int64_t count() const {
        int64_t n = 1;
        for (auto s : shape) n *= s;
        return n;
    }
    template <class T>
    const T* as() const { return reinterpret_cast<const T*>(bytes.data()); }
    // Converts any supported numeric dtype to double.
    std::vector<double> to_double() const {
        std::vector<double> r((size_t)count());
        for (int64_t i = 0; i < count(); ++i) r[i] = get(i);
        return r;
    }
    double get(int64_t i) const {
        const std::string t = descr.substr(1);
        if (t == "f4") return as<float>()[i];
        if (t == "f8") return as<double>()[i];
        if (t == "f2") return half_to_float(as<uint16_t>()[i]);
        if (t == "i4") return as<int32_t>()[i];
        if (t == "i2") return as<int16_t>()[i];
        if (t == "u1") return as<uint8_t>()[i];
        if (t == "i1") return as<int8_t>()[i];
        if (t == "u2") return as<uint16_t>()[i];
        if (t == "i8") return (double)as<int64_t>()[i];
        throw std::runtime_error("npy: unsupported dtype " + descr);
    }
};

inline NpyArray npy_load(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("npy: cannot open " + path);
    char magic[6];
    f.read(magic, 6);
    if (std::memcmp(magic, "\x93NUMPY", 6) != 0) throw std::runtime_error("npy: bad magic " + path);
    uint8_t ver[2];
    f.read((char*)ver, 2);
    uint32_t hlen = 0;
    if (ver[0] == 1) {
        uint16_t h;
        f.read((char*)&h, 2);
        hlen = h;
    } else {
        f.read((char*)&hlen, 4);
    }
    std::string hdr(hlen, ' ');
    f.read(&hdr[0], hlen);
    NpyArray a;
    auto p = hdr.find("'descr':");
    auto q1 = hdr.find('\'', p + 8);
    auto q2 = hdr.find('\'', q1 + 1);
    a.descr = hdr.substr(q1 + 1, q2 - q1 - 1);
    if (hdr.find("'fortran_order': True") != std::string::npos) throw std::runtime_error("npy: fortran order");
    auto s1 = hdr.find('(', hdr.find("'shape':"));
    auto s2 = hdr.find(')', s1);
    std::stringstream ss(hdr.substr(s1 + 1, s2 - s1 - 1));
    std::string tok;
    while (std::getline(ss, tok, ',')) {
        if (tok.find_first_not_of(" ") == std::string::npos) continue;
        a.shape.push_back(std::stoll(tok));
    }
    int esz = std::stoi(a.descr.substr(2));
    a.bytes.resize((size_t)(a.count() * esz));
    f.read(a.bytes.data(), (std::streamsize)a.bytes.size());
    return a;
}

template <class T>
inline const char* npy_descr();
template <> inline const char* npy_descr<float>() { return "<f4"; }
template <> inline const char* npy_descr<double>() { return "<f8"; }
template <> inline const char* npy_descr<int32_t>() { return "<i4"; }
template <> inline const char* npy_descr<int16_t>() { return "<i2"; }
template <> inline const char* npy_descr<uint8_t>() { return "|u1"; }
template <> inline const char* npy_descr<uint16_t>() { return "<f2"; }  // we only store halfs as u16

template <class T>
inline void npy_save(const std::string& path, const T* data, const std::vector<int64_t>& shape) {
    std::string sh;
    for (size_t i = 0; i < shape.size(); ++i) sh += std::to_string(shape[i]) + (shape.size() == 1 || i + 1 < shape.size() ? "," : "");
    std::string hdr = std::string("{'descr': '") + npy_descr<T>() + "', 'fortran_order': False, 'shape': (" + sh + "), }";
    size_t total = 10 + hdr.size() + 1;
    hdr += std::string((64 - total % 64) % 64, ' ') + "\n";
    std::ofstream f(path, std::ios::binary);
    f.write("\x93NUMPY\x01\x00", 8);
    uint16_t hl = (uint16_t)hdr.size();
    f.write((const char*)&hl, 2);
    f.write(hdr.data(), (std::streamsize)hdr.size());
    int64_t n = 1;
    for (auto s : shape) n *= s;
    f.write((const char*)data, (std::streamsize)(n * sizeof(T)));
}

}  // namespace tsc
