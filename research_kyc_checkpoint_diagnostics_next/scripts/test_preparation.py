"""Only pure CPU mocks, AST, and tiny synthetic arrays; no worker startup."""
from common import *
import ast
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import gates
from call_guard import CallGuard
from metrics import score, aggregate, direction_gripper, ratio, entry_agreement, investment_decision


class Counter:
    def __init__(self):
        self.n = 0
    def reserve(self, *args):
        if self.n >= 16:
            raise RuntimeError('cap')
        self.n += 1; return self.n


class PreparationTests(unittest.TestCase):
    def fake_input_stage(self, root):
        protocol = root/'PROTOCOL.md'; protocol.write_text('MOCK protocol')
        evidence = root/'review.md'; evidence.write_text('MOCK human-reviewed evidence')
        manifest = dict(protocol_sha256=sha(protocol), files={}, sources={})
        write(root/'candidate_manifest.json', manifest)
        mh = sha(root/'candidate_manifest.json'); ph = sha(protocol)
        review = dict(decision='APPROVE', protocol_sha256=ph, code_manifest_sha256=mh,
                      evidence_file='review.md', evidence_sha256=sha(evidence))
        write(root/'review_gate.json', dict(state='APPROVED', codex=review, deepseek=review))
        now = time.time()-1
        dispatch = dict(mode='RUN', executor=EXECUTOR, protocol_sha256=ph, code_manifest_sha256=mh,
            caps=CAPS, GPU_seconds=600, run_id='MOCK_ONLY', input_stage_authorized=True,
            dispatch_epoch=now, deadline_epoch=now+8*3600)
        write(root/'dispatch.json', dispatch)
        counts = {**{k: 0 for k in CAPS}, 'workers': 1, 'make_env': 1, 'renders': 12, 'readPixels': 24}
        record = dict(state='EXITED', exit_code=0, identity=dict(pid=99999999, start_ticks=1),
                      GPU_seconds=40, counts_after_exit=counts)
        write(root/'stages/input.json', record)
        state = dict(run_id='MOCK_ONLY', counts=counts, deadline_epoch=dispatch['deadline_epoch'],
                     stages={'input': record}, active_lease=None, GPU_seconds=40)
        write(root/'run_state.json', state)
        files = {}
        for j in [0, 1, 4, 5]:
            name = 'inputs/sample_%02d.npz' % j
            (root/'inputs').mkdir(exist_ok=True); (root/name).write_bytes(b'MOCK, not input data')
            files[name] = sha(root/name)
        result = dict(state='COMPLETE_HEALTHY_PENDING_PARENT', all_health_pass=True,
                      samples=[dict(sample=j, frames=[dict(health=True)]*3) for j in [0, 1, 4, 5]],
                      input_files=files, source_hashes={})
        write(root/'input_result.json', result)
        approval = dict(mode='RUN_MODEL', decision='APPROVE', actual_images_viewed=True,
            CPU_originals_checked=True, reviewer_thread_id='01a18138-0f15-76b2-b5cf-20e1722782a9',
            run_id='MOCK_ONLY', code_manifest_sha256=mh, input_result_sha256=sha(root/'input_result.json'),
            input_files=files, source_hashes={}, model_stage_authorized=True,
            input_stage_record_sha256=sha(root/'stages/input.json'), counts_after_input=counts,
            review_evidence_file='review.md', review_evidence_sha256=sha(evidence))
        write(root/'input_gate.json', approval)
        return dispatch, approval

    def guard(self):
        counter = Counter()
        return CallGuard(counter.reserve, lambda *a: None), counter

    def test_policy_internal_charged_once(self):
        guard, counter = self.guard()
        for _ in range(16):
            guard.expect(dict(branch='official_prior'))
            guard.policy_enter('official_prior', ['image', 'qpos', 'cam_extrinsics'], 1)
            guard.internal_enter(False, 1); guard.complete()
        self.assertEqual((counter.n, guard.policy_entries, guard.internal_entries), (16, 16, 16))
        with self.assertRaises(RuntimeError): guard.policy_enter('official_prior', [], 1)

    def test_implicit_internal_consumes_attempt(self):
        guard, counter = self.guard()
        with self.assertRaises(RuntimeError): guard.internal_enter(False, 1)
        self.assertEqual(counter.n, 1)

    def test_second_internal_consumes_extra_attempt_and_stops(self):
        guard, counter = self.guard(); guard.expect(dict(branch='official_prior'))
        guard.policy_enter('official_prior', ['image', 'qpos', 'cam_extrinsics'], 1)
        guard.internal_enter(False, 1)
        with self.assertRaises(RuntimeError): guard.internal_enter(False, 1)
        self.assertEqual(counter.n, 2)

    def test_labels_rejected_in_prior_before_internal(self):
        guard, counter = self.guard(); guard.expect(dict(branch='custom_prior'))
        with self.assertRaises(RuntimeError):
            guard.policy_enter('custom_prior', ['image', 'qpos', 'cam_extrinsics', 'actions'], 1)
        self.assertEqual((counter.n, guard.internal_entries), (1, 0))

    def test_posterior_explicit(self):
        guard, counter = self.guard(); guard.expect(dict(branch='official_posterior'))
        guard.policy_enter('official_posterior', ['image', 'qpos', 'cam_extrinsics', 'actions', 'is_pad'], 1)
        guard.internal_enter(True, 1); guard.complete(); self.assertEqual(counter.n, 1)

    def test_wrong_internal_branch_stops(self):
        guard, counter = self.guard(); guard.expect(dict(branch='official_prior'))
        guard.policy_enter('official_prior', ['image', 'qpos', 'cam_extrinsics'], 1)
        with self.assertRaises(RuntimeError): guard.internal_enter(True, 1)
        self.assertEqual(counter.n, 1)

    def test_batch_not_one_stops(self):
        guard, counter = self.guard(); guard.expect(dict(branch='official_prior'))
        with self.assertRaises(RuntimeError): guard.policy_enter('official_prior', [], 2)
        self.assertEqual(counter.n, 1)

    def test_malformed_policy_input_is_still_charged(self):
        guard, counter = self.guard(); guard.expect(dict(branch='official_prior'))
        with self.assertRaises((AttributeError, RuntimeError)):
            guard.policy_enter('official_prior', data={'image': 'malformed'})
        self.assertEqual(counter.n, 1)

    def test_worker_gate_is_first_before_framework(self):
        for file in ['input_worker.py', 'model_worker.py']:
            tree = ast.parse((P/'scripts'/file).read_text())
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    text = ast.unparse(node)
                    self.assertFalse(any(x in text for x in ['torch', 'numpy', 'robosuite', 'models.']))
            main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
            self.assertEqual(main.body[0].value.func.id, 'worker_gate')

    def test_no_held_fixture_or_manual_finalizer_GC(self):
        for file in ['input_worker.py', 'input_runtime.py']:
            tree = ast.parse((P/'scripts'/file).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Name): self.assertNotEqual(node.id, 'HELD')
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, ['__del__', 'collect'])

    def test_model_worker_has_no_environment_import(self):
        tree = ast.parse((P/'scripts/model_worker.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.assertFalse(any(x in ast.unparse(node) for x in ['robosuite', 'experiment_lib', 'EpisodicDataset']))

    def test_no_RUN_fails_pure_gate(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as root, patch.object(gates, 'P', Path(root)):
            with self.assertRaisesRegex(RuntimeError, 'NO_RUN_AUTHORIZATION'): gates.gate('input')

    def test_exact_mock_gates_then_changed_protocol_denied(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            self.assertEqual(gates.gate('model')['run_id'], 'MOCK_ONLY')
            (root/'PROTOCOL.md').write_text('changed')
            with self.assertRaises(RuntimeError): gates.gate('input')

    def test_unviewed_parent_input_denied(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); _, approval = self.fake_input_stage(root)
            approval['actual_images_viewed'] = False; write(root/'input_gate.json', approval)
            with self.assertRaises(RuntimeError): gates.gate('model')

    def test_changed_input_denied(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            (root/'inputs/sample_00.npz').write_bytes(b'changed')
            with self.assertRaises(RuntimeError): gates.gate('model')

    def test_late_destructor_fatal_denied(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            write(root/'results/input/fatal.json', [dict(error='mock late destructor')])
            with self.assertRaises(RuntimeError): gates.gate('model')

    def test_live_input_or_outstanding_lease_denied(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            state = read(root/'run_state.json'); state['active_lease'] = dict(stage='input')
            write(root/'run_state.json', state)
            with self.assertRaises(RuntimeError): gates.gate('model')

    def test_worker_model_lease_does_not_reject_approved_input(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            state = read(root/'run_state.json'); state['active_lease'] = dict(stage='model')
            write(root/'run_state.json', state)
            self.assertEqual(gates.gate('model')['run_id'], 'MOCK_ONLY')

    def test_cumulative_call_cap_is_not_reset(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            state = read(root/'run_state.json'); state['active_lease'] = dict(stage='model')
            state['counts']['ACT'] = 15; write(root/'run_state.json', state)
            self.assertEqual(gates.reserve('ACT', 'model', 'mock'), 16)
            with self.assertRaises(RuntimeError): gates.reserve('ACT', 'model', 'mock denied')
            self.assertEqual(read(root/'run_state.json')['counts']['ACT'], 16)

    def test_wrong_executor_or_budget_rejected(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); dispatch, _ = self.fake_input_stage(root)
            dispatch['executor'] = dict(thread_id='wrong', model='wrong', reasoning_effort='low')
            write(root/'dispatch.json', dispatch)
            with self.assertRaises(RuntimeError): gates.gate('input')

    def test_missing_final_DeepSeek_code_review_rejected(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            review = read(root/'review_gate.json'); review['deepseek']['decision'] = 'PENDING'
            write(root/'review_gate.json', review)
            with self.assertRaises(RuntimeError): gates.gate('input')

    def test_direct_worker_without_supervisor_lease_rejected(self):
        with tempfile.TemporaryDirectory(dir=P/'tmp') as name, patch.object(gates, 'P', Path(name)):
            root = Path(name); self.fake_input_stage(root)
            with self.assertRaises(RuntimeError): gates.worker_gate('input')

    def test_positive_signal_requires_both_constants_and_two_demos(self):
        scores = {k: dict(xyz_normalized_MAE=.1 if k == 'official_prior' else 1.,
                         all7_normalized_MAE=.1 if k == 'official_prior' else 1.) for k in ['official_prior', 'median', 'mean']}
        direction = {k: dict(cosine_mean=1., gripper_sign_accuracy=1., gripper_transition_hamming=0.)
                     for k in ['official_prior', 'median']}
        per = [dict(demo=i%2, scores=scores) for i in range(4)]
        self.assertTrue(investment_decision(scores, per, direction, True).startswith('MINIMAL_CLOSED_LOOP_PLAN'))
        scores['mean']['xyz_normalized_MAE'] = .01
        self.assertFalse(investment_decision(scores, per, direction, True).startswith('MINIMAL_CLOSED_LOOP_PLAN'))

    def test_frozen_constant_scores_match_parent_CPU_reference(self):
        constants = read(D/'execution/constants.json'); stats = read(R/'manifests/dataset_stats.json')
        parent = read(P/'artifacts/parent_reference_baselines.json')
        for row in parent['samples']:
            with np.load(D/('execution/inputs/sample_%02d.npz' % row['sample']), allow_pickle=False) as z:
                target, valid = z['expert_raw_chunk'], ~z['mask_chunk']
            for name in ['mean', 'median']:
                value = score(constants['per_position_'+name+'_raw'], target, valid,
                              np.asarray(stats['action_std'], float))
                for key in ['xyz_normalized_MAE', 'all7_normalized_MAE', 'all7_normalized_RMSE']:
                    self.assertAlmostEqual(value[key], row['scores'][name][key], places=13)

    def test_valid_objects_in_wrong_renderer_context_are_not_healthy(self):
        from input_runtime import InputRuntime
        runtime = InputRuntime.__new__(InputRuntime)
        runtime.expected_context = 'B'; runtime.expected_ids = {'offFBO': 1}
        event = dict(current_context='A', gl={'errors': {'codes': [0]}},
                     active_objects={'owner_context': 'A', 'state': 'MEASURED_IN_OWNER_CONTEXT'})
        self.assertFalse(runtime.healthy_event(event))

    def test_masks_and_float64_error(self):
        p = np.array([[1]*7, [999]*7], float); t = np.zeros((2, 7)); m = np.array([True, False])
        self.assertEqual(score(p, t, m, np.ones(7))['all7_normalized_MAE'], 1.)

    def test_RMSE_names_are_mathematically_different(self):
        p = [np.zeros((1, 7)), np.ones((1, 7))*2]; t = [np.zeros((1, 7))]*2
        value = aggregate(p, t, [np.ones(1, bool)]*2, np.ones(7))
        self.assertEqual(value['mean_state_normalized_RMSE'], 1.)
        self.assertAlmostEqual(value['pooled_valid_step_normalized_RMSE'], np.sqrt(2))

    def test_zero_denominator_null(self):
        self.assertIsNone(ratio(1, 0)); self.assertEqual(ratio(1, 2), .5)

    def test_small_prediction_direction_is_penalized(self):
        p = np.zeros((2, 7)); t = np.ones((2, 7)); m = np.ones(2, bool)
        value = direction_gripper(p, t, m)
        self.assertEqual(value['cosine_mean'], 0.)
        self.assertEqual(value['small_prediction_count'], 2)
        self.assertEqual(value['gripper_sign_accuracy'], 0.)

    def test_gripper_sign_and_transition(self):
        p = np.ones((3, 7)); t = p.copy(); t[:, 6] = [-1, 1, 1]
        value = direction_gripper(p, t, np.ones(3, bool))
        self.assertEqual(value['gripper_transition_hamming'], .5)
        self.assertEqual(value['expert_transition_count'], 1)

    def test_noise_formula_hard_cap_and_no_borrow(self):
        a = np.zeros((30, 7)); first = {s: dict(official_prior=a.copy(), custom_prior=a.copy()) for s in [0, 1, 4, 5]}
        repeats = {s: dict(official_prior=a.copy()+1e-4, custom_prior=a.copy()) for s in [0, 1]}
        first[4]['custom_prior'][0, 0] = 2e-5
        rows = entry_agreement(first, repeats)
        self.assertEqual(rows[0]['tolerance'], 2e-4); self.assertFalse(rows[2]['passed'])
        repeats[0]['official_prior'] += .01
        self.assertTrue(entry_agreement(first, repeats)[0]['numeric_unstable'])

    def test_direction_veto_overrides_positive_errors(self):
        scores = {k: dict(xyz_normalized_MAE=.1 if k == 'official_prior' else 1.,
                         all7_normalized_MAE=.1 if k == 'official_prior' else 1.) for k in ['official_prior', 'median', 'mean']}
        direction = {k: dict(cosine_mean=0 if k == 'official_prior' else 1,
            gripper_sign_accuracy=1., gripper_transition_hamming=0.) for k in ['official_prior', 'median']}
        per = [dict(demo=i%2, scores=scores) for i in range(4)]
        self.assertEqual(investment_decision(scores, per, direction, True), 'INCONCLUSIVE_DIRECTION_GRIPPER_DEGRADATION')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(PreparationTests))
    write(P/'cpu_preparation_tests.json', dict(utc=utc(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), passed=result.wasSuccessful(),
        GL_contexts=0, models_constructed=0, forwards=0, experimental_workers=0))
    raise SystemExit(0 if result.wasSuccessful() else 1)
