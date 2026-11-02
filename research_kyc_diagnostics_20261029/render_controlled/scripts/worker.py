"""Identical held A/B fixture, exactly one controlled A release, one condition."""
from lc_common import *
from owned_release import release_owned,one_shot_release,pointer_value
from telemetry import Telemetry
import argparse,contextlib,inspect,sys,weakref
import numpy as np
import torch
from PIL import Image
sys.path.insert(0,str(R/'scripts'))
import experiment_lib as lib
import robosuite.utils.binding_utils as bu
from robosuite.renderers.context import egl_context as ec
from robosuite.environments.base import MujocoEnv

API=None;OUT=None;WID=0;MODE=None;ENTRY='INIT';PHASE='INIT';EXPECTED_TAG=None
HELD=[];WEAK=[];TAG_OWNERS={};GUARDS={};FRAMES=[];SENT=False;START=None
REFERENCE_PIXEL_SHA='688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37'

class ControlledTelemetry(Telemetry):
    def observe(self,label,renderer=None,ids=None,**extra):
        tag=getattr(renderer,'_fixture_tag',None) if renderer is not None else None
        if tag and label in ['baseline_before_con_free','owner_bound_before_con_free']:
            GUARDS[tag]['con_free_attempts']+=1
        if tag and label in ['baseline_after_con_free','owner_bound_after_con_free']:
            GUARDS[tag]['con_free_returns']+=1
        return super().observe(label,renderer,ids,**extra)

def event(name,renderer=None,ids=None,**kw):return API.observe(name,renderer,ids,**kw)
def arrmeta(name,a):
    value=np.array(a,copy=True,order='C');file=OUT/(name+'.npy');np.save(file,value,allow_pickle=False)
    return {'file':str(file.relative_to(P)),'shape':list(value.shape),'dtype':str(value.dtype),
       'sha256':hashlib.sha256(value.tobytes()).hexdigest(),'file_sha256':sha(file),'independent_copy':not np.shares_memory(value,a)}
def native_reserve(kind):
    cap=2 if kind=='renders' else 4
    if read(P/'counts.json')[kind]-START[kind]>=cap:raise RuntimeError('implicit calls consumed this condition budget')
    return reserve(kind,WID,ENTRY+('_sentinel' if SENT else '_normal'))

def baseline_body(self):
    ids=API.ids(getattr(self,'con',None));event('baseline_before_con_free',self,ids)
    self.con.free()
    event('baseline_after_con_free',self,ids)
    try:self.gl_ctx.free()
    except Exception as exc:
        event('baseline_original_gl_free_exception',exception_type=type(exc).__name__)
        pass
    del self.con
    del self.gl_ctx
    del self.scn
    del self.cam
    del self.vopt
    del self.pert

def shared_destructor(self):
    tag=getattr(self,'_fixture_tag',None);state=getattr(self,'_controlled_release_state','NEW')
    if tag not in GUARDS:
        API.failure('unregistered_renderer_destructor','RuntimeError');raise RuntimeError('unregistered renderer')
    GUARDS[tag]['invocations']+=1
    if state=='NEW':
        if tag!=EXPECTED_TAG or PHASE not in ['TRIGGER_A','CLEANUP_A','CLEANUP_B']:
            API.failure('unexpected_natural_first_release','RuntimeError');raise RuntimeError('unexpected natural release')
        GUARDS[tag]['first_entries']+=1
    elif state=='DONE':GUARDS[tag]['skipped_DONE']+=1
    elif state=='RUNNING':
        GUARDS[tag]['skipped_RUNNING']+=1;API.failure('unexpected_reentrant_release','RuntimeError');raise RuntimeError('reentrant fixture release')
    action=baseline_body if MODE=='baseline' else lambda renderer:release_owned(renderer,API)
    done=one_shot_release(self,action,API)
    if done:GUARDS[tag]['first_completed']+=1
    write(OUT/'guard_counts.json',GUARDS)

def install():
    original_init=ec.EGLGLContext.__init__
    def gl_init(self,*a,**kw):
        event('EGL_constructor_enter');result=original_init(self,*a,**kw);API.register(self);event('EGL_constructor_exit',actor_context=API.owner(self));return result
    ec.EGLGLContext.__init__=gl_init
    original_renderer=bu.MjRenderContext.__init__
    def renderer_init(self,*a,**kw):
        event('renderer_constructor_enter');result=original_renderer(self,*a,**kw);API.register_renderer(self)
        tag='r'+str(len(HELD)+1);self._fixture_tag=tag;self._controlled_release_state='NEW'
        TAG_OWNERS[tag]=API.owner(self.gl_ctx)
        GUARDS[tag]={'invocations':0,'first_entries':0,'first_completed':0,'con_free_attempts':0,'con_free_returns':0,'context_destroy_successes':0,'skipped_DONE':0,'skipped_RUNNING':0}
        HELD.append(self);WEAK.append(weakref.ref(self))  # Explicit common fixture, not telemetry retention.
        event('renderer_constructed_and_fixture_held',self,renderer_tag=tag)
        return result
    bu.MjRenderContext.__init__=renderer_init
    original_free=ec.EGLGLContext.free
    def gl_free(self,*a,**kw):
        actor=API.owner(self);event('EGL_free_enter',actor_context=actor)
        try:return original_free(self,*a,**kw)
        finally:event('EGL_free_exit',actor_context=actor)
    ec.EGLGLContext.free=gl_free
    for name in ['eglReleaseThread','eglMakeCurrent','eglDestroyContext']:
        fn=getattr(ec.EGL,name)
        def make_wrapper(name,fn):
            def wrap(*a,**kw):
                ptr=pointer_value(a[1]) if name=='eglDestroyContext' and len(a)>1 else 0
                actor=API.address_to_key.get(ptr);event(name+'_enter',actor_context=actor)
                result=fn(*a,**kw)
                if name=='eglDestroyContext' and bool(result):
                    API.destroyed(ptr)
                    for tag,key in TAG_OWNERS.items():
                        if key==actor:GUARDS[tag]['context_destroy_successes']+=1
                event(name+'_exit',actor_context=actor,returned=bool(result));return result
            return wrap
        setattr(ec.EGL,name,make_wrapper(name,fn))
    source=inspect.getsource(bu.MjRenderContext.__del__)
    write(OUT/'original_destructor.json',{'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'upstream_file_sha256':sha(R/'vendor/robosuite/robosuite/utils/binding_utils.py'),
       'common_guard':'same shared_destructor for both conditions; first body is original baseline or corrected owner transaction','mode':MODE},True)
    (P/f'local_only/w{WID}_original_destructor.txt').write_text(source)
    bu.MjRenderContext.__del__=shared_destructor
    original_render=bu.mujoco.mjr_render
    def render(*a,**kw):
        n=native_reserve('renders');event('mjr_render_before',ordinal=n)
        try:return original_render(*a,**kw)
        finally:event('mjr_render_after',ordinal=n)
    bu.mujoco.mjr_render=render
    original_read=bu.mujoco.mjr_readPixels
    def readpixels(*a,**kw):
        global SENT
        n=native_reserve('readPixels');rgb=kw['rgb'];before=event('mjr_readPixels_before',ordinal=n,sentinel=SENT)
        result=original_read(*a,**kw);raw=np.array(rgb,copy=True);meta=arrmeta(f'read_{n:02d}_'+('sentinel' if SENT else 'raw'),raw)
        after=event('mjr_readPixels_after',ordinal=n,sentinel=SENT,array=meta)
        if not SENT:
            row={'entry':ENTRY,'ordinal':n,'raw':meta,'before':before,'after':after};FRAMES.append(row)
            if raw.shape!=(256,256,3):raise RuntimeError('implicit non256 render; stop without extra sentinel')
            sentinel=np.full((256,256,3),165,np.uint8);SENT=True
            try:bu.mujoco.mjr_readPixels(rgb=sentinel,depth=None,viewport=kw['viewport'],con=kw['con'])
            finally:SENT=False
            row['sentinel']={'retained_165_fraction':float(np.mean(sentinel==165)),'normal_165_fraction':float(np.mean(raw==165)),
                'equal_preflip_raw':bool(np.array_equal(sentinel,raw)),'max_abs_preflip_difference':int(abs(sentinel.astype(np.int16)-raw.astype(np.int16)).max()),
                'separate_buffer':not np.shares_memory(sentinel,rgb),'inside_original_lock':bu._MjSim_render_lock.locked()}
            write(OUT/'readback.json',FRAMES)
        return result
    bu.mujoco.mjr_readPixels=readpixels
    def forbidden_step(*a,**kw):reserve('env_steps',WID,ENTRY)
    MujocoEnv.step=forbidden_step

@contextlib.contextmanager
def flip_track():
    original=np.flipud
    def flip(a):
        arrmeta(ENTRY+'_flip_input',a);result=original(a);arrmeta(ENTRY+'_flip_output',result);return result
    np.flipud=flip
    try:yield
    finally:np.flipud=original

def capture_frame(env,state,T,label):
    global ENTRY
    ENTRY=label;API.entry=ENTRY
    lib.seed_all(20261029);env.sim.set_state_from_flattened(state);env.sim.forward();lib.camera_pose(env,T)
    actual=env.sim.get_state().flatten().copy();assert np.array_equal(actual,state)
    begin=len(FRAMES);event('frame_before')
    with flip_track():rgb=lib.render(env,T)
    tensor=torch.from_numpy(rgb).permute(2,0,1).float()/255
    value=tensor.numpy().copy();meta=arrmeta(label+'_tensor_rgb',value)
    np.savez_compressed(OUT/(label+'_saved.npz'),rgb_float=value.copy())
    with np.load(OUT/(label+'_saved.npz')) as z:saved=z['rgb_float'].copy()
    pixels=np.rint(saved.transpose(1,2,0)*255).astype(np.uint8);Image.fromarray(pixels).save(OUT/(label+'.png'))
    new=FRAMES[begin:];assert len(new)==1;rb=new[0];raw=np.load(P/rb['raw']['file'])
    assert np.array_equal(np.flip(raw,0),pixels)
    errors_ok=all(r['gl'] is not None and r['gl']['errors']['codes']==[0] for r in [rb['before'],rb['after']])
    row={'entry':label,'tensor':meta,'pixel_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'normal_read_ordinal':rb['ordinal'],
      'state_sha256':hashlib.sha256(actual.tobytes()).hexdigest(),'T_sha256':hashlib.sha256(T.tobytes()).hexdigest(),
      'xml_sha256':hashlib.sha256(env.model.get_xml().encode()).hexdigest(),'raw_to_png_exact_flip':True,
      'readback_healthy':bool(errors_ok and rb['sentinel']['equal_preflip_raw'] and rb['before']['current_context'] is not None),
      'matches_reference_pixels':hashlib.sha256(pixels.tobytes()).hexdigest()==REFERENCE_PIXEL_SHA}
    write(OUT/(label+'_metrics.json'),row);event('frame_after');API.check()
    return row,pixels

def main(wid,mode):
    global API,OUT,WID,MODE,ENTRY,PHASE,EXPECTED_TAG,START
    WID=wid;MODE=mode;OUT=P/f'results/worker_{wid}_{mode}';OUT.mkdir(exist_ok=False)
    gate();START=read(P/'counts.json');API=ControlledTelemetry(ec,OUT,WID);install()
    env=None;A=None;B=None;result_state='PARTIAL';before=None;after=None;fixture=None
    try:
        reserve('make_env',WID,'make_env0');event('before_make_env');env=lib.make_env(0);event('after_make_env');API.check()
        if len(HELD)!=2 or API.owner_sequence!=2:raise RuntimeError('STOP_FIXTURE_NOT_EXACTLY_TWO_RENDERERS')
        active=[r for r in HELD if r.sim is env.sim];retired=[r for r in HELD if r.sim is not env.sim]
        if len(active)!=1 or len(retired)!=1:raise RuntimeError('STOP_FIXTURE_SIM_IDENTITIES')
        B=active[0];A=retired[0];del active,retired
        ka=API.owner(A.gl_ctx);kb=API.owner(B.gl_ctx);current=API.capture()
        if not ka or not kb or ka==kb or not API.live(ka) or not API.live(kb) or current['key']!=kb or not current['context']:
            raise RuntimeError('STOP_FIXTURE_CONTEXT_IDENTITIES')
        fixture={'controlled_trigger_not_natural_GC':True,'retired_tag':A._fixture_tag,'active_tag':B._fixture_tag,'A_context':ka,'B_context':kb,
          'A_sim_is_env_sim':False,'B_sim_is_env_sim':True,'B_original_ids':API.ids(B.con),'A_initial_ids':API.ids(A.con),
          'renderer_count':len(HELD),'context_count':API.owner_sequence}
        write(OUT/'fixture.json',fixture,True);event('fixture_verified',B,fixture=fixture)
        with np.load(D/'execution/inputs/sample_00.npz') as z:state=z['source_state_f32'].copy();T=z['T_given'].copy()
        (P/f'local_only/w{wid}_model.xml').write_text(env.model.get_xml())
        before,before_pixels=capture_frame(env,state,T,'before')
        if not before['readback_healthy'] or not before['matches_reference_pixels']:
            result_state='STOP_BEFORE_CONTROL_MISMATCH';return
        ENTRY='CONTROLLED_RELEASE_A';API.entry=ENTRY;PHASE='TRIGGER_A';EXPECTED_TAG=A._fixture_tag
        with bu._MjSim_render_lock:
            event('controlled_A_release_enter',A,lock_locked=bu._MjSim_render_lock.locked(),A_context=ka,B_context=kb)
            A.__del__()
            event('controlled_A_release_exit',B,lock_locked=bu._MjSim_render_lock.locked(),A_context=ka,B_context=kb,A_live=API.live(ka),B_live=API.live(kb))
        API.check();PHASE='AFTER_A';EXPECTED_TAG=None
        if API.live(ka) or not API.live(kb):raise RuntimeError('STOP_CONTEXT_LIFETIMES_AFTER_A')
        tagA=A._fixture_tag
        if GUARDS[tagA]['first_completed']!=1 or GUARDS[tagA]['con_free_returns']!=1 or GUARDS[tagA]['context_destroy_successes']!=1:raise RuntimeError('STOP_A_RELEASE_NOT_EXACTLY_ONCE')
        if API.ids(B.con)!=fixture['B_original_ids'] or API.owner_sequence!=2:raise RuntimeError('STOP_B_RESOURCE_IDENTITY_CHANGED')
        HELD.remove(A);del A;A=None
        after,after_pixels=capture_frame(env,state,T,'after')
        after['matches_before_pixels']=bool(np.array_equal(after_pixels,before_pixels));write(OUT/'after_metrics.json',after)
        result_state='COMPLETE'
    finally:
        ENTRY='CLEANUP';API.entry=ENTRY;PHASE='CLEANUP_A'
        if A is not None and getattr(A,'_controlled_release_state','NEW')=='NEW':
            EXPECTED_TAG=A._fixture_tag;A.__del__()
        PHASE='CLEANUP_B'
        if B is not None and getattr(B,'_controlled_release_state','NEW')=='NEW':
            EXPECTED_TAG=B._fixture_tag;B.__del__()
        EXPECTED_TAG=None;PHASE='CLEANUP_ENV'
        if env is not None:env.close()
        HELD.clear();A=None;B=None;env=None
        API.check()
        if fixture is not None:
            for tag in [fixture['retired_tag'],fixture['active_tag']]:
                if GUARDS[tag]['first_completed']!=1 or GUARDS[tag]['con_free_returns']!=1 or GUARDS[tag]['context_destroy_successes']!=1 or GUARDS[tag]['skipped_RUNNING']:
                    raise RuntimeError('cleanup exactly-once failure')
        if any(c['alive'] for c in API.contexts.values()):raise RuntimeError('live context leak after cleanup')
        write(OUT/'guard_counts.json',GUARDS)
        write(OUT/'result.json',{'utc':utc(),'state':result_state,'mode':mode,'before':before,'after':after,'fixture':fixture,
          'guard_counts':GUARDS,'all_contexts_destroyed':not any(c['alive'] for c in API.contexts.values()),'fatal':API.fatal,
          'fixture_strong_refs_remaining':len(HELD),'old_0_of_32_cause':'UNKNOWN'})
        event('worker_cleanup_completed')
        # The common DONE guard stays installed through this dedicated process's
        # exit so a late natural finalizer cannot fall back to substantive free.

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',type=int,choices=[1,2],required=True);p.add_argument('--mode',choices=['baseline','fix'],required=True)
    a=p.parse_args();main(a.worker,a.mode)
