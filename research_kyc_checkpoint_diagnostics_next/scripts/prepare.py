"""CPU-only candidate freeze. NEVER authorizes or starts a worker."""
from common import *
import ast
import difflib
import importlib.metadata
import numpy as np

CODE = ['common.py', 'lc_common.py', 'gates.py', 'owned_release.py', 'telemetry.py',
        'runtime_safety.py', 'input_runtime.py', 'input_worker.py', 'call_guard.py',
        'model_worker.py', 'metrics.py', 'analyze.py', 'supervisor.py',
        'test_owned_release.py', 'test_preparation.py', 'test_render_health.py', 'prepare.py']


def function_info(path, qualified):
    source = path.read_text(); node = ast.parse(source)
    for name in qualified.split('.'):
        node = next(n for n in node.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    text = ast.get_source_segment(source, node)
    return dict(file=str(path), function=qualified, line=node.lineno, end_line=node.end_lineno,
                source_sha256=sha(path), segment_sha256=hashlib.sha256(text.encode()).hexdigest())


def main():
    require(not (P/'dispatch.json').exists() and not (P/'run_state.json').exists(),
            'candidate freeze prohibited after formal RUN dispatch')
    require(read(P/'cpu_mock.json')['passed'] and read(P/'cpu_preparation_tests.json')['passed'],
            'CPU preflight tests have not passed')
    for name in CODE:
        text = (P/'scripts'/name).read_text()
        compile(ast.parse(text), str(P/'scripts'/name), 'exec')  # no module execution
    old_plan = D/'execution/sample_plan.json'
    selected = [x for x in read(old_plan)['ordered_samples'] if x['sample'] in [0, 1, 4, 5]]
    require([x['sample'] for x in selected] == [0, 1, 4, 5], 'source order differs')
    write(P/'sample_plan.json', dict(source=str(old_plan), source_sha256=sha(old_plan), samples=selected,
         independent_demos=2, states=4, training_dataset_max_seq_length=130))
    calls = []
    for sample in selected:
        for branch in ['official_prior', 'custom_prior', 'official_posterior']:
            calls.append(dict(id='s%02d_%s' % (sample['sample'], branch), sample=sample['sample'],
                         branch=branch, seed=sample['seed1'], repeat=False, batch=1))
    for sample in selected[:2]:
        for branch in ['official_prior', 'custom_prior']:
            calls.append(dict(id='s%02d_%s_repeat' % (sample['sample'], branch), sample=sample['sample'],
                         branch=branch, seed=sample['seed1'], repeat=True, batch=1))
    write(P/'call_plan.json', dict(calls=calls, call_cap=16, latent_prior='actual upstream zero z',
         precision='FP32 parameters + CUDA BF16 autocast; TF32 off', no_warmup=True))
    criteria_source = P/'notes/02_判据交叉处理_供最终协议.md'
    (P/'criteria_reference.md').write_text(criteria_source.read_text())
    sources = [D/'execution/scripts/stage1.py', D/'execution/sample_plan.json', D/'execution/constants.json',
        D/'execution/results/checkpoint_audit.json', D/'artifacts/parent_stats_constants_audit.json',
        D/'render_controlled/scripts/owned_release.py', D/'render_controlled/scripts/telemetry.py',
        D/'render_lifecycle/results/worker_1_baseline/early.png']
    sources += [D/('execution/inputs/sample_%02d.npz' % x['sample']) for x in selected]
    sources += [R/'scripts/experiment_lib.py', R/'scripts/common.py', R/'manifests/C_config.json',
        R/'manifests/dataset_stats.json', R/'checkpoints/C_latest.pt', R/'assets/liftrand_eef_delta.hdf5',
        R/'cache/torch/hub/checkpoints/resnet18-f37072fd.pth', R/'env/bin/python',
        K/'utils.py', K/'eval.py', K/'cam_embedding.py', K/'camera_poses/train_cameras.json']
    sources += sorted((K/'models').glob('*.py'))
    sources += [R/'vendor/robosuite/robosuite'/name for name in
        ['utils/binding_utils.py', 'renderers/context/egl_context.py', 'environments/base.py', 'wrappers/action_wrapper.py']]
    site = R/'env/lib/python3.11/site-packages'
    sources += [site/name for name in ['torch/hub.py', 'torch/nn/modules/module.py',
                'torchvision/models/_api.py', 'torchvision/models/resnet.py']]
    hashes = {str(path): sha(path) for path in sources}
    audit = read(D/'execution/results/checkpoint_audit.json')
    require(hashes[str(R/'checkpoints/C_latest.pt')] == audit['sha256']
            and not audit['nonfinite_keys'] and audit['state_dict_entries'] == 375, 'old checkpoint audit mismatch')
    constants = read(D/'execution/constants.json')
    parent = read(P/'artifacts/parent_reference_baselines.json')
    require(sha(D/'execution/constants.json') == parent['constant_sha256']
            and sha(R/'manifests/dataset_stats.json') == parent['stats_sha256']
            and hashes[str(R/'assets/liftrand_eef_delta.hdf5')] == parent['data_sha256']
            == constants['source_data_sha256'], 'frozen baseline/stats/data SHA mismatch')
    for sample in selected:
        with np.load(D/('execution/inputs/sample_%02d.npz' % sample['sample']), allow_pickle=False) as z:
            require(hashlib.sha256(z['source_state_f32'].tobytes()).hexdigest() == sample['source_state_f32']['sha256'],
                    'source state SHA mismatch')
            require(hashlib.sha256(z['expert_raw_chunk'].tobytes()).hexdigest() == sample['raw_expert_chunk']['sha256'],
                    'target SHA mismatch')
            require(not z['mask_chunk'].any() and np.array_equal(z['T_given'], sample['T']), 'fixed mask/T differ')
    mapping = [function_info(path, name) for path, names in [
        (D/'execution/scripts/stage1.py', ['prepare_inputs', 'official_eval_data', 'frozen_dataset_choices']),
        (R/'scripts/experiment_lib.py', ['make_env', 'render', 'policy_input']),
        (K/'utils.py', ['EpisodicDataset.__init__', 'EpisodicDataset.__getitem__']),
        (K/'eval.py', ['Evaluator.__init__', 'Evaluator._render_cam_image', 'Evaluator._image_to_tensor']),
        (K/'models/act.py', ['ACTPolicy.__call__']),
        (K/'models/detr_vae.py', ['DETRVAE.forward', 'build'])] for name in names]
    write(P/'source_map.json', dict(functions=mapping, criteria_source=str(criteria_source),
        criteria_source_sha256=sha(criteria_source), copied_modules='copied_sources.json',
        adaptations=['natural release wrapper has no held/forced fixture',
          'same-raw official preprocessing compiles exact pinned function AST',
          'only dataset random time/camera draws fixed, RNG restored',
          'narrow builder torch proxy suppresses real optimizer only',
          'cached ResNet URL resolves read-only approved local file',
          'policy/internal ticket counts and two explicit supervised stages']))
    for old, new, label in [(D/'execution/scripts/stage1.py', P/'scripts/input_worker.py', 'input_worker_from_stage1'),
                           (D/'render_controlled/scripts/worker.py', P/'scripts/input_runtime.py', 'natural_runtime_from_controlled'),
                           (D/'render_controlled/scripts/lc_common.py', P/'scripts/lc_common.py', 'lc_common')]:
        diff = ''.join(difflib.unified_diff(old.read_text().splitlines(True), new.read_text().splitlines(True),
                       fromfile=str(old), tofile=str(new), n=3))
        (P/'patches'/(label+'.diff')).write_text(diff)
    # Templates intentionally cannot authorize anything and use separate names.
    write(P/'RUN_GATE_TEMPLATE.json', dict(state='NOT_APPROVED_TEMPLATE',
        review_gate=dict(state='APPROVED_ONLY_AFTER_BOTH_REVIEWS',
          codex=dict(decision='PENDING', protocol_sha256='FINAL_SHA', code_manifest_sha256='FINAL_SHA',
                     evidence_file='discussion/PENDING.md', evidence_sha256='FINAL_SHA'),
          deepseek=dict(decision='PENDING', protocol_sha256='FINAL_SHA', code_manifest_sha256='FINAL_SHA',
                        evidence_file='discussion/PENDING.md', evidence_sha256='FINAL_SHA')),
        dispatch=dict(mode='NOT_RUN', executor=EXECUTOR, run_id=None, input_stage_authorized=False,
          protocol_sha256='FINAL_SHA', code_manifest_sha256='FINAL_SHA', caps=CAPS, GPU_seconds=600,
          dispatch_epoch=None, deadline_epoch=None)))
    write(P/'INPUT_GATE_TEMPLATE.json', dict(decision='PENDING', mode='NOT_RUN', run_id=None,
        actual_images_viewed=False, CPU_originals_checked=False, model_stage_authorized=False,
        reviewer_thread_id='01a18138-0f15-76b2-b5cf-20e1722782a9',
        code_manifest_sha256='FINAL_SHA', input_result_sha256='FINAL_SHA',
        input_stage_record_sha256='FINAL_SHA', counts_after_input={}, input_files={}, source_hashes={},
        review_evidence_file=None, review_evidence_sha256=None))
    local = ['AGENTS.md', '00_本轮授权.md', '00_任务基础_原文.md', 'orchestration/basis.json',
             'PROTOCOL.md', 'sample_plan.json', 'call_plan.json', 'criteria_reference.md',
             'source_map.json', 'copied_sources.json', 'cpu_mock.json', 'cpu_preparation_tests.json',
             'RUN_GATE_TEMPLATE.json', 'INPUT_GATE_TEMPLATE.json',
             'notes/02_判据交叉处理_供最终协议.md', 'artifacts/parent_reference_baselines.json',
             'artifacts/parent_render_gate_regression_v2.json']
    local += ['scripts/'+name for name in CODE]
    local += [str(path.relative_to(P)) for path in sorted((P/'patches').glob('*.diff'))]
    manifest = dict(state='CANDIDATE_NOT_RUN_NOT_REVIEWED', utc=utc(), protocol_sha256=sha(P/'PROTOCOL.md'),
        files={name: sha(P/name) for name in local}, sources=hashes, caps=CAPS, GPU_seconds=600,
        input_allocation_seconds=210, model_minimum_seconds=390, release_margin_seconds=15,
        deadline='new formal RUN dispatch +8h', executor=EXECUTOR,
        framework_versions={name: importlib.metadata.version(name) for name in ['torch', 'torchvision', 'numpy']},
        CPU_preparation_only=True, new_GL_contexts=0, model_constructions=0, model_forwards=0,
        experimental_workers_started=0, optimizer_updates=0,
        source_preservation='read only; source SHA verified before each authorized stage')
    write(P/'candidate_manifest.json', manifest)
    print(json.dumps(dict(state='CANDIDATE_NOT_RUN', protocol_sha256=manifest['protocol_sha256'],
          candidate_manifest_sha256=sha(P/'candidate_manifest.json'), local_files=len(local),
          source_files=len(sources), GL_model_observations=0)))


if __name__ == '__main__':
    main()
