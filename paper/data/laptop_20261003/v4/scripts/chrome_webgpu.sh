#!/bin/bash
# Launches Chrome for BrowSeg benchmarks on Linux. WebGPU is off by default in Chrome 142 on Linux, so
# the flags below enable it. BROWSEG_GPU=nv selects the NVIDIA Vulkan driver, otherwise the Intel one.
if [ "$BROWSEG_GPU" = "nv" ]; then
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
else
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/intel_icd.x86_64.json
fi
exec /usr/bin/google-chrome --enable-unsafe-webgpu --enable-features=Vulkan "$@"
