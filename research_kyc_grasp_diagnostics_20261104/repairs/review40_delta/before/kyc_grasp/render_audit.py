"""Bounded raw/sentinel capture. A/B fix ownership; C observes native release."""
from .common import *
from .ledger import reserve,current_stage
from .telemetry import Telemetry
from .owned_release import release_owned,pointer_value

class RenderAudit:
    def __init__(self,strict=True,owner_release=True):
        import numpy as np
        import robosuite.utils.binding_utils as bu
        from robosuite.renderers.context import egl_context as ec
        from robosuite.environments.base import MujocoEnv
        self.np=np;self.bu=bu;self.env=None;self.strict=strict;self.owner_release=owner_release;self.stage=current_stage();self.entry='INIT';self.frames={};self.persist_arrays=True;self.last_arrays=None
        self.out=P/('results/'+self.stage);self.out.mkdir(exist_ok=False)
        self.api=Telemetry(ec,self.out,PHASES.index(self.stage)+1);api=self.api
        old_init=ec.EGLGLContext.__init__
        def init(obj,*a,**kw):
            api.note('EGL_constructor_enter');r=old_init(obj,*a,**kw);api.register(obj);api.note('EGL_constructor_exit',actor_context=api.owner(obj));return r
        ec.EGLGLContext.__init__=init
        old_renderer=bu.MjRenderContext.__init__
        def renderer(obj,*a,**kw):
            r=old_renderer(obj,*a,**kw);api.register_renderer(obj);api.observe('renderer_constructed',obj);return r
        bu.MjRenderContext.__init__=renderer
        native_destructor=bu.MjRenderContext.__del__
        def destructor(obj):
            previous=api.capture();owner=api.owner(getattr(obj,'gl_ctx',None));api.observe('natural_renderer_release_enter',obj,releasing_owner=owner,previous_context=previous['key'],owner_fix=owner_release)
            try:
                if owner_release:release_owned(obj,api)
                else:native_destructor(obj)
                api.note('natural_renderer_release_exit',releasing_owner=owner,previous_context=previous['key'],owner_fix=owner_release)
            except BaseException as exc:api.failure('natural_destructor',type(exc).__name__);raise
        bu.MjRenderContext.__del__=destructor
        for name in ['eglMakeCurrent','eglReleaseThread','eglDestroyContext']:
            original=getattr(ec.EGL,name)
            def factory(name,original):
                def f(*a,**kw):
                    address=pointer_value(a[1]) if name=='eglDestroyContext' else 0;actor=api.address_to_key.get(address);api.note(name+'_enter',actor_context=actor)
                    r=original(*a,**kw)
                    if name=='eglDestroyContext' and bool(r):api.destroyed(address)
                    api.note(name+'_exit',actor_context=actor,returned=bool(r));return r
                return f
            setattr(ec.EGL,name,factory(name,original))
        if not hasattr(MujocoEnv,'_kyc_diag_original_step'):MujocoEnv._kyc_diag_original_step=MujocoEnv.step
        def unplanned_step(*a,**kw):
            reserve('env_steps','builder','unplanned_step_before_control_recorder');raise RuntimeError('unplanned native env step')
        MujocoEnv.step=unplanned_step
        old_reset=MujocoEnv.reset
        def reset(env,*a,**kw):reserve('resets','builder',self.entry);return old_reset(env,*a,**kw)
        MujocoEnv.reset=reset
        old_render=bu.mujoco.mjr_render
        def render(*a,**kw):
            reserve('renders','renderer',self.entry);before=api.note('mjr_render_before');self.check_health(before,'render_before')
            r=old_render(*a,**kw);after=api.note('mjr_render_after');self.check_health(after,'render_after');return r
        bu.mujoco.mjr_render=render
        old_read=bu.mujoco.mjr_readPixels
        def read_pixels(*a,**kw):
            require(bu._MjSim_render_lock.locked(),'native read outside original render lock')
            reserve('readPixels','renderer',self.entry);before=api.note('mjr_readPixels_before',sentinel=False);self.check_health(before,'read_before')
            r=old_read(*a,**kw);normal=np.array(kw['rgb'],copy=True);after=api.note('mjr_readPixels_after',sentinel=False);self.check_health(after,'read_after')
            sentinel=np.full(normal.shape,165,np.uint8);reserve('readPixels','renderer',self.entry)
            sb=api.note('mjr_readPixels_before',sentinel=True);self.check_health(sb,'sentinel_before')
            old_read(rgb=sentinel,depth=None,viewport=kw['viewport'],con=kw['con']);sa=api.note('mjr_readPixels_after',sentinel=True);self.check_health(sa,'sentinel_after')
            require(self.entry not in self.frames,'unplanned duplicate render/read in frame')
            healthy=all(self.healthy(e) for e in [before,after,sb,sa]);equal=bool(np.array_equal(normal,sentinel))
            self.last_arrays=dict(normal=normal,sentinel=sentinel)
            f=self.out/(self.entry+'_readback.npz') if self.persist_arrays or not (healthy and equal) else None
            if f is not None:save_npz(f,normal=normal,sentinel=sentinel)
            row=dict(entry=self.entry,file=str(f.relative_to(P)) if f is not None else None,sha256=sha(f) if f is not None else None,raw_sha256=hashlib.sha256(normal.tobytes()).hexdigest(),sentinel_sha256=hashlib.sha256(sentinel.tobytes()).hexdigest(),raw_shape=list(normal.shape),raw_dtype=str(normal.dtype),normal_sentinel_equal=equal,GL_health=healthy,readback_healthy=healthy and equal,independent_buffer=not np.shares_memory(kw['rgb'],sentinel),normal_165_fraction=float(np.mean(normal==165)),sentinel_165_fraction=float(np.mean(sentinel==165)),events=[before,after,sb,sa])
            self.frames[self.entry]=row;write(self.out/'readbacks.json',self.frames)
            if self.strict:require(row['readback_healthy'],'STOP_UNHEALTHY_READBACK')
            return r
        bu.mujoco.mjr_readPixels=read_pixels
    def label(self,x):self.entry=x;self.api.entry=x
    def healthy(self,event):
        if self.env is None:return False
        renderer=self.env.sim._render_context_offscreen;owner=self.api.owner(renderer.gl_ctx);ids=self.api.ids(renderer.con);objects=event.get('active_objects') or {}
        return bool(owner and event.get('current_context')==owner and event.get('gl') and event['gl']['errors']['codes']==[0] and objects.get('state')=='MEASURED_IN_OWNER_CONTEXT' and objects.get('ids')==ids and len(objects.get('framebuffers',{}))==3 and len(objects.get('renderbuffers',{}))==4 and all(v['is_framebuffer'] for v in objects['framebuffers'].values()) and all(v['is_renderbuffer'] for v in objects['renderbuffers'].values()))
    def check_health(self,event,where):
        if self.strict:require(self.bu._MjSim_render_lock.locked() and self.healthy(event),'STOP_UNHEALTHY_'+where)
    def frame(self,lib,T,label,save_png=False):
        self.label(label);pixels=lib.render(self.env,T);row=self.frames[label]
        with self.np.load(P/row['file'],allow_pickle=False) as z:require(self.np.array_equal(pixels,self.np.flip(z['normal'],0)),'readback/flip boundary mismatch')
        if save_png:
            from PIL import Image
            Image.fromarray(pixels).save(self.out/(label+'.png'))
        return pixels,row
