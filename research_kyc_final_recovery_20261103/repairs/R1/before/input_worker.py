"""Worker 1, reachable only after final double review and a new RUN dispatch."""
from common import *
from gates import worker_gate, reserve
import contextlib
import sys


@contextlib.contextmanager
def dataset_choices(sample, np, lib):
    state = lib.rng_state(); randint = np.random.randint; choice = np.random.choice
    uses = dict(time=0, camera=0)
    def fixed_time(low, high=None, size=None, dtype=int):
        if high is None and low == sample['demo_length'] and size is None and uses['time'] == 0:
            uses['time'] += 1; return sample['t']
        return randint(low, high=high, size=size, dtype=dtype)
    def fixed_camera(a, size=None, replace=True, p=None):
        expected = np.arange(sample['demo_id'], sample['demo_id']+3, dtype=np.int64)
        if np.array_equal(a, expected) and size == 1 and replace is False and uses['camera'] == 0:
            uses['camera'] += 1; return np.array([sample['camera_index']], dtype=np.int64)
        return choice(a, size=size, replace=replace, p=p)
    np.random.randint = fixed_time; np.random.choice = fixed_camera
    try:
        yield uses
    finally:
        np.random.randint = randint; np.random.choice = choice
        lib.restore_rng(state)
        require(uses == dict(time=1, camera=1), 'dataset fixed draws differ from source')


def main():
    worker_gate('input')  # must precede ALL numpy/torch/vendor imports
    from runtime_safety import isolation, torch_guards, forbidden
    isolation()
    import numpy as np
    import torch
    from PIL import Image
    torch_guards(torch)
    sys.path.insert(0, str(R/'scripts'))
    import experiment_lib as lib
    from utils import EpisodicDataset
    from eval import Evaluator
    from cam_embedding import PluckerEmbedder
    import robosuite.utils.binding_utils as bu
    from robosuite.renderers.context import egl_context as ec
    from robosuite.environments.base import MujocoEnv
    from input_runtime import InputRuntime
    from types import SimpleNamespace
    # Any step or second path to make_env is guarded before its native action.
    MujocoEnv.step = lambda *a, **kw: reserve('env_steps', 'input', 'forbidden_env.step')
    original_make_env = lib.make_env
    def make_env(*args, **kwargs):
        ordinal = reserve('make_env', 'input', 'lib.make_env')
        require(ordinal == 1, 'unexpected second make_env attempt; no replacement')
        return original_make_env(*args, **kwargs)
    lib.make_env = make_env
    runtime = InputRuntime(ec, bu, np); runtime.install()
    api = runtime.api
    args = SimpleNamespace(**read(R/'manifests/C_config.json'))
    stats = {k: np.asarray(v, dtype=np.float32) for k, v in read(R/'manifests/dataset_stats.json').items()}
    require(args.prob_drop_proprio == 1 and not args.use_cam_pose and args.chunk_size == 30,
            'frozen conditioning configuration changed')
    env = ds = evaluator = embedder = None
    rows = []; result_state = 'PARTIAL'; failure = None

    def array(x):
        return x.detach().cpu().numpy().copy() if torch.is_tensor(x) else np.array(x, copy=True)

    def compare(a, b, exact=False):
        a, b = array(a), array(b)
        same = a.shape == b.shape
        return dict(pass_=bool(same and (np.array_equal(a, b) if exact else
                    np.allclose(a, b, atol=1e-7, rtol=1e-6))),
                    exact=bool(same and np.array_equal(a, b)),
                    max_abs=float(np.max(np.abs(a.astype(float)-b.astype(float)))) if same else None)

    def capture(sample, entry, action, is_dataset=False):
        label = 's%02d_%s' % (sample['sample'], entry); runtime.label(label)
        state = old_inputs['source_state_f32'].copy()
        lib.seed_all(sample['seed1']); env.sim.set_state_from_flattened(state); env.sim.forward()
        expected = state.astype(np.float64)
        original_flip = np.flipud; flips = []
        def flip(value):
            runtime.save_array(label+'_flip_input', value)
            result = original_flip(value)
            runtime.save_array(label+'_flip_output', result); flips.append(True)
            return result
        np.flipud = flip
        try:
            value = action()
        finally:
            np.flipud = original_flip
        require(len(flips) == 1 and label in runtime.frames, 'entry did not produce exactly one saved frame')
        tensor = array(value['image'][0, :3]) if is_dataset else (
            np.asarray(value).transpose(2, 0, 1).astype(np.float32) / np.float32(255))
        runtime.save_array(label+'_tensor_rgb', tensor)
        path = runtime.out/(label+'_saved.npz')
        np.savez_compressed(path, rgb_float=tensor)
        with np.load(path, allow_pickle=False) as z:
            saved = z['rgb_float'].copy()
        pixels = np.rint(saved.transpose(1, 2, 0)*255).astype(np.uint8)
        Image.fromarray(pixels).save(runtime.out/(label+'.png'))
        raw = np.load(P/runtime.frames[label]['normal']['file'], allow_pickle=False)
        flip_in = np.load(runtime.out/(label+'_flip_input.npy'), allow_pickle=False)
        flip_out = np.load(runtime.out/(label+'_flip_output.npy'), allow_pickle=False)
        boundaries = dict(raw_to_flip_input=bool(np.array_equal(raw, flip_in)),
            flip_input_to_output=bool(np.array_equal(np.flip(flip_in, 0), flip_out)),
            flip_output_to_tensor=bool(np.array_equal(flip_out.transpose(2, 0, 1).astype(np.float32)/np.float32(255), tensor)),
            tensor_to_npz=bool(np.array_equal(tensor, saved)),
            npz_to_png=bool(np.array_equal(pixels, np.asarray(Image.open(runtime.out/(label+'.png'))))))
        require(all(boundaries.values()), 'saved conversion boundary mismatch')
        require(np.array_equal(env.sim.get_state().flatten(), expected), 'state mutated by input entry')
        if sample['sample'] == 0:
            require(hashlib.sha256(pixels.tobytes()).hexdigest() == REFERENCE_SHA,
                    'sample0 fixed healthy reference mismatch')
        api.check()
        return value, pixels, dict(label=label, raw=runtime.frames[label]['normal'],
            pixel_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),
            state_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
            T_sha256=hashlib.sha256(np.asarray(sample['T']).tobytes()).hexdigest(),
            XML_sha256=hashlib.sha256(env.model.get_xml().encode()).hexdigest(), health=True,
            boundaries=boundaries)

    try:
        runtime.label('INIT_make_env'); env = lib.make_env(0); api.check()
        env.step = lambda *a, **kw: reserve('env_steps', 'input', 'forbidden_wrapped_env.step')
        runtime.expected_context = api.owner(env.sim._render_context_offscreen.gl_ctx)
        runtime.expected_ids = api.ids(env.sim._render_context_offscreen.con)
        require(runtime.expected_context and api.live(runtime.expected_context), 'active renderer owner unknown')
        (P/'local_only/source_model.xml').write_text(env.model.get_xml())
        # Preserve the actual original stage1 constructor order and arguments.
        runtime.label('INIT_Dataset')
        ds = EpisodicDataset(list(range(200)), stats, args,
            camera_poses_file='train_cameras.json', transform='id', env=env, max_seq_length=130)
        api.check(); runtime.label('INIT_Evaluator')
        evaluator = Evaluator(env, stats, str(lib.DATA), args)
        api.check(); runtime.label('INIT_embedder')
        embedder = PluckerEmbedder(img_size=256, device='cuda'); api.check()
        # Exact original pure evaluation preprocessing function, compiled from
        # its pinned AST without importing old stage1 (which has broad imports).
        import ast
        source = D/'execution/scripts/stage1.py'
        node = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'official_eval_data')
        namespace = dict(torch=torch, np=np)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        official_eval_data = namespace['official_eval_data']
        for sample in read(P/'sample_plan.json')['samples']:
            with np.load(D/('execution/inputs/sample_%02d.npz' % sample['sample']), allow_pickle=False) as z:
                old_inputs = {k: z[k].copy() for k in ['source_state_f32', 'T_given',
                    'expert_raw_chunk', 'mask_chunk', 'normalized_actions_full', 'mask_full']}
            require(hashlib.sha256(old_inputs['source_state_f32'].tobytes()).hexdigest()
                    == sample['source_state_f32']['sha256'], 'sample source hash mismatch')
            T = np.asarray(sample['T']); require(np.array_equal(T, old_inputs['T_given']), 'T changed')
            uses = {}
            def dataset_action():
                with dataset_choices(sample, np, lib) as controlled:
                    item = ds[sample['demo_id']]
                    uses.update(controlled)
                    return item
            item, rgb_ds, ds_frame = capture(sample, 'dataset', dataset_action, True)
            _, rgb_ev, ev_frame = capture(sample, 'evaluator', lambda: evaluator._render_cam_image(T))
            _, rgb_custom, custom_frame = capture(sample, 'custom', lambda: lib.render(env, T))
            # Input comparison intentionally reuses ONE saved canonical raw;
            # the other two renders audit entry behavior, not model differences.
            canonical_raw = np.load(P/ds_frame['raw']['file'], allow_pickle=False)
            common_rgb = np.flip(canonical_raw, 0).copy()
            runtime.label('PURE_PREPROCESS_s%02d' % sample['sample'])
            lib.seed_all(sample['seed1'])
            official = official_eval_data(evaluator, common_rgb.copy(), T)
            custom = lib.policy_input(common_rgb.copy(), T, lib.intrinsics(env), stats, embedder, True)
            dataset = {k: item[k][None] for k in ['image', 'qpos', 'cam_extrinsics']}
            expected_shapes = dict(image=(1, 1, 9, 256, 256), qpos=(1, 7), cam_extrinsics=(1, 2, 4, 4))
            require(all(tuple(value.shape) == expected_shapes[key] and value.dtype == torch.float32
                    for data in [official, custom, dataset] for key, value in data.items()),
                    'STOP_INPUT_SHAPE_DTYPE_SEMANTICS')
            require(tuple(item['actions'].shape) == (130, 7) and item['actions'].dtype == torch.float32
                    and tuple(item['is_pad'].shape) == (130,) and item['is_pad'].dtype == torch.bool,
                    'STOP_POSTERIOR_LABEL_SHAPE_DTYPE')
            checks = {name: compare(official[name], custom[name]) for name in official}
            checks['RGB3'] = compare(official['image'][:, :, :3], custom['image'][:, :, :3])
            checks['Plucker6'] = compare(official['image'][:, :, 3:], custom['image'][:, :, 3:])
            checks.update({'dataset_'+name: compare(dataset[name], official[name]) for name in official})
            checks['entry_rgb_evaluator'] = compare(rgb_ds, rgb_ev, True)
            checks['entry_rgb_custom'] = compare(rgb_ds, rgb_custom, True)
            checks['normalized_actions'] = compare(item['actions'], old_inputs['normalized_actions_full'], True)
            checks['mask'] = compare(item['is_pad'], old_inputs['mask_full'], True)
            checks['dropped_qpos'] = compare(item['qpos'], -stats['state_mean']/stats['state_std'], True)
            require(all(x['pass_'] for x in checks.values()), 'STOP_INPUT_TENSOR_OR_ENTRY_DISCREPANCY')
            arrays = {prefix+'_'+key: array(val) for prefix, data in [('official', official),
                       ('custom', custom), ('dataset', dataset)] for key, val in data.items()}
            arrays.update(canonical_raw=canonical_raw, rgb_uint8=common_rgb,
                source_state_f32=old_inputs['source_state_f32'], T=T, K=lib.intrinsics(env),
                actions_full=array(item['actions']), is_pad_full=array(item['is_pad']),
                expert_raw_chunk=old_inputs['expert_raw_chunk'], valid_mask=~old_inputs['mask_chunk'])
            require(all(np.isfinite(v).all() for v in arrays.values()), 'nonfinite input')
            path = P/('inputs/sample_%02d.npz' % sample['sample'])
            require(not path.exists(), 'input overwrite')
            np.savez_compressed(path, **arrays)
            rows.append(dict(sample=sample['sample'], demo=sample['demo_id'], checks=checks,
                controlled_draws=uses, frames=[ds_frame, ev_frame, custom_frame],
                canonical_raw=ds_frame['raw'], input_npz=str(path.relative_to(P)), input_sha256=sha(path),
                tensor_metadata={k: dict(shape=list(v.shape), dtype=str(v.dtype),
                    sha256=hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()) for k, v in arrays.items()}))
            write(P/'input_progress.json', dict(state='PREPARING', samples=rows))
        result_state = 'COMPLETE_HEALTHY_PENDING_PARENT'
    except BaseException as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        runtime.label('CLEANUP')
        cleanup_error = None
        try:
            if ds is not None:
                ds.env = None  # same original stage1 finally behavior
            if env is not None:
                env.close()  # only upstream MjSim.free's own gc.collect, no forced harness GC
            ds = evaluator = embedder = env = None
            api.check()
            require(not any(x['alive'] for x in api.contexts.values()), 'context still live after original cleanup')
        except BaseException as exc:
            cleanup_error = exc; result_state = 'PARTIAL'
            failure = (failure or '') + '; cleanup:' + type(exc).__name__ + ':' + str(exc)
        events = [json.loads(v) for v in (runtime.out/'events.jsonl').read_text().splitlines()]
        target = [i for i, e in enumerate(events) if e['event'] == 'natural_renderer_release_enter'
                  and e['entry'] != 'CLEANUP' and e.get('releasing_owner')
                  and e.get('previous_context') and e['releasing_owner'] != e['previous_context']]
        files = {str(f.relative_to(P)): sha(f) for directory in [P/'inputs', runtime.out]
                 for f in sorted(directory.rglob('*')) if f.is_file()}
        write(P/'input_result.json', dict(utc=utc(), state=result_state, failure=failure,
            all_health_pass=result_state == 'COMPLETE_HEALTHY_PENDING_PARENT', samples=rows,
            input_files=files, source_hashes=read(P/'candidate_manifest.json')['sources'],
            natural_target_window='TARGET_WINDOW_OBSERVED' if target else 'NOT_REPRODUCED',
            natural_target_entry_indices=target, fixture_strong_refs=False, forced_destructor=False,
            forced_gc=False, all_contexts_destroyed=not any(x['alive'] for x in api.contexts.values()),
            ACT='NOT_RUN', model_stage='WAITING_PARENT_GATE'))
        if cleanup_error:
            raise cleanup_error


if __name__ == '__main__':
    main()
