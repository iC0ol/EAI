# B2 Confirmation report — matched-state CAC intervention

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
| Max observation MAE | 0.000175 |
| Max geometry error (m) | 0 |

## Per-horizon success

| h | State-mean success probability | State-cluster 95% CI |
|---:|---:|---|
| 1 | 0.989 | [0.967, 1.000] |
| 2 | 0.967 | [0.900, 1.000] |
| 4 | 0.967 | [0.900, 1.000] |
| 8 | 0.989 | [0.967, 1.000] |
| 15 | 0.978 | [0.933, 1.000] |

## Primary pre-registered contrast

`p_s(h) = mean(success over 3 repeats)`; `Delta_s = 0.5*(p_s(1)+p_s(2)) - p_s(15)`.

| Quantity | Estimate | 95% state-cluster bootstrap CI |
|---|---:|---|
| Slope per metre | 0.0000 | [0.0000, 0.0000] |
| Slope per millimetre | 0.000000 | — |
| Predicted Delta at c10 | 0.0000 | — |
| Predicted Delta at c90 | 0.0000 | — |
| **E = pred(c10) - pred(c90)** | **0.0000** | **[0.0000, 0.0000]** |

Pre-registered practical threshold: E >= 0.08. Point estimate meets threshold: **False**.

Clearance c10/c90: -0.049510 / -0.006682 m.

Statistical method: 5,000 state-cluster bootstrap resamples for confidence intervals; 100,000 state-level clearance permutations for the slope null; slope permutation p=1. E has the same permutation p because c10/c90 are fixed.

## Secondary h-vs-h15 comparisons

CIs: state-cluster bootstrap. p-values: paired sign-flip (difference) and clearance permutation (slope), each with 100,000 permutations; Holm correction over the four h-vs-h15 comparisons.

| h | Mean success difference vs h=15 | 95% CI | Holm p (difference) | Clearance slope / m | 95% CI | Holm p (slope) |
|---:|---:|---|---:|---:|---|---:|
| 1 | 0.011 | [0.000, 0.033] | 1 | 0.4324 | [0.0000, 1.5198] | 1 |
| 2 | -0.011 | [-0.033, 0.000] | 1 | -0.4324 | [-1.5292, 0.0000] | 1 |
| 4 | -0.011 | [-0.033, 0.000] | 1 | -0.4324 | [-1.5890, 0.0000] | 1 |
| 8 | 0.011 | [-0.033, 0.067] | 1 | 1.1442 | [0.0000, 3.6657] | 1 |

## Categorical h x clearance interaction (secondary)

Linear probability model over state-level `p_s(h)`, reference h=15, state-cluster bootstrap CIs.

| Term | Coefficient | 95% CI |
|---|---:|---|
| `intercept_h15` | 0.9778 | [0.9333, 1.0000] |
| `horizon_main_h1` | 0.0006 | [-0.0123, 0.0113] |
| `horizon_main_h2` | -0.0427 | [-0.1555, 0.0000] |
| `horizon_main_h4` | -0.0427 | [-0.1555, 0.0000] |
| `horizon_main_h8` | 0.0179 | [-0.0150, 0.0667] |
| `interaction_h1_x_clearance_per_m` | -0.4324 | [-1.5803, 0.0000] |
| `interaction_h2_x_clearance_per_m` | -1.2973 | [-4.7409, 0.0000] |
| `interaction_h4_x_clearance_per_m` | -1.2973 | [-4.7409, 0.0000] |
| `interaction_h8_x_clearance_per_m` | 0.2793 | [-0.0000, 1.3715] |

## Cost

| h | Mean policy calls after branch | Mean wall time (s) | Total calls |
|---:|---:|---:|---:|
| 1 | 23.10 | 57.66 | 2079 |
| 2 | 23.03 | 57.67 | 2073 |
| 4 | 22.97 | 57.69 | 2067 |
| 8 | 22.53 | 57.17 | 2028 |
| 15 | 22.13 | 56.89 | 1992 |

## Descriptive clearance bins

| Bin | Clearance range (m) | States | Delta mean |
|---:|---|---:|---:|
| 0 | [-0.056951, -0.030153] | 10 | 0.000 |
| 1 | [-0.030153, -0.011351] | 10 | 0.000 |
| 2 | [-0.011351, -0.003891] | 10 | 0.000 |

## Decision

**CONFIRMATION_NO_PRACTICALLY_MEANINGFUL_EFFECT**

This is a protocol-level statistical decision for the confirmation split only. It is not a claim that B2 has passed, and the other split is not pooled.

## Interpretation limits

- The independent unit is the matched physical state, not the 450 branch episodes.
- Repeats are nested within state x horizon; bootstrap resamples whole state IDs.
- Hypothesis-test p-values come from state-level permutation nulls, not from the bootstrap distribution.
- Discovery and confirmation are analyzed independently and are never pooled.
- A wide interval is inconclusive; non-significance is not proof of no effect.
- B2 does not train CAC or establish a deployment-time visual clearance estimator.
