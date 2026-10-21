"""Phase 3.7 offline model process: sanitized images/questions only, no private reads."""
from datetime import datetime
import importlib.metadata
import json
from pathlib import Path
import random
import subprocess
import time
import traceback
from zoneinfo import ZoneInfo
import yaml
from .scale_io import load_inputs,parse_response,firewall,verify_frozen
from .infer_vlm import DeviceMemoryMonitor,append_json
from .vlm_io import sha256

ROOT=Path(__file__).resolve().parents[2]


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',choices=['4b','8b'],required=True)
    parser.add_argument('--run',choices=['smoke8b','vlm8b_a','vlm4b_new'],required=True)
    parser.add_argument('--datasets',nargs='+',choices=['smoke','old16','new24'],required=True)
    args=parser.parse_args()
    cfg_path=ROOT/'configs/phase3_7.yaml'
    cfg=yaml.safe_load(cfg_path.read_text())
    cfg.update(cfg['models'][args.model])
    templates={kind:(ROOT/value['path']).read_text() for kind,value in cfg['prompts'].items()}
    prompt_shas={kind:sha256(ROOT/value['path']) for kind,value in cfg['prompts'].items()}
    output=ROOT/'outputs/phase3_7'/args.run
    output.mkdir(parents=True,exist_ok=False)
    events=firewall(ROOT)
    if args.datasets!=['smoke']:verify_frozen(ROOT)
    inputs=[]
    for dataset in args.datasets:
        rows=load_inputs(ROOT,dataset)
        if len(rows)!={'smoke':1,'old16':16,'new24':24}[dataset]:raise ValueError('Wrong sample count')
        for row,path in rows:row['dataset']=dataset;inputs.append((row,path))
    records={'poststate':inputs}
    session={'started_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'status':'running',
        'model_id':cfg['model_id'],'model_revision':cfg['model_revision'],'seed':cfg['seed'],
        'datasets':args.datasets,'config_sha256':sha256(cfg_path),'prompt_sha256':prompt_shas,'prompts':cfg['prompts'],
        'source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
        'input_manifests_sha256':{d:sha256(ROOT/f'diagnostics/phase3_7/inputs/{d}.jsonl') for d in args.datasets}}
    (output/'session.json').write_text(json.dumps(session,indent=2)+'\n')
    count=0
    try:
        import numpy as np
        import torch
        from PIL import Image
        from transformers import AutoProcessor,GenerationConfig,Qwen3VLForConditionalGeneration
        assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        random.seed(cfg['seed']);np.random.seed(cfg['seed']);torch.manual_seed(cfg['seed'])
        torch.cuda.manual_seed_all(cfg['seed']);torch.set_num_threads(8)
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
        torch.backends.cudnn.benchmark=False
        torch.set_grad_enabled(False)
        free,total=torch.cuda.mem_get_info()
        session['gpu_before_load']={'free_mib':free/2**20,'total_mib':total/2**20}
        if args.model=='8b' and free/2**20<19500:raise RuntimeError('Insufficient free memory for BF16 with reserve; no cleanup or quantization allowed')
        torch.cuda.reset_peak_memory_stats()
        started=time.perf_counter()
        model=Qwen3VLForConditionalGeneration.from_pretrained(ROOT/cfg['model_local_dir'],
            dtype=torch.bfloat16,device_map={'':cfg['device']},attn_implementation=cfg['attention'],
            local_files_only=True,trust_remote_code=False,use_safetensors=True)
        model.eval()
        session['parameter_count']=sum(p.numel() for p in model.parameters())
        session['actual_parameter_dtypes']=sorted({str(p.dtype) for p in model.parameters()})
        session['quantization']=None
        assert session['actual_parameter_dtypes']==['torch.bfloat16']
        processor=AutoProcessor.from_pretrained(ROOT/cfg['model_local_dir'],local_files_only=True,
            trust_remote_code=False,min_pixels=cfg['min_pixels'],max_pixels=cfg['max_pixels'])
        torch.cuda.synchronize()
        session.update({'model_load_seconds':time.perf_counter()-started,
            'model_load_peak_allocated_mib':torch.cuda.max_memory_allocated()/2**20,
            'gpu':torch.cuda.get_device_name(),'torch_cuda':torch.version.cuda,
            'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()}})
        explicit={key:cfg[key] for key in ['do_sample','num_beams','max_new_tokens','use_model_defaults','temperature','top_p','top_k']}
        generation=GenerationConfig(do_sample=False,num_beams=1,max_new_tokens=cfg['max_new_tokens'],use_cache=True,
            eos_token_id=model.generation_config.eos_token_id,pad_token_id=model.generation_config.pad_token_id,
            bos_token_id=model.generation_config.bos_token_id,temperature=None,top_p=None,top_k=None)
        prepared,_=model._prepare_generation_config(generation,**explicit)
        assert prepared.do_sample is False and prepared.num_beams==1
        session['effective_generation_config']=prepared.to_dict()
        session['explicit_generate_kwargs']=explicit
        vision_calls=[0]
        hook=model.model.visual.register_forward_pre_hook(lambda module,args:vision_calls.__setitem__(0,vision_calls[0]+1))
        for kind,inputs_list in records.items():
            for record,image_path in inputs_list:
                qid=record['query_id'];start=time.perf_counter()
                row={'query_id':qid,'dataset':record['dataset'],'kind':kind,'model_id':cfg['model_id'],'model_revision':cfg['model_revision'],
                    'seed':cfg['seed'],'prompt_version':cfg['prompts'][kind]['version'],'prompt_sha256':prompt_shas[kind],
                    'config_sha256':session['config_sha256'],'input_image_sha256':record['input_image_sha256'],
                    'decoding_config':explicit,'status':'running','response_text':None,'parse_ok':False,
                    'parsed_output':None,'parse_error':None}
                prompt=templates[kind].replace('{{CONTEXT_JSON}}',json.dumps(record['context'],sort_keys=True))
                if '{{CONTEXT_JSON}}' in prompt:
                    raise ValueError('Unfilled context template')
                evidence={'query_id':qid,'source_image':record['image'],'input_image_sha256':record['input_image_sha256'],
                          'prompt_text':prompt,'prompt_sha256':prompt_shas[kind]}
                try:
                    with Image.open(image_path) as source:
                        image=source.convert('RGB')
                    messages=[{'role':'user','content':[{'type':'image','image':image},{'type':'text','text':prompt}]}]
                    torch.cuda.reset_peak_memory_stats()
                    with DeviceMemoryMonitor() as monitor:
                        prep_start=time.perf_counter()
                        tensors=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
                            return_dict=True,return_tensors='pt')
                        assert tensors['pixel_values'].numel()>0
                        image_tokens=int((tensors['input_ids']==model.config.image_token_id).sum())
                        assert image_tokens>0
                        evidence.update({'pixel_values_shape':list(tensors['pixel_values'].shape),
                            'image_grid_thw':tensors['image_grid_thw'].tolist(),'image_token_count':image_tokens,
                            'input_token_count':int(tensors['input_ids'].shape[-1])})
                        (output/f'{qid}_input.json').write_text(json.dumps(evidence,indent=2)+'\n')
                        tensors=tensors.to(model.device);torch.cuda.synchronize()
                        row['preprocess_seconds']=time.perf_counter()-prep_start
                        before=vision_calls[0];gen_start=time.perf_counter()
                        with torch.inference_mode():
                            generated=model.generate(**tensors,generation_config=prepared,**explicit)
                        torch.cuda.synchronize()
                        row['inference_seconds']=time.perf_counter()-gen_start
                        row['vision_forward_calls']=vision_calls[0]-before
                        assert row['vision_forward_calls']>0
                        trimmed=generated[:,tensors['input_ids'].shape[-1]:]
                        raw=processor.batch_decode(trimmed,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
                        row.update({'response_text':raw,'generated_tokens':int(trimmed.shape[-1]),
                            'hit_token_limit':int(trimmed.shape[-1])>=cfg['max_new_tokens'],
                            'image_token_count':image_tokens,'peak_allocated_mib':torch.cuda.max_memory_allocated()/2**20,
                            'peak_reserved_mib':torch.cuda.max_memory_reserved()/2**20})
                    row['nvidia_peak_device_used_mib']=monitor.peak
                    row.update(parse_response(raw,kind))
                    row['status']='ok' if row['parse_ok'] else 'parse_error'
                    (output/f'{qid}_response.txt').write_text(raw)
                    del tensors,generated,trimmed
                except Exception as exc:
                    row.update({'status':'oom' if isinstance(exc,torch.cuda.OutOfMemoryError) else 'inference_error',
                        'error':repr(exc),'traceback':traceback.format_exc(),'elapsed_seconds':time.perf_counter()-start})
                    append_json(output/'predictions.jsonl',row)
                    raise
                row['elapsed_seconds']=time.perf_counter()-start
                row['end_to_end_seconds']=row['elapsed_seconds']
                append_json(output/'predictions.jsonl',row);count+=1
                print(json.dumps({k:row.get(k) for k in ['query_id','kind','status','parsed_output','inference_seconds']},ensure_ascii=False),flush=True)
        hook.remove()
        session['status']='completed'
    except Exception as exc:
        session.update({'status':'failed','error':repr(exc),'traceback':traceback.format_exc()})
        raise
    finally:
        session.update({'finished_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                        'completed_queries':count,'data_read_events':sorted(set(events))})
        (output/'session.json').write_text(json.dumps(session,indent=2)+'\n')


if __name__=='__main__':
    main()
