# Records of the BrowSeg paper

The files behind the numbers of the paper (BrowSeg build 022925c; reference: TotalSegmentator 2.18.0 run on the CPU).
The CT images are not included; see `lits_cases.csv`.

| File | Contents | Used for |
|---|---|---|
| `data/lits_cases.csv` | The 30 cases: Task03_Liver file name, ID used in the records, slices, pixel and slice spacing, selection group, SHA-256 of the file | Data (Methods) |
| `data/lits_summary.csv` | One row per environment (desktop GPU, desktop CPU, laptop GPU) x case x task: label-map hashes of the runs, whether the runs were identical, differing voxels against the reference, smallest per-structure Dice, time (s; GPU: mean of runs 2 and 3), CT loading time (s), WebAssembly memory (MiB) | Table 1, Table 2 and the agreement, time and memory in the Results |
| `data/desktop_hashes.json` | Expected label-map hashes, desktop GPU path | `web/bench.html?local=1` |
| `data/desktop_hashes_wasm20.json` | The same for the CPU path | `web/bench.html?local=1` |

Differing voxels are counted on the original CT grid. The measurement logs and the analysis scripts are available
from the authors on request.
