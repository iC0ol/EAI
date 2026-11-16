# Gate B v2 analysis summary

## B1 full paired horizon scan

Initial states: **100**

| h | Successes | N | Success rate | Wilson 95% CI | Mean policy calls | Mean wall time (s) |
|---:|---:|---:|---:|---|---:|---:|
| 1 | 66 | 100 | 0.660 | [0.563, 0.745] | 500.00 | 500.81 |
| 2 | 72 | 100 | 0.720 | [0.625, 0.799] | 250.00 | 278.47 |
| 4 | 81 | 100 | 0.810 | [0.722, 0.875] | 125.00 | 167.38 |
| 8 | 87 | 100 | 0.870 | [0.790, 0.922] | 63.00 | 112.93 |
| 15 | 93 | 100 | 0.930 | [0.863, 0.966] | 34.00 | 87.92 |

Cochran's Q: q=34.2000, df=4, p=6.78021e-07

Paired risk differences vs h=8 (95% cluster-bootstrap CI, Holm-adjusted p):
- h=1: -0.210 [-0.320, -0.110]; Holm p=0.00129625
- h=15: 0.060 [-0.010, 0.140]; Holm p=0.420227
- h=2: -0.150 [-0.250, -0.050]; Holm p=0.0243902
- h=4: -0.060 [-0.150, 0.030]; Holm p=0.420227

## Interpretation limits

- B1 pairing is valid only when every seed has the same initial simulator-state hash across horizons.
- B2 is valid only if snapshot/restore deterministic replay passed and discovery/confirmation states are disjoint.
- A wide interval is inconclusive; do not treat non-significance as evidence of no effect.
- This analysis does not train CAC or establish a deployment-time visual clearance estimator.
