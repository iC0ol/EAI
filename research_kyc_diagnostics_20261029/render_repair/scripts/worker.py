"""One fresh interpreter; instrument before make_env; no model or control calls."""
from repair_common import *
import argparse,ctypes,ctypes.util,contextlib,sys,threading,random
import numpy as np
import torch
from PIL import Image
from types import SimpleNamespace
sys.path.insert(0,str(R/'scripts'))
import experiment_lib as lib
from utils import EpisodicDataset
from eval import Evaluator
from cam_embedding import PluckerEmbedder
import robosuite.utils.binding_utils as bu
from robosuite.renderers.context import egl_context as ec
from robosuite.environments.base import MujocoEnv
from context_binding import bind_in_existing_render_lock

WORKER=0;OUT=None;ENTRY='INIT';TARGET=0;FIX=False;SENTINEL=False;FRAME=None
MAP={};FRAMES=[];ORIGINALS=[];ACTIVE=True
native=ctypes.CDLL(ctypes.util.find_library('GL') or 'libGL.so.1')
native.glCheckFramebufferStatus.argtypes=[ctypes.c_uint];native.glCheckFramebufferStatus.restype=ctypes.c_uint
native.glGetError.argtypes=[];native.glGetError.restype=ctypes.c_uint
def pointer(obj):
    if obj is None or not bool(obj):return 0
    try:
        address=getattr(obj,'address',None)
        if address is not None:return int(address or 0)
        return int(ctypes.cast(obj,ctypes.c_void_p).value or 0)
    except (TypeError,ValueError):return 0
def target(obj):return pointer(getattr(obj,'_context',None)) if obj is not None else TARGET
def alias(value):
    if not value:return None
    if value not in MAP:
        MAP[value]=f'w{WORKER}_ctx{len(MAP)+1}'
        write(P/f'local_only/w{WORKER}_context_addresses.json',{str(k):v for k,v in MAP.items()})
    return MAP[value]
def snap(glctx=None):
    current=pointer(ec.EGL.eglGetCurrentContext());wanted=target(glctx)
    out={'current':alias(current),'target':alias(wanted),'match':bool(current and wanted and current==wanted)}
    if not current:out.update(framebuffer_status=None,gl_errors=None,gl_state='NO_CURRENT_CONTEXT');return out
    status=int(native.glCheckFramebufferStatus(0x8D40));errors=[];drained=False
    for _ in range(8):
        e=int(native.glGetError());errors.append(e)
        if e==0:drained=True;break
    out.update(framebuffer_status=status,gl_errors=errors,gl_state='ERRORS_DRAINED' if drained else 'GL_ERROR_NOT_DRAINED')
    return out
def event(name,obj=None,**data):
    record={'utc':utc(),'monotonic':time.monotonic(),'thread_id':threading.get_ident(),'worker':WORKER,
            'entry':ENTRY,'event':name,'telemetry':snap(obj),**data}
    if ACTIVE:append(OUT/'events.jsonl',record)
    return record['telemetry']
def patch(owner,name,fn):
    ORIGINALS.append((owner,name,getattr(owner,name)));setattr(owner,name,fn)
def primitive_exception(e):return {'type':type(e).__name__,'code':int(e.err) if isinstance(getattr(e,'err',None),int) else None}
def wrap_lifecycle(owner,name,has_self=True):
    original=getattr(owner,name)
    def wrapper(*args,**kwargs):
        obj=args[0] if has_self and args else None
        event(name+'_enter',obj if isinstance(obj,ec.EGLGLContext) else None)
        try:return original(*args,**kwargs)
        except BaseException as e:
            event(name+'_exception',exception=primitive_exception(e));raise
        finally:event(name+'_exit',obj if isinstance(obj,ec.EGLGLContext) else None)
    patch(owner,name,wrapper)
def save_array(name,value):
    copy=np.array(value,copy=True,order='C')
    file=OUT/(name+'.npy');np.save(file,copy,allow_pickle=False)
    return {'file':str(file.relative_to(P)),'shape':list(copy.shape),'dtype':str(copy.dtype),
            'sha256':hashlib.sha256(copy.tobytes()).hexdigest(),'file_sha256':sha(file),
            'independent_copy':not np.shares_memory(copy,value)}
def render_hook(original):
    def wrapped(self,*a,**kw):
        global TARGET
        TARGET=target(self.gl_ctx)
        event('MjRenderContext.render_enter',self.gl_ctx,original_lock_locked=bu._MjSim_render_lock.locked(),repair=FIX)
        if FIX:bind_in_existing_render_lock(self,bu._MjSim_render_lock,event)
        result=original(self,*a,**kw)
        after=event('MjRenderContext.render_exit',self.gl_ctx,repair=FIX)
        if FIX and not after['match']:raise RuntimeError('context lost after render; no rebind')
        return result
    return wrapped
def install():
    for name in ['__init__','make_current','free']:wrap_lifecycle(ec.EGLGLContext,name)
    for name in ['eglReleaseThread','eglMakeCurrent','eglDestroyContext']:wrap_lifecycle(ec.EGL,name,False)
    for owner,name in [(bu.MjRenderContext,'__init__'),(bu.MjSim,'free'),(MujocoEnv,'reset'),(MujocoEnv,'close')]:wrap_lifecycle(owner,name)
    original_render=bu.mujoco.mjr_render
    def low_render(*a,**kw):
        ordinal=reserve('renders',WORKER,ENTRY);event('mjr_render_enter',ordinal=ordinal)
        try:return original_render(*a,**kw)
        finally:event('mjr_render_exit',ordinal=ordinal)
    patch(bu.mujoco,'mjr_render',low_render)
    original_read=bu.mujoco.mjr_readPixels
    def low_read(*a,**kw):
        global SENTINEL
        ordinal=reserve('readPixels',WORKER,ENTRY+('_sentinel' if SENTINEL else '_normal'))
        rgb=kw.get('rgb',a[0] if a else None);con=kw.get('con',a[3] if len(a)>3 else None)
        fields={key:int(getattr(con,key)) for key in ['currentBuffer','offWidth','offHeight','offSamples','offFBO','offFBO_r'] if hasattr(con,key)}
        before=event('mjr_readPixels_enter',ordinal=ordinal,sentinel=SENTINEL,mujoco_buffer=fields)
        result=original_read(*a,**kw)
        normal=np.array(rgb,copy=True,order='C')
        meta=save_array(f'read_{ordinal:02d}_'+('sentinel' if SENTINEL else 'normal_raw'),normal)
        after=event('mjr_readPixels_exit',ordinal=ordinal,sentinel=SENTINEL,native_return=None,array=meta)
        if not SENTINEL:
            row={'entry':ENTRY,'ordinal':ordinal,'before':before,'after':after,'raw':meta,'sentinel':None}
            FRAMES.append(row)
            if normal.shape==(256,256,3):
                sentinel=np.full((256,256,3),165,dtype=np.uint8)
                SENTINEL=True
                try:bu.mujoco.mjr_readPixels(rgb=sentinel,depth=None,viewport=kw['viewport'],con=con)
                finally:SENTINEL=False
                # Sentinel is pre-flip readback, compared to exactly this frame's pre-flip raw.
                row['sentinel']={'retained_165_fraction':float(np.mean(sentinel==165)),
                    'raw_165_fraction':float(np.mean(normal==165)),'equal_raw':bool(np.array_equal(sentinel,normal)),
                    'maxabs_to_raw':int(np.max(abs(sentinel.astype(np.int16)-normal.astype(np.int16)))),
                    'separate_buffer':not np.shares_memory(sentinel,rgb),'value':165}
            else:row['sentinel']={'state':'NOT_RUN','reason':'implicit non256 render; no extra shape allocation'}
            write(OUT/'readback.json',FRAMES)
        return result
    patch(bu.mujoco,'mjr_readPixels',low_read)
    patch(bu.MjRenderContext,'render',render_hook(bu.MjRenderContext.render))
    original_pixels=bu.MjRenderContext.read_pixels
    def pixels(self,*a,**kw):
        before=event('read_pixels_enter',self.gl_ctx,lock_locked=bu._MjSim_render_lock.locked())
        if FIX and not before['match']:raise RuntimeError('context lost before read; no rebind')
        result=original_pixels(self,*a,**kw)
        image=result[0] if isinstance(result,tuple) else result
        save_array(ENTRY+f'_read_pixels_return_preflip_{read(P/"counts.json")["readPixels"]:02d}',image)
        event('read_pixels_exit',self.gl_ctx,lock_locked=bu._MjSim_render_lock.locked())
        return result
    patch(bu.MjRenderContext,'read_pixels',pixels)
    def forbidden_step(*a,**kw):
        reserve('env_steps',WORKER,ENTRY);raise RuntimeError('env.step forbidden')
    patch(MujocoEnv,'step',forbidden_step)

@contextlib.contextmanager
def forced_choices(length):
    state=lib.rng_state();ri=np.random.randint;ch=np.random.choice
    def r(low,high=None,size=None,dtype=int):
        if high is None and low==length and size is None:return 0
        return ri(low,high,size,dtype)
    def c(a,size=None,replace=True,p=None):
        if np.array_equal(a,np.arange(3)) and size==1 and not replace:return np.array([1],np.int64)
        return ch(a,size,replace,p)
    np.random.randint=r;np.random.choice=c
    try:yield
    finally:np.random.randint=ri;np.random.choice=ch;lib.restore_rng(state)
@contextlib.contextmanager
def track_flip():
    original=np.flipud
    def wrapper(a):
        save_array(ENTRY+'_flip_input',a)
        out=original(a);save_array(ENTRY+'_flip_output',out)
        return out
    np.flipud=wrapper
    try:yield
    finally:np.flipud=original
def frame_health(rows):
    return bool(rows) and all(r['before']['match'] and r['after']['match'] and
        r['before']['framebuffer_status']==0x8CD5 and r['after']['framebuffer_status']==0x8CD5 and
        all(e==0 for e in r['before']['gl_errors']+r['after']['gl_errors']) and
        r['sentinel'].get('equal_raw',False) and r['sentinel'].get('retained_165_fraction',1)<.99 for r in rows)
def main(worker):
    global WORKER,OUT,ENTRY,FIX,ACTIVE
    WORKER=worker;OUT=P/f'results/worker_{worker}';OUT.mkdir(exist_ok=False)
    gate();install();env=None;ds=None
    try:
        reserve('make_env',WORKER,'make_env0');event('before_make_env')
        env=lib.make_env(0);event('after_make_env')
        source_xml=env.model.get_xml();(P/f'local_only/w{worker}_model.xml').write_text(source_xml)
        args=SimpleNamespace(**read(R/'manifests/C_config.json'))
        stats={k:np.asarray(v,np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
        event('before_Dataset');ds=EpisodicDataset(list(range(200)),stats,args,camera_poses_file='train_cameras.json',transform='id',env=env,
            max_seq_length=read(D/'execution/sample_plan.json')['training_dataset_max_seq_length']);event('after_Dataset')
        event('before_Evaluator');evaluator=Evaluator(env,stats,str(lib.DATA),args);event('after_Evaluator')
        embedder=PluckerEmbedder(img_size=256,device='cuda');event('after_embedder')
        with np.load(D/'execution/inputs/sample_00.npz') as z:state=z['source_state_f32'].copy();T=z['T_given'].copy()
        entries=[]
        for phase in ['baseline','repair']:
            if phase=='repair':
                base=[r for r in FRAMES if r['entry'].startswith('baseline_')]
                supports=any(not r['before']['match'] and r['sentinel'].get('retained_165_fraction',0)>.99 for r in base)
                if not supports:
                    write(OUT/'result.json',{'worker':worker,'state':'NOT_REPRODUCED_OR_NO_SUPPORTED_REPAIR','repair':'NOT_RUN','entries':entries,'readback':FRAMES})
                    return
                choice={'utc':utc(),'worker':worker,'chosen':'make_current_inside_existing_render_lock',
                   'support_read_ordinals':[r['ordinal'] for r in base if not r['before']['match']],
                   'single_change':'bind target gl_ctx once inside original lock before original MjRenderContext.render; check after render/read entry; no rebind',
                   'against_and_limits':'sentinel alone insufficient; baseline context mismatch and no-write must align; lifecycle trigger and old training require independent evidence',
                   'module_sha256':sha(P/'scripts/context_binding.py')}
                if not (P/'repair_choice.json').exists():write(P/'repair_choice.json',choice,True)
                else:assert read(P/'repair_choice.json')['chosen']==choice['chosen']
                write(OUT/'repair_choice.json',choice)
                FIX=True
            for path in ['dataset','evaluator','custom']:
                ENTRY=phase+'_'+path
                item=None
                # Initialization implicit renders consume the same global budget, never free repeats.
                if read(P/'counts.json')['renders']>=12 or read(P/'counts.json')['readPixels']>22:
                    raise RuntimeError('budget insufficient for next render+sentinel; PARTIAL')
                lib.seed_all(20261029);env.sim.set_state_from_flattened(state);env.sim.forward();lib.camera_pose(env,T)
                actual=env.sim.get_state().flatten().copy();assert np.array_equal(actual,state)
                xmlsha=hashlib.sha256(env.model.get_xml().encode()).hexdigest()
                event('entry_before',state_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),xml_sha256=xmlsha,T_sha256=hashlib.sha256(T.tobytes()).hexdigest())
                before=len(FRAMES)
                with track_flip():
                    if path=='dataset':
                        with forced_choices(ds.demo_lengths[0]):item=ds[0]
                        rgbtensor=item['image'][0,:3]
                    elif path=='evaluator':
                        rgb=evaluator._render_cam_image(T);rgbtensor=evaluator._image_to_tensor(rgb,T)[:3]
                    else:
                        rgb=lib.render(env,T);item=lib.policy_input(rgb,T,lib.intrinsics(env),stats,embedder,True);rgbtensor=item['image'][0,0,:3]
                tensor=rgbtensor.detach().float().cpu().numpy().copy();tensor_meta=save_array(ENTRY+'_float_tensor_rgb',tensor)
                saved=np.array(tensor,copy=True);np.savez_compressed(OUT/(ENTRY+'_saved.npz'),rgb_float=saved)
                with np.load(OUT/(ENTRY+'_saved.npz')) as z:loaded=z['rgb_float'].copy()
                pixels=np.rint(loaded.transpose(1,2,0)*255).astype(np.uint8);Image.fromarray(pixels).save(OUT/(ENTRY+'.png'))
                assert np.array_equal(saved,loaded)
                current=FRAMES[before:];assert len(current)==1,'one normal read per entry'
                raw=np.load(P/current[0]['raw']['file'])
                expected=np.flip(raw,axis=0).copy()
                row={'entry':ENTRY,'tensor':tensor_meta,'saved_npz_sha256':sha(OUT/(ENTRY+'_saved.npz')),
                    'raw_to_saved_flip_exact':bool(np.array_equal(expected,pixels)),
                    'source_state_sha256':hashlib.sha256(actual.tobytes()).hexdigest(),'xml_sha256':xmlsha,
                    'T_sha256':hashlib.sha256(T.tobytes()).hexdigest(),'pixel_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),
                    'read_ordinal':current[0]['ordinal'],'provisional_readback_healthy':frame_health(current)}
                # Same raw RGB, three pure copied source RGB preprocessing formulas, no rendering.
                common=np.flip(raw,axis=0).copy()
                from torchvision.transforms import functional as TF
                a=TF.resize(torch.from_numpy(common).float().div(255).permute(2,0,1),256)
                b=torch.from_numpy(common).float().div(255).permute(2,0,1)
                c=torch.from_numpy(common).permute(2,0,1).float().div(255)
                row['common_raw_rgb_preprocessing']={'dataset_eval_equal':bool(torch.equal(a,b)),
                   'dataset_custom_equal':bool(torch.equal(a,c)),'scope':'RGB numeric formulas only; Dataset Resize256 no-op; no ray geometry or model claim'}
                np.savez_compressed(OUT/(ENTRY+'_common_raw_preprocess.npz'),dataset=a.numpy().copy(),evaluator=b.numpy().copy(),custom=c.numpy().copy())
                entries.append(row);write(OUT/'entries.json',entries)
                event('entry_after')
                del rgbtensor,item,tensor,saved,loaded,pixels,raw,expected,common,a,b,c,current
                if path!='dataset':del rgb
            if phase=='repair' and not frame_health([r for r in FRAMES if r['entry'].startswith('repair_')]):
                raise RuntimeError('first supported repair failed; no second repair')
        fixed=[e for e in entries if e['entry'].startswith('repair_')]
        write(OUT/'result.json',{'worker':worker,'state':'REPAIR_PROVISIONAL_PASS_AWAIT_VISUAL','entries':entries,
              'readback':FRAMES,'repair_three_entries_pixel_equal':len({e['pixel_sha256'] for e in fixed})==1,
              'requires_visual_check':True,'trigger_source':'evaluate event chain; not inferred from source alone','historic_0_of_32_cause':'UNKNOWN'})
    finally:
        ENTRY='CLEANUP'
        if ds is not None:ds.env=None
        if env is not None:env.close()
        event('cleanup_completed')
        # Restore every monkeypatch; no active simulator reference is retained by logging.
        for owner,name,original in reversed(ORIGINALS):setattr(owner,name,original)
        ACTIVE=False
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--worker',type=int,choices=[1,2],required=True)
    main(ap.parse_args().worker)
