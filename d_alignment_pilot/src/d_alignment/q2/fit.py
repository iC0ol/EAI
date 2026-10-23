"""Anchor-only LOEO selection; this program is mounted without query access."""
import argparse
from pathlib import Path

import numpy as np

from .common import load_view, read_json, sha256, write_json
from .models import calibrate, curve, fit_ridge, fit_xcorr, mean_response_cost, ridge_cost
from .signals import change_signal, times


def fit_anchors(views, settings):
    assert len(views) == 8
    records = []
    for history in settings["history_candidates"]:
        for alpha in settings["ridge_candidates"]:
            validation, baseline = [], []
            for fold in range(8):
                training = [v for j, v in enumerate(views) if j != fold]
                fitted = fit_ridge(training, history, alpha, settings)
                validation.append(ridge_cost(views[fold], fitted, 0, settings))
                baseline.append(mean_response_cost(views[fold], fitted, settings))
            records.append({"history": history, "alpha": alpha, "fold_costs": validation,
                            "mean_cost": float(np.mean(validation)), "fold_mean_response_costs": baseline})
    best = min(r["mean_cost"] for r in records)
    chosen = min((r for r in records if r["mean_cost"] <= best + 1e-12), key=lambda r: (r["history"], -r["alpha"]))
    r2 = 1 - chosen["mean_cost"] / np.mean(chosen["fold_mean_response_costs"])
    oof = {"xcorr": [], "arx": []}
    fold_phases = []
    for fold in range(8):
        training = [v for j, v in enumerate(views) if j != fold]
        xc = fit_xcorr(training, settings)
        ar = fit_ridge(training, chosen["history"], chosen["alpha"], settings)
        oof["xcorr"].append(curve(views[fold], "xcorr", xc, settings))
        oof["arx"].append(curve(views[fold], "arx", ar, settings))
        fold_phases.append(xc["phase"])
    zero = settings["candidate_lags"].index(0)
    correlation = float(np.mean([1-c[zero] for c in oof["xcorr"]]))
    full_xc = fit_xcorr(views, settings)
    full_ar = fit_ridge(views, chosen["history"], chosen["alpha"], settings)
    cal = {"xcorr": calibrate(oof["xcorr"], correlation < .1, settings),
           "arx": calibrate(oof["arx"], r2 < 0, settings)}
    changes = np.concatenate([change_signal(v["command"])[times(len(v["command"]), settings)] for v in views])
    quantiles = np.quantile(changes, settings["motion_quantiles"]).tolist()
    model = {"settings": settings, "xcorr": full_xc, "arx": full_ar, "calibration": cal,
             "change_quantiles": quantiles}
    selection = {"folds": 8, "rule": "LOEO mean clean-response group MSE; fold normalization fitted on seven anchors",
                 "anchor_sample_ids": [str(v["sample_id"]) for v in views],
                 "grid": records, "selected_history": chosen["history"], "selected_alpha": chosen["alpha"],
                 "arx_oof_R2": float(r2), "xcorr_oof_correlation": correlation,
                 "xcorr_phase": full_xc["phase"], "xcorr_phase_costs": full_xc["phase_mean_costs"],
                 "xcorr_active_axes": full_xc["active_axes"], "fold_xcorr_phases": fold_phases,
                 "oof_candidate_scores": {k: [c.tolist() for c in values] for k, values in oof.items()},
                 "calibration": cal, "change_quantiles": quantiles,
                 "query_samples_used_for_fitting_or_selection": 0}
    return model, selection


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--anchors", required=True)
    p.add_argument("--settings", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    paths = sorted(Path(args.anchors).glob("*.npz"))
    model, selection = fit_anchors([load_view(p) for p in paths], read_json(args.settings))
    out = Path(args.output)
    write_json(out / "model.json", model)
    selection["model_sha256"] = sha256(out / "model.json")
    selection["input_hashes"] = {p.name: sha256(p) for p in paths}
    write_json(out / "selection.json", selection)
    print(f"Anchor-only selection complete: H={selection['selected_history']}, lambda={selection['selected_alpha']}")


if __name__ == "__main__":
    main()
