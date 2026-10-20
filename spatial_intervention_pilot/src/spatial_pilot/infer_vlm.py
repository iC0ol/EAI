"""Offline Qwen3-VL smoke inference. No geometry, family or truth imports."""
import argparse
from datetime import datetime
import importlib.metadata
import json
from pathlib import Path
import random
import subprocess
import threading
import time
import traceback
import yaml
from .vlm_io import build_prompt, inference_read_guard, load_public_records, parse_response, sha256

ROOT = Path(__file__).resolve().parents[2]


def append_json(path,value):
    with path.open('a') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
        stream.flush()


class DeviceMemoryMonitor:
    """Total device usage includes other processes; separate from torch peak."""
    def __init__(self):
        self.peak = 0
        self.stop = threading.Event()
    def poll(self):
        while not self.stop.is_set():
            result = subprocess.run(['nvidia-smi','--id=0','--query-gpu=memory.used',
                                     '--format=csv,noheader,nounits'],capture_output=True,text=True)
            if result.returncode == 0:
                self.peak = max(self.peak,int(result.stdout.strip()))
            self.stop.wait(.5)
    def __enter__(self):
        self.thread = threading.Thread(target=self.poll,daemon=True)
        self.thread.start()
        return self
    def __exit__(self,*args):
        self.stop.set()
        self.thread.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['single','three','core'],required=True)
    args = parser.parse_args()
    config_path = ROOT/'configs/vlm_smoke.yaml'
    cfg = yaml.safe_load(config_path.read_text())
    template_path = ROOT/cfg['prompt_path']
    template = template_path.read_text()
    output = ROOT/'outputs/phase3'/args.stage
    output.mkdir(parents=True,exist_ok=True)
    predictions = output/'predictions.jsonl'
    if predictions.exists() or (output/'session.json').exists():
        raise FileExistsError(f'Preserve existing run: {predictions}; no automatic reruns')
    selected = cfg['stages'][args.stage]
    assert cfg['batch_size'] == 1 and cfg['do_sample'] is False and cfg['num_beams'] == 1
    reads = inference_read_guard(ROOT)
    public = load_public_records(ROOT,cfg,selected_ids=selected)
    previous_stage = {'three':'single','core':'three'}.get(args.stage)
    previous = {}
    if previous_stage:
        previous_path = ROOT/'outputs/phase3'/previous_stage/'predictions.jsonl'
        for line in previous_path.read_text().splitlines():
            row = json.loads(line)
            if row['status'] != 'ok' or not row['parse_ok']:
                raise ValueError('Previous smoke stage did not succeed; preserve failure and report it')
            previous[row['sample_id']] = row
    provenance = {'model_id':cfg['model_id'],'model_revision':cfg['model_revision'],
                  'prompt_version':cfg['prompt_version'],'prompt_sha256':sha256(template_path),
                  'config_sha256':sha256(config_path),'seed':cfg['seed']}
    session = {'stage':args.stage,'started_at':datetime.now().astimezone().isoformat(),
               **provenance,'sample_ids':selected,'read_guard':'public data/images only; private data/reports blocked',
               'source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()}
    (output/'session.json').write_text(json.dumps(session,indent=2)+'\n')
    try:
        import numpy as np
        import torch
        from PIL import Image
        from transformers import AutoProcessor, GenerationConfig, Qwen3VLForConditionalGeneration
        assert torch.cuda.is_available(), 'CUDA unavailable'
        assert torch.cuda.is_bf16_supported(), 'Requested BF16 unavailable; no silent substitution'
        random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed'])
        torch.cuda.manual_seed_all(cfg['seed'])
        torch.set_num_threads(8)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.set_grad_enabled(False)
        model_path = ROOT/cfg['model_local_dir']
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path,dtype=torch.bfloat16,device_map={'':cfg['device']},
            attn_implementation=cfg['attention'],local_files_only=True,
            trust_remote_code=False,use_safetensors=True)
        model.eval()
        processor = AutoProcessor.from_pretrained(model_path,local_files_only=True,
            trust_remote_code=False,min_pixels=cfg['min_pixels'],max_pixels=cfg['max_pixels'])
        torch.cuda.synchronize()
        session.update({'model_load_seconds':time.perf_counter()-started,
                        'model_load_peak_allocated_mib':torch.cuda.max_memory_allocated()/2**20,
                        'model_load_peak_reserved_mib':torch.cuda.max_memory_reserved()/2**20,
                        'torch_cuda_version':torch.version.cuda,'gpu':torch.cuda.get_device_name(),
                        'device_map':{str(k):str(v) for k,v in model.hf_device_map.items()},
                        'dependencies':{name:importlib.metadata.version(name) for name in
                            ['torch','torchvision','transformers','accelerate','huggingface-hub','pillow','numpy']}})
        generation = GenerationConfig(do_sample=False,num_beams=1,max_new_tokens=cfg['max_new_tokens'],
            use_cache=True,eos_token_id=model.generation_config.eos_token_id,
            pad_token_id=model.generation_config.pad_token_id,bos_token_id=model.generation_config.bos_token_id)
        session['generation_config'] = generation.to_dict()
        vision_calls = [0]
        hook = model.model.visual.register_forward_pre_hook(lambda module,inputs:vision_calls.__setitem__(0,vision_calls[0]+1))
        for sid in selected:
            record,image_path = public[sid]
            if sid in previous:
                row = previous[sid]
                if any(row[k] != v for k,v in provenance.items()) or row['input_image_sha256'] != record['input_image_sha256']:
                    raise ValueError('Reuse provenance mismatch')
                append_json(predictions,dict(row,reused_from_stage=previous_stage))
                print(f'{args.stage}: reused {sid} from {previous_stage}',flush=True)
                continue
            row = {'sample_id':sid,**provenance,'input_image_sha256':record['input_image_sha256'],
                   'stage_first_inferred':args.stage,'reused_from_stage':None,'response_text':None,
                   'parsed_output':None,'parse_ok':False,'parse_error':None,'status':'running',
                   'decoding_config':{'do_sample':False,'num_beams':1,'max_new_tokens':cfg['max_new_tokens']}}
            start = time.perf_counter()
            try:
                prompt = build_prompt(record,template)
                with Image.open(image_path) as image_file:
                    image = image_file.convert('RGB')
                messages = [{'role':'user','content':[{'type':'image','image':image},{'type':'text','text':prompt}]}]
                torch.cuda.reset_peak_memory_stats()
                with DeviceMemoryMonitor() as monitor:
                    prep_started = time.perf_counter()
                    inputs = processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
                                                           return_dict=True,return_tensors='pt')
                    assert 'pixel_values' in inputs and inputs['pixel_values'].numel() > 0, 'Missing image tensor'
                    assert 'image_grid_thw' in inputs, 'Missing image grid'
                    image_tokens = int((inputs['input_ids'] == model.config.image_token_id).sum())
                    assert image_tokens > 0, 'Missing image token positions'
                    evidence = {'sample_id':sid,'source_image':str(image_path.relative_to(ROOT)),
                                'input_image_sha256':record['input_image_sha256'],'original_image_size':list(image.size),
                                'prompt_text':prompt,'prompt_sha256':provenance['prompt_sha256'],
                                'model_revision':cfg['model_revision'],'pixel_values_shape':list(inputs['pixel_values'].shape),
                                'image_grid_thw':inputs['image_grid_thw'].tolist(),'image_token_count':image_tokens,
                                'input_token_count':int(inputs['input_ids'].shape[-1])}
                    inputs = inputs.to(model.device)
                    torch.cuda.synchronize()
                    row['preprocess_seconds'] = time.perf_counter()-prep_started
                    calls_before = vision_calls[0]
                    generation_started = time.perf_counter()
                    with torch.inference_mode():
                        generated = model.generate(**inputs,generation_config=generation)
                    torch.cuda.synchronize()
                    row['inference_seconds'] = time.perf_counter()-generation_started
                    row['vision_forward_calls'] = vision_calls[0]-calls_before
                    assert row['vision_forward_calls'] > 0, 'Vision encoder was not executed'
                    trimmed = generated[:,inputs['input_ids'].shape[-1]:]
                    raw = processor.batch_decode(trimmed,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
                    row.update({'response_text':raw,'generated_tokens':int(trimmed.shape[-1]),
                                'hit_token_limit':int(trimmed.shape[-1]) >= cfg['max_new_tokens'],
                                'input_token_count':evidence['input_token_count'],'image_token_count':image_tokens,
                                'image_grid_thw':evidence['image_grid_thw'],'peak_vram_mb':torch.cuda.max_memory_allocated()/2**20,
                                'peak_reserved_mib':torch.cuda.max_memory_reserved()/2**20})
                row['nvidia_peak_device_used_mib'] = monitor.peak
                row.update(parse_response(raw))
                row['status'] = 'ok' if row['parse_ok'] else 'parse_error'
                row['sample_elapsed_seconds'] = time.perf_counter()-start
                evidence['vision_forward_calls'] = row['vision_forward_calls']
                (output/f'{sid}_input.json').write_text(json.dumps(evidence,indent=2)+'\n')
                (output/f'{sid}_response.txt').write_text(raw)
                del inputs,generated,trimmed
            except Exception as exc:
                row.update({'status':'oom' if isinstance(exc,torch.cuda.OutOfMemoryError) else 'inference_error',
                            'error':repr(exc),'traceback':traceback.format_exc(),
                            'sample_elapsed_seconds':time.perf_counter()-start})
                append_json(predictions,row)
                raise
            append_json(predictions,row)
            print(json.dumps({key:row.get(key) for key in ['sample_id','status','parsed_output',
                              'inference_seconds','peak_vram_mb','vision_forward_calls']},ensure_ascii=False),flush=True)
            if row['status'] != 'ok':
                raise RuntimeError('Invalid structured response preserved without repair; stop and report')
        hook.remove()
        session['status'] = 'completed'
    except Exception as exc:
        session.update({'status':'failed','error':repr(exc),'traceback':traceback.format_exc()})
        raise
    finally:
        session['finished_at'] = datetime.now().astimezone().isoformat()
        session['data_read_events'] = sorted(set(reads))
        (output/'session.json').write_text(json.dumps(session,indent=2)+'\n')


if __name__ == '__main__':
    main()
