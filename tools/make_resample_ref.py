import numpy as np, json
from scipy import ndimage
d = 'ref/resample/'
rng = np.random.default_rng(0)
# random tests
a = rng.normal(0, 300, (23, 31, 17)).round()
np.save(d + 'rand_in.npy', a)
np.save(d + 'rand_o3.npy', ndimage.zoom(a, (0.43, 1.7, 0.9), order=3, mode='nearest'))
np.save(d + 'rand_o0.npy', ndimage.zoom(a, (2.3, 0.6, 1.1), order=0, mode='nearest'))
# real CT: TS path (canonical ct -> 6mm, order 3, int32)
ct = np.load('ref/case1_cpu/ct_can.npy').astype(np.float64)
z = json.load(open('ref/case1_cpu/ct_can.json'))['zooms']
zoom = np.array(z, dtype=np.float32) / np.array([6.0, 6.0, 6.0])
r = ndimage.zoom(ct, zoom, order=3, mode='nearest').astype(np.int32)
ref = np.load('ref/case1_cpu/298_in.npy')
print('scipy repro of TS 298_in equal:', r.shape, ref.shape, np.array_equal(r, ref))
np.save(d + 'ct_f64.npy', np.ascontiguousarray(ct))
