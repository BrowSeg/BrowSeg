// Meshes a binary mask stored as npy (X,Y,Z order) with the C++ mesher, in the same
// frame as the IRCAD V6 script (world = origin + index * spacing).
// usage: mesh_from_npy <mask.npy> sx sy sz ox oy oz <out.obj> [target_res sigma taubin]
#include <chrono>
#include <cstdio>

#include "tsc/mesh.h"
#include "tsc/npy.h"

using namespace tsc;

int main(int argc, char** argv) {
    if (argc < 9) {
        std::printf("usage: mesh_from_npy mask.npy sx sy sz ox oy oz out.obj [target_res sigma taubin]\n");
        return 2;
    }
    NpyArray a = npy_load(argv[1]);
    Volume<uint8_t> v(Shape3{a.shape[0], a.shape[1], a.shape[2]});
    for (int64_t i = 0; i < v.size(); ++i) v.data[(size_t)i] = a.get(i) > 0.5 ? 1 : 0;
    v.affine = identity_affine();
    for (int d = 0; d < 3; ++d) {
        v.affine[d * 4 + d] = std::atof(argv[2 + d]);
        v.affine[d * 4 + 3] = std::atof(argv[5 + d]);
    }
    MeshOptions o = mesh_options_for("liver_vessels", false);
    if (argc > 9) o.target_res_mm = std::atof(argv[9]);
    if (argc > 10) o.smooth_sigma_mm = std::atof(argv[10]);
    if (argc > 11) o.taubin_iterations = std::atoi(argv[11]);
    auto t0 = std::chrono::steady_clock::now();
    Mesh m = mask_to_mesh(v, 1, o);
    double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    write_obj(m, argv[8]);
    std::printf("%zu vertices, %zu triangles, %.2f mL, %.0f ms\n", m.num_vertices(), m.num_triangles(), mesh_volume_ml(m), ms);
    return 0;
}
