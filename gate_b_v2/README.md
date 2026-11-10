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

**Important blockers are intentional:** the code refuses h=16 if checkpoint temporal alignment
leaves fewer than 16 future actions, and B2 refuses to collect states until the insertion-stage
window is researcher-frozen. No workstation checkpoint/MuJoCo integration run has yet been done.
