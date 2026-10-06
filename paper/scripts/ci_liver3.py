"""Clopper-Pearson 95% CI for the liver-task totals (main text after the 2026-10-06 refocus on the three liver tasks).
Counts from Table 4 (exactness.csv via make_tables): WebGPU 20 + 17 + 20 = 57 of 60, CPU 19 + 17 + 19 = 55 of 60.
Output: ../analysis/ci_liver3_20261006.txt"""
from scipy.stats import beta
def cp(k, n, a=0.05):
    lo = 0 if k == 0 else beta.ppf(a / 2, k, n - k + 1); hi = 1 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return 100 * lo, 100 * hi
for lab, k, n in [("WebGPU liver 3 tasks", 57, 60), ("CPU liver 3 tasks", 55, 60), ("WebGPU liver_segments", 17, 20)]:
    lo, hi = cp(k, n); print(f"{lab}: {k}/{n} = {100*k/n:.1f}%  95%CI {lo:.1f}-{hi:.1f}%")
