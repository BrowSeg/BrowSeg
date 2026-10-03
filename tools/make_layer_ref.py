"""
Dump per-stage activations of one network patch (fp32, CPU) for kernel-level
verification of the C++ UNet.

usage: python make_layer_ref.py <task_id> <pre.npy> <out_dir>
Writes: patch_in.npy (1,1,P,P,P), enc{s}.npy, dec{s}.npy, logits.npy (fp32)
The patch is the first sliding-window tile after nnU-Net's padding.
"""
import os, sys
from pathlib import Path
import numpy as np
import torch

_r = str(Path.home() / ".totalsegmentator" / "nnunet" / "results")
for _k in ("nnUNet_raw", "nnUNet_preprocessed", "nnUNet_results"):
    os.environ[_k] = _r


def main():
    task_id, pre, out = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
    from nnunetv2.utilities.file_path_utilities import get_output_folder
    from acvl_utils.cropping_and_padding.padding import pad_nd_image
    import glob
    mdir = glob.glob(os.path.join(_r, f"Dataset{task_id:03d}_*", "*__nnUNetPlans__3d_fullres"))[0]
    pr = nnUNetPredictor(tile_step_size=0.5, use_gaussian=True, use_mirroring=False,
                         perform_everything_on_device=False, device=torch.device("cpu"))
    pr.initialize_from_trained_model_folder(mdir, use_folds=[0], checkpoint_name="checkpoint_final.pth")
    net = pr.network.eval()
    print(net)
    ps = pr.configuration_manager.patch_size
    data = torch.from_numpy(np.load(pre))
    padded, _ = pad_nd_image(data, ps, "constant", {"value": 0}, True, None)
    x = padded[None, :, :ps[0], :ps[1], :ps[2]].contiguous()
    np.save(out / "patch_in.npy", x.numpy())
    acts = {}
    for i, st in enumerate(net.encoder.stages):
        st.register_forward_hook(lambda m, inp, o, i=i: acts.__setitem__(f"enc{i}", o.detach().clone()))
    for i, st in enumerate(net.decoder.stages):
        st.register_forward_hook(lambda m, inp, o, i=i: acts.__setitem__(f"dec{i}", o.detach().clone()))
    torch.set_num_threads(os.cpu_count())
    with torch.no_grad():
        y = net(x)
    np.save(out / "logits.npy", y.numpy())
    for k, v in acts.items():
        np.save(out / f"{k}.npy", v.numpy())
        print(k, tuple(v.shape))


if __name__ == "__main__":
    main()
