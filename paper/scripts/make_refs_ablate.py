"""N26: Python TotalSegmentator 2.18 on the GPU with one setting changed, to separate the causes of the GPU differences
(Table 5). Same as make_refs.py otherwise.

usage: python make_refs_ablate.py <fp32|det> <cases_dir> <out_dir> <task:roi>[;...] [case,...]
  fp32: torch.autocast disabled (nnU-Net runs the network in fp16 mixed precision on cuda by default) and TF32 off
        (cudnn.allow_tf32, cuda.matmul.allow_tf32 = False): full 32-bit network on the GPU.
  det : mixed precision kept; cudnn.benchmark = False (nnU-Net sets True), cudnn.deterministic = True and
        torch.use_deterministic_algorithms(True, warn_only=True): fixed algorithm choice.
Run with the ts218 env.
"""
import sys, os, contextlib, importlib.util, json
from pathlib import Path
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
# nnunetv2.paths reads these at import; TotalSegmentator sets them only when it is imported, so set them first (det imports nnunetv2 early)
_r = str(Path.home() / ".totalsegmentator" / "nnunet" / "results")
for _k in ("nnUNet_raw", "nnUNet_preprocessed", "nnUNet_results"):
    os.environ.setdefault(_k, _r)
import torch

CALLS = {"autocast_replaced": 0}


def run():
    mode = sys.argv.pop(1)
    if mode == "fp32":
        def _no_autocast(*a, **k):
            CALLS["autocast_replaced"] += 1
            return contextlib.nullcontext()
        torch.autocast = _no_autocast
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
    elif mode == "det":
        from nnunetv2.inference import predict_from_raw_data as pr
        _init = pr.nnUNetPredictor.__init__
        def _init_det(self, *a, **k):
            _init(self, *a, **k)
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
        pr.nnUNetPredictor.__init__ = _init_det
        torch.use_deterministic_algorithms(True, warn_only=True)
    else:
        raise SystemExit("mode must be fp32 or det")

    spec = importlib.util.spec_from_file_location("make_refs", Path(__file__).with_name("make_refs.py"))
    mr = importlib.util.module_from_spec(spec); spec.loader.exec_module(mr)
    sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "gpu"] + sys.argv[3:]
    mr.main()
    Path(sys.argv[2], "_ablation.json").write_text(json.dumps({"mode": mode, "torch": torch.__version__,
        "cudnn_benchmark": torch.backends.cudnn.benchmark, "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32, **CALLS}))
    print("ablation", mode, CALLS)


if __name__ == "__main__":  # Windows: TS uses multiprocessing (spawn re-imports this file)
    run()
