#!/usr/bin/env python3
"""Build sources/papers.jsonl from retrieved arXiv metadata plus hand-written
annotation records. Annotations were written after reading the stored full text;
`read_level` reflects what was actually opened, not what was hoped for."""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

meta = {}
for f in glob.glob(os.path.join(ROOT, "notes", "arxiv_round*.jsonl")):
    for line in open(f):
        r = json.loads(line)
        meta.setdefault(r["id"].split("v")[0], r)

# id: (read_level, verification, topic_tags, evidence_locations, relation, annotation, code, weights, data, evalentry, license)
A = {
"2510.02268": ("FULL_TEXT", "VERIFIED", ["A_cross_view", "F_user_baseline"],
  "Abstract; Table I (six-task success rates); §IV-A.4 action space; §IV-A.7 view scaling; Fig. 13 real-robot 21 rollouts",
  "User's prior baseline; direct competitor in category A; asset-dependency case",
  "Conditions ACT/DP/SmolVLA on per-pixel Plucker ray maps. Gains are strongly task-dependent: ACT +27.0pp on Lift but only +1.0pp on RollBall and +4.2pp on PickPlaceCan; absolute ACT success ranges 10.8% (AssemblySquare) to 33.6% (Lift). Real-robot evaluation uses 21 rollouts per setting and a custom 'half-success' criterion. No limitations section. Repository ships code, demo-collection and reproduce configs but no checkpoints.",
  "https://github.com/ripl/CamPoseOpensource", "NOT_RELEASED (no checkpoint in repo; training from scratch)",
  "Released tasks + demonstrations via setup.sh", "reproduce/reproduce.py keyed by figure and seed", "MIT"),

"2610.12696": ("FULL_TEXT", "VERIFIED", ["E_diagnosis", "B_action_grounding"],
  "Abstract; §VII Limitations; Fig. 11 failure-mode composition; §VI discussion",
  "Closest real-robot evidence that spatial grounding is separable from manipulation execution",
  "Six tabletop tasks on SO-101, 4,092 episodes. Matched-scene design holds the physical action fixed while swapping a direct instruction for an OOD spatial instruction. ID 67.5-73.3% falls to OOD 40.7-52.0%; matched direct instructions recover 28.3-40.0pp. Failure taxonomy separates wrong instance, grasp failure, control drift, incorrect spatial outcome, no-action. Limitations: one embodiment, <=5 objects, non-identical resets, zero-shot no-action conditions.",
  "https://justintiensmith.github.io/Spa-Bench/", "UNKNOWN", "Dataset page stated as available; not downloaded here",
  "Benchmark data + rollouts stated", "UNKNOWN"),

"2609.37292": ("FULL_TEXT", "VERIFIED", ["D_active_perception", "C_occlusion"],
  "Abstract; §4 acquisition-exploitation gap discussion; Table 2 (SR/CVG); §5.4 viewpoint-stabilisation ablation",
  "Direct competitor for any 'use what you looked at' candidate; supplies the key negative result",
  "BAVO-Bench bimanual occlusion benchmark plus A-FAR. Reports an acquisition-exploitation gap: high visibility-recovery (CVG) does not imply task success. Expressing observations in the moving camera frame drops average SR from 41.0 to 28.0 (ManiFlow) and 44.7 to 27.0 (A-FAR), i.e. viewpoint-stable geometry is a prerequisite for using temporal cues.",
  "UNKNOWN (paper does not state a public repo in the extracted text)", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.23891": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; §5 Expected Contributions; §6 Conclusion",
  "Evidence that 'when is evidence sufficient' is an openly posed problem - but this is a proposal",
  "Position/architecture proposal for task-sufficient active perception on a mobile manipulator. No experiments, no results; evaluation is described in future tense. Useful only as evidence that the question is recognised as open, not as evidence about it.",
  "NONE", "NONE", "NONE", "NONE", "N/A"),

"2609.24124": ("FULL_TEXT", "VERIFIED", ["C_memory", "D_active_perception"],
  "Abstract; Table 8 (proprioceptive conditioning); Table 9 (action heads); §4.3 memory write policy",
  "Raises the bar for memory/active-perception candidates; exposes confound sizes",
  "ActiveArena-Sim + 35-task benchmark + 13 VLA configurations. Findings: uniform temporal memory sampling generalises better OOD than event-triggered writing; larger memory is not inherently better; explicit proprioceptive state raises ID 50.86->62.97 and OOD 16.86->47.60. Action head choice alone moves success 62.97 / 40.00 / 22.34 (OFT / GR00T / FAST), larger than many 'spatial module' effects.",
  "https://leeibo.github.io/ActiveArena", "UNKNOWN", "Stated open-source", "Stated open-source", "UNKNOWN"),

"2609.32762": ("FULL_TEXT", "VERIFIED", ["A_cross_view"],
  "Abstract; contributions list; Tables VI-VII (randomisation ranges)",
  "Strongest 'simple recipe already solves viewpoint generalisation' counterexample",
  "Explicitly 'deliberately not a new architecture': dense visual tokens + geometry-foundation-model backbone + robot-frame rotary positional encoding of vision, proprioception and action. Zero-shot sim-to-real transfer under random cameras. Each component is prior work; contribution is isolating which ingredients matter. Undercuts claims that a new cross-view module is a scientific contribution.",
  "https://vgp-sim2real.github.io/", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2603.26757": ("PARTIAL_TEXT", "VERIFIED", ["A_cross_view"],
  "Abstract only in this reading pass",
  "Competing framing: multi-view demonstrations as the data-side answer to viewpoint generalisation",
  "Asks what multi-view demonstrations offer and how to synthesise them. Relevant as a direct competitor to view-robustness method papers; not read in full, so claims are limited to the abstract.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.38104": ("FULL_TEXT", "VERIFIED", ["measurement_confound", "action_interface"],
  "Abstract; §VIII-A matching level and attribution; Fig. 3 and Fig. 4",
  "Core methodological warning for any action-level comparison",
  "Same nominal action-space label can denote different executed controllers. Changing only the physical action scale changes sample-median success by 0.645-1.000 across PegInsert/GearMesh/NutThread with 10 independently trained policies per condition. Even matched local command gain does not equalise trained-policy outcomes. Rule: report the executed pathway and state the physical quantity being matched.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.23408": ("FULL_TEXT", "VERIFIED", ["action_interface"],
  "Abstract; §4.3; §5 practical guidelines",
  "Confound magnitude for action-space choices",
  "13,000+ real-world rollouts, 500+ trained models. Delta actions consistently better temporally; joint space more robust spatially for single-platform performance; task space better for cross-embodiment transfer. Shows action representation is a first-order experimental variable, not an implementation detail.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.35039": ("FULL_TEXT", "PARTIALLY_VERIFIED", ["D_active_perception"],
  "Abstract; Table II; §VI",
  "Excluded from evidence: metadata/PDF title mismatch, no results",
  "arXiv metadata title is 'Do Not Cut When Uncertain: Rejectable and Calibrated Decision Heads...' but the PDF at the same identifier is titled 'SeeReach-VLA: Sign-Aware Edge Deployment for Vineyard Harvesting under Occlusion'. The PDF ends with '[Results to be reported in the final version.]'. Recorded as a corpus integrity anomaly; no claim relies on it.",
  "NONE", "NONE", "NONE", "NONE", "N/A"),

"2609.06114": ("FULL_TEXT", "VERIFIED", ["E_diagnosis", "failure_boundary"],
  "Abstract; Table 2; §5 Limitation; §6 Conclusion",
  "Example of failure-boundary learning; not spatial-specific",
  "Digital-twin on-policy rollout pipeline that labels progress phases and shapes flow-matching velocity fields. Reports 84.4/72.2 (ID/Unseen) on pi0.5. Requires a high-fidelity digital twin per task - a heavy asset dependency for a master's project.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.05376": ("FULL_TEXT", "VERIFIED", ["E_diagnosis", "B_action_grounding"],
  "Abstract; final limitations paragraph before references",
  "Closest small-scale 'diagnose then intervene' template; also a caution about cell sizes",
  "Conditional visual grounding: which entity matters depends on manipulation phase. Controlled ACT experiments vary object/receptacle competitors, localise failures to pick vs place, then apply distractor augmentation, phase-dependent attention regularisation and visual prompting; validated on a UR3e. Limitations: 20 hardware trials per cell, correlational representation analyses, five VLA trials per subgoal.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2606.02277": ("FULL_TEXT", "VERIFIED", ["E_diagnosis"],
  "Abstract; §6 Table 5; §7 Discussion",
  "Decomposition template: grasp success vs target selection",
  "RoboSemanticBench turns multiple-choice questions into answer-block grasping, then separates Grasp Success Rate from Target Selection Rate. QwenGR00T chooses the wrong target in 95.92% of grasp-success/task-failure cases; ReasoningVLA has an incorrect chain-of-thought in only 6.70% of such cases, i.e. correct reasoning with wrong action is the dominant failure.",
  "https://github.com/ZGC-EmbodyAI/RoboSemanticBench", "UNKNOWN", "Benchmark data", "UNKNOWN", "UNKNOWN"),

"2605.30161": ("FULL_TEXT", "VERIFIED", ["E_representation_probe"],
  "Abstract; Table 5; §6 Conclusion",
  "Representation-level diagnostic that stops short of action",
  "Probes vertical-distance entanglement in VLMs and introduces SpatialTunnel to remove perspective correlations. Shows representational structure predicts benchmark accuracy - but all outcomes are VQA accuracy, never robot action success. This is the exact gap a spatial-action paper would have to bridge.",
  "UNKNOWN", "UNKNOWN", "Synthetic benchmark stated", "UNKNOWN", "UNKNOWN"),

"2601.09954": ("FULL_TEXT", "VERIFIED", ["E_representation_probe"],
  "Abstract; §1 contributions",
  "Architectural claim about spatial blindness in VLMs",
  "Argues 1D RoPE and CLIP-style encoders discard 2D structure; shows alternative encoders and 2D positional encodings improve spatial benchmarks. Again benchmark-level only, no robot action endpoint.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2605.30557": ("PARTIAL_TEXT", "VERIFIED", ["E_representation_probe"],
  "Abstract only",
  "Awareness/abstention of VLMs on spatial questions",
  "Asks whether VLMs know when not to answer spatial questions. Relevant to but not evidence about robot action; abstract-level only in this pass.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.38285": ("PARTIAL_TEXT", "VERIFIED", ["E_representation_probe"],
  "Abstract; §4.3 ablations; §5 Conclusion",
  "Example of measured geometric interventions used as training signal",
  "GaugeVLM builds preference margins from measured geometric error plus intervention profiles that link answer-odds changes to geometric magnitude. Improves spatial benchmarks across three backbones and transfers to unseen magnitudes. Note: AI-assistance statement discloses use of Claude-Fable-5 and GPT-6-Astra for editing, literature retrieval and synthetic data generation.",
  "UNKNOWN", "UNKNOWN", "Synthetic scene data described", "UNKNOWN", "UNKNOWN"),

"2606.03943": ("PARTIAL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract only",
  "Point-dynamics as an action interface - category B competitor",
  "Fine-tunes a video model to predict RGB plus dynamic 3D pointmaps; point dynamics are the embodiment-agnostic interface to a diffusion action decoder. Abstract-level only.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.24674": ("FULL_TEXT", "VERIFIED", ["B_geometry_robustness", "E_diagnosis"],
  "Abstract; Fig. 4 (real robot, N=30 per task/method); limitations paragraph",
  "Shows a depth-noise cliff and that matched noisy training only partially recovers",
  "3D policies treat corrupted depth as reliable. NISE adds cross-view geometric self-supervision and Gaussian-marginalised 3D attention. Real-robot comparisons DP3 / 3DDA / RVT-2 vs NISE with N=30 trials per task. Residual failure: multi-view-consistent wrong surfaces (transparent objects) are not fixed.",
  "https://nise-robotics.github.io/", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2608.01826": ("PARTIAL_TEXT", "VERIFIED", ["A_cross_view", "B_spatial_interface"],
  "Abstract only", "Multi-camera action-facing representation competitor",
  "Multi-view unified camera fields as geometry-shaped action-facing representations for RGB-only multi-camera VLA policies. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2608.01066": ("PARTIAL_TEXT", "VERIFIED", ["A_cross_view"],
  "Abstract only", "Direct competitor to cross-view consistency methods",
  "Monocular-geometry-guided cross-view consistency for viewpoint-robust manipulation. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2607.11498": ("FULL_TEXT", "VERIFIED", ["A_cross_view", "B_spatial_interface"],
  "Abstract; §I introduction",
  "Robot-centric pointmap result: large gains, directly relevant to frame-choice questions",
  "SeeR-VLA lifts depth to pointmaps and transforms them into an end-effector-origin, robot-base-aligned frame; adds pointmap features to RGB tokens without extra tokens. +6.4pp average over RGB-only pi0.5 across 24 RoboCasa tasks and +32.5pp across four real tasks; beats PointVLA by 3.5 and 23.7pp. End-effector centring with base-aligned axes works best; benefit grows with viewpoint diversity.",
  "Project page referenced in paper", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2607.09825": ("FULL_TEXT", "VERIFIED", ["B_representation", "E_diagnosis"],
  "Abstract; contributions list",
  "Closest precedent for oracle upper bounds and failure taxonomies at small scale",
  "Frozen encoder comparison on ManiSkill3 PickCube-v1: object-centric slots 55.0+-2.9% vs dense DINO global feature 32.6+-1.5%; adding a 2D spatial goal and native rendering reaches 68.7+-4.2%, just below a privileged 3D-oracle bound of 71.7+-4.1%. An automated kinematic failure taxonomy separates Near-Miss (spatial precision) from No-Grasp (object tracking); spatial grounding reduces Near-Miss but leaves No-Grasp unchanged.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2606.15232": ("PARTIAL_TEXT", "VERIFIED", ["B_representation"],
  "Abstract only", "Direct competitor on implicit spatial representation in visuomotor policies",
  "Rethinks implicit spatial representation in visuomotor policy learning. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2603.13033": ("FULL_TEXT", "VERIFIED", ["E_diagnosis"],
  "Abstract; §5.5 frame-of-reference analysis; §5.6 efficiency; §6 Discussion; §7 Conclusion",
  "Simulated diagnostic benchmark decoupling localisation from execution; evidence on reference-frame deficits",
  "ESPIRE reformulates spatial tasks as localisation + execution so VLMs that cannot emit low-level actions can still be diagnosed. Finds humans prefer the intrinsic frame of a near reference object while models default to the relative frame. Reports ~9.25 s per VLM inference and ~18.12 s per move request on a 4090 - useful for cost planning.",
  "The paper states code availability; not independently confirmed", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.07047": ("FULL_TEXT", "VERIFIED", ["C_memory"],
  "Abstract; benchmark design sections",
  "Process-level memory benchmark; part of the crowded memory-evaluation space",
  "MEMOBench evaluates memory at process level rather than only end success. Included as a direct competitor to any memory-diagnosis candidate.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2603.04639": ("FULL_TEXT", "VERIFIED", ["C_memory"],
  "Abstract; benchmark sections",
  "Memory benchmark for generalist policies",
  "RoboMME benchmarks and analyses memory for robotic generalist policies. Part of the crowding evidence for category C.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2608.23138": ("FULL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract; execution-contract description",
  "Typed spatial readout interface; strong action-level numbers",
  "Pointing-VLA replaces text coordinates with typed heads (points, object-functional grounding heatmaps, trajectories). 72.9% average on Bridge/WidowX four-task set without Bridge finetuning under collision-enabled CuRobo execution; as spatial guidance for pi0.5 raises real-robot success 52.7% -> 80.7% across three visual contexts; typed heads 6.68-6.90x faster than text decoding.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.24705": ("PARTIAL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract only", "Relational spatial alignment competitor",
  "Relational spatial alignment for VLA models. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.22997": ("PARTIAL_TEXT", "VERIFIED", ["A_cross_view"],
  "Abstract only", "Geometric conditioning competitor",
  "GR-VIP: geometric representation conditioning for precise visuomotor policy. Abstract-level only; HTML fetch was rate-limited.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.23396": ("PARTIAL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract only", "Active view imagination competitor",
  "AWAM: active trajectory-conditioned view imagination for robust manipulation. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2608.05730": ("FULL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract; results paragraph",
  "Shows spatial anchors change executed motion - a useful positive control for 'does spatial input change action'",
  "XR-authored visual intent anchors rendered into the RGB observation. 91.25% success with intended anchors vs 77.5% with random anchors vs 50% no-anchor on 80 held-out Unity episodes; the policy redirects motion to arbitrary anchors, showing it uses anchor position rather than appearance. Small n, Unity-only.",
  "UNKNOWN", "UNKNOWN", "200 demonstrations collected by authors", "UNKNOWN", "UNKNOWN"),

"2604.21241": ("FULL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract; results",
  "Explicit spatial tolerance region in training objective",
  "CorridorVLA predicts sparse spatial anchors as incremental physical changes and imposes a tolerance corridor on a flow-matching action head. +3.4-12.4% over SmolVLA/GR00T on LIBERO-Plus, 83.21% for GR00T-Corr. Notably uses the word 'tolerance' for a *permitted deviation region*, not for task difficulty.",
  "https://github.com/corridorVLA", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2606.26800": ("PARTIAL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract only", "Structured scene interface competitor",
  "SSI-Policy learns structured scene interfaces for vision-language manipulation. Abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.15572": ("PARTIAL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract only", "Agent-interface-aligned supervision for mobile manipulation",
  "Look Before You Move. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2607.01658": ("FULL_TEXT", "VERIFIED", ["F_attention_steering"],
  "Abstract; results", "Direct competitor on 'where to look' supervision",
  "Teaches VLA models what to see and where to look. Included as a direct competitor for attention/grounding supervision candidates.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.04139": ("FULL_TEXT", "VERIFIED", ["E_representation_probe"],
  "Abstract; experiments", "Predictive spatial reasoning in VLMs; benchmark-level",
  "From Sight to Foresight studies predictive spatial reasoning in vision-language models. Benchmark-level, not action-level.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.07082": ("PARTIAL_TEXT", "VERIFIED", ["F_on_device_reasoning"],
  "Abstract only", "On-device visual spatial reasoning via iterative space representation",
  "MosaicThinker. Abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2512.02902": ("FULL_TEXT", "VERIFIED", ["E_evaluation_claim"],
  "Abstract; experiments", "Counter-claim to 'VLAs lack spatial modelling'",
  "Argues VLA models are more generalizable than assumed when physical and spatial modelling are evaluated properly. Important as a counterexample to deficit-framing papers.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2406.10721": ("FULL_TEXT", "VERIFIED", ["B_affordance"],
  "Abstract; method; experiments", "Foundational spatial-affordance VLM",
  "RoboPoint: a VLM for spatial affordance prediction, predicting valid placement/grasp points. Foundational reference for point-based spatial affordance interfaces.", "https://github.com/wentaoyuan/RoboPoint", "Stated released", "Stated released", "UNKNOWN", "UNKNOWN"),

"2411.16537": ("FULL_TEXT", "VERIFIED", ["E_benchmark"],
  "Abstract; dataset design", "Spatial-understanding training/eval for 2D and 3D VLMs",
  "RoboSpatial teaches spatial understanding to 2D and 3D vision-language models for robotics. Foundational benchmark/dataset reference.", "https://github.com/NVlabs/RoboSpatial", "Stated released", "Stated released", "UNKNOWN", "UNKNOWN"),

"2401.12168": ("FULL_TEXT", "VERIFIED", ["E_benchmark"],
  "Abstract; data generation; experiments", "Origin of internet-scale spatial VQA supervision",
  "SpatialVLM endows VLMs with spatial reasoning via automatically generated 3D spatial VQA data. Foundational; benchmark-level endpoint.", "https://github.com/remyxai/SpatialVLM", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.34051": ("FULL_TEXT", "VERIFIED", ["E_benchmark"],
  "Abstract; benchmark design", "Spatial-understanding benchmark for robotics",
  "BEHAVIOR-Spatial Benchmark evaluates spatial understanding for robotics. Part of the crowding evidence in category E.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2606.03240": ("PARTIAL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract only", "State-guided spatial alignment competitor", "GeoAlign. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2608.24959": ("PARTIAL_TEXT", "VERIFIED", ["B_geometry"],
  "Abstract only", "Geometry-aware spatial reasoning VLA", "GaussVLA. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.13812": ("PARTIAL_TEXT", "VERIFIED", ["B_geometry"],
  "Abstract only", "Unified 3D scene/motion/action VLA", "GeomVLA. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.24525": ("PARTIAL_TEXT", "VERIFIED", ["B_geometry"],
  "Abstract only", "3D-enabled VLA", "Bridge3D. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2605.29416": ("PARTIAL_TEXT", "VERIFIED", ["B_geometry"],
  "Abstract only", "3D spatial/instance understanding for VLA", "3DVLA. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2501.15830": ("FULL_TEXT", "VERIFIED", ["B_geometry", "F_foundation"],
  "Abstract; method; experiments", "Representative 'spatial representation for VLA' baseline",
  "SpatialVLA explores spatial representations (Ego3D position encoding, adaptive action grids) for VLA models. Representative of the large 3D-VLA family and a required baseline for any representation claim.", "https://github.com/SpatialVLA/SpatialVLA", "Stated released", "Stated released", "UNKNOWN", "UNKNOWN"),

"2510.12276": ("PARTIAL_TEXT", "VERIFIED", ["B_geometry"],
  "Abstract only", "Implicit spatial representation alignment", "Spatial Forcing. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2508.15874": ("PARTIAL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract only", "Spatial-aware modelling and reasoning for manipulation",
  "Spatial Policy. Abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2611.05058": ("PARTIAL_TEXT", "VERIFIED", ["F_geometric_abstraction"],
  "Abstract only", "Latest (cutoff-adjacent) geometric abstraction for agentic policies",
  "Asks whether agentic policies need to look at every step. Dated 2026-11-03, two days before the cutoff; abstract-level only, so no strong claim is made about it.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.27734": ("PARTIAL_TEXT", "VERIFIED", ["A_cross_view"],
  "Abstract only", "Novel-view augmentation competitor", "InfiNoVA. Abstract-level only.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.11508": ("PARTIAL_TEXT", "VERIFIED", ["A_cross_view"],
  "Abstract only", "Wrist-camera adaptation for view robustness", "WARP-VLA. Abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2607.05396": ("FULL_TEXT", "VERIFIED", ["A_cross_view", "calibration"],
  "Abstract; method description", "Calibration-free alternative to explicit extrinsics",
  "CamVLA predicts camera-centric end-effector actions plus a 6-DoF hand-eye matrix, composing them deterministically into a base-frame action. Calibration-free, depth-free, single-view. Directly relevant to any candidate about extrinsics: it removes the need to be told the extrinsics at all.",
  "https://alibaba-damo-academy.github.io/CamVLA/", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.23252": ("PARTIAL_TEXT", "VERIFIED", ["action_interface"],
  "Abstract only", "Evidence that world models are sensitive to action parameterisation",
  "Robot world models are not invariant to how actions are written. Supports the action-interface confound argument; abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.23378": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; experiments", "Observation-aligned data adaptation for active perception",
  "Look Before You Act bridges active perception and VLA models via observation-aligned data adaptation. Direct competitor in category D.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2603.12193": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; experiments", "Active perception and manipulation in VLA",
  "SaPaVe: active perception and manipulation in vision-language-action models. Direct competitor in category D.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2601.08325": ("PARTIAL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract only", "Active perception injected into VLA", "ActiveVLA. Abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.18514": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; scaling experiments", "Scaling study of active perception",
  "ActiveScale scales active perception across model, data and hardware. Useful evidence about how much of the gain is data/compute rather than mechanism.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.04600": ("PARTIAL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract only", "Learning active perception from egocentric human data",
  "Act, Sense, Act. Abstract-level only (HTML fetch rate-limited).", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2506.15666": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; experiments", "Active perception from human demonstrations",
  "Vision in Action learns active perception from human demonstrations. Direct competitor in category D.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.27247": ("FULL_TEXT", "VERIFIED", ["decision_audit", "C_memory"],
  "Abstract; Table 3; §V Discussion",
  "Closest methodological precedent to any decision-level audit; also supplies the seed-noise caution",
  "Counterfactual Memory Audit crosses two histories at a verified-identical present and queries a frozen policy under common randomness. On Mem-0 every audited Put Back pair changes action but only 20/64 pairs are fully reliable; on hardware, five of nine completed Put Back manipulations reach the wrong target. Critically: action-seed variation (0.0674 rad joint RMS) is much larger than the memory-swap difference (0.0076 rad), so an intervention can be smaller than run-to-run noise.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2604.18000": ("FULL_TEXT", "VERIFIED", ["E_diagnosis", "decision_audit"],
  "Abstract; §6.3 causal interventions; §7 Conclusion",
  "Causal-intervention benchmark showing behavioural inertia and proprioceptive overfitting",
  "BeTTER isolates high-level cognitive breakdowns from motor limits. Under targeted causal interventions, policies perform 'air grasps' at expected object locations and freeze on contradictory visual/proprioceptive state, i.e. they rely on sequential priors rather than verifying the scene.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.28955": ("FULL_TEXT", "VERIFIED", ["decision_audit", "attention"],
  "Abstract; Table V", "Counterfactual visual intervention used as supervision",
  "ActGaze learns action-grounded gaze through counterfactual visual interventions. On LEGO assembly, pi0.5 13/20 -> ActGaze 15/20 under clutter, but both 11/20 under strong lighting change. Small cells; gain is specific to spatial distractors, not global appearance.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2606.16667": ("FULL_TEXT", "VERIFIED", ["abstention"],
  "Abstract; §1", "Three-way answer/abstain/acquire decision under a compute budget",
  "Budgeted Conformal Evidence Acquisition replaces binary abstention with answer / abstain / acquire more visual evidence. Notes that naive acquisition breaks the conformal guarantee (risk overshoot up to 17 points) and that a single horizontal-flip intervention lifts spatial-relation verification AUROC from 0.57 to 0.77. VLM benchmark, not robot action.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2605.20544": ("FULL_TEXT", "VERIFIED", ["abstention"],
  "Abstract; taxonomy; results", "Embodied abstention benchmark",
  "RoboAbstention builds 6,069 instructions with verifiable abstention conditions. Best model Gemini 2.5 Flash abstains on only 39.0%; embodied planner 16.5%; defensive prompting lifts to 93.6% but does not solve it. VLM planner level, not low-level action.",
  "https://purseclab.github.io/RoboAbstention", "UNKNOWN", "Stated open-source", "UNKNOWN", "UNKNOWN"),

"2607.13618": ("FULL_TEXT", "VERIFIED", ["decision_audit"],
  "Abstract; §5", "Perception-action gap with a fair Bayes-filter oracle",
  "STOCKTAKE is a 26-week supply-chain POMDP with an exact Bayes-filter reference policy on the same observation stream. Models detect 84-88% of hidden failures yet two of four fall below the symptom-blind floor - a knowing-doing gap. Domain is not robotics, so it is methodological evidence only.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2605.18746": ("FULL_TEXT", "VERIFIED", ["E_benchmark", "D_active_perception"],
  "Abstract; task taxonomy; findings", "Closest benchmark to 'spatial evidence must be acted on'",
  "ESI-Bench (OmniGibson, 10 categories / 29 subcategories) forces perception-locomotion-manipulation sequencing. Finds active exploration beats passive, random multi-view adds noise, failures are mostly 'action blindness' (poor actions -> poor observations), imperfect 3D grounding can be worse than 2D, and models commit prematurely with high confidence unlike humans who seek falsifying views. Public data and eval scripts stated.",
  "https://esi-bench.github.io/", "UNKNOWN", "Stated public", "Stated public", "UNKNOWN"),

"2609.30833": ("FULL_TEXT", "VERIFIED", ["planning_execution"],
  "Abstract; experiments", "Planning-execution gap in hierarchical VLA",
  "Fast Plans, Faithful Actions targets the planning-execution gap in hierarchical VLA. Direct competitor for any 'decision changes but execution does not' framing.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.22299": ("FULL_TEXT", "VERIFIED", ["decision_audit"],
  "Abstract; six-condition chain", "Strongest evidence that acquired evidence can be informative but unused",
  "Defines six ordered conditions for test-time physical diagnosis to pay off. After transfer to unseen mechanisms the chain breaks at evidence use: a frozen decoder does not change its choice even when the full trace is available, while a linear model on trace increments recovers the correct choice on held-out mechanisms. Failure concentrates at the richest evidence level.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.13516": ("FULL_TEXT", "VERIFIED", ["runtime_monitoring"],
  "Abstract; evaluation design", "Counterfactual evaluation of runtime monitors",
  "RESCUE asks whether an alarm is worth acting on and evaluates VLA runtime monitors counterfactually. Direct competitor for 'should the robot stop/re-observe' candidates.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.04243": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; experiments", "Viewpoint optimisation with MAE",
  "Viewpoint Matters dynamically optimises viewpoints with a masked autoencoder for visual manipulation. Direct competitor in category D.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2511.17001": ("FULL_TEXT", "VERIFIED", ["action_interface", "A_cross_view"],
  "Abstract; experiments", "Camera-frame action unification",
  "Unify Robot Actions in Camera Frame argues for expressing actions in the camera frame. Competes directly with base-frame/robot-frame action interfaces; abstract-level claims only in this pass.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2506.06196": ("FULL_TEXT", "VERIFIED", ["B_spatial_interface"],
  "Abstract; experiments", "Spatially grounded mid-level representations",
  "Bridging Perception and Action studies spatially grounded mid-level representations for robot generalisation. Direct competitor for 'representation between perception and action' claims.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2611.03937": ("FULL_TEXT", "VERIFIED", ["E_diagnosis"],
  "Abstract; method", "Counterfactual imagination training for spatial intelligence",
  "FlowBench uses counterfactual imagination training for spatial intelligence. Dated 2026-11-02, inside the cutoff window; included as crowding evidence.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2608.13605": ("FULL_TEXT", "VERIFIED", ["D_active_perception"],
  "Abstract; experiments", "Active perception for disambiguation",
  "Active Perception for Embodied Disambiguation. Direct competitor for 're-observe to disambiguate' candidates.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.06556": ("FULL_TEXT", "VERIFIED", ["robustness_benchmark"],
  "Abstract; §1", "Hierarchical spatial-generalisation benchmark",
  "LIBERO-X adds progressive difficulty levels for spatial generalisation, object recognition and instruction understanding, plus a more diverse teleoperated training set. Shows large drops under cumulative perturbations.", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.18843": ("FULL_TEXT", "VERIFIED", ["robustness_benchmark"],
  "Abstract; Fig. 1; severity definitions", "Closest existing dose-response robustness benchmark",
  "LIBERO-RIG perturbs only robot hardware and setup across 11 axes x 5 severity levels x 4 suites, 500 episodes per condition, nine VLA models. Pooled success 0.932 -> 0.767 at middle severity -> 0.509 at highest. Reports that training on visual perturbations does not mitigate faults that leave camera images unchanged. Crucially it reports pooled success per axis, not per-task failure thresholds, and does not link perturbations to representation benefit.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.12032": ("FULL_TEXT", "VERIFIED", ["modality_arbitration"],
  "Abstract; phase analysis; method", "Vision is under-used exactly in motion-transition phases",
  "Finds that in motion-transition sub-phases requiring target localisation the vision modality plays a limited role, because proprioception offers faster loss reduction and dominates optimisation. Proposes gradient adjustment with phase guidance (GAP). Preempts a naive 'vision is ignored' candidate.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2609.16815": ("FULL_TEXT", "VERIFIED", ["cue_conflict", "modality_arbitration"],
  "Abstract; §1 cue-conflict construction", "Cue-conflict intervention methodology applied to embodiment cues",
  "Visual embodiment dependence: cue-conflict observations pair task state from one stage with visible embodiment configuration from another. Across four policies in sim and real, visible configuration can dominate task-state cues. Remedy is embodiment canonicalisation in 3D point clouds, not removal.",
  "https://tonyfang.net/ved", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2607.29169": ("FULL_TEXT", "VERIFIED", ["runtime_monitoring"],
  "Abstract; results", "Runtime visual-action consistency safeguarding with large gains",
  "ActFovea is plug-and-play: action-conditioned foveated regions plus consistency checks between visual motion, observation freshness, proprioception and action transitions. On pi0 across LIBERO suites, success under localised visual overlays rises 49.3% -> 90.3%, closing 93.7% of the gap to clean; +7.0pp under action drift, +9.8pp under visual delay. Strong evidence that runtime consistency checks are a high-leverage, cheap intervention.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2605.18045": ("FULL_TEXT", "VERIFIED", ["uncertainty_gating"],
  "Abstract; results", "Uncertainty only helps gating above a competence regime",
  "Confidence-gated autonomy evaluated with rank correlation and act/defer agreement. Finds a dataset-dependent competence regime below which uncertainty gives a weak, unstable error ranking; above it, softmax/MC-dropout/ensembles behave similarly and threshold choice dominates outcomes. So 'add calibrated uncertainty' is not a free win.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.01626": ("FULL_TEXT", "VERIFIED", ["error_dynamics", "measurement"],
  "Abstract; method; findings", "Closest measurement precedent to an error/tolerance study",
  "Injects a small action error at each state and measures whether it contracts or expands under open-loop and closed-loop execution. Across twelve manipulation tasks in three suites, confidently stable states are rare and amplification is common; amplification is front-loaded so short windows overestimate long-horizon propagation; open-loop regime is predictable from camera and proprioception, closed-loop propagation only partially.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.15425": ("FULL_TEXT", "VERIFIED", ["compositional_generalisation"],
  "Abstract; benchmark; results", "Start-state gap in skill recombination",
  "RoboCombine: full-instruction training reaches 40.0% on covered combinations but 7.7% on recombination. Failures concentrate at transitions; Pose Robust Task Initialization raises ordered success from 4.21% to 18.16%. Relevant to long-horizon spatial-state handoff, not to single-skill spatial precision.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2603.22876": ("FULL_TEXT", "VERIFIED", ["sim2real", "measurement"],
  "Abstract; protocol", "Large empirical sim-to-real study with spatial factors",
  "Examines domain randomisation, photorealistic rendering, physics modelling and RL updates over 10k+ real-world trials, with an evaluation protocol covering background, lighting, distractors, object types and spatial features. Shows the kind of trial budget a credible robustness claim needs.",
  "UNKNOWN", "UNKNOWN", "Released platforms and protocol stated", "UNKNOWN", "UNKNOWN"),

"2609.26567": ("FULL_TEXT", "VERIFIED", ["measurement", "retrieval_audit"],
  "Abstract; §1", "Audit methodology showing scores can describe the library, not the rule",
  "Executes every stored experience in every query scene to get the full transfer table, then shows that visual nearest-neighbour rules concentrate on one experience and that visual distance ranks candidates within a scene no better than chance for four of five embeddings at K=50 (AUROC 0.45-0.52). Strong precedent that exhaustive-table audits are publishable and that plausible similarity metrics can fail at the decision level.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2607.03758": ("FULL_TEXT", "VERIFIED", ["planning_tolerance"],
  "Abstract; §1", "Tolerance exists in planning but as a feasibility region, not a predictor of representation benefit",
  "Planner-agnostic adversarial attack for tolerance-aware manipulation: success is task-level feasibility over goal regions rather than exact-pose tracking. Confirms that 'tolerance' in robotics usually means a feasible goal set, which is a different construct from the action-tolerance-versus-representation-benefit question raised in this report.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
"2509.18644": ("FULL_TEXT", "VERIFIED", ["modality_arbitration", "proprioception"],
  "Abstract; experiments",
  "Counter-evidence to 'more state input helps'",
  "Asks whether proprioceptive states are needed in visuomotor policies. Cited as a counterweight to ActiveArena's +12/+30 pp proprioception result: the benefit is setting-dependent, not universal.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2603.26779": ("ABSTRACT_ONLY", "VERIFIED", ["E_representation_probe"],
  "Abstract only",
  "Bound on spatial imagery reasoning in frontier models",
  "Argues frontier LLMs have limits in spatial imagery reasoning. Recorded as an adjacent capability bound; no claim in this report relies on it.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2604.09338": ("FULL_TEXT", "VERIFIED", ["E_reasoning_bound", "navigation"],
  "Abstract; §5 Conclusion; Figure 10",
  "Best evidence that classical planning beats LLM spatial reasoning on navigation",
  "Spatial-Gym: 2D grid pathfinding with interacting constraints, step-by-step and backtracking. Best model 16.0% vs human 98.0%; vision input reduces solve rate by 73%; A* solves navigation, so constraint satisfaction is the bottleneck. Supports the report's claim that navigation/planning is not the place to look for novelty.",
  "UNKNOWN", "UNKNOWN", "Gymnasium environment stated", "UNKNOWN", "UNKNOWN"),

"2605.15836": ("ABSTRACT_ONLY", "VERIFIED", ["shortcut", "representation"],
  "Abstract only",
  "Name collision only: different 'GAP' from 2602.12032",
  "Geometric Anchor Pre-training for data-efficient visuomotor learning. Registered solely to disambiguate it from the gradient-adjustment GAP in 2602.12032; not used as evidence.",
  "https://lambdavi.github.io/gap", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2610.29646": ("PARTIAL_TEXT", "VERIFIED", ["decision_value", "evaluation"],
  "Abstract; Figure 1; held-out protocol",
  "Methodological standard C1 must meet: predictive ≠ decision-useful",
  "Tests whether 'paired instruction dependence' (does the demonstrator change its first decision when only the goal changes) predicts downstream corpus selection. Across 136 seeded corpora, 56 development / 80 held-out. The audit is reliable and lowers MAE, but the primary proper-log-score increment is +0.059 nats with a 95% CI of [-0.027, 0.133] and the prespecified top-20% selection gain is not established. Direct lesson: a diagnostic can be reliable and predictive yet add little decision value when compressed into an unsigned statistic, so C1 must be scored on selection utility, not correlation.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2602.17659": ("PARTIAL_TEXT", "VERIFIED", ["counterfactual_failure", "evidence_use"],
  "Abstract; method description",
  "Direct competitor for evidence-use remedies in VLA",
  "Introduces LIBERO-CF, a counterfactual benchmark that assigns alternative instructions under the same scene, and Counterfactual Action Guidance: a dual-branch scheme comparing a language-conditioned policy against a language-unconditioned vision-action module at action selection. Reports +9.7% language-following accuracy and +3.6% success for pi0.5 on under-observed tasks, +15.5%/+8.5% with a VA model, and 17.2% real-world success gain. Reinforces that vision shortcuts, not missing spatial representation, drive many instruction-following failures.",
  "UNKNOWN", "UNKNOWN", "LIBERO-CF benchmark stated", "UNKNOWN", "UNKNOWN"),

"2606.08881": ("PARTIAL_TEXT", "VERIFIED", ["failure_taxonomy", "benchmark"],
  "Abstract; §1; §5 Limitations",
  "Failure-taxonomy benchmark on low-cost hardware; execution instability dominates",
  "Real-world SO-101 benchmark of pi0.5, SmolVLA, Wall-X and ACT across four tasks with a structured failure taxonomy, semantic vs execution-level decomposition, and recovery-aware metrics. Finds execution instability the dominant failure source and recovery capability strongly architecture-dependent. Relevant to C1 as evidence that on low-cost hardware the dominant failure mode may be execution, not spatial precision.",
  "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

"2611.05058": ("PARTIAL_TEXT", "VERIFIED", ["agentic_geometry", "when_to_look"],
  "Abstract; §4 policy synthesis numbers; §5 online execution; §6 query reduction",
  "Agentic evidence that grounded geometry pays off where fine alignment is required",
  "Replaces repeated image interpretation with a typed, evidence-aware 3D symbol layer refreshed from calibrated RGB-D and read by the language model, invoking visual reasoning only on demand. Policy synthesis: Geometric Abstraction reaches 45.2% vs 21.2% at R1 on Bridge+cylinder and 57.2% vs 17.2% on Three-cube stacking; Ring-on-peg stays 0% for pixel reasoning through R2 while geometric abstraction reaches 38.0% at R3. Online execution: Bridge-tower 28/50 vs 12/50, Tower relocation 42/50 vs 15/50. Also cuts attached images from 10.94 to 2.72 and model time by 49.4% on Ring-on-peg. Dated 2026-11-03, two days before the cutoff; read at partial depth after a competitor screen of the abstract-only set.",
  "https://geometric-abstraction.github.io", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),

}

FULL = set("""2510.02268 2610.12696 2609.37292 2610.23891 2609.24124 2609.32762 2610.38104
2602.23408 2609.05376 2606.02277 2607.11498 2607.09825 2610.24674 2609.27247 2604.18000
2609.28955 2609.22299 2610.01626 2610.18843 2607.05396 2605.18746 2603.13033 2602.12032
2609.16815 2607.29169 2605.18045 2607.13618 2609.26567 2604.21241 2608.05730 2606.16667
2605.20544 2607.03758""".split())

ABSTRACT_ONLY = set("""2603.26757 2605.30557 2608.01826 2608.01066 2606.15232 2610.24705 2610.22997
2610.23396 2606.26800 2610.15572 2602.07082 2606.03240 2608.24959 2609.13812 2609.24525
2605.29416 2510.12276 2508.15874 2609.27734 2610.11508 2609.23252 2601.08325
2602.04600 2609.07047 2603.04639 2609.18514 2603.12193 2607.01658 2610.04139 2512.02902
2406.10721 2411.16537 2401.12168 2610.34051 2609.30833 2602.04243 2511.17001 2506.06196
2611.03937 2608.13605 2603.22876 2606.03943 """.split())

out = []
for pid, (lvl, ver, tags, ev, rel, ann, code, weights, data, evalentry, lic) in A.items():
    m = meta.get(pid)
    if not m:
        continue
    authors = m["authors"]
    out.append({
        "id": pid,
        "title": m["title"],
        "authors": authors if len(authors) <= 4 else authors[:3] + ["et al."],
        "year": m["published"][:4],
        "posted": m["published"],
        "venue_status": "preprint (arXiv), venue not verified"
        if pid not in ("2510.02268",) else "ICRA 2026 (stated in official repo README)",
        "arxiv_abs": f"https://arxiv.org/abs/{pid}",
        "pdf": f"https://arxiv.org/pdf/{pid}",
        "read_level": ("FULL_TEXT" if pid in FULL else "ABSTRACT_ONLY" if pid in ABSTRACT_ONLY else "PARTIAL_TEXT"),
        "verification": ver,
        "topic_tags": tags,
        "evidence_locations": ev,
        "relation": rel,
        "claim_summary": ann,
        "code": code,
        "weights": weights,
        "data": data,
        "eval_entry": evalentry,
        "license": lic,
        "local_fulltext": f"papers/{pid}__*.txt" if os.path.exists(os.path.join(ROOT, "papers")) and glob.glob(os.path.join(ROOT, "papers", f"{pid}__*.txt")) else None,
        "retrieved": "2026-11-05",
    })

out.sort(key=lambda r: r["posted"], reverse=True)
with open(os.path.join(ROOT, "sources", "papers.jsonl"), "w") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("wrote", len(out))
