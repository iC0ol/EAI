from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .analysis import analyze_b1, analyze_b2_split, write_markdown_summary
from .core import utc_run_id, write_json
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
    config = _load_config(args.config)
    experiment = _build_experiment(args, config)
    try:
        path = experiment.run_b1(args.episodes, collect_b2_states=args.collect_b2_states)
        print("B1 episodes written to {}".format(path))
        print("Run directory: {}".format(experiment.run_dir))
    finally:
        experiment.close()
    return 0


def _cmd_b2(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    experiment = _build_experiment(args, config, require_existing=True)
    try:
        path = experiment.run_b2(args.split)
        print("B2 episodes written to {}".format(path))
    finally:
        experiment.close()
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError("Run directory does not exist: {}".format(run_dir))
    n_bootstrap = int(args.bootstrap_samples)
    seed = int(args.seed)
    results = {}
    if (run_dir / "b1_episodes.jsonl").is_file():
        results["b1"] = analyze_b1(run_dir, n_bootstrap=n_bootstrap, seed=seed)
    for split in ("discovery", "confirmation"):
        if (run_dir / "b2_{}_episodes.jsonl".format(split)).is_file():
            results["b2_{}".format(split)] = analyze_b2_split(
                run_dir, split, n_bootstrap=n_bootstrap, seed=seed
            )
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

    b1 = subparsers.add_parser("b1", help="Run paired full-episode horizon sweep")
    _add_runtime_args(b1)
    b1.add_argument("--episodes", type=int, default=None)
    b1.add_argument("--collect-b2-states", action="store_true")
    b1.set_defaults(func=_cmd_b1)

    b2 = subparsers.add_parser("b2", help="Run matched-state B2 branches from a B1 run directory")
    _add_runtime_args(b2)
    b2.add_argument("--split", choices=["discovery", "confirmation"], required=True)
    b2.set_defaults(func=_cmd_b2)

    analyze = subparsers.add_parser("analyze", help="Analyze saved B1/B2 JSONL results")
    analyze.add_argument("--run-dir", required=True)
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
