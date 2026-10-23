# M-Gate 0 v2 — preregistered protocol

2026-10-23, Asia/Shanghai. Frozen before any M expert-prefix replay, policy
suffix, nominal M outcome or directional outcome. The resource audit only read
the dataset/checkpoints and constructed an environment without action steps.
No earlier M v1 protocol/results exist in this checkout or its branch history.
The supplied v2 task is the execution authority; the two remote-host discussion
documents were not supplied and are not claimed to have been independently read.
This document implements the complete v2 instructions without requiring them.

## Scope and provenance

Base `cea2502eee1dd6504035f4fcde47af1833a90b93`, new branch
`research/m-gate0`, same EAI checkout. Previous active D-Q2 branch remains at
`75c0271`. Only `m_direction_pilot/` may be added/changed relative to the base.
No training, model/data download, D run, second task, robot experiment, system
modification, Gate 1 experiment or fitted probability model is authorized.
The installed D venv and pinned upstream libraries are reused read-only;
all new caches/traces are inside M. Do not run the D launcher or D experiment.

Task: Square PH low_dim, robomimic 0.4.0, robosuite 1.5.1, MuJoCo 3.2.3,
Panda/BASIC/OSC_POSE. The 7D action is a normalized control command, not measured
EEF displacement. Actual audited world translation scale is 0.05 m per unit;
rotation scale 0.5 rad per unit; input delta, achieved-goal reference, no position
or orientation goal limits, 20 Hz with 0.002 s simulation steps, lite_physics=false.
Source/checkpoint SHA256s are frozen in `configs/gate0.json` and checked at runtime.
No on-policy action may replace the expert fork action.

Source HDF5 SHA256: `45d8cabb6d57a4c03e839aa5e4b3e58fb60fe8bd20e1951fec563a2abfd14951`.
Clean42: `1b4cdec2acc38977c6d3be0ab651dad595a67ccdee97be5d41b2ebebd230bae9`.
Clean43: `619d80882072f1a94e413e449736a9febab05d4c503238ede2cb758f686d8ade`.
Resource audit accesses every episode's states/actions/obs/next_obs, verifies
finite data, time increments, shapes and next_obs[t]=obs[t+1]. The absolute
object pose (object[7:14]), EEF pos/quat and gripper qpos form the original
16D Clean policy input. Cache-dependent relative object fields are excluded,
matching the frozen Clean training; the source data is unchanged.

## Offline source/state selection

Sorted numeric episode IDs from the original official `valid` mask (20 episodes).
NumPy default_rng(202610230) permutation, first six episodes; first four dev,
last two held out. Two states per episode. No nominal policy outcome is used.
Original validation episodes were used by the old Clean training workflow for
validation, so this is an episode-isolated M measurement split, not a claim that
all policy design was blind to these demonstrations.

Candidate t must satisfy 8 <= t < T-5 and source dones[t]=0. Peg1 pose is read
from that episode's XML (position [0.23,0.1,0.85]). Phase pools:

- grasp/contact proxy: nut z < 0.85 m, expert gripper > 0, EEF-to-nut < 0.09 m.
- insertion/approach proxy: nut-to-peg xy distance < 0.055 m, nut z > 0.85 m,
  expert gripper > 0. These are geometric proxies, not exact contact labels.

For each episode, default_rng(202610230 + numeric_episode_ID), choose one
uniform index from grasp then one from insertion. Empty pool: stop, no source
replacement. Boundary check follows selection; a rejected candidate remains in
the denominator and is never replaced. All pools and selection flags are saved.
These rules were set after reading source geometry, before all M outcomes.

| State | Source | t | Split | Phase |
|---|---|---:|---|---|
| S00 | demo_191 | 52 | development | grasp |
| S01 | demo_191 | 107 | development | insertion |
| S02 | demo_21 | 65 | development | grasp |
| S03 | demo_21 | 165 | development | insertion |
| S04 | demo_56 | 55 | development | grasp |
| S05 | demo_56 | 110 | development | insertion |
| S06 | demo_32 | 61 | development | grasp |
| S07 | demo_32 | 127 | development | insertion |
| S08 | demo_105 | 71 | held-out | grasp |
| S09 | demo_105 | 126 | held-out | insertion |
| S10 | demo_27 | 78 | held-out | grasp |
| S11 | demo_27 | 155 | held-out | insertion |

## Replay, intervention and closed-loop time

For EVERY branch instantiate/reset the same official environment, restore only
the episode's XML and initial recorded state, then replay actions[0:t] in order.
No recorded state is imposed again, no teleport to t, no expert suffix.
Replay reconstructs controller targets, gripper state, contacts, observable cache
and the live two-observation history. The old async relative sensors are not
used in policy conditioning. Compare live and recorded absolute observations,
sim states, EEF/nut position and geodesic quaternion angle along the prefix and
at t; retain numerical diagnostics and raw state hashes even when unequal.

At t execute exactly expert actions[t] (nominal) or actions[t]+delta once.
Only the first three translation coordinates change. Instrument the composite
controller input, arm scale_action input/output and resulting target without
changing calculations. Reject any perturbed translation at or outside [-1,1],
or an original rotation/gripper outside its legal interval. Unchanged gripper
+-1 is valid. No silent clipping of the intervention. Later policy actions can
reach controller clipping; record them and actual controller receipt separately.

After the expert step append live obs[t+1]; policy history is [obs[t],obs[t+1]].
Reset the stateless frozen policy once at handover and immediately replan at
t+1, then t+9,t+17,... in both paired branches. Use original horizon16,
observation history2, action chunk8, OA prediction slice [1:9], DDIM16/eta0.
Do not initialize with cached raw source history while physics uses replay.

Common endpoint: episode action index 399 has executed (400 total control steps
including the expert prefix); suffix length is 400-t, including the intervention
step. Do not stop on success/failure. This preserves the current official
robomimic Square evaluation horizon400 (generate_paper_configs.py) and existing
Clean evaluation convention; robosuite's internal default horizon1000 with
ignore_done=true is separately reported, not mistaken for the benchmark limit.
Y is official task success ever during the suffix; also record final success,
first successful absolute step and all success flags. Fork states must not
already be successful in the live environment.

Pair randomness by state ID, stream0 and replan index, using SHA256-derived
stable seeds (`io.stable_seed`). Reset Python/NumPy before environment creation;
give each DP replan its own torch.Generator via official policy kwargs. Record
seed, initial noise tensor hash and generator state hash. Control time/replan
count does not depend on call ordering or success. Use one env, two CPU threads,
3090, FP32/TF32 off, deterministic Torch/cuDNN settings and fixed CUBLAS workspace.
This is a paired deterministic probe, not repeated Bernoulli sampling. Seed43
gets the same expert state/action and noise schedule, then its own closed loop.

## Gate A: mandatory before B

Primary allocation: all 12 frozen states, two independent complete prefix+zero
suffix replays each under Clean42/stream0 = 24 complete suffixes. Compare fork
start physical state, controller/cache/history/RNG snapshots; every received
action, trajectory, replan/noise schedule, final and ever success. Source replay
acceptance maxima, fixed now: selected observation <=1e-3, EEF/nut position
<=1e-3 m, EEF/nut geodesic angle <=0.01 rad, flattened sim state <=0.01,
time error <=1e-8 s, along prefix and at t. These bound reconstruction error;
they are distinct from the stricter identical-branch repetition checks.

Zero-repeat acceptance: initial selected obs <=1e-5; trajectory selected obs,
received actions and EEF/nut position <=1e-5; rotation angle <=1e-4 rad; sim state
<=1e-4. Replan/noise schedule and official final/ever success must be identical.
State/controller/cache/history hashes are reported; byte equality is stronger
evidence when it occurs, not a substitute for physical/geodesic errors.

Any zero-repeat success flip stops as Invalid. Any replay/engineering failure
stops B. One causal engineering investigation is allowed, without changing
scientific states, thresholds, controller or action interface to improve results.
At most three extra zero pairs (6 suffixes) can be registered in an addendum
before running the diagnosed repair; no automatic retry. All failed/partial
attempts and prefix work remain in the ledger. No blanket restart of A.

## Exact Gate B matrix and budget

All vectors are unit length in normalized world translation command space.
Axes x,y,z; mixed xy=(1,1,0)/sqrt2, xz=(1,0,1)/sqrt2,
yz=(0,1,1)/sqrt2; both signs. r1=0.2, r2=0.1, respectively 10 and 5 mm
target increments under this scale, not actual EEF displacements.

| Block | Frozen allocation | Suffixes |
|---|---|---:|
| B1 | Clean42, all12, one nominal + xyz both signs, r1 | 84 |
| B2 | Clean42, S08/S09/S10, xy/xz/yz both signs, r1 | 18 |
| B3 | Clean42, S00/S03, z both signs, r2 | 4 |
| B4 | Clean43, S01/S09, new nominal + xyz both signs, r1 | 14 |
| B total | Execute in this order, no outcome-dependent changes | 120 |
| A | 24 planned + at most6 diagnosed repair branches | <=30 |
| All | Nominals count; completed plus attempted branches accounted | <=150 |

B2/B3 reuse the exact B1 nominal for that state; there are no hidden baseline
repeats. B4 has a new checkpoint-specific nominal. State/action/plan files are
immutable after registration. Before each branch reserve its unique ID in an
append-only attempt ledger; never overwrite/resume/retry a started suffix.
Technical rejections and branches not run after a stop remain visible for all
12 states and all120 planned branches. Prefix actions/time/CPU are additional
costs, recorded separately. Hard wall limit48h, earlier stop on resource/interface
block. A leftover allowance is not a reason to add a probe.

## Outcomes and audit C

Delta_loss = Y(nominal)-Y(perturbed), in {-1,0,+1}. Improvement=-1 is retained.
Report every signed pair; do not automatically average signs. Describe within
state directional contrasts and plus/minus asymmetry, source episode then state,
checkpoint and radius. B's120 suffixes are not120 independent states. Use raw
clustered counts; no p-value or tight interval from six source episodes. Auxiliary
EEF/nut/peg position, insertion-axis angle, ncon, first success/recovery time do
not replace success. ncon is only coarse contact presence, never contact normal.

Predefined explanatory audit order:

1. Isotropic/state scalar: equal norm cannot create within-state direction ranks.
2. World axes: sign-averaged losses and rankings, dev-only nonnegative least
   squares diagonal fit on squared unit directions as a descriptive baseline.
   Also distinguish a general fixed3x3 PSD metric: B1 dev axes cannot identify
   off-diagonal entries, so its failure cannot be inferred from a diagonal fit.
3. Object frame: use the live nut absolute quaternion to transform each world
   unit vector; dev-only NNLS on squared local components, held-out ranking
   inspection. Scalar state weights cannot repair within-state rank reversals.
4. Task frame: live peg1 body rotation, local insertion z and transverse xy;
   squared components with dev-only NNLS. Peg frame may coincide with world.
   Exact contact normals are not inferred from ncon. If geometry/fidelity is
   unavailable, mark baseline unavailable and necessity unresolved.
5. Report signed/asymmetric/improving patterns before any symmetric interpretation.
6. Inspect held-out xyz and mixed directions without re-fitting. NNLS is only
   a three-coefficient exploratory geometric summary, not a trained teacher or
   probability model. No held-out NLL/state-shuffle significance is claimed.

Rank contradictions/residuals are descriptive, require a nonzero actual outcome
contrast and must be shown as raw pairs. Fit models only after all permitted B
rows finish or a stop is recorded. No outcome-driven source/direction/radius
replacement. Sparse/all-equal labels cannot certify a simple explanation.

## Fixed decision rules and interpretation

- **Stop/Invalid (Engineering blocked)**: source/fork replay fails, zero repeat
  changes success, uncontrolled clipping/randomness, budget or data-boundary
  contamination. No scientific verdict about M; B is prohibited if A fails.
- **No-Go for symmetric-PSD M**: strong sign-asymmetric or improving outcomes
  recur across at least two valid source episodes with confirmed command
  directions and stable zero replay. Report them as contradictions to a purely
  symmetric, monotonically penalizing local model under these paired streams,
  not population probability estimates. No linear/asymmetric head rescue.
- **No-Go / simple explanation sufficient**: only if independently held-out
  informative contrasts are credibly explained by fixed geometry/global rules,
  with scope/underidentifiability acknowledged. No statistical exclusion from
  the small sample and no claim about all possible3x3 metrics.
- **Potential Go to discussion of a separately registered Gate1**: directional
  outcome contrasts at multiple states from at least two source episodes,
  stable A, held-out mixed-direction descriptive counterexamples to preregistered
  scalar/fixed geometric ranks, and no strong symmetric-PSD contradiction.
  This authorizes only a plan discussion, not training/probes. Global3x3
  underidentifiability and policy dependence must still be disclosed.
- **Stop/Inconclusive**: all/sparse outcome labels, insufficient effective sources,
  unavailable geometry, incomplete B2/reproducibility, exhausted budget or
  unresolved general-global explanation. Do not interpret as direction irrelevant.

No universal 10% flip/3pp policy improvement threshold. Single Square task,
expert demonstration states, this controller and frozen continuation policies
only. Clean43 two-state check is a warning, not cross-policy generalization.
Do not train40-parameter M. If a later Gate1 draft is warranted, retain the v2
2-task budget exactly1000+320+200+450+30=2000, with repeated probes only one
nominal+one perturbation each, and submit a plan without execution.

## Immutable records and implementation checks

Protocol's independent commit SHA will be written to `registration.json` after
commit and before the first replay. Record later code commit before execution;
any scientific amendment needs an explicit dated addendum and cannot turn
revealed results into preregistered validation. Source and execution hashes are
recorded per branch. Required tests: prefix/time semantics, expert rather than
policy fork, actual controller receipt and unchanged other4 dimensions, equal
axis/mixed norms, boundary rejection, episode-disjoint frozen split, baseline
deduplication, RNG/replan consistency, exclusive results, budget reservation,
hash checks and every planned state retained in the denominator. Real zero
reproducibility and source-fidelity tests are measured in A, not mocked away.

Paths: configs/gate0.json; outputs/gate0/{frozen_state_manifest.csv,selection_pool.csv,
branch_plan.csv,gate_a_plan.csv,attempt_ledger.jsonl,branch_results/,paired_outcomes.csv,
by_source.csv,summary.json,sha256_manifest.json}; reports/gate0/{resource_audit.md,
expert_fork_fidelity.md,fixed_baseline_audit.md,gate0_go_no_go.md,commands_and_costs.md,
logs/}; local/gate0/traces/ stores complete local NPZ traces, indexed by SHA.
No HDF5/checkpoint/runtime/cache/credentials are committed. Push only the new
branch and then stop for researcher review.
