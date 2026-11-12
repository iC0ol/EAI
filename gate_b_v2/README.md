# Gate B v2 — Square-MH experiment harness

The source package is uploaded atomically as the repository-root archive `gate_b_v2_source.tar.xz`.
From the repository root, unpack it with:

```bash
tar -xJf gate_b_v2_source.tar.xz -C .
cd gate_b_v2
```

Archive SHA256: `5a4a43e0b0a4f1476f10e0c5d6bfe233b64d34fa03dccdc432c7d86a30eaaa7b`.

Then read `reports/IMPLEMENTATION_STATUS.md`, `configs/gate_b.yaml`, and this directory's
`AGENTS.md`. The code is an evaluation harness only: it does not train CAC or modify the official
checkpoint. Run `python -m pytest -q` before simulator work.

**Important boundaries are intentional:** the B1 protocol is amended to
`h ∈ {1,2,4,8,15}` because H=16 with To=2 leaves 15 executable future actions; the code still
refuses h=16. B1 Pilot uses seeds 200000–200019 and B1 Full uses 200020–200119 (120 disjoint
states, no Pilot reuse), with separate records/manifests, locked 20×5 / 100×5 counts and a strict
analysis completeness gate. B1 is also locked to the B0-verified checkpoint/dataset/DP-tree
SHA256, max_steps=500, H=16/To=2, RTX 3090, torch/CUDA versions, `cuda:0` and policy offset; the
B1 CLI accepts only `--b1-phase` and `--run-dir`. B1 cannot collect B2 states; B2 refuses to
collect states until its insertion-stage window is researcher-frozen. B0 is complete at 84/100 on
the RTX 3090 (`reports/B0_REPORT.md`). B1 has **not** been run and awaits explicit authorization;
see `reports/B1_FINAL_READINESS_REPORT.md`.
