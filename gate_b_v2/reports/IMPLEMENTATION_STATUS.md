# Gate B v2 code implementation status

Updated: 2026-11-10 after workstation integration.

## Authoring baseline (unchanged facts)

The archive's unit tests and implementation were authored without importing
Diffusion Policy, robomimic, robosuite, MuJoCo, the checkpoint or the dataset.
That authoring baseline was 8 tests; it is superseded by the workstation run
below.

## Workstation integration performed

- Checkpoint-native loading through the upstream DP workspace payload; EMA
  selected because `training.use_ema=true`.
- The checkpoint is the **absolute-action** variant: action shape 10,
  `abs_action=true`, `rotation_6d`, `control_delta=false`. Implemented the
  official 10→7 conversion and DP's 6-D rotation convention.
- Checkpoint H=16, To=2, `n_action_steps=8`; only 15 future actions exist, so
  h=16 remains invalid and B1 is blocked.
- The normalizer is stored in the model/EMA state dict (36 keys), not in the
  pickled payload; loading is verified.
- Two 84×84 RGB cameras, proprio dims 3/4/2 and 7-D OSC actions are verified
  on the live simulator.
- Live collision-geometry inference: SquareNut aperture half-extents
  0.02275 m, peg half-extent 0.016 m.
- Final-state robomimic success predicate; sticky `success_seen` is diagnostic.
- OSMesa rendering matches official stored frames (corr 0.998, mean diff
  ~1.5/255); policy queries on official observations match the next demo pose
  within 0.8–2.5 cm and reproduce the gripper sign.
- Closed-loop from an official demo start state succeeds.

## Verification

- `pytest -q`: **25 passed**.
- `compileall`: clean.
- `bash -n` on all launchers: clean.

## Current status (2026-11-11)

1. **CUDA resolved by the authorized reboot**: kernel module and userspace are
   both 580.178.04; the RTX 3090 passes real matmul and cuDNN checks. A
   workspace-local `.cuda_compat/libcuda.so` symlink is needed because cuDNN
   dlopens the unversioned name; no system file was changed.
2. **Formal B0 completed**: 84/100 (0.84) on seeds 100000–100099, h=8, 500
   steps, device cuda:0. Wilson 95 % CI 0.7558–0.8990. No episode was skipped
   or replaced; 16 real failures are retained. See `reports/B0_REPORT.md`.
3. **B1 remains blocked**: h=16 is not executable with H=16/To=2 (15 future
   actions). Needs a researcher-approved horizon amendment. Not started.
4. **B2 remains blocked**: insertion-stage window is not frozen and no
   snapshot/restore replay was run. No B2 state was collected.

## Interpretation limits

The checkpoint's 1.000 was measured on its own `test_start_seed=4,500,000`,
not the Gate B seeds 100000–100099; B0 is a new measurement on the protocol
seeds under the checkpoint-native 10-D absolute-action semantics. No Gate C
decision is made.

See `reports/CODE_REVIEW.md`, `reports/B0_STATUS.md` and
`reports/WORKSTATION_EXECUTION_LOG.md`.
