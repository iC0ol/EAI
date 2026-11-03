"""Float64 CPU arithmetic, fixed dual baselines, no fitted constants."""
import numpy as np


def ratio(numerator, denominator):
    return None if denominator == 0 else float(numerator/denominator)


def score(prediction_raw, target_raw, valid, std):
    prediction_raw = np.asarray(prediction_raw, np.float64)
    target_raw = np.asarray(target_raw, np.float64)
    valid = np.asarray(valid, bool); std = np.asarray(std, np.float64)
    error = prediction_raw-target_raw
    e = error/std
    return dict(xyz_normalized_MAE=float(np.abs(e[valid, :3]).mean()),
        all7_normalized_MAE=float(np.abs(e[valid]).mean()),
        all7_normalized_RMSE=float(np.sqrt(np.square(e[valid]).mean())),
        normalized_MAE_by_dim=np.abs(e[valid]).mean(0).tolist(),
        normalized_RMSE_by_dim=np.sqrt(np.square(e[valid]).mean(0)).tolist(),
        raw_MAE_by_dim=np.abs(error[valid]).mean(0).tolist(),
        raw_RMSE_by_dim=np.sqrt(np.square(error[valid]).mean(0)).tolist(),
        raw_MAE=float(np.abs(error[valid]).mean()),
        valid_steps=int(valid.sum()))


def direction_gripper(prediction, target, valid):
    prediction, target = np.asarray(prediction, float), np.asarray(target, float)
    valid = np.asarray(valid, bool)
    pnorm = np.linalg.norm(prediction[:, :3], axis=1)
    tnorm = np.linalg.norm(target[:, :3], axis=1)
    eligible = valid & (tnorm > 1e-6)
    active = eligible & (pnorm > 1e-6)
    cosine = np.zeros(len(valid), np.float64)  # keep small predictions as zero, do not delete them
    cosine[active] = (prediction[active, :3]*target[active, :3]).sum(1)/(pnorm[active]*tnorm[active])
    cosine = np.clip(cosine, -1, 1)
    ps, ts = np.sign(prediction[:, 6]), np.sign(target[:, 6])
    adjacent = valid[:-1] & valid[1:]
    pt, tt = ps[1:] != ps[:-1], ts[1:] != ts[:-1]
    return dict(cosine_mean=float(cosine[eligible].mean()) if eligible.any() else None,
        expert_direction_valid_count=int(eligible.sum()), small_prediction_count=int((eligible & ~active).sum()),
        xyz_axis_sign_accuracy=(np.sign(prediction[valid, :3]) == np.sign(target[valid, :3])).mean(0).tolist(),
        gripper_sign_accuracy=float((ps[valid] == ts[valid]).mean()),
        gripper_zero_prediction_count=int((ps[valid] == 0).sum()),
        gripper_transition_hamming=float((pt[adjacent] != tt[adjacent]).mean()) if adjacent.any() else None,
        expert_transition_count=int(tt[adjacent].sum()), predicted_transition_count=int(pt[adjacent].sum()),
        valid_adjacent_pairs=int(adjacent.sum()),
        transition_interpretation='no extra false transitions alone does not establish timing ability')


def aggregate(predictions, targets, masks, std):
    rows = [score(p, t, m, std) for p, t, m in zip(predictions, targets, masks)]
    pool = np.concatenate([(np.asarray(p, float)-np.asarray(t, float))[m]/std
                           for p, t, m in zip(predictions, targets, masks)])
    return dict(xyz_normalized_MAE=float(np.mean([x['xyz_normalized_MAE'] for x in rows])),
        all7_normalized_MAE=float(np.mean([x['all7_normalized_MAE'] for x in rows])),
        mean_state_normalized_RMSE=float(np.mean([x['all7_normalized_RMSE'] for x in rows])),
        pooled_valid_step_normalized_RMSE=float(np.sqrt(np.square(pool).mean())),
        normalized_MAE_by_dim=np.mean([x['normalized_MAE_by_dim'] for x in rows], axis=0).tolist(),
        raw_MAE_by_dim=np.mean([x['raw_MAE_by_dim'] for x in rows], axis=0).tolist())


def average_direction(rows):
    result = {}
    for key in ['cosine_mean', 'gripper_sign_accuracy', 'gripper_transition_hamming']:
        values = [r[key] for r in rows if r[key] is not None]
        result[key] = float(np.mean(values)) if values else None
    result['samples_with_eligible_direction'] = sum(r['cosine_mean'] is not None for r in rows)
    return result


def entry_agreement(first, repeats):
    rows = []
    for sample in [0, 1, 4, 5]:
        a, b = first[sample]['official_prior'], first[sample]['custom_prior']
        diff = float(np.abs(a-b).max())
        row = dict(sample=sample, bit_equal=bool(np.array_equal(a, b)), normalized_maxabs=diff)
        if sample in [0, 1]:
            noise = {branch: float(np.abs(repeats[sample][branch]-first[sample][branch]).max())
                     for branch in ['official_prior', 'custom_prior']}
            unstable = any(v > 1e-3 for v in noise.values())
            tolerance = max(1e-5, 2*max(noise.values()))
            row.update(repeat_maxabs=noise, tolerance=tolerance, numeric_unstable=unstable,
                       passed=not unstable and diff <= tolerance, scope='this repeated state only')
        else:
            row.update(tolerance=1e-5, numeric_unstable=None, passed=diff <= 1e-5,
                       scope='single pair agreement only; no repeat stability claim/no borrowed noise')
        rows.append(row)
    return rows


def investment_decision(scores, per_state, direction, entry_pass):
    official, median, mean = [scores[k] for k in ['official_prior', 'median', 'mean']]
    if not entry_pass:
        return 'NUMERICAL_OR_ENTRY_INCONCLUSIVE'
    if any(scores[b][key] <= 1e-8 for b in ['median', 'mean']
           for key in ['xyz_normalized_MAE', 'all7_normalized_MAE']):
        return 'INCONCLUSIVE_NEAR_ZERO_FLOOR'
    a, b = direction['official_prior'], direction['median']
    if any(a[k] is None or b[k] is None for k in ['cosine_mean', 'gripper_transition_hamming']):
        return 'INCONCLUSIVE_DIRECTION_OR_TRANSITION_UNDEFINED'
    degraded = (a['cosine_mean'] < b['cosine_mean']-1e-8
                or a['gripper_sign_accuracy'] < b['gripper_sign_accuracy']-1e-8
                or a['gripper_transition_hamming'] > b['gripper_transition_hamming']+1e-8)
    if degraded:
        return 'INCONCLUSIVE_DIRECTION_GRIPPER_DEGRADATION'
    good = [r for r in per_state if all(r['scores']['official_prior']['xyz_normalized_MAE']
            < r['scores'][baseline]['xyz_normalized_MAE'] for baseline in ['median', 'mean'])]
    candidate = (all(official['xyz_normalized_MAE'] <= .8*x['xyz_normalized_MAE'] for x in [median, mean])
                 and all(official['all7_normalized_MAE'] <= x['all7_normalized_MAE'] for x in [median, mean])
                 and len(good) >= 3 and len({r['demo'] for r in good}) == 2)
    if candidate:
        return 'MINIMAL_CLOSED_LOOP_PLAN_SIGNAL_ONLY_NOT_EXECUTION_AUTHORIZATION'
    no_gain = all(official[key] >= scores[baseline][key] for baseline in ['median', 'mean']
                  for key in ['xyz_normalized_MAE', 'all7_normalized_MAE'])
    return ('CONDITIONAL_PAUSE_IF_NO_CLEAR_REPAIRABLE_CAUSE_PARENT_REVIEW_REQUIRED' if no_gain else
            'INCONCLUSIVE_MIXED_OR_WEAK_SIGNAL')
