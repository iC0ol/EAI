# B2 Discovery report — matched-state CAC intervention

Protocol: `B2_PROTOCOL_REVISION_20261116` (B2 v1.1).
Marker: **B2** (not PREFLIGHT).

## Integrity

| Check | Result |
|---|---|
| States (`state_id` is the independent unit) | 30 |
| Branch episodes | 450 (30 x 5 x 3 required) |
| Completeness / duplicate / mixed-split gate | passed |
| Snapshot validation (every selected state) | passed |
| Max snapshot state error | 0 |
| Max observation MAE | 0.000211 |
| Max geometry error (m) | 0 |

## Per-horizon success

| h | State-mean success probability | State-cluster 95% CI |
|---:|---:|---|
| 1 | 0.933 | [0.833, 1.000] |
| 2 | 0.944 | [0.878, 1.000] |
| 4 | 0.944 | [0.889, 0.989] |
| 8 | 0.944 | [0.867, 1.000] |
| 15 | 0.933 | [0.844, 1.000] |

## Primary pre-registered contrast

`p_s(h) = mean(success over 3 repeats)`; `Delta_s = 0.5*(p_s(1)+p_s(2)) - p_s(15)`.

| Quantity | Estimate | 95% state-cluster bootstrap CI |
|---|---:|---|
| Slope per metre | -1.1972 | [-3.3614, 0.3397] |
| Slope per millimetre | -0.001197 | — |
| Predicted Delta at c10 | 0.0340 | — |
| Predicted Delta at c90 | -0.0217 | — |
| **E = pred(c10) - pred(c90)** | **0.0557** | **[-0.0158, 0.1564]** |

Pre-registered practical threshold: E >= 0.08. Point estimate meets threshold: **False**.

Clearance c10/c90: -0.050998 / -0.004469 m.

Statistical method: 5,000 state-cluster bootstrap resamples for confidence intervals; 100,000 state-level clearance permutations for the slope null; slope permutation p=0.343857. E has the same permutation p because c10/c90 are fixed.

## Secondary h-vs-h15 comparisons

CIs: state-cluster bootstrap. p-values: paired sign-flip (difference) and clearance permutation (slope), each with 100,000 permutations; Holm correction over the four h-vs-h15 comparisons.

| h | Mean success difference vs h=15 | 95% CI | Holm p (difference) | Clearance slope / m | 95% CI | Holm p (slope) |
|---:|---:|---|---:|---:|---|---:|
| 1 | 0.000 | [-0.033, 0.033] | 1 | -1.2403 | [-3.5087, 0.0000] | 0.9044 |
| 2 | 0.011 | [-0.056, 0.078] | 1 | -1.1542 | [-4.1349, 1.2603] | 1 |
| 4 | 0.011 | [-0.033, 0.056] | 1 | -0.9531 | [-3.5568, 1.3507] | 1 |
| 8 | 0.011 | [-0.022, 0.044] | 1 | 0.1092 | [-1.8297, 2.0129] | 1 |

## Categorical h x clearance interaction (secondary)

Linear probability model over state-level `p_s(h)`, reference h=15, state-cluster bootstrap CIs.

| Term | Coefficient | 95% CI |
|---|---:|---|
| `intercept_h15` | 0.9333 | [0.8444, 1.0000] |
| `horizon_main_h1` | -0.0062 | [-0.1694, 0.1235] |
| `horizon_main_h2` | 0.0072 | [-0.0973, 0.1041] |
| `horizon_main_h4` | 0.0127 | [-0.0756, 0.1114] |
| `horizon_main_h8` | 0.0416 | [-0.0193, 0.1411] |
| `interaction_h1_x_clearance_per_m` | -0.2291 | [-5.1821, 4.2634] |
| `interaction_h2_x_clearance_per_m` | -0.1430 | [-3.4250, 2.5419] |
| `interaction_h4_x_clearance_per_m` | 0.0581 | [-2.4997, 2.9647] |
| `interaction_h8_x_clearance_per_m` | 1.1204 | [-1.3916, 5.0630] |

## Cost

| h | Mean policy calls after branch | Mean wall time (s) | Total calls |
|---:|---:|---:|---:|
| 1 | 23.87 | 60.11 | 2148 |
| 2 | 23.77 | 60.16 | 2139 |
| 4 | 23.57 | 59.97 | 2121 |
| 8 | 23.40 | 59.78 | 2106 |
| 15 | 22.93 | 59.38 | 2064 |

## Descriptive clearance bins

| Bin | Clearance range (m) | States | Delta mean |
|---:|---|---:|---:|
| 0 | [-0.052708, -0.036729] | 10 | 0.067 |
| 1 | [-0.036729, -0.016080] | 10 | -0.033 |
| 2 | [-0.016080, -0.000348] | 10 | -0.017 |

## Decision

**DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED**

This is a protocol-level statistical decision for the discovery split only. It is not a claim that B2 has passed, and the other split is not pooled.

## Interpretation limits

- The independent unit is the matched physical state, not the 450 branch episodes.
- Repeats are nested within state x horizon; bootstrap resamples whole state IDs.
- Hypothesis-test p-values come from state-level permutation nulls, not from the bootstrap distribution.
- Discovery and confirmation are analyzed independently and are never pooled.
- A wide interval is inconclusive; non-significance is not proof of no effect.
- B2 does not train CAC or establish a deployment-time visual clearance estimator.
