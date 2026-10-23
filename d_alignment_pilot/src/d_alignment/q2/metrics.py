"""Post-freeze scoring mathematics. Never mounted into the estimator."""
import numpy as np


def repair_metrics(corrupted, oracle_full, crop, idx, estimated_lag, settings, limits, change_thresholds):
    original_times = crop + idx
    oracle = oracle_full[original_times]
    repaired = corrupted[idx-estimated_lag]
    difference = repaired - oracle
    trans_error = settings["translation_command_scale_m"] * difference[:, :3]
    rot_error = settings["rotation_command_scale_rad"] * difference[:, 3:6]
    grip_error = np.sign(repaired[:, 6]) != np.sign(oracle[:, 6])
    full_sign = np.sign(oracle_full[:, 6])
    switches = np.flatnonzero(np.diff(full_sign) != 0) + 1
    radius = limits["switch_radius_steps"]
    switch_mask = np.any(np.abs(original_times[:, None]-switches[None, :]) <= radius, axis=1)
    from .signals import change_signal
    g = change_signal(oracle_full)[original_times]
    low = g <= change_thresholds[0]
    high = (g >= change_thresholds[1]) & ~low
    masks = {"low_change": low, "middle_change": ~low & ~high, "high_change": high, "gripper_switch": switch_mask}

    def one(mask):
        n = int(mask.sum())
        return {"timesteps": n,
                "translation_command_rmse_m": float(np.sqrt(np.mean(np.sum(trans_error[mask]**2, axis=1)))) if n else None,
                "rotation_command_rmse_rad": float(np.sqrt(np.mean(np.sum(rot_error[mask]**2, axis=1)))) if n else None,
                "gripper_sign_disagreement": float(np.mean(grip_error[mask])) if n else None}

    overall = one(np.ones(len(idx), dtype=bool))
    switch_error = float(grip_error[switch_mask].mean()) if switch_mask.any() else None
    negligible = bool(overall["translation_command_rmse_m"] <= limits["translation_command_vector_rmse_m"] and
                      overall["rotation_command_rmse_rad"] <= limits["rotation_command_vector_rmse_rad"] and
                      overall["gripper_sign_disagreement"] <= limits["gripper_sign_disagreement_rate"] and
                      (switch_error is None or switch_error <= limits["gripper_switch_window_disagreement_rate"]))
    energy = (np.sum(trans_error**2, axis=1)/limits["translation_command_vector_rmse_m"]**2 +
              np.sum(rot_error**2, axis=1)/limits["rotation_command_vector_rmse_rad"]**2 + grip_error.astype(float)/.01)
    return {**overall, "action_exact": bool(np.array_equal(repaired, oracle)),
            "negligible_label_consequence": negligible,
            "gripper_switch_disagreement": switch_error,
            "meaningful_switch_error": bool(switch_error is not None and switch_error > limits["gripper_switch_window_disagreement_rate"]),
            "low_change_error_energy_fraction": float(energy[low].sum()/energy.sum()) if energy.sum() else 0.,
            "regions": {name: one(mask) for name, mask in masks.items()}}


def cluster_summary(rows, key, seed=9017, repeats=10000):
    episodes = sorted({r["episode"] for r in rows})
    means = []
    for episode in episodes:
        values = [float(r[key]) for r in rows if r["episode"] == episode and r.get(key) is not None]
        means.append(float(np.mean(values)) if values else np.nan)
    values = np.asarray(means)
    rng = np.random.default_rng(seed)
    draws = values[rng.integers(len(values), size=(repeats, len(values))) ]
    count = np.isfinite(draws).sum(axis=1)
    resampled = np.nansum(draws, axis=1)[count > 0] / count[count > 0]
    return {"mean": float(np.nanmean(values)) if np.isfinite(values).any() else None,
            "cluster_bootstrap_95ci": np.quantile(resampled, [.025, .975]).tolist() if len(resampled) else None,
            "independent_sources": len(episodes), "sources_with_metric": int(np.isfinite(values).sum())}


def midrank(scores, true_index, tolerance):
    values = np.asarray(scores)
    less = int(np.count_nonzero(values < values[true_index]-tolerance))
    equal = int(np.count_nonzero(np.abs(values-values[true_index]) <= tolerance))
    return less + (equal+1)/2
