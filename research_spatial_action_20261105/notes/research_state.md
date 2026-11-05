# Research state — spatial understanding for robot action

Last updated: 2026-11-05 (Asia/Shanghai), final pass (competitor screens). Search cutoff 2026-11-05.

## Status: COMPLETE (pushed to codex/spatial-action-survey-20261105 — see git log for HEAD)

## Pass 1 (initial delivery)
- 130 queries, ~2,360 unique records, 88 registered at first delivery.
## Current totals (final)
- 99 registered (2 in pass 3, 1 in pass 4, 4 in the competitor screens): 33 full / 25 partial / 41 abstract-only.
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
4. **Report revised**: C1 re-scoped to "failure-mode composition → benefit prediction"; score 4.0 → 3.35
   (later 3.1, see Pass 6); judgment "priority" → "conditional, medium-low confidence"; gates 4 → 6 (later 7).

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
- KYC 2510.02268: **28 citing works, about 24 of them viewpoint/camera-robustness variants** (VersaCamVLA, Fisheye-VLA, RayViT,
  AxisGuide, Cross-View Action Consistency, ...). None studies benefit prediction. Strong citation-level evidence
  that category A is saturated.
- 2512.02902: 17 citing (alignment/adaptation).
- LIBERO-RIG: 1 citing. CMA: 1 citing. RSB: 1 citing.
- More Structure 2607.09825: persistent 429, citing list still missing; 2610.01626 retrieved with 0 citing works.

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

## Pass 5 (asset verification for the surviving candidate)

- Checked arXiv HTML hrefs and PDF strings for the four papers C1 would reuse
  (2607.09825, 2610.18843, 2610.01626, 2512.02902): **no project or code URL in any of them**
  (only arXiv/LaTeXML boilerplate). GitHub repo search for "LIBERO-RIG" finds no matching repo,
  although the paper says "We release the benchmark together with manifests".
- Consequence recorded in the register (`code = NO_URL_IN_PAPER`), in report §2-C1 items 10-11,
  in §5, and as a new feasibility uncertainty in COMPLETION.json: the failure taxonomy and the
  tolerance protocol must be reimplemented (estimated 1-2 weeks, unverified).
- Also refreshed the stale "pushed at" note in this file.

## Remaining blocker
- None material. OpenAlex filter=cites and S2 for 2607.09825 still 429, but Scholar/OpenAlex both
  indicate zero citations for that paper.

## Pass 6 (competitor screens, final)

Two systematic sweeps of the unread set rather than re-reading:

1. **Abstract-only screen**: listed all 40 titles; only 2611.05058 ("Do Agentic
   Policies Need to Look at Every Step?") asked a related question, so it was
   fetched and read. Result: on Ring-on-peg (fine alignment) geometric
   abstraction reaches 38.0% at revision 3 while pixel reasoning stays 0.0%;
   Bridge-tower 28/50 vs 12/50 online. Supports C1's H1 in direction but is an
   LLM policy-synthesis setting, recorded with that caveat.
2. **New phrasing sweep** (six queries: when-3D, depth-helps, geometry-helps,
   value-of-3D, task-dependent, which-tasks-benefit) found the decisive paper:
   **2608.03052 "How Should VLA Models Use Proprioceptive State?"** already runs
   the controlled-ablation paradigm (5 interfaces, fixed backbone, 45 atomic + 20
   composite tasks, history 1-96 frames, task-family-dependent effects) for
   proprioceptive state. Correction after reading its mechanism section: it
   varies interface and history depth, **not input precision** (its noise analysis
   concerns action-generation noise). So C1 is not "a change of input" but "same
   paradigm, different independent variable"; LIBERO-RIG separately provides the
   precision-to-success ladder. C1's contribution is therefore the combination
   into a cross-task prediction, not a new variable.

Consequences applied: C1 importance 3 -> 2, weighted 3.35 -> **3.1**; new failure
cause (g) "combinational reuse of an established paradigm and ladder"; 2607.17454 (Gated GeoBoN) added
as a direct C2 competitor; 2606.13877 (ContactWorld) registered as another
"which representation matters" study. Registry 95 -> 99 (33 full / 25 partial /
41 abstract-only). Every cited ID is now registered (78/78).

## Pass 7 (background continuation: delivery-integrity review, 2026-11-05)

Triggered by the instruction that delivery had not fully passed review. This pass did not re-run
the survey; it audited whether the delivered artifacts are self-consistent and traceable, and
fixed what was not.

### Checks performed
1. **All 101 arXiv IDs re-fetched** from `arxiv.org/abs/<id>` and title-matched against the
   registry: 101/101 identical. No fabricated IDs.
2. **Registry ↔ local files ↔ report** cross-check by script. Citations in the report are all
   registered; 8 registry entries have no local file (all ABSTRACT_ONLY, consistent).
3. **Round-4 raw dump screen**: found `2609.12641` (LIT) downloaded but never registered.
4. **Citation retry**: S2 returned More Structure's citation list (empty). OpenAlex single-work
   `cited_by_count` discovered to be non-informative (returns 0 for KYC, which has 22-28).
5. **Counts re-derived**: 136 queries in `notes/*.queries.json`, 2,480 unique IDs in the dumps.

### Material findings
- **LIT (2609.12641)** is a direct C2 competitor (goal-change counterfactual) and, more
  importantly, a **counterexample to sharp failure-mode specificity**: on the real robot its
  generic interface fix raises lighting/camera/distractor success by +16.7/+16.7/+13.3. It is
  also open code + weights + data (Apache-2.0), unlike every paper C1 would reuse.
- **Headroom confound**: across LIT's four architectures on the same camera perturbation, gain
  tracks (1 - baseline): +27.43 at 16.40, +22.01 at 58.29, +9.01 at 39.40, +2.39 at 82.16.
  C1 must beat a headroom null model, not just a task-difficulty model. This is now H5, a stop
  condition, and part of gate 5.
- **2512.02902 is one-shot adaptation**: gate 4 now requires equal data budget for the
  alignment control.
- **RRDF (2610.02813)** registered abstract-only as C2's ACT-scale nearest neighbour.

### Deliverable state
- Registry 101 (34 full / 25 partial / 42 abstract). Report, executive summary, self-audit,
  nearest-neighbour review, search log and completion JSON all updated.
- Conclusion unchanged: C1 is the only surviving candidate, 3.1 (ceiling), conditional.
- No experiments, no downloads of weights/data, no installs.

### Remaining unknowns
- 42 abstract-only papers could hide a competitor (crowding judgement only).
- S2 has indexing lag for very recent papers, so "0 citing" is weak for 2026-10+ work.
- C1's core premise (constructing same-task/different-failure-mode variants) is still untested
  and can only be answered by an authorized experiment.
