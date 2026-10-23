"""Trusted launchers. Estimator never receives this module or source workspace."""
import datetime
import os
import shutil
import subprocess
import time
from pathlib import Path

from .common import deadline, read_json, sha256, write_json

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / "data/derived/q2_blind"
PUBLIC = ROOT / "outputs/q2_blind"
CONFIG = ROOT / "configs/q2_blind/experiment.json"
SAFE_MODULES = ("__init__.py", "common.py", "signals.py", "models.py", "fit.py", "estimate.py", "probe.py")


def snapshot_code(destination):
    package = Path(destination) / "d_alignment/q2"
    package.mkdir(parents=True, exist_ok=False)
    (package.parent / "__init__.py").write_text('"""Isolated Q2 runtime package."""\n')
    hashes = {}
    for filename in SAFE_MODULES:
        source = ROOT / "src/d_alignment/q2" / filename
        shutil.copyfile(source, package / filename)
        hashes[filename] = sha256(source)
    return hashes


def sandbox_command(code, mounts, output, module, arguments):
    # Runtime installations are read-only; EAI data and credentials are absent.
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
           "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
           "--ro-bind", "/home/asus/anaconda3", "/home/asus/anaconda3",
           "--ro-bind", str(ROOT / ".venv"), str(ROOT / ".venv"),
           "--ro-bind", str(code), "/code", "--bind", str(output), "/out",
           "--tmpfs", "/tmp", "--dev", "/dev", "--proc", "/proc", "--dir", "/work", "--chdir", "/work",
           "--setenv", "PYTHONPATH", "/code", "--setenv", "PYTHONNOUSERSITE", "1",
           "--setenv", "HOME", "/tmp", "--setenv", "PATH", "/usr/bin:/bin"]
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
        cmd += ["--setenv", variable, "2"]
    for host, guest in mounts:
        cmd += ["--ro-bind", str(host), guest]
    return cmd + [str(ROOT / ".venv/bin/python"), "-m", module] + list(arguments)


def forbidden_paths():
    return [str(ROOT / "data/raw/square_ph_low_dim_v15.hdf5"),
            str(ROOT / "data/manifests/injection_truth.json"),
            str(LOCAL / "private/truth.json"), str(CONFIG),
            "/code/d_alignment/q2/build.py", "/code/d_alignment/q2/score.py"]


def execute(cmd, log, timeout=600):
    started = time.monotonic()
    with Path(log).open("x") as handle:
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout)
    assert result.returncode == 0, f"Isolated command failed ({result.returncode}); see {log}"
    return time.monotonic() - started


def fit():
    deadline(read_json(CONFIG))
    started = time.monotonic()
    code = LOCAL / "fit_code"
    hashes = snapshot_code(code)
    output = LOCAL / "model"
    output.mkdir(exist_ok=False)
    mounts = [(LOCAL / "anchors", "/anchors"), (ROOT / "configs/q2_blind/estimator.json", "/settings.json")]
    logs = ROOT / "reports/q2_blind/logs"
    logs.mkdir(parents=True, exist_ok=True)
    probe_args = ["--output", "/out/access_probe.json"]
    for path in forbidden_paths():
        probe_args += ["--forbidden", path]
    execute(sandbox_command(code, mounts, output, "d_alignment.q2.probe", probe_args), logs / "anchor_access_probe.txt")
    execute(sandbox_command(code, mounts, output, "d_alignment.q2.fit",
                           ["--anchors", "/anchors", "--settings", "/settings.json", "--output", "/out"]), logs / "anchor_fit.txt")
    shutil.copyfile(output / "selection.json", PUBLIC / "anchor_model_selection.json")
    shutil.copyfile(output / "access_probe.json", PUBLIC / "anchor_access_probe.json")
    write_json(PUBLIC / "anchor_model_frozen.json", {"model_sha256": sha256(output / "model.json"),
               "selection_sha256": sha256(output / "selection.json"), "safe_code_sha256": hashes,
               "settings_sha256": sha256(ROOT / "configs/q2_blind/estimator.json"),
               "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "fit_wall_seconds": time.monotonic()-started, "query_samples_available_to_fitter": 0,
               "anchor_access_probe_passed": True})
    print("Anchor fit and active access probes passed; model frozen before query construction")


def predict():
    cfg = read_json(CONFIG)
    deadline(cfg)
    tests = read_json(PUBLIC / "preblind_tests.json")
    assert tests["passed"] and tests["failures"] == 0
    receipt = read_json(PUBLIC / "anchor_model_frozen.json")
    assert sha256(LOCAL / "model/model.json") == receipt["model_sha256"]
    for filename, expected in receipt["safe_code_sha256"].items():
        assert sha256(ROOT / "src/d_alignment/q2" / filename) == expected, "Estimator implementation changed after anchor freeze"
    blind = read_json(PUBLIC / "blind_input_hashes.json")
    assert len(blind["files"]) == cfg["test_samples"]
    assert read_json(PUBLIC / "blind_packet_audit.json")["passed"]
    out = LOCAL / "individual_predictions"
    out.mkdir(exist_ok=False)
    logdir = LOCAL / "prediction_logs"
    logdir.mkdir(exist_ok=False)
    code = LOCAL / "fit_code"
    started = time.monotonic()
    records = []
    probe_args = ["--output", "/out/query_access_probe.json"]
    for path in forbidden_paths() + [str(LOCAL / "anchors/anchor_0000.npz")]:
        probe_args += ["--forbidden", path]
    execute(sandbox_command(code, [(LOCAL / "model/model.json", "/model.json")], out,
                            "d_alignment.q2.probe", probe_args), logdir / "query_access_probe.txt")
    for sample in blind["dispatch_order"]:
        deadline(cfg)
        source = LOCAL / "queries" / f"{sample}.npz"
        assert sha256(source) == blind["files"][sample]
        target = out / sample
        target.mkdir()
        mounts = [(source, "/input.npz"), (LOCAL / "model/model.json", "/model.json")]
        execute(sandbox_command(code, mounts, target, "d_alignment.q2.estimate",
                                ["--input", "/input.npz", "--model", "/model.json", "--output", "/out/prediction.json"]), logdir / f"{sample}.txt", timeout=60)
        records.extend(read_json(target / "prediction.json"))
    assert len(records) == 2 * cfg["test_samples"]
    prediction_path = PUBLIC / "predictions.jsonl"
    import json
    with prediction_path.open("x") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    shutil.copyfile(out / "query_access_probe.json", PUBLIC / "query_access_probe.json")
    # Freeze results before the separate scorer has authority to read truth.
    write_json(PUBLIC / "predictions_frozen.json", {"predictions_sha256": sha256(prediction_path),
               "model_sha256": receipt["model_sha256"], "safe_code_sha256": receipt["safe_code_sha256"],
               "blind_inputs_sha256": sha256(PUBLIC / "blind_input_hashes.json"),
               "blind_packet_audit_sha256": sha256(PUBLIC / "blind_packet_audit.json"),
               "preblind_tests_sha256": sha256(PUBLIC / "preblind_tests.json"),
               "query_access_probe_sha256": sha256(PUBLIC / "query_access_probe.json"),
               "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "prediction_wall_seconds": time.monotonic()-started, "prediction_records": len(records),
               "isolated_processes": len(blind["dispatch_order"]), "truth_opened_by_estimator": False})
    os.chmod(prediction_path, 0o444)
    print("Frozen 224 predictions from 112 isolated single-packet processes; truth not read")
