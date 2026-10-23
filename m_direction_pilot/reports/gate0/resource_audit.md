# Resource and methods audit

Read-only audit completed 2026-10-23 before all M suffixes. Detailed measured
configuration, all200 episode access checks and asset hashes are in
`resource_audit.json`. Original data51,145,256 bytes and each Clean checkpoint
66,283,884 bytes matched the expected SHA256. Both Clean runs have50,000 updates
and fixed final EMA weights. No training was executed here.

Installed Python3.9.13 venv, Torch2.2.2+cu121, MuJoCo3.2.3, robomimic0.4.0,
robosuite1.5.1; pinned DP source5ba07ac6661db573af695b419a7947ecb704690f.
GPU3090/24GiB, driver550.144.03. Initial sandbox GPU query could not access the
driver; the same read-only query outside the sandbox succeeded. GPU workloads
will use the approved project launcher outside that restriction. No driver,
CUDA, Python, ROS or system setting was modified. Optional robosuite_models and
private macro warnings do not prevent the existing Panda low-dim environment.

Environment construction confirmed world-frame delta OSC_POSE commands and
0.05m/0.5rad scaling. Official robomimic benchmark400-step evaluation horizon is
separate from the internal robosuite default1000; the experiment uses400 total
steps, including the replay prefix, as preregistered. Replay ability remains
unverified until A. Merely restoring flattened state is not accepted as A.

The old D data-time audit is background evidence about asynchronous derived
object sensors. M excludes those same fields and verifies live source fidelity;
no D predictions, misalignment experiment, training script or Q2 model is used.
No M v1 artifact or registration was found; the current branch is from the exact
requested frozen base. The two discussion source files referenced in the brief
are unavailable locally; their quoted v2 decisions suffice for this Gate0.

## Verified neighboring methods

- [SCRIM, arXiv2610.17709v1](https://arxiv.org/html/2610.17709v1), verified
  2026-10-23: trains a bounded adversarial disturbance policy and value critic
  around frozen imitation, scores expert demonstration states by downstream
  sensitivity and reweights BC. M would need evidence that a scalar score loses
  useful within-state direction structure. Gate0 trains neither adversary nor
  critic and establishes no novelty over SCRIM.
- [Set-Supervised Diffusion Policy, RSS2026 project](https://set-supervised-diffusion-policy.github.io/)
  and [arXiv2606.01865](https://arxiv.org/abs/2606.01865): uses paired undesired
  robot chunks and human corrective chunks to construct desired action sets.
  M's proposed metric is a different representation, but set-valued supervision
  is a strong neighboring mechanism; Gate0 does not compare trained policies.
- [AggreVaTeD, ICML2017](https://proceedings.mlr.press/v70/sun17d.html): uses
  training-time expert cost-to-go oracles for differentiable imitation updates.
  M measures binary outcomes under a frozen learned continuation, which is
  neither an expert cost-to-go oracle nor a demonstrated learning advantage.
- [Measuring the Stability Assumption Behind Action Chunking, arXiv2610.01626v1](https://arxiv.org/html/2610.01626v1):
  measures finite-horizon error propagation after action perturbations under
  open-loop and replanning execution. M instead asks about equal-norm signed
  directions and official task outcomes. Both require trustworthy paired forks;
  propagation rates are not interchangeable with task success or a Q Hessian.

These are mechanism checks from primary publications/project pages. They do not
establish M's innovation or require installing/running these methods at Gate0.
Unverified “TDC/directional compliance” is not introduced as a mandatory baseline.
