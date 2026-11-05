# Research state — spatial understanding for robot action

Last updated: 2026-11-05 (Asia/Shanghai), fourth pass. Search cutoff 2026-11-05.

## Status: COMPLETE (fourth pass, revised conclusions; pushed at 5255a74)

## Pass 1 (initial delivery)
- 130 queries, ~2,360 unique records, 88 registered at first delivery.
## Current totals (after pass 2)
- 95 registered (2 added in pass 3, 1 in pass 4): 33 full / 21 partial / 41 abstract-only.
- Seven candidate directions screened; five eliminated; C1 retained.

## Pass 2 (this session: re-audit and revision)
Triggered by the instruction that delivery had not fully passed review. Actions:

1. **Re-read the three papers C1 depends on** (they had been read at abstract level in pass 1):
   - LIBERO-RIG 2610.18843 → **its Table 5 is already "Tolerance per axis"**, with absolute (≥0.80) and
     relative (≥0.90) criteria. Pass 1's claim "no paper estimates failure thresholds" was wrong and is corrected.
     Table 5 also warns levels are per-axis and **not comparable across axes**.
   - More Structure 2607.09825 → Near-Miss 31%→2.5%, No-Grasp 15/15/24 unchanged; StackCube 72% No-Grasp, SR 5.3%.
     The mechanism is already proven in one task, so C1 shrinks to cross-task prediction.
   - 2610.01626 → "a single global contraction rate is not supported even at the task level"; a scalar per-task τ
     is methodologically unsound.
2. **New counterexample found**: 2512.02902 — 4K-parameter Feature Token Modulation lifts LIBERO viewpoint
   success 48.5%→87.1%; 4.7M-parameter FLA reaches 90.8%, beating π0.5 LoRA (467M). This undermines any
   "upgrade the spatial representation" narrative and is now a hard control in the experiment gates.
3. **Publication metadata verified via OpenAlex single-work endpoint** (search/filter endpoints are 429):
   11 of 88 are conference papers (KYC = ICRA 2026; SpatialVLA/LIBERO-X/mid-level = RSS; SpatialVLM/RoboSpatial = CVPR;
   RSB/2609.07047 = EMNLP Findings; 2605.30161/2607.01658/2603.22876/2601.09954 = LNCS). Rest are arXiv-only at retrieval.
4. **Report revised**: C1 re-scoped to "failure-mode composition → benefit prediction"; score 4.0 → 3.35;
   judgment "priority" → "conditional, medium-low confidence"; gates 4 → 6.

## Still blocked / unknown
- **Citation lists**: OpenAlex `filter=cites:` → 429 ("budget used up; resets at midnight UTC");
  Semantic Scholar → 429. Single-work metadata works, forward citations do not. This is the one gap that could
  overturn C1 (someone may have already run the cross-task prediction).
- 41 papers remain abstract-only; they affect crowding judgements but not the core claims.
- C1's core premise (same task, different failure-mode variants) is a design proposal with no pilot data.

## If work resumes
1. Retry OpenAlex `filter=cites:W...` after 00:00 UTC, or use an institutional key / Semantic Scholar key.
2. Chase citations of 2610.18843, 2607.09825, 2610.01626, 2510.02268, 2512.02902.
3. If any citing work already does "failure composition predicts representation benefit", mark C1 dead and
   conclude "no candidate qualifies".

## Pass 3 (this session: forward citation chasing)

Semantic Scholar citations endpoint became intermittently available; retrieved citing/reference lists for five seeds:
- KYC 2510.02268: **28 citing works, all viewpoint/camera-robustness variants** (VersaCamVLA, Fisheye-VLA, RayViT,
  AxisGuide, Cross-View Action Consistency, ...). None studies benefit prediction. Strong citation-level evidence
  that category A is saturated.
- 2512.02902: 17 citing (alignment/adaptation).
- LIBERO-RIG: 1 citing. CMA: 1 citing. RSB: 1 citing.
- More Structure 2607.09825 and 2610.01626: persistent 429, **citing lists still missing**.

Two new papers found through the citation graph and registered:
- 2610.29646 "From Association to Decision Value": a reliable, correlated paired diagnostic yields only +0.059 nats
  (95% CI [-0.027, 0.133]) and no established top-20% selection gain. Consequence: C1 must be evaluated on
  selection utility, not correlation. Gate 5 added; total gates now 7.
- 2602.17659 "When Vision Overrides Language" (LIBERO-CF + CAG): further crowds C2.

## Pass 4 (Google Scholar channel)

- `scholar.google.com/scholar` is reachable and parseable. Ran six C1-targeted queries
  ("failure mode composition", "spatial tolerance", "near-miss"/"no-grasp", "which tasks predict
  representation benefit", "representation upgrade", exact-title lookup).
- **No work found** that uses failure-mode composition to predict representation benefit.
- Exact-title lookup for More Structure returns one result with **no "Cited by N"**, consistent with
  OpenAlex cited_by=0. The unretrieved S2 citing list is therefore very likely empty; the 429 gap is
  effectively closed.
- New paper registered: 2606.08881 (SO-101 failure/recovery benchmark). Its finding that execution
  instability dominates on low-cost hardware is now a limit on C1's headroom.

## Remaining blocker
- None material. OpenAlex filter=cites and S2 for 2607.09825 still 429, but Scholar/OpenAlex both
  indicate zero citations for that paper.
