# 2609.12641 — Breaking the Vision–Action Shortcut (LIT), and 2610.02813 (RRDF)

Read 2026-11-05 for the pass-7 competitor screen. Both papers were found earlier in the raw
search dumps and one of them had a downloaded full text that was never registered. Recording
them here because they change the competitor field for C1 (shortcut dependence) and C2
(evidence use), and because LIT is the best-resourced competitor in this whole scope.

## 2609.12641 — Latent Interface Training (LIT)

- Title: *Breaking the Vision–Action Shortcut: Latent Interface Training for Generalizable
  Robotics Foundation Models*
- Authors: Jianman Lin, Shailesh Shailesh, Zhongyi Luo, Jiafei Duan (SCUT / NUS / NTU)
- Posted: 2026-09-11. arXiv only at retrieval (no OpenAlex conference record checked; the
  arXiv page carries no journal ref).
- Read level: FULL_TEXT (arXiv HTML rendering, `papers/2609.12641__breaking_vision_action_shortcut.txt`).

### What it claims

Standard VLA/WAM training lets backbone visual tokens condition the action expert directly, so
the expert can latch onto visual cues that correlate with actions in-distribution ("vision–action
shortcut"). LIT removes that route and forces all visual conditioning through 100 learnable
latent tokens supervised to reconstruct the chunk's terminal SE(3) goal. Stage 1 trains an
image-free action prior conditioned on language, state and terminal pose; Stage 2 trains the
interface. Applied unchanged to π0.5, MolmoAct2 (VLAs) and FAST-WAM, ImageWAM (WAMs).

### Numbers I will use (with locations)

| Claim | Value | Location |
|---|---|---|
| Overall LIBERO-Plus gain, four architectures | +3.87 … +10.70 pp | Abstract; §IV-C |
| Per-architecture overall | π0.5 68.97→79.67; MolmoAct2 63.62→71.92; FAST-WAM 51.44→60.63; ImageWAM 83.02→86.89 | §IV-C |
| Camera-viewpoint cell, π0.5 | 58.29→80.30 (+22.01) | Table II |
| Camera-viewpoint cell, ImageWAM | 82.16→84.55 (+2.39) | Table II |
| Camera-viewpoint cell, FAST-WAM | 16.40→43.83 (+27.43) | Table II |
| Camera-viewpoint cell, MolmoAct2 | 39.40→48.41 (+9.01) | Table II |
| Comparisons improved | 26 of 28, no decrease > 2.11 pp | §IV-C |
| Real robot, aggregated | ID 74.7→88.0; lighting OOD 53.3→70.0; camera OOD 30.0→46.7; distractors OOD 50.0→63.3 | §IV-D, Fig. 6 |
| Real-robot protocol | 300 demos (100/task); 25 ID rollouts/task; 10 rollouts/task per OOD condition | §IV-D |
| Goal-change counterfactual | baseline keeps going to the original goal; LIT redirects | §IV-E1, Fig. 5 |

### Why it matters for this investigation

1. **It is a C2 direct competitor.** Fig. 5's goal-changing intervention (change the instructed
   goal, hold scene and state fixed) is the same manipulation C2 proposes, and the reported
   baseline behaviour — continuing toward the original goal — is exactly the "acquired evidence
   does not change the executed decision" phenomenon. LIT then *fixes* it with an interface
   change. This is one more reason C2 is a method transfer, not a new question.

2. **It is a counterexample to the sharp form of C1's H1.** More Structure shows a targeted
   spatial intervention fixing Near-Miss and leaving No-Grasp untouched. LIT shows the opposite
   pattern for a generic interface fix: on the real robot the three OOD conditions improve by
   nearly the same amount (+16.7 lighting, +16.7 camera, +13.3 distractors). So "an intervention
   fixes the failure mode it addresses" is not a general law; a generic robustness intervention
   can move every axis at once. C1 must therefore contrast a *targeted* intervention with a
   *generic* one on the same tasks, otherwise any observed gain can be attributed to generic
   robustness.

3. **It supplies a headroom illustration.** Across four architectures on the same camera
   perturbation, the gain ranges from +2.39 (baseline already 82.16) to +27.43 (baseline 16.40).
   This is consistent with gains being bounded by headroom, (1 − baseline). Any predictor of
   "where a spatial upgrade pays" must beat the trivial headroom model, not just a
   task-difficulty model. This is the sharpest new confound found in pass 7.

4. **It narrows the "do an interface" space further.** LIT joins 2608.03052 (proprioceptive
   state interfaces) and 2512.02902 (token modulation) as published, systematically ablated
   interface interventions. The empirical message is that interface choice matters a lot and is
   already being mapped out by others.

### Assets (read-only check, 2026-11-05)

- Project page <https://magiclab-nus.github.io/LIT/> (HTTP 200).
- Code: <https://github.com/MAGICLAB-NUS/LIT>, Apache-2.0 per the README badge and `LICENSE`.
  The README is an integration manual: six steps, named coupling layers and file paths for four
  host architectures (`mask_image_from_action_expert` in MolmoAct2's LeRobot policy, attention
  mask in π0.5, `goal_prior_stage` configs in FAST-WAM, `backbones/imagewam.py`), plus a
  "three checks" section for silent failures.
- Weights: Hugging Face `shailes-h/Molmoact2-LIT` (real-robot checkpoints); README states public,
  no login needed.
- Data: Hugging Face `shailes-h/yam_bimanual_manipulation`.
- **Contrast that matters for feasibility**: LIT — the closest thing to a turnkey "fix the
  visual shortcut" recipe in this scope — is open code + weights + data, while the four papers
  C1 would reuse (More Structure, LIBERO-RIG, 2610.01626, 2512.02902) publish no URL at all.
  The reproducible half of this literature is the interface-modification half, which is also the
  half where novelty is exhausted. That is a structural argument against both "build another
  interface" and "reuse someone's measurement protocol".

### Limits of this reading

- Table II's HTML extraction splits cells across lines; the four camera-viewpoint cells above
  were read individually and cross-checked against §IV-C's prose (which repeats π0.5's +22.01,
  MolmoAct2's +21.74 sensor-noise etc.). Other cells were not transcribed.
- Real-robot evidence is 25 rollouts/task ID and 10/task OOD — the same small-sample regime
  flagged elsewhere in the report.
- LIT's four host models are 4B-class; nothing here says the effect transfers to an ACT/DP-scale
  policy on a 3090, which is the regime C1 would use.

## 2610.02813 — Register-Routed Delayed Fusion (RRDF)

- Title: *Register-Routed Delayed Fusion: Rewiring Shortcut-Prone Observation Fusion in
  Visuomotor Imitation*
- Authors: Jieting Long, Weidong Cai, Weiming Zhi. Posted 2026-10-02.
- Read level: ABSTRACT_ONLY (abstract from Semantic Scholar record; arXiv abs page checked
  2026-11-05). No full text downloaded.
- Claim: fusion topology decides when visual and compact (proprioceptive) tokens interact;
  dense fusion lets compact cues leak into visual representations early. RRDF masks direct
  compact–visual attention and stages interaction through a learned register workspace. Five
  simulation + three real tasks; matches or improves dense ACT nominally and under appearance
  shift / held-out positions; "phase-matched input probes show lower measured state-to-image
  sensitivity"; registers alone do not reproduce the gain.
- Why registered: it is a *measurement + intervention* pair aimed at exactly the sensitivity
  question C2 would ask ("does the policy actually use the visual evidence?"), and it does so on
  ACT-scale policies (the regime the researcher can run), not 4B VLAs. If C2 were ever revived,
  this is its nearest neighbour and must be cited. It does not change C2's verdict: C2 is
  already at importance 1 and is not a short-paper candidate.
- Assets: UNKNOWN (not checked; abstract-only).
