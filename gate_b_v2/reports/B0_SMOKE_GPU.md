# GPU Smoke Test (RTX 3090)

Date: 2026-11-11 12:01–12:23 Asia/Shanghai. Branch `codex/gate-b-v2`,
HEAD `043d189b53f8ddd3bbfeb30f3d78e22f37f6a416`.

This is an engineering check, **not** the formal B0 baseline.

## Environment

| Item | Value |
|---|---|
| Driver | 580.178.04 (kernel module and userspace) |
| GPU | NVIDIA GeForce RTX 3090, 24,576 MiB, capability (8, 6) |
| PyTorch | 1.12.1+cu116, CUDA runtime 11.6 |
| cuDNN | 8302 |
| Device used | `cuda:0` |
| Renderer | OSMesa CPU (validated against official frames) |
| Checkpoint | official `epoch=1950-test_mean_score=1.000.ckpt` |

CUDA verification (required script): `is_available=True`, GPU count 1, device
name `NVIDIA GeForce RTX 3090`, capability `(8, 6)`, 1024×1024 matmul and
`torch.cuda.synchronize()` succeeded.

## Configuration

Temporary config `logs/smoke_gpu_config.yaml` (not the formal config):
`seed_start=4,600,000` (independent diagnostic range), 10 episodes, h=8,
max_steps=500, `device=cuda:0`, video capture on.

## First attempt and fix

The first attempt aborted before any episode:

```text
Could not load library libcudnn_cnn_infer.so.8.
Error: libcuda.so: cannot open shared object file: No such file or directory
```

Cause: the 580 driver installs `libcuda.so.1` but no unversioned `libcuda.so`,
which cuDNN dlopens. A workspace-local symlink
`.cuda_compat/libcuda.so -> /usr/lib/x86_64-linux-gnu/libcuda.so.1` was added
to the launcher; no system file was modified. A real cuDNN convolution then
succeeded on the 3090. The failed run directory
`runs/b0_smoke_gpu_20261111/` is preserved as evidence and was not reused.

## Results

10/10 episodes completed and succeeded:

| Metric | Value |
|---|---|
| Episodes | 10 |
| Seeds | 4,600,000–4,600,009 (unique, no gaps) |
| Horizon | 8 |
| Steps per episode | 500 |
| Policy calls per episode | 63 |
| Successes | 10 |
| Success rate | 1.0 (engineering check only) |
| Mean wall time | 113.06 s |
| `success_error` | none |
| NaN / Inf / CUDA errors | none |
| Videos | 2 mp4 files, 251 frames each, 10 fps |

Manifest confirms `action_dim=10`, `abs_action=true`, `env_action_dim=7`,
`control_delta=false`, H=16, To=2, available future actions 15.

GPU monitoring during the smoke: max utilization 90 %, mean 34.9 %, max
memory 3,567 MiB. The policy therefore ran on the RTX 3090, not on CPU.

Videos are written at 96×96 by the H.264 encoder (dimension padding); the
policy observations remain 84×84 float32 in `[0, 1]`, as verified earlier and
by the successful forward passes.

## Coexisting process

PID 2371 (`python -m app.container role --role trainer`, another user) was
running throughout: 0 % GPU utilization during checks and 298 MiB GPU memory.
It did not conflict with the smoke; it was not killed or modified.

## Evidence

- `reports/b0_smoke_gpu_episodes.jsonl`
- `reports/b0_smoke_gpu_summary.json`
- `reports/b0_smoke_gpu_manifest.json`
- `reports/gpu_monitor_smoke_summary.json`
- raw run: `runs/b0_smoke_gpu_20261111b/`
