# Gate B v2 analysis summary

## B1 pilot paired horizon scan

Initial states: **20**

| h | Successes | N | Success rate | Wilson 95% CI | Mean policy calls | Mean wall time (s) |
|---:|---:|---:|---:|---|---:|---:|
| 1 | 15 | 20 | 0.750 | [0.531, 0.888] | 500.00 | 501.36 |
| 2 | 14 | 20 | 0.700 | [0.481, 0.855] | 250.00 | 279.19 |
| 4 | 17 | 20 | 0.850 | [0.640, 0.948] | 125.00 | 167.41 |
| 8 | 18 | 20 | 0.900 | [0.699, 0.972] | 63.00 | 112.74 |
| 15 | 18 | 20 | 0.900 | [0.699, 0.972] | 34.00 | 87.88 |

Cochran's Q: q=6.6000, df=4, p=0.158598

Paired risk differences vs h=8 (95% cluster-bootstrap CI, Holm-adjusted p):
- h=1: -0.150 [-0.300, 0.000]; Holm p=0.75
- h=15: 0.000 [-0.200, 0.200]; Holm p=1
- h=2: -0.200 [-0.400, -0.050]; Holm p=0.5
- h=4: -0.050 [-0.250, 0.100]; Holm p=1

## Interpretation limits

- B1 pairing is valid only when every seed has the same initial simulator-state hash across horizons.
- B2 is valid only if snapshot/restore deterministic replay passed and discovery/confirmation states are disjoint.
- A wide interval is inconclusive; do not treat non-significance as evidence of no effect.
- This analysis does not train CAC or establish a deployment-time visual clearance estimator.
