"""Only two fixed classical model classes; no source-data paths or truth reader."""
import numpy as np

from .signals import commands, features, group_mse, motion, times


def weighted_stats(arrays):
    mean = np.mean([x.mean(axis=0) for x in arrays], axis=0)
    variance = np.mean([np.mean((x - mean)**2, axis=0) for x in arrays], axis=0)
    return mean, np.sqrt(np.maximum(variance, 0))


def fit_ridge(views, history, alpha, settings):
    xy = [features(v, history, 0, settings) for v in views]
    xs, ys = [p[0] for p in xy], [p[1] for p in xy]
    xm, xstd = weighted_stats(xs)
    ym, ystd = weighted_stats(ys)
    xscale = np.where(xstd > 1e-12, xstd, 1.)
    yscale = np.maximum(ystd, settings["output_scale_floors"])
    x = np.concatenate([(a - xm) / xscale for a in xs])
    y = np.concatenate([(b - ym) / yscale for b in ys])
    weights = np.concatenate([np.full(len(a), 1 / (len(xs)*len(a))) for a in xs])
    beta = np.linalg.solve(x.T @ (weights[:, None]*x) + alpha*np.eye(x.shape[1]), x.T @ (weights[:, None]*y))
    return {"history": history, "alpha": alpha, "xmean": xm.tolist(), "xscale": xscale.tolist(),
            "ymean": ym.tolist(), "yscale": yscale.tolist(), "beta": beta.tolist()}


def ridge_cost(view, model, candidate, settings):
    x, y = features(view, model["history"], candidate, settings)
    prediction = ((x - model["xmean"]) / model["xscale"]) @ np.asarray(model["beta"])
    target = (y - model["ymean"]) / model["yscale"]
    return group_mse(prediction - target)


def mean_response_cost(view, model, settings):
    idx = times(len(view["command"]), settings)
    return group_mse((motion(view)[idx] - model["ymean"]) / model["yscale"])


def correlation(a, b):
    a, b = a - a.mean(axis=0), b - b.mean(axis=0)
    denom = np.sqrt(np.sum(a*a, axis=0)*np.sum(b*b, axis=0))
    return np.divide(np.sum(a*b, axis=0), denom, out=np.zeros(a.shape[1]), where=denom > 1e-20)


def xcorr_cost(view, model, candidate, settings):
    idx = times(len(view["command"]), settings)
    cmd_idx = idx - model["phase"] - candidate
    assert cmd_idx.min() >= 0 and cmd_idx.max() < len(view["command"])
    if not model["active_axes"]:
        return 1.
    corrs = correlation(commands(view, settings)[cmd_idx, :3], motion(view)[idx, :3])
    return float(1 - np.mean(corrs[model["active_axes"]]))


def fit_xcorr(views, settings):
    _, us = weighted_stats([commands(v, settings)[:, :3] for v in views])
    _, vs = weighted_stats([motion(v)[:, :3] for v in views])
    active = np.flatnonzero((us >= 1e-5) & (vs >= 1e-6)).tolist()
    values = []
    for phase in settings["xcorr_phase_candidates"]:
        model = {"phase": phase, "active_axes": active}
        values.append(float(np.mean([xcorr_cost(v, model, 0, settings) for v in views])))
    chosen = int(np.argmin(values))
    return {"phase": settings["xcorr_phase_candidates"][chosen], "active_axes": active,
            "phase_mean_costs": values}


def curve(view, method, model, settings):
    function = xcorr_cost if method == "xcorr" else ridge_cost
    return np.asarray([function(view, model, d, settings) for d in settings["candidate_lags"]])


def summarize(scores, calibration, settings):
    scores = np.asarray(scores, dtype=float)
    assert scores.shape == (9,) and np.isfinite(scores).all()
    candidates = settings["candidate_lags"]
    tolerance = settings["tie_tolerance"] * max(1., float(np.max(np.abs(scores))))
    minimum = float(scores.min())
    tied = [d for d, s in zip(candidates, scores) if s <= minimum + tolerance]
    best = min(tied, key=lambda d: (abs(d), d))
    order = sorted(range(9), key=lambda j: (scores[j], abs(candidates[j]), candidates[j]))
    span = float(np.ptp(scores))
    gap = float(scores[order[1]] - scores[order[0]])
    flat = bool(span <= settings["flat_score_relative_tolerance"] * (1 + np.mean(np.abs(scores))))
    near = [d for d, s in zip(candidates, scores) if s <= minimum + calibration["tau"] * span + tolerance]
    return {"estimated_lag": best, "scores": scores.tolist(), "candidate_lags": candidates,
            "best_score": minimum, "second_best_score": float(scores[order[1]]),
            "score_gap": gap, "normalized_gap": gap/span if span > 1e-20 else 0.,
            "near_lags": near, "ambiguous": len(near) > 1, "unidentifiable": flat,
            "unreliable": bool(minimum > calibration["quality_q95"] or calibration["model_mismatch"])}


def calibrate(curves, model_mismatch, settings):
    zero = settings["candidate_lags"].index(0)
    excess = [(max(0., c[zero] - c.min()) / np.ptp(c)) if np.ptp(c) > 1e-20 else 1. for c in curves]
    return {"tau": float(min(1., max(settings["near_set_min_normalized_tolerance"],
                                     np.quantile(excess, settings["near_set_oof_excess_quantile"])))),
            "quality_q95": float(np.quantile([c.min() for c in curves], .95)),
            "model_mismatch": bool(model_mismatch), "oof_true_excess_normalized": list(map(float, excess))}
