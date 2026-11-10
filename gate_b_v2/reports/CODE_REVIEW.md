# Gate B v2 source review against official DP / robomimic / robosuite

Date: 2026-11-10. Reviewed source: archive SHA256
`5a4a43e0b0a4f1476f10e0c5d6bfe233b64d34fa03dccdc432c7d86a30eaaa7b`.
References used: pinned Diffusion Policy `5ba07ac…`, robomimic 0.2.0,
robosuite 1.2.0 (cheng-chi `277ab958…`), and the actual checkpoint payload.

## Checklist

| # | Item | Result |
|---|---|---|
| 1 | Official Square-MH checkpoint load | Verified through the upstream workspace payload. `TrainDiffusionUnetHybridWorkspace` + `DiffusionUnetHybridImagePolicy`; 255.6 M diffusion + 22.4 M vision parameters. `load_payload` restores model, EMA and normalizer. |
| 2 | EMA vs plain model | Checkpoint `training.use_ema=true` and `ema_model` state exists; harness selects `workspace.ema_model`, matching DP eval. |
| 3 | Image shape/channel/dtype | `[3,84,84]` CHW float32 in `[0,1]`, matching DP's image normalizer (scale 2, offset −1). Confirmed on the live renderer, not only in metadata. Added fail-closed range validation. |
| 4 | Two 84×84 RGB observations | `agentview_image` and `robot0_eye_in_hand_image` both render at 84×84. Low-dim dataset metadata lacks `camera_names`; names are now derived from the checkpoint shape_meta. |
| 5 | Proprio dimensions | `robot0_eef_pos` [3], `robot0_eef_quat` [4], `robot0_gripper_qpos` [2]; verified against live observations. |
| 6 | Action output | **Checkpoint emits 10-D absolute actions**, not the 7-D delta action in the written protocol. `abs_action=true`, `rotation_6d`, `image_abs.hdf5`. Harness now reproduces DP's `undo_transform_action` (3 position + 6-D rotation → 3 axis-angle + gripper) and switches OSC to `control_delta=false`. |
| 7 | Action normalization/coordinates | Action normalizer is stored inside the model/EMA state dict (36 normalizer keys), not in the pickled payload; verified. Policy outputs are unnormalized by DP before the harness converts 10→7. |
| 8 | Gripper semantics | Last action dimension; passed through unchanged into robosuite's OSC_POSE 7-D action. |
| 9 | SquareNut / peg collision geometry | Live inference identifies four aperture bars: half-extents 0.02275 m (x and y), peg half-extent 0.016 m; signed clearance and z gap computed from MuJoCo geoms. Unit tests cover centering, offset and yaw. |
| 10 | Success predicate | robomimic `is_success()['task']` is a **final-state** predicate. Harness previously reported the sticky `success_seen` flag; fixed. Smoke records now carry `success`, `success_seen` and `success_error`. |
| 11 | Snapshot/restore completeness | Code review only: captures MuJoCo state+XML, controller/gripper fields, robosuite counters, task state, RNGs and observation history; restore validates class identity and replays a probe. **Not exercised on the live simulator; B2 remains blocked.** |
| 12 | JSONL and paired-state logging | Per-episode JSONL, initial-state SHA256 paired across horizons, environment manifest and per-run summaries verified by the end-to-end run. |

## Defects found and fixed

### F1. Success was sticky instead of final-state
`EpisodeEnv.success()` returned `success_seen`, which stays true after the
first success even if the object later leaves the goal. robomimic evaluates
`_check_success()` on the final state. Fixed in `src/gate_b_v2/env.py`; the
sticky flag is retained as a diagnostic. Tests: `tests/test_env.py`.

### F2. RGB range was not validated
`stack_observation_history` accepted any RGB array. DP's image normalizer maps
`[0,1] → [-1,1]`; a uint8 or 255-scaled image would silently corrupt inputs.
Raw uint8 HWC is now converted with robomimic's `/255` rule; other ranges fail
closed. Tests: `tests/test_core.py`.

### F3. DP commit metadata inherited from the parent repository
`git_commit()` ran `git -C dp_root` and, because the DP checkout has no
`.git`, recorded the EAI repository HEAD as the DP commit. It now requires the
path to be the work-tree root and records a deterministic
`dp_source_tree_sha256`. Tests: `tests/test_core.py`.

### F4. Wrong action semantics for the archived checkpoint
The harness assumed 7-D delta actions. The actual checkpoint is 10-D absolute
(`shape_meta.action.shape=[10]`, `abs_action=true`, `rotation_6d`). Sending
10-D values to the 7-D OSC controller cannot work. Added
`src/gate_b_v2/actions.py` (pytorch3d-compatible 6-D rotation convention),
`control_delta=false`, and conversion at every env step, including the B2 probe.
Tests: `tests/test_actions.py` (round trip against scipy).

### F5. Image environment built from low-dim metadata lacked cameras
The official image dataset's `env_args` contains camera names; the low-dim
metadata used here does not. Without them robosuite renders no eye-in-hand
image and the wrapper raised `KeyError`. Names are derived from the checkpoint
RGB keys. Tests: `tests/test_env.py`.

### F6. Test collection picked up vendored DP tests
Vendoring the DP source made `pytest -q` collect its unrelated tests and fail.
Added `testpaths = ["tests"]` and `norecursedirs` to `pyproject.toml`.

### F7. Workstation launcher leaked ROS paths
Run scripts appended inherited `PYTHONPATH` (ROS 2, Python 3.10) to the
Python 3.9 venv. `scripts/gateb_env.sh` unsets it and pins the isolated venv,
MuJoCo/OSMesa libraries and offline wandb. All launchers source it.

## Non-defects confirmed against upstream

- DP pads the observation history by repeating the earliest available frame;
  the harness does the same.
- DP slices `action_pred[:, To-1:]`; with H=16, To=2 only 15 actions are
  executable. The harness fails closed for h=16.
- robomimic 0.2.0's `EnvRobosuite` forces `use_object_obs=True` regardless of
  the env_meta override; this is harmless because the policy consumes only
  shape_meta keys.
- DP's image normalizer is `[0,1] → [-1,1]`; robomimic returns processed
  `[0,1]` CHW images by default (`postprocess_visual_obs=True`).

## Protocol deviations requiring researcher attention

1. **Action space:** the named checkpoint is 10-D absolute-action, while the
   protocol text specifies 7-D delta. The harness now runs the checkpoint's
   official semantics; the protocol text should be amended or a 7-D checkpoint
   substituted.
2. **B1 h=16 is not executable** with H=16 and To=2 (`16 − (2−1) = 15`). B1 was
   not started. The horizon list needs a protocol amendment (for example, use
   15 in place of 16).
3. **B2** remains blocked by the unfrozen insertion-stage window; no B2 state
   was collected.

## Verification

- `python -m compileall -q src tests`: clean.
- `pytest -q`: **25 passed**.
- Checkpoint CPU load: EMA policy, chunk `(15, 10)`, 6.87 s per call.
- Live env: two 84×84 cameras, 7-D OSC action, one step OK.
- End-to-end 16-step rollout on CPU: OK (2 policy calls, 15.15 s).
