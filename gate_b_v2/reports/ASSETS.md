# Gate B v2 assets

All assets live under `gate_b_v2/assets/` and are excluded from Git. Downloaded
2026-11-10 (Asia/Shanghai).

## Source archive

| Item | Value |
|---|---|
| File | `gate_b_v2_source.tar.xz` (repository root) |
| SHA256 | `5a4a43e0b0a4f1476f10e0c5d6bfe233b64d34fa03dccdc432c7d86a30eaaa7b` |
| Verified | matches the README value |
| Extracted to | `gate_b_v2/` (isolated staging copy under `.gate_b_v2_unpack/`) |

## Official Square-MH image checkpoint

| Item | Value |
|---|---|
| URL | `https://diffusion-policy.cs.columbia.edu/data/experiments/image/square_mh/diffusion_policy_cnn/train_2/checkpoints/epoch%3D1950-test_mean_score%3D1.000.ckpt` |
| Local path | `assets/square_mh/epoch=1950-test_mean_score=1.000.ckpt` |
| Bytes | 4,627,773,609 (matches HTTP Content-Length) |
| SHA256 | `adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d` |
| Published config | `reports/square_mh_published_config.yaml` (saved verbatim) |

Checkpoint facts from `reports/checkpoint_audit.json`:

| Field | Value |
|---|---|
| Workspace | `TrainDiffusionUnetHybridWorkspace` |
| Policy | `DiffusionUnetHybridImagePolicy` |
| Horizon H | 16 |
| `n_obs_steps` To | 2 |
| `n_action_steps` | 8 |
| Executable future actions | **15** (`16 - (2 - 1)`) → h=16 invalid |
| Action shape | **[10]** (3 position + 6-D rotation + 1 gripper) |
| `abs_action` | **true**, `rotation_6d` |
| Dataset in config | `square/mh/image_abs.hdf5` |
| `use_ema` | true; `ema_model` state present |
| Normalizer | 36 state-dict keys inside `model` and `ema_model` (not in pickles) |
| Observation keys | `agentview_image` [3,84,84], `robot0_eye_in_hand_image` [3,84,84], `robot0_eef_pos` [3], `robot0_eef_quat` [4], `robot0_gripper_qpos` [2] |

The checkpoint is the **absolute-action** Square-MH image variant, not the
7-D delta-action variant assumed by the written Gate B protocol.

## Square-MH dataset (environment metadata only)

| Item | Value |
|---|---|
| URL | `http://downloads.cs.stanford.edu/downloads/rt_benchmark/square/mh/low_dim.hdf5` |
| Local path | `assets/square_mh/low_dim.hdf5` |
| Bytes | 123,863,240 |
| SHA256 | `7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887` |
| Demos | 300 |
| env_name | `NutAssemblySquare` |
| Env kwargs | Panda, OSC_POSE, 84×84, control_delta true (switched to false for this checkpoint) |

Evaluation needs only `data.attrs["env_args"]` from this file, not the images.
The 84.75 GB `robomimic_image.zip` bundle was **not** downloaded. Because the
low-dim metadata omits `camera_names`, the harness derives them from the
checkpoint `shape_meta` (`agentview`, `robot0_eye_in_hand`).

## Pinned source

| Item | Value |
|---|---|
| Diffusion Policy | commit `5ba07ac6661db573af695b419a7947ecb704690f` (prior audit in `d_alignment_pilot/configs/versions.json`) |
| Local copy | `third_party/diffusion_policy` (19 MB, Git-excluded) |
| Source tree SHA256 | `aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21` |
| robosuite | cheng-chi fork `277ab9588ad7a4f4b55cf75508b44aa67ec171f0` (version 1.2.0) |
| robomimic | 0.2.0 |
| MuJoCo | 2.1.0 (bundled with free-mujoco-py 2.1.6) |
