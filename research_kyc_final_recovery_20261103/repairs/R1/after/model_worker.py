"""Worker 2: saved healthy inputs only, no environment/renderer import."""
from .common import *
from .gates import worker_gate, reserve
from .call_guard import CallGuard
import sys


def main():
    worker_gate('model')  # fail closed before numpy/torch/ACT imports
    from .runtime_safety import isolation, torch_guards, cached_backbone_only, forbidden
    isolation()
    import numpy as np
    import torch
    from .loader import load_actual
    modules, provenance = load_actual()
    torch_guards(torch)
    cached_loader = cached_backbone_only(torch)
    import torchvision.models._api
    torchvision.models._api.load_state_dict_from_url = cached_loader
    class NoOptimizer:
        def __init__(self, *args, **kwargs):
            pass
        step = zero_grad = state_dict = load_state_dict = forbidden
    ACTPolicy = modules['models.act'].ACTPolicy
    DETRVAE = modules['models.detr_vae'].DETRVAE
    builder_module = modules['models.detr_vae']
    write(P/'results/model_module_provenance.json', provenance)
    from types import SimpleNamespace
    class InferenceTorchProxy:
        def __getattr__(self, name):
            return SimpleNamespace(AdamW=NoOptimizer) if name == 'optim' else getattr(torch, name)
    # Narrow in-memory adapter: only this builder's torch.optim factory changes;
    # torch, vendor files, architecture statements and all state keys stay intact.
    builder_module.torch = InferenceTorchProxy()
    torch.optim.AdamW.step = forbidden
    import random
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    # No deterministic-algorithm substitution/retry; same BF16 autocast as old deployment.
    events = P/'model_events.jsonl'
    guard = CallGuard(reserve, lambda event, ticket: append(events,
                      dict(utc=utc(), event=event, ticket=ticket)))
    current_branch = None; captured = None; captured_input = None
    old_policy = ACTPolicy.__call__; old_internal = DETRVAE.forward
    def policy_call(self, data):
        guard.policy_enter(current_branch, data=data)
        require(not self.training and not torch.is_grad_enabled(), 'eval/no_grad required')
        result = old_policy(self, data)
        guard.complete()
        return result
    def internal(self, data):
        nonlocal captured, captured_input
        guard.internal_enter(data=data)
        has_labels = isinstance(data, dict) and data.get('actions') is not None
        require(not self.training and not torch.is_grad_enabled(), 'internal model train/grad enabled')
        require(data.get('is_pad') is None if not has_labels else data['is_pad'] is not None,
                'internal prior mask leakage')
        captured_input = {k: v.detach().float().cpu().numpy().copy() for k, v in data.items()
                          if torch.is_tensor(v) and v.dtype != torch.bool}
        if has_labels:
            captured_input['is_pad'] = data['is_pad'].detach().cpu().numpy().copy()
        outputs = old_internal(self, data)
        a, padding, latent = outputs
        def arr(value):
            return value.detach().float().cpu().numpy().copy() if value is not None else np.empty((0,), np.float32)
        captured = dict(normalized_chunk=arr(a)[0], padding_prediction=arr(padding)[0],
                        mu=arr(latent[0]), logvar=arr(latent[1]))
        return outputs
    ACTPolicy.__call__ = policy_call; DETRVAE.forward = internal
    args = SimpleNamespace(**read(R/'manifests/C_config.json'))
    stats = {k: np.asarray(v, np.float32) for k, v in read(R/'manifests/dataset_stats.json').items()}
    policy = None; ck = None; completed = []
    try:
        plan = read(P/'call_plan.json')['calls']
        require(len(plan) == 16, 'call plan count')
        # These are the original ACT architecture/build statements, with only
        # the optimizer factory replaced by an inert, non-training sentinel.
        seed = 0; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        policy = ACTPolicy(args)
        ck = torch.load(R/'checkpoints/C_latest.pt', map_location='cpu', weights_only=False)
        require(ck['args'] == vars(args), 'checkpoint architecture args differ')
        require(all(np.array_equal(np.asarray(ck['stats'][k], np.float32), v) for k, v in stats.items()),
                'checkpoint normalization differs')
        state = ck['model_state_dict']
        require(len(state) == 375 and all(torch.isfinite(v).all().item() for v in state.values()),
                'checkpoint tensor count/nonfinite')
        loaded = policy.load_state_dict(state, strict=True)
        require(not loaded.missing_keys and not loaded.unexpected_keys, 'strict load keys mismatch')
        write(P/'strict_load.json', dict(utc=utc(), strict=True, missing_keys=list(loaded.missing_keys),
            unexpected_keys=list(loaded.unexpected_keys), checkpoint_sha256=sha(R/'checkpoints/C_latest.pt'),
            optimizer_created=False, optimizer_state_loaded=False,
            cached_pretrained_sha256=sha(R/'cache/torch/hub/checkpoints/resnet18-f37072fd.pth')))
        del state; ck = None
        policy.eval()
        policy.configure_optimizers = forbidden
        for parameter in policy.parameters():
            parameter.requires_grad_(False)
        require(all(torch.isfinite(v).all().item() for v in policy.state_dict().values()),
                'nonfinite loaded model')
        output_dir = P/'results/predictions'; output_dir.mkdir(exist_ok=False)
        first_outputs = {}
        repeat_outputs = {}
        for item in plan:
            current_branch = item['branch']; guard.expect(item)
            sample = item['sample']; prefix = 'custom' if current_branch.startswith('custom') else (
                'dataset' if current_branch == 'official_posterior' else 'official')
            path = P/('inputs/sample_%02d.npz' % sample)
            with np.load(path, allow_pickle=False) as z:
                inputs = {key: torch.from_numpy(z[prefix+'_'+key].copy()).to('cuda')
                          for key in ['image', 'qpos', 'cam_extrinsics']}
                if current_branch == 'official_posterior':
                    inputs['actions'] = torch.from_numpy(z['actions_full'].copy()).to('cuda')[None]
                    inputs['is_pad'] = torch.from_numpy(z['is_pad_full'].copy()).to('cuda')[None]
            require(all(torch.isfinite(v).all().item() for v in inputs.values()), 'nonfinite model input')
            input_hashes = {k: hashlib.sha256(v.detach().cpu().numpy().tobytes()).hexdigest()
                            for k, v in inputs.items()}
            seed = item['seed']; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
            captured = captured_input = None
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                result = policy({k: v.clone() for k, v in inputs.items()})
            torch.cuda.synchronize()
            require(captured is not None and captured['normalized_chunk'].shape == (30, 7)
                    and all(np.isfinite(v).all() for v in captured.values()), 'malformed/nonfinite model output')
            norm = captured['normalized_chunk']
            raw = norm.astype(np.float64)*stats['action_std'].astype(np.float64) + stats['action_mean'].astype(np.float64)
            out = output_dir/(item['id']+'.npz')
            require(not out.exists(), 'prediction overwrite/retry')
            np.savez_compressed(out, raw_chunk=raw, **captured,
                                **{'internal_'+k: v for k, v in captured_input.items()})
            record = dict(utc=utc(), **item, policy_input_keys=sorted(inputs),
                input_hashes=input_hashes, input_file_sha256=sha(path),
                output_npz=str(out.relative_to(P)), output_sha256=sha(out),
                precision='FP32 parameters/inputs + CUDA BF16 autocast, TF32 off',
                prior_latent='zero vector (actual upstream code)' if current_branch != 'official_posterior' else None,
                posterior='one seeded reparameterization; labels only in this diagnostic' if current_branch == 'official_posterior' else None,
                loss={k: float(v) for k, v in result.items()} if isinstance(result, dict) else None)
            completed.append(record); write(P/'model_progress.json', dict(state='RUNNING', calls=completed))
            write(output_dir/(item['id']+'.json'), record)
            if not item['repeat']:
                first_outputs[(sample, current_branch)] = norm.copy()
            else:
                repeat_outputs[(sample, current_branch)] = norm.copy()
            # States without repeats have an immediately decidable fixed pair
            # gate: stop before posterior/next state if that gate fails.
            if sample in [4, 5] and current_branch == 'custom_prior':
                require(float(np.abs(norm-first_outputs[(sample, 'official_prior')]).max()) <= 1e-5,
                        'NUMERICAL_OR_ENTRY_INCONCLUSIVE; no extra calls')
            if item['repeat']:
                require(float(np.abs(norm-first_outputs[(sample, current_branch)]).max()) <= 1e-3,
                        'NUMERIC_UNSTABLE; no extra calls')
                if current_branch == 'custom_prior':
                    noise = max(float(np.abs(repeat_outputs[(sample, branch)]-first_outputs[(sample, branch)]).max())
                                for branch in ['official_prior', 'custom_prior'])
                    delta = float(np.abs(first_outputs[(sample, 'official_prior')]
                                        -first_outputs[(sample, 'custom_prior')]).max())
                    require(delta <= max(1e-5, 2*noise), 'NUMERICAL_OR_ENTRY_INCONCLUSIVE; no extra calls')
        require(guard.policy_entries == guard.internal_entries == 16 and guard.active is None,
                'logical/internal call accounting mismatch')
        write(P/'model_result.json', dict(utc=utc(), state='COMPLETE', calls=completed,
            policy_entries=guard.policy_entries, internal_entries=guard.internal_entries,
            ACT_logical_calls_charged=16, envs_created=0, render='NOT_RUN',
            backward='NOT_RUN', optimizer='NOT_CREATED', rollout='NOT_RUN'))
    except BaseException as exc:
        write(P/'model_result.json', dict(utc=utc(), state='STOPPED', calls=completed,
              error=type(exc).__name__+': '+str(exc), no_retry=True))
        raise
    finally:
        policy = ck = None
        if torch.cuda.is_initialized():
            torch.cuda.synchronize(); torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
