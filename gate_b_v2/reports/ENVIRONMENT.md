# Gate B v2 workstation environment

Recorded 2026-11-10 (Asia/Shanghai). All runtimes live inside `gate_b_v2/` and
are excluded from Git. No system Python, system CUDA, ROS 2, VGPO, NVIDIA
driver package or `spatial_intervention_pilot/` file was modified.

## Hardware and OS

| Item | Value |
|---|---|
| OS | Linux 6.8.0-60-generic, Ubuntu 22.04 userland, glibc 2.35 |
| CPU | 4 cores |
| RAM | 31 GiB total |
| Disk | 468 GB root, 170 GB free at start |
| GPU | NVIDIA GeForce RTX 3090 (24 GB) — driver mismatch, see blocker |

## Runtime (isolated venv)

Prefix: `gate_b_v2/.venv` (Python 3.9.13 from the existing Anaconda base).

| Software | Version |
|---|---|
| torch / torchvision | 1.12.1+cu116 / 0.13.1+cu116 |
| torch CUDA runtime | 11.6 |
| numpy / scipy / h5py | 1.23.3 / 1.9.1 / 3.7.0 |
| hydra-core / omegaconf / dill | 1.2.0 / 2.3.1 / 0.3.5.1 |
| diffusers / huggingface_hub | 0.11.1 / 0.12.1 |
| pandas | 1.5.3 |
| robomimic | 0.2.0 (PyPI sdist) |
| robosuite | 1.2.0, cheng-chi fork `277ab958…` |
| free-mujoco-py | 2.1.6 (mujoco_py 2.0.2.13, MuJoCo 2.1.0 bundled) |
| numba / gym | 0.56.4 / 0.21.0 |
| wandb | 0.13.3 (offline) |
| pytest | 7.1.2 |

Full transitive pins: `reports/requirements.lock`.
Machine-readable versions: `reports/runtime_versions.json`.

## Installation notes and workstation adaptations

1. **Aliyun PyPI mirror stalled** on `numpy`; installs were restarted against
   `https://pypi.org/simple`. The default pip mirror is unchanged.
2. The venv is launched with `PYTHONPATH` stripped; the login shell exports ROS
   2 Python 3.10 paths that otherwise leak into Python 3.9 imports.
   `scripts/gateb_env.sh` handles this for every launcher.
3. `diffusers 0.11.1` requires `huggingface_hub<0.13`; latest hub removed
   `HfFolder`. Pinned 0.12.1.
4. `pandas` is imported by DP's `json_logger` through the training workspace.
5. **Driver blocker:** loaded kernel module is 550.144.03, while DKMS and
   userspace are 580.178.04. `nvidia-smi` fails with
   `Failed to initialize NVML: Driver/library version mismatch`; torch reports
   CUDA error 804 and `cuda_available=False`. A reboot is required to load the
   installed 580 kernel module. No driver files were changed.
6. **MuJoCo rendering:** free-mujoco-py only auto-detects drivers under
   `/usr/lib/nvidia-*`, which this Ubuntu layout does not use, so it silently
   selects the OSMesa CPU build. Ubuntu `libosmesa6`/`libosmesa6-dev` 23.2.1
   packages were downloaded with `apt-get download` and extracted into
   `.mesa/` without sudo. The built `cymj` extension links OSMesa; the runtime
   preloads the system `libstdc++` because the extension also carries an
   Anaconda rpath with an older `GLIBCXX`. This is a headless software-render
   build; it is independent of the broken CUDA driver but is not the official
   3090 rendering path.
7. `egl_probe` returns `[]` while the driver is mismatched, so robomimic does
   not set `render_gpu_device_id`; OSMesa ignores it.
8. The low-dim dataset metadata lacks `camera_names`; the harness derives
   `agentview` and `robot0_eye_in_hand` from the checkpoint RGB keys.

## Launch

```bash
cd /home/asus/EAI/gate_b_v2
source scripts/gateb_env.sh
python -m gate_b_v2.cli audit
```

## Verification commands run

```text
python -m compileall -q src tests          -> clean
PYTHONPATH=src pytest -q                   -> 25 passed
checkpoint load (CPU, EMA)                 -> OK, 15x10 chunk in 6.87 s
NutAssemblySquare env + 2 cameras + step   -> OK
live collision geometry                    -> aperture half 0.02275 m, peg half 0.016 m
16-step end-to-end rollout (CPU)           -> OK, 2 policy calls, 15.15 s
```
