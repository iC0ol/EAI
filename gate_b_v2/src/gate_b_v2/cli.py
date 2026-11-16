from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .analysis import analyze_b1, analyze_b2_split, write_b2_report, write_markdown_summary
from .core import utc_run_id, write_json
from .geometry import run_live_geometry_audit
from .harvest import harvest_split, run_preflight_smoke, run_source_episode
from .locks import load_b1_full_manifest, validate_b2_config
from .runner import GateBExperiment, _resolve_runtime_paths


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_config(path: Optional[str]) -> Dict[str, Any]:
    config_path = Path(path).expanduser() if path else (_project_root() / "configs" / "gate_b.yaml")
    if not config_path.is_absolute():
        config_path = (_project_root() / config_path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError("Config not found: {}".format(config_path))
    with config_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Config root must be a YAML mapping")
    return config


def _add_runtime_args(parser: argparse.ArgumentParser, include_run_dir: bool = True) -> None:
    parser.add_argument("--config", default=None, help="YAML config; defaults to configs/gate_b.yaml")
    parser.add_argument("--dp-root", default=None, help="Path to official Diffusion Policy source checkout")
    parser.add_argument("--checkpoint", default=None, help="Square-MH image CNN checkpoint path")
    parser.add_argument("--dataset", default=None, help="Square-MH image HDF5 dataset path")
    parser.add_argument("--max-steps", type=int, default=None, help="Override official runner max_steps")
    if include_run_dir:
        parser.add_argument("--run-dir", default=None, help="Existing or new run directory")


def _new_run_dir(config: Dict[str, Any], project_root: Path, explicit: Optional[str]) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path.resolve() if path.is_absolute() else (project_root / path).resolve()
    output_root = Path(config["paths"].get("output_root", "runs")).expanduser()
    if not output_root.is_absolute():
        output_root = (project_root / output_root).resolve()
    return output_root / utc_run_id()


def _build_experiment(args: argparse.Namespace, config: Dict[str, Any], require_existing: bool = False) -> GateBExperiment:
    project_root = _project_root()
    dp_root, checkpoint, dataset = _resolve_runtime_paths(
        config, project_root,
        {"dp_root": args.dp_root, "checkpoint": args.checkpoint, "dataset": args.dataset},
    )
    run_dir = _new_run_dir(config, project_root, getattr(args, "run_dir", None))
    if require_existing and not run_dir.is_dir():
        raise FileNotFoundError("Run directory does not exist: {}".format(run_dir))
    return GateBExperiment(
        config=config,
        project_root=project_root,
        dp_root=dp_root,
        checkpoint=checkpoint,
        dataset=dataset,
        run_dir=run_dir,
        max_steps_override=args.max_steps,
    )


def _cmd_audit(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    project_root = _project_root()
    dp_root, checkpoint, dataset = _resolve_runtime_paths(
        config, project_root,
        {"dp_root": args.dp_root, "checkpoint": args.checkpoint, "dataset": args.dataset},
    )
    checks = {
        "dp_root_exists": dp_root.is_dir(),
        "dp_root_has_diffusion_policy": (dp_root / "diffusion_policy").is_dir(),
        "checkpoint_exists": checkpoint.is_file(),
        "dataset_exists": dataset.is_file(),
        "checkpoint_path": str(checkpoint),
        "dataset_path": str(dataset),
        "dp_root": str(dp_root),
        "note": "Audit does not load weights, install packages, or start simulation.",
    }
    if checkpoint.is_file():
        checks["checkpoint_bytes"] = checkpoint.stat().st_size
    if dataset.is_file():
        checks["dataset_bytes"] = dataset.stat().st_size
    out = Path(args.output or (project_root / "audit_assets.json")).expanduser()
    if not out.is_absolute():
        out = (project_root / out).resolve()
    write_json(out, checks)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("Wrote {}".format(out))
    return 0 if all(checks[k] for k in ("dp_root_exists", "dp_root_has_diffusion_policy", "checkpoint_exists", "dataset_exists")) else 2


def _cmd_smoke(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    experiment = _build_experiment(args, config)
    try:
        path = experiment.run_smoke(args.episodes)
        print("Smoke episodes written to {}".format(path))
        print(json.dumps(experiment._summarize(path), indent=2))
    finally:
        experiment.close()
    return 0


def _cmd_b0(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    experiment = _build_experiment(args, config)
    try:
        path = experiment.run_b0_baseline(args.episodes)
        print("B0 baseline written to {}".format(path))
        print(json.dumps(experiment._summarize(path), indent=2))
    finally:
        experiment.close()
    return 0


def _cmd_b1(args: argparse.Namespace) -> int:
    # Formal B1 ignores user paths/overrides. The fixed project config is
    # loaded and every critical value is re-validated in run_b1 against the
    # B0-derived lock.
    config = _load_config(None)
    locked_args = argparse.Namespace(
        dp_root=None,
        checkpoint=None,
        dataset=None,
        max_steps=None,
        run_dir=args.run_dir,
    )
    experiment = _build_experiment(locked_args, config)
    try:
        path = experiment.run_b1(args.b1_phase)
        print("B1 episodes written to {}".format(path))
        print("Run directory: {}".format(experiment.run_dir))
    finally:
        experiment.close()
    return 0


def _build_b2_experiment(args: argparse.Namespace, require_existing: bool) -> GateBExperiment:
    """Build the B2 experiment from the fixed config only.

    B2 deliberately exposes no checkpoint/dataset/DP-root/max-steps/device or
    config override.  The only user-supplied path is the run directory.
    """
    config = _load_config(None)
    validate_b2_config(config)
    locked_args = argparse.Namespace(
        dp_root=None,
        checkpoint=None,
        dataset=None,
        max_steps=None,
        run_dir=args.run_dir,
    )
    return _build_experiment(locked_args, config, require_existing=require_existing)


def _cmd_b2_geometry_audit(args: argparse.Namespace) -> int:
    experiment = _build_b2_experiment(args, require_existing=False)
    try:
        experiment.env.reset(299999)
        output = Path(args.output).expanduser() if args.output else (
            experiment.run_dir / "b2_geometry_audit.json"
        )
        if not output.is_absolute():
            output = (experiment.run_dir / output).resolve()
        audit = run_live_geometry_audit(experiment.env.robosuite_env, output)
        print("Geometry audit written to {}".format(output))
        print(json.dumps({"status": audit["status"], "reason": audit.get("reason")}, indent=2))
        return 0 if audit["status"] == "PASS" else 2
    finally:
        experiment.close()


def _cmd_b2_harvest(args: argparse.Namespace) -> int:
    experiment = _build_b2_experiment(args, require_existing=False)
    try:
        path = harvest_split(experiment, args.split)
        print("B2 {} state manifest written to {}".format(args.split, path))
    finally:
        experiment.close()
    return 0


def _cmd_b2(args: argparse.Namespace) -> int:
    experiment = _build_b2_experiment(args, require_existing=True)
    try:
        path = experiment.run_b2(args.split)
        print("B2 {} branch episodes written to {}".format(args.split, path))
    finally:
        experiment.close()
    return 0


def _cmd_b2_preflight(args: argparse.Namespace) -> int:
    experiment = _build_b2_experiment(args, require_existing=False)
    try:
        preflight_dir = experiment.run_dir
        audit_path = preflight_dir / "b2_geometry_audit.json"
        experiment.env.reset(int(args.seed))
        audit = run_live_geometry_audit(experiment.env.robosuite_env, audit_path)

        experiment.env.reset(int(args.seed))
        snapshot_dir = preflight_dir / "snapshots" / "preflight"
        record = run_source_episode(
            experiment,
            "preflight",
            int(args.seed),
            snapshot_dir,
            preflight=True,
            fallback_step=int(args.fallback_step),
        )
        if record is None:
            raise RuntimeError("PREFLIGHT snapshot capture failed for seed {}".format(args.seed))
        validation_path = experiment._validate_all_b2_snapshots([record], "preflight")
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        smoke_records = None
        if args.smoke_seeds:
            smoke_seeds = [int(item.strip()) for item in args.smoke_seeds.split(",") if item.strip()]
            smoke_records = run_preflight_smoke(
                experiment, preflight_dir / "state_smoke", smoke_seeds
            )
        summary = {
            "marker": "PREFLIGHT",
            "scientific_data": False,
            "seed": int(args.seed),
            "geometry_audit": audit_path.name,
            "geometry_status": audit["status"],
            "snapshot_file": record["snapshot_file"],
            "snapshot_sha256": record["snapshot_sha256"],
            "gate_reached": bool(not record.get("preflight_fallback", False)),
            "snapshot_validation": validation_path.name,
            "snapshot_validation_all_passed": bool(validation["all_passed"]),
            "state_smoke_records": str(smoke_records) if smoke_records is not None else None,
            "note": "Throwaway preflight; excluded from B2 formal discovery/confirmation data.",
        }
        write_json(preflight_dir / "b2_preflight_summary.json", summary)
        print(json.dumps(summary, indent=2))
        if audit["status"] != "PASS" or not validation["all_passed"]:
            return 2
    finally:
        experiment.close()
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError("Run directory does not exist: {}".format(run_dir))
    config = _load_config(args.config)
    evaluation = config["evaluation"]
    n_bootstrap = int(args.bootstrap_samples)
    seed = int(args.seed)
    results = {}
    b1_file = (
        run_dir / "b1_{}_episodes.jsonl".format(args.b1_phase)
        if args.b1_phase
        else None
    )
    if b1_file is not None and b1_file.is_file():
        results["b1_{}".format(args.b1_phase)] = analyze_b1(
            run_dir,
            n_bootstrap=n_bootstrap,
            seed=seed,
            phase=args.b1_phase,
            reference=int(evaluation.get("b1_reference_horizon", 8)),
            alpha=float(evaluation.get("b1_alpha", 0.05)),
            practical_diff=float(evaluation.get("b1_practical_diff", 0.08)),
            ceiling_threshold=float(evaluation.get("b1_ceiling_threshold", 0.95)),
            floor_threshold=float(evaluation.get("b1_floor_threshold", 0.05)),
            expected_horizons=[int(x) for x in evaluation.get("horizons", [1, 2, 4, 8, 15])],
            expected_phase_ranges={
                "pilot": (int(evaluation.get("b1_pilot_seed_start", 200000)),
                          int(evaluation.get("b1_pilot_episodes", 20))),
                "full": (int(evaluation.get("b1_full_seed_start", 200020)),
                         int(evaluation.get("b1_full_episodes", 100))),
            },
        )
    elif args.b1_phase is not None:
        raise FileNotFoundError("B1 {} records not found: {}".format(args.b1_phase, b1_file))
    elif any(
        (run_dir / name).is_file()
        for name in ("b1_pilot_episodes.jsonl", "b1_full_episodes.jsonl", "b1_episodes.jsonl")
    ):
        results["b1"] = analyze_b1(
            run_dir,
            n_bootstrap=n_bootstrap,
            seed=seed,
            phase=None,
            reference=int(evaluation.get("b1_reference_horizon", 8)),
            alpha=float(evaluation.get("b1_alpha", 0.05)),
            practical_diff=float(evaluation.get("b1_practical_diff", 0.08)),
            ceiling_threshold=float(evaluation.get("b1_ceiling_threshold", 0.95)),
            floor_threshold=float(evaluation.get("b1_floor_threshold", 0.05)),
            expected_horizons=[int(x) for x in evaluation.get("horizons", [1, 2, 4, 8, 15])],
            expected_phase_ranges={
                "pilot": (int(evaluation.get("b1_pilot_seed_start", 200000)),
                          int(evaluation.get("b1_pilot_episodes", 20))),
                "full": (int(evaluation.get("b1_full_seed_start", 200020)),
                         int(evaluation.get("b1_full_episodes", 100))),
            },
        )
    for split in ("discovery", "confirmation"):
        if (run_dir / "b2_{}_episodes.jsonl".format(split)).is_file():
            analysis = analyze_b2_split(
                run_dir, split, n_bootstrap=n_bootstrap, seed=seed, config=config
            )
            write_b2_report(run_dir, split, analysis)
            results["b2_{}".format(split)] = analysis
    summary = write_markdown_summary(run_dir)
    print("Analysis complete: {}".format(summary))
    print(json.dumps({key: value.get("n_initial_states", value.get("n_states")) for key, value in results.items()}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Square-MH Gate B v2 experiment harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Check asset paths only; does not load model or run simulation")
    _add_runtime_args(audit, include_run_dir=False)
    audit.add_argument("--output", default=None)
    audit.set_defaults(func=_cmd_audit)

    smoke = subparsers.add_parser("smoke", help="Run 5-10 B0 smoke episodes at the checkpoint's default h=8")
    _add_runtime_args(smoke)
    smoke.add_argument("--episodes", type=int, default=None)
    smoke.set_defaults(func=_cmd_smoke)

    b0 = subparsers.add_parser("b0", help="Run fixed-h=8 local baseline episodes")
    _add_runtime_args(b0)
    b0.add_argument("--episodes", type=int, default=None)
    b0.set_defaults(func=_cmd_b0)

    b1 = subparsers.add_parser(
        "b1",
        help="Run the locked formal paired horizon sweep (Pilot or Full)",
    )
    b1.add_argument("--b1-phase", choices=["pilot", "full"], default="pilot",
                    help="Pilot (20 states) or Full (100 states); counts locked by config")
    b1.add_argument("--run-dir", default=None, help="Existing or new run directory")
    b1.set_defaults(func=_cmd_b1)

    b2_geometry = subparsers.add_parser(
        "b2-geometry-audit",
        help="Run the live MuJoCo collision-geometry audit (PREFLIGHT only)",
    )
    b2_geometry.add_argument("--run-dir", default=None, help="Run directory for audit output")
    b2_geometry.add_argument("--output", default=None, help="Audit JSON path (default: run dir)")
    b2_geometry.set_defaults(func=_cmd_b2_geometry_audit)

    b2_harvest = subparsers.add_parser(
        "b2-harvest",
        help="Harvest and deterministically select 30 B2 states for one split",
    )
    b2_harvest.add_argument("--split", choices=["discovery", "confirmation"], required=True)
    b2_harvest.add_argument("--run-dir", default=None, help="Run directory (new for each split)")
    b2_harvest.set_defaults(func=_cmd_b2_harvest)

    b2_preflight = subparsers.add_parser(
        "b2-preflight",
        help="Reserved-seed snapshot/restore and geometry PREFLIGHT; never scientific data",
    )
    b2_preflight.add_argument("--run-dir", default=None, help="Preflight run directory")
    b2_preflight.add_argument("--seed", type=int, default=299999,
                              help="Reserved preflight seed (default 299999)")
    b2_preflight.add_argument("--fallback-step", type=int, default=500,
                              help="Capture a preflight snapshot at this step if the gate is not reached")
    b2_preflight.add_argument("--smoke-seeds", default=None,
                              help="Optional comma-separated non-formal seeds for a throwaway state smoke test")
    b2_preflight.set_defaults(func=_cmd_b2_preflight)

    b2 = subparsers.add_parser(
        "b2",
        help="Run the locked B2 matched-state branch experiment for one split",
    )
    b2.add_argument("--split", choices=["discovery", "confirmation"], required=True)
    b2.add_argument("--run-dir", default=None, help="Existing B2 run directory")
    b2.set_defaults(func=_cmd_b2)

    analyze = subparsers.add_parser("analyze", help="Analyze saved B1/B2 JSONL results")
    analyze.add_argument("--run-dir", required=True)
    analyze.add_argument("--config", default=None, help="YAML config for B1 statistical settings")
    analyze.add_argument("--b1-phase", choices=["pilot", "full"], default=None,
                         help="Select b1_pilot/b1_full records; auto-detect if omitted")
    analyze.add_argument("--bootstrap-samples", type=int, default=5000)
    analyze.add_argument("--seed", type=int, default=20261110)
    analyze.set_defaults(func=_cmd_analyze)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted; partial JSONL records remain in the run directory.", file=sys.stderr)
        return 130
    except Exception as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
