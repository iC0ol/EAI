# B0 status

Date: 2026-11-10 (Asia/Shanghai).

## Official B0 — NOT STARTED (blocked)

The official B0 baseline requires the RTX 3090 (`evaluation.device: cuda:0`).
CUDA is unavailable on this workstation:

```text
nvidia-smi: Failed to initialize NVML: Driver/library version mismatch
             NVML library version: 580.178
/proc/driver/nvidia/version: kernel module 550.144.03
dpkg: nvidia-driver-580 / nvidia-dkms-580 = 580.178.04
torch 1.12.1+cu116: cuda_available=False
  RuntimeError: cudaGetDeviceCount -> Error 804:
  forward compatibility was attempted on non supported HW
```

The installed 580 kernel module cannot be loaded until the machine reboots; the
running kernel still has the old 550 module. No driver or system CUDA file was
modified. **No official B0 episode has been run and no B0 success rate is
claimed.**

## Pipeline validation performed on CPU

Because CUDA is blocked, the full loop was exercised on CPU with the same
checkpoint, simulator and code path. These runs are pipeline validation only,
not the protocol's 3090 baseline.

| Check | Result | Evidence |
|---|---|---|
| Checkpoint load (CPU, EMA) | OK; action chunk `(15, 10)`; 6.87 s per policy call | `reports/checkpoint_audit.json` |
| Env creation | `NutAssemblySquare`, 2×84×84 cameras, 7-D OSC, `control_delta=false` | console log |
| One env step | OK; observations `[3,84,84]` float32 in `[0,1]` | console log |
| Live geometry | aperture half 0.02275 m, peg half 0.016 m | console log |
| 16-step end-to-end rollout | OK; 2 policy calls; 15.15 s | `runs/cpu_pipeline_smoke/` |
| Full 500-step CPU smoke, seeds 100000/100001 | **0/2**; 63 policy calls each | `runs/cpu_smoke_full5/` |
| 500-step failure-mode diagnostic, seed 100000 | Robot approaches the SquareNut but hovers ~3–5 cm off and never closes the gripper (−1 = open) | `runs/diag500/`, `runs/diag100000/` |

The 0/2 CPU result is **not** an official baseline and is not yet interpreted
as a policy failure: the renderer is OSMesa/llvmpipe, while the checkpoint was
trained and evaluated with GPU OpenGL. A direct comparison against the official
`image.hdf5` observations is in progress (download at report time). If the
rendered frames match the stored training frames, the failure points to a real
harness bug and must be fixed before any GPU baseline.

CPU policy-call time is ~7 s versus a fraction of a second on a 3090, so 100
full episodes would take roughly 12 hours on CPU. That is neither the
authorized hardware condition nor a substitute for the official baseline.

## B1 — NOT STARTED

Blocked twice over:

1. B0 has not passed on the 3090.
2. The actual checkpoint has H=16, To=2, so only `16 − (2−1) = 15` future
   actions exist. `h=16` is invalid. Per the protocol and `AGENTS.md`, the
   harness fails closed and no padding/repetition/stale action is used. The
   horizon list needs a researcher-approved amendment before B1.

## B2 — BLOCKED

- The insertion-stage window (`z_gap_min_m`, `z_gap_max_m`,
  `max_xy_center_distance_m`) is not frozen in `configs/gate_b.yaml`
  (`stage_gate.frozen: false`). The harness refuses to collect B2 states.
- Snapshot/restore deterministic replay has not been executed on the live
  simulator.
- B0/B1 prerequisites are unmet.

No B2 state, branch or outcome was collected.

## Required next action

Reboot the workstation so the installed 580.178.04 kernel module is loaded,
then re-run the CUDA check and the official B0 smoke/baseline. A reboot will
terminate this agent session; the user/researcher must authorize and perform
it (or confirm that it may be done).
