"""Exactly one baseline or owner-safe condition; installed before make_env."""
from lc_common import *
from owned_release import release_owned,pointer_value
from telemetry import Telemetry
import argparse,contextlib,inspect,sys
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

API=None;OUT=None;WID=0;ENTRY='INIT';SENT=False;PATCHES=[];FRAMES=[];START=None
def patch(owner,name,new):PATCHES.append((owner,name,getattr(owner,name)));setattr(owner,name,new)
def arrmeta(name,a):
    independent=np.array(a,copy=True,order='C');path=OUT/(name+'.npy');np.save(path,independent,allow_pickle=False)
    return {'file':str(path.relative_to(P)),'shape':list(independent.shape),'dtype':str(independent.dtype),
      'sha256':hashlib.sha256(independent.tobytes()).hexdigest(),'file_sha256':sha(path),'independent_copy':not np.shares_memory(independent,a)}
def event(label,renderer=None,ids=None,**kw):return API.observe(label,renderer,ids,**kw)
def reserve_local(kind):
    c=read(P/'counts.json');cap=4 if kind=='renders' else 8
    if c[kind]-START[kind]>=cap:raise RuntimeError('implicit calls exhausted local worker allocation')
    return reserve(kind,WID,ENTRY+('_sentinel' if SENT else '_normal'))

def baseline_destructor(self):
    # Original upstream statements/order retained, with primitive event windows only.
    ids=API.ids(getattr(self,'con',None));event('baseline_before_con_free',self,ids)
    self.con.free()
    event('baseline_after_con_free',self,ids)
    try:
        self.gl_ctx.free()
    except Exception as exc:
        event('baseline_original_gl_free_exception',exception_type=type(exc).__name__)
        pass
    del self.con
    del self.gl_ctx
    del self.scn
    del self.cam
    del self.vopt
    del self.pert

def fixed_destructor(self):release_owned(self,API)

def install(mode):
    original=ec.EGLGLContext.__init__
    def context_init(self,*a,**kw):
        event('EGL_constructor_enter');result=original(self,*a,**kw);API.register(self);event('EGL_constructor_exit',actor_context=API.owner(self));return result
    patch(ec.EGLGLContext,'__init__',context_init)
    original_renderer=bu.MjRenderContext.__init__
    def renderer_init(self,*a,**kw):
        event('renderer_constructor_enter');result=original_renderer(self,*a,**kw)
        API.register_renderer(self);event('renderer_constructor_exit',self);return result
    patch(bu.MjRenderContext,'__init__',renderer_init)
    original_egl_free=ec.EGLGLContext.free
    def egl_free(self,*a,**kw):
        actor=API.owner(self);event('EGL_free_enter',actor_context=actor)
        try:return original_egl_free(self,*a,**kw)
        finally:event('EGL_free_exit',actor_context=actor)
    patch(ec.EGLGLContext,'free',egl_free)
    for name in ['eglReleaseThread','eglMakeCurrent','eglDestroyContext']:
        fn=getattr(ec.EGL,name)
        def make_wrapper(name,fn):
            def wrapper(*a,**kw):
                address=pointer_value(a[1]) if name=='eglDestroyContext' and len(a)>1 else 0
                actor=API.address_to_key.get(address)
                event(name+'_enter',actor_context=actor)
                result=fn(*a,**kw)
                if name=='eglDestroyContext' and bool(result):API.destroyed(address)
                event(name+'_exit',actor_context=actor,returned=bool(result))
                return result
            return wrapper
        patch(ec.EGL,name,make_wrapper(name,fn))
    source=inspect.getsource(bu.MjRenderContext.__del__)
    write(OUT/'destructor_source.json',{'original_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
       'original_file_sha256':sha(R/'vendor/robosuite/robosuite/utils/binding_utils.py'),
       'condition':mode,'baseline_semantics':'con.free; try gl_ctx.free except Exception pass; delete con/gl_ctx/scn/cam/vopt/pert',
       'fixed_change':'owner binding for resource release and restoration of still-live previous; partial/duplicate guards'},True)
    (P/f'local_only/w{WID}_original_destructor.txt').write_text(source)
    patch(bu.MjRenderContext,'__del__',baseline_destructor if mode=='baseline' else fixed_destructor)
    original_render=bu.mujoco.mjr_render
    def render(*a,**kw):
        ordinal=reserve_local('renders');event('mjr_render_before',ordinal=ordinal)
        try:return original_render(*a,**kw)
        finally:event('mjr_render_after',ordinal=ordinal)
    patch(bu.mujoco,'mjr_render',render)
    original_read=bu.mujoco.mjr_readPixels
    def pixels(*a,**kw):
        global SENT
        ordinal=reserve_local('readPixels');rgb=kw['rgb'];con=kw['con']
        before=event('mjr_readPixels_before',ordinal=ordinal,sentinel=SENT)
        result=original_read(*a,**kw)
        raw=np.array(rgb,copy=True);meta=arrmeta(f'read_{ordinal:02d}_'+('sentinel' if SENT else 'raw'),raw)
        after=event('mjr_readPixels_after',ordinal=ordinal,sentinel=SENT,array=meta)
        if not SENT:
            row={'entry':ENTRY,'ordinal':ordinal,'raw':meta,'before':before,'after':after,'sentinel':None};FRAMES.append(row)
            if raw.shape==(256,256,3):
                sent=np.full((256,256,3),165,dtype=np.uint8);SENT=True
                try:bu.mujoco.mjr_readPixels(rgb=sent,depth=None,viewport=kw['viewport'],con=con)
                finally:SENT=False
                row['sentinel']={'value':165,'retained_fraction':float(np.mean(sent==165)),
                    'normal_165_fraction':float(np.mean(raw==165)),'equal_preflip_raw':bool(np.array_equal(sent,raw)),
                    'max_abs_preflip_difference':int(abs(sent.astype(np.int16)-raw.astype(np.int16)).max()),
                    'separate_buffer':not np.shares_memory(sent,rgb),'executed_inside_original_lock':bu._MjSim_render_lock.locked()}
            else:row['sentinel']={'state':'NOT_RUN','reason':'implicit non256 render'}
            write(OUT/'readback.json',FRAMES)
        return result
    patch(bu.mujoco,'mjr_readPixels',pixels)
    def forbid_step(*a,**kw):reserve('env_steps',WID,ENTRY)
    patch(MujocoEnv,'step',forbid_step)

@contextlib.contextmanager
def choices(length):
    state=lib.rng_state();ri=np.random.randint;ch=np.random.choice;counts={'t':0,'camera':0}
    def r(low,high=None,size=None,dtype=int):
        if high is None and low==length and size is None:counts['t']+=1;return 0
        return ri(low,high,size,dtype)
    def c(a,size=None,replace=True,p=None):
        if np.array_equal(a,np.arange(3)) and size==1 and not replace:counts['camera']+=1;return np.array([1],np.int64)
        return ch(a,size,replace,p)
    np.random.randint=r;np.random.choice=c
    try:yield counts
    finally:np.random.randint=ri;np.random.choice=ch;lib.restore_rng(state)
@contextlib.contextmanager
def flip_track():
    original=np.flipud
    def flip(a):
        arrmeta(ENTRY+'_flip_input',a);out=original(a);arrmeta(ENTRY+'_flip_output',out);return out
    np.flipud=flip
    try:yield
    finally:np.flipud=original

def main(wid,mode):
    global API,OUT,WID,ENTRY,START
    WID=wid;OUT=P/f'results/worker_{wid}_{mode}';OUT.mkdir(exist_ok=False)
    gate();API=Telemetry(ec,OUT,WID);START=read(P/'counts.json');install(mode)
    env=None;ds=None;entries=[];result_state='PARTIAL'
    try:
        reserve('make_env',WID,'make_env0');event('before_make_env');env=lib.make_env(0);event('after_make_env');API.check()
        with np.load(D/'execution/inputs/sample_00.npz') as z:state=z['source_state_f32'].copy();T=z['T_given'].copy()
        source_xml=env.model.get_xml();(P/f'local_only/w{wid}_model.xml').write_text(source_xml)
        args=SimpleNamespace(**read(R/'manifests/C_config.json'));stats={k:np.asarray(v,np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
        evaluator=None;embedder=None
        for path in ['early','dataset','evaluator','custom']:
            if path=='dataset':
                ENTRY='CONSTRUCT_DATASET';API.entry=ENTRY;event('before_Dataset')
                ds=EpisodicDataset(list(range(200)),stats,args,camera_poses_file='train_cameras.json',transform='id',env=env,
                  max_seq_length=read(D/'execution/sample_plan.json')['training_dataset_max_seq_length']);event('after_Dataset');API.check()
                event('before_Evaluator');evaluator=Evaluator(env,stats,str(lib.DATA),args);event('after_Evaluator')
                embedder=PluckerEmbedder(img_size=256,device='cuda');event('after_embedder');API.check()
            ENTRY=path;API.entry=ENTRY;item=None
            if read(P/'counts.json')['renders']-START['renders']>=4 or read(P/'counts.json')['readPixels']-START['readPixels']>6:
                result_state='PARTIAL_IMPLICIT_BUDGET';break
            lib.seed_all(20261029);env.sim.set_state_from_flattened(state);env.sim.forward();lib.camera_pose(env,T)
            actual=env.sim.get_state().flatten().copy();assert np.array_equal(actual,state)
            before=len(FRAMES);event('entry_before')
            with flip_track():
                if path=='early':
                    rgb=lib.render(env,T);tensor=torch.from_numpy(rgb).permute(2,0,1).float()/255
                elif path=='dataset':
                    with choices(ds.demo_lengths[0]) as controls:item=ds[0]
                    assert controls=={'t':1,'camera':1};tensor=item['image'][0,:3]
                elif path=='evaluator':
                    rgb=evaluator._render_cam_image(T);tensor=evaluator._image_to_tensor(rgb,T)[:3]
                else:
                    rgb=lib.render(env,T);item=lib.policy_input(rgb,T,lib.intrinsics(env),stats,embedder,True);tensor=item['image'][0,0,:3]
            value=tensor.detach().float().cpu().numpy().copy();tm=arrmeta(ENTRY+'_tensor_rgb',value)
            np.savez_compressed(OUT/(ENTRY+'_saved.npz'),rgb_float=value.copy())
            with np.load(OUT/(ENTRY+'_saved.npz')) as z:saved=z['rgb_float'].copy()
            pixels=np.rint(saved.transpose(1,2,0)*255).astype(np.uint8);Image.fromarray(pixels).save(OUT/(ENTRY+'.png'))
            new=FRAMES[before:];assert len(new)==1;raw=np.load(P/new[0]['raw']['file'])
            assert np.array_equal(np.flip(raw,0),pixels)
            from torchvision.transforms import functional as TF
            common=np.flip(raw,0).copy();a=TF.resize(torch.from_numpy(common).float().div(255).permute(2,0,1),256)
            b=torch.from_numpy(common).float().div(255).permute(2,0,1);c=torch.from_numpy(common).permute(2,0,1).float().div(255)
            np.savez_compressed(OUT/(ENTRY+'_common_preprocess.npz'),dataset=a.numpy().copy(),evaluator=b.numpy().copy(),custom=c.numpy().copy())
            entries.append({'entry':ENTRY,'tensor':tm,'raw_to_png_exact_flip':True,'common_rgb_equal':bool(torch.equal(a,b) and torch.equal(a,c)),
                'pixel_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'state_sha256':hashlib.sha256(actual.tobytes()).hexdigest(),
                'T_sha256':hashlib.sha256(T.tobytes()).hexdigest(),'xml_sha256':hashlib.sha256(env.model.get_xml().encode()).hexdigest(),
                'normal_read_ordinal':new[0]['ordinal']})
            write(OUT/'entries.json',entries);event('entry_after');API.check()
            del item,tensor,value,saved,pixels,new,raw,common,a,b,c
            if path!='dataset':del rgb
        if len(entries)==4:result_state='COMPLETE'
    finally:
        ENTRY='CLEANUP';API.entry=ENTRY
        if ds is not None:ds.env=None
        if env is not None:env.close()
        API.check();event('cleanup_completed')
        write(OUT/'result.json',{'utc':utc(),'condition':mode,'state':result_state,'entries':len(entries),'fatal_lifecycle_errors':API.fatal,
          'counts_at_end':read(P/'counts.json'),'old_0_of_32_cause':'UNKNOWN'})
        for owner,name,original in reversed(PATCHES):setattr(owner,name,original)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',type=int,choices=[1,2],required=True);p.add_argument('--mode',choices=['baseline','fix'],required=True)
    args=p.parse_args();main(args.worker,args.mode)
