"""Run only on already saved model outputs. No torch/model/env imports."""
from common import *
from metrics import *


def main():
    state = read(P/'run_state.json')
    require(state and state['active_lease'] is None and state['GPU_seconds'] <= 600
            and state['counts']['ACT'] == 16 and state['counts']['workers'] == 2
            and state['stages'].get('model', {}).get('exit_code') == 0,
            'model stage not successfully exited within cumulative budget: analysis NOT_RUN')
    model = read(P/'model_result.json')
    require(model and model['state'] == 'COMPLETE', 'no complete model result: metrics NOT_RUN')
    plan = read(P/'sample_plan.json')['samples']
    constants = read(D/'execution/constants.json')
    stats = read(R/'manifests/dataset_stats.json')
    std, mean = [np.asarray(stats[key], np.float64) for key in ['action_std', 'action_mean']]
    first = {}; repeats = {}; predictions = {key: [] for key in
        ['official_prior', 'custom_prior', 'official_posterior', 'mean', 'median']}
    targets = []; masks = []; per_state = []; directions = {k: [] for k in predictions}
    for sample in plan:
        j = sample['sample']; first[j] = {}; repeats[j] = {}
        with np.load(P/('inputs/sample_%02d.npz' % j), allow_pickle=False) as z:
            target, valid = z['expert_raw_chunk'].astype(float), z['valid_mask'].astype(bool)
        targets.append(target); masks.append(valid); values = {}
        for record in model['calls']:
            if record['sample'] != j:
                continue
            require(sha(P/record['output_npz']) == record['output_sha256'], 'prediction changed')
            with np.load(P/record['output_npz'], allow_pickle=False) as z:
                normalized, raw = z['normalized_chunk'].astype(float), z['raw_chunk'].astype(float)
            require(np.array_equal(raw, normalized*std+mean), 'physical unit conversion changed')
            (repeats if record['repeat'] else first)[j][record['branch']] = normalized
            if not record['repeat']:
                values[record['branch']] = raw
        values.update({name: np.asarray(constants['per_position_'+name+'_raw'], float)
                       for name in ['mean', 'median']})
        scores = {name: score(value, target, valid, std) for name, value in values.items()}
        ds = {name: direction_gripper(value, target, valid) for name, value in values.items()}
        for name, value in values.items():
            predictions[name].append(value); directions[name].append(ds[name])
        ratios = {name: {baseline: {key: ratio(scores[name][key], scores[baseline][key])
                    for key in ['xyz_normalized_MAE', 'all7_normalized_MAE', 'all7_normalized_RMSE']}
                    for baseline in ['mean', 'median']} for name in
                    ['official_prior', 'custom_prior', 'official_posterior']}
        per_state.append(dict(sample=j, demo=sample['demo_id'], t=sample['t'], scores=scores,
                              direction_gripper=ds, dual_constant_ratios=ratios))
    summary = {name: aggregate(value, targets, masks, std) for name, value in predictions.items()}
    direction = {name: average_direction(value) for name, value in directions.items()}
    agreement = entry_agreement(first, repeats)
    decisions = investment_decision(summary, per_state, direction, all(x['passed'] for x in agreement))
    per_demo = {str(demo): {name: aggregate([v[i] for i, s in enumerate(plan) if s['demo_id'] == demo],
                       [targets[i] for i, s in enumerate(plan) if s['demo_id'] == demo],
                       [masks[i] for i, s in enumerate(plan) if s['demo_id'] == demo], std)
                       for name, v in predictions.items()} for demo in [0, 50]}
    per_position = {}
    for name, values in predictions.items():
        errors = np.stack([(p-t)/std for p, t in zip(values, targets)])
        valid = np.stack(masks)
        per_position[name] = [dict(chunk_position=k, valid_states=int(valid[:, k].sum()),
            normalized_MAE_by_dim=np.abs(errors[valid[:, k], k]).mean(0).tolist(),
            normalized_RMSE_by_dim=np.sqrt(np.square(errors[valid[:, k], k]).mean(0)).tolist())
            for k in range(30)]
    diversity = {}
    for name, values in predictions.items():
        normal = np.stack([(v-mean)/std for v in values])
        diversity[name] = dict(first_position_across_state_std_by_dim=normal[:, 0].std(0).tolist(),
            chunk_position_across_state_std_by_dim=normal.std(0).tolist(),
            pairwise_normalized_MAE=[dict(samples=[plan[i]['sample'], plan[j]['sample']],
                value=float(np.abs(normal[i]-normal[j])[masks[i] & masks[j]].mean()))
                for i in range(4) for j in range(i+1, 4)])
    result = dict(utc=utc(), state='COMPLETE_CPU_STATISTICS', investment_screen=decisions,
        per_state=per_state, equal_state_aggregate=summary, per_demo=per_demo,
        per_chunk_position=per_position, direction_gripper_equal_state=direction,
        entry_agreement=agreement, descriptive_diversity=diversity,
        aggregate_dual_constant_ratios={name: {b: {k: ratio(summary[name][k], summary[b][k]) for k in
            ['xyz_normalized_MAE', 'all7_normalized_MAE', 'mean_state_normalized_RMSE', 'pooled_valid_step_normalized_RMSE']}
            for b in ['mean', 'median']} for name in ['official_prior', 'custom_prior', 'official_posterior']},
        arithmetic='float64; first outputs only for capability scores; valid steps; samples equally weighted',
        baseline_anchor='training-sampling-weighted 30x7 median; mean must also be beaten, no oracle stitching',
        independent_demos=2, states=4, labels='seen training states only',
        repairable_cause_assessment='not automated; parent research review required before conditional pause',
        raw_units=['m', 'm', 'm', 'axis-angle-coordinate delta rad', 'axis-angle-coordinate delta rad',
                   'axis-angle-coordinate delta rad', 'unitless gripper command'],
        standard_units='(raw - frozen action_mean)/frozen action_std',
        limitations=['not task success', 'no visual-causal dependence test', 'no generalization',
                     'posterior one draw per state only', 'samples4/5 have no individual noise estimate'],
        historic_0_of_32_cause='UNKNOWN', further_experiment_authorization=False)
    write(P/'analysis.json', result)


if __name__ == '__main__':
    main()
