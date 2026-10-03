"""
Export the TotalSegmentator class maps needed by the C++ pipeline to
weights/classmaps.txt:

  task <name> <idx> <class>          output label map of a task (class_map[task])
  part <task_id> <model_idx> <class> how a part model's labels map to class names
                                     (class_map_5_parts via map_taskid_to_partname_ct)

It also checks that the part maps agree with each model's dataset.json labels.
"""
import os, glob, json
from totalsegmentator.map_to_binary import class_map, class_map_5_parts, map_taskid_to_partname_ct

R = os.path.join(os.path.expanduser("~"), ".totalsegmentator", "nnunet", "results")
lines = []
for task in ["total", "liver_segments", "liver_vessels"]:
    for idx, name in sorted(class_map[task].items()):
        lines.append(f"task {task} {idx} {name}")
for tid, part in map_taskid_to_partname_ct.items():
    pm = class_map_5_parts[part]
    for idx, name in sorted(pm.items()):
        lines.append(f"part {tid} {idx} {name}")
    d = glob.glob(os.path.join(R, f"Dataset{tid}_*", "*__nnUNetPlans__3d_fullres"))
    if d:
        labels = json.load(open(os.path.join(d[0], "dataset.json")))["labels"]
        ds = {v: k for k, v in labels.items() if v != 0}
        diff = {k: (ds.get(k), v) for k, v in pm.items() if ds.get(k) != v}
        print(f"part {tid} ({part}): {len(pm)} classes, differences vs dataset.json: {diff if diff else 'none'}")
out = os.path.join(os.path.dirname(__file__), "..", "weights", "classmaps.txt")
open(out, "w", newline="\n").write("\n".join(lines) + "\n")
print("total classes:", len(class_map["total"]), " liver_segments:", class_map["liver_segments"])
print("wrote", os.path.abspath(out))
