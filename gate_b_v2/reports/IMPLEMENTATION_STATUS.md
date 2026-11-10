# Gate B v2 code implementation status

Date: 2026-11-10

## Implemented in this branch

- Checkpoint-native policy loading through the upstream Diffusion Policy workspace payload.
- Square-MH image environment construction through the upstream robomimic and DP wrappers.
- B0 smoke and fixed-h=8 baseline runners.
- B1 paired horizon runner with deterministic initial-state hash checks.
- Full `action_pred` extraction for variable execution lengths.
- Collision-geometry-derived SquareNut aperture and square peg projected signed clearance, with
  axial z gap logged separately.
- Snapshot/restore capture, replay validation, and B2 branch runner.
- JSONL logs, asset manifest, videos/frame fallback, and paired/cluster-bootstrap analysis.
- Unit tests for temporal alignment, horizon validation, observation stacking, synthetic SquareNut
  clearance, and interaction-slope analysis.

## Local verification performed during code authoring

- `PYTHONPATH=src python -m pytest -q`: **8 passed**.
- `python -m compileall -q src tests`: passed.

These tests do not import or run Diffusion Policy, robomimic, robosuite, MuJoCo, the checkpoint, or
the Square-MH HDF5 dataset. No checkpoint was downloaded or loaded, no simulator was started, and
no B0/B1/B2 benchmark was run during code authoring.

## Explicit workstation integration gates

1. Verify the checkpoint's actual `n_obs_steps` and available future action count. With H=16 and
   To=2, only 15 future actions are executable; current code fails closed for h=16.
2. Verify camera observation shapes and dtypes against checkpoint `shape_meta`.
3. Verify actual task success predicate/reward and local B0 baseline.
4. Validate live geometry identification against the installed SquareNut and peg collision geoms.
5. Approve/freeze B2 insertion-stage bounds before state collection.
6. Pass deterministic snapshot/restore replay on the real simulator before B2.

## No scientific result claimed

The code is an experiment harness, not evidence for CAC. The Gate B protocol remains unexecuted.
