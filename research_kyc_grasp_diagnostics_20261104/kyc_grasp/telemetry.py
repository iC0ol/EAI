"""Read-only GL queries, context-generation identities, weak renderer registry."""
from .lc_common import *
from .owned_release import pointer_value
import ctypes,ctypes.util,weakref,threading

FBO_FIELDS=('offFBO','offFBO_r','shadowFBO')
RBO_FIELDS=('offColor','offColor_r','offDepthStencil','offDepthStencil_r')

class Telemetry:
    def __init__(self,ec,out,worker):
        self.ec=ec;self.out=out;self.worker=worker;self.entry='INIT';self.contexts={};self.address_to_key={}
        self.renderers=weakref.WeakValueDictionary();self.fatal=[];self.owner_sequence=0
        self.gl=ctypes.CDLL(ctypes.util.find_library('GL') or 'libGL.so.1')
        specs={'glGetIntegerv':([ctypes.c_uint,ctypes.POINTER(ctypes.c_int)],None),
          'glCheckFramebufferStatus':([ctypes.c_uint],ctypes.c_uint),'glGetError':([],ctypes.c_uint),
          'glIsFramebuffer':([ctypes.c_uint],ctypes.c_ubyte),'glIsRenderbuffer':([ctypes.c_uint],ctypes.c_ubyte),
          'glGetFramebufferAttachmentParameteriv':([ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_int)],None),
          'glGetRenderbufferParameteriv':([ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_int)],None)}
        for name,(args,ret) in specs.items():f=getattr(self.gl,name);f.argtypes=args;f.restype=ret
    def raw_capture(self):
        e=self.ec.EGL
        return {'context':pointer_value(e.eglGetCurrentContext()),'display':pointer_value(e.eglGetCurrentDisplay()),
                'draw':pointer_value(e.eglGetCurrentSurface(0x3059)),'read':pointer_value(e.eglGetCurrentSurface(0x305A))}
    def capture(self):
        v=self.raw_capture();v['key']=self.address_to_key.get(v['context']) if v['context'] else None
        return v
    def register(self,glctx):
        address=pointer_value(getattr(glctx,'_context',None))
        if not address:return
        self.owner_sequence+=1;key=f'w{self.worker}_ctx{self.owner_sequence}'
        self.contexts[key]={'address':address,'alive':True};self.address_to_key[address]=key
        write(P/f'local_only/w{self.worker}_context_map.json',self.contexts)
        self.note('context_registered',context=key)
    def owner(self,glctx):
        address=pointer_value(getattr(glctx,'_context',None)) if glctx is not None else 0
        return self.address_to_key.get(address) if address else None
    def live(self,key):return bool(key in self.contexts and self.contexts[key]['alive'])
    def destroyed(self,address):
        key=self.address_to_key.get(address)
        if key:self.contexts[key]['alive']=False
    def ids(self,con):
        return {name:int(getattr(con,name)) for name in FBO_FIELDS+RBO_FIELDS if con is not None and hasattr(con,name)}
    def register_renderer(self,renderer):
        key=self.owner(getattr(renderer,'gl_ctx',None))
        if key:self.renderers[key]=renderer
    def integer(self,name):
        out=ctypes.c_int();self.gl.glGetIntegerv(name,ctypes.byref(out));return int(out.value)
    def errors(self):
        if not pointer_value(self.ec.EGL.eglGetCurrentContext()):return {'codes':None,'drained':False,'state':'NO_CURRENT_CONTEXT'}
        codes=[]
        for _ in range(8):
            e=int(self.gl.glGetError());codes.append(e)
            if e==0:return {'codes':codes,'drained':True}
        return {'codes':codes,'drained':False,'state':'GL_ERROR_NOT_DRAINED'}
    def attachment(self,target,attachment,pname):
        v=ctypes.c_int();self.gl.glGetFramebufferAttachmentParameteriv(target,attachment,pname,ctypes.byref(v));return int(v.value)
    def bound_fbo(self,target,binding):
        if binding==0:return {'object_id':0,'state':'DEFAULT_FBO_NOT_ASSIGNED_TO_OFFSCREEN_OBJECT'}
        result={'object_id':binding,'status':int(self.gl.glCheckFramebufferStatus(target)),'attachments':{}}
        for name,a in [('color0',0x8CE0),('depth',0x8D00),('stencil',0x8D20)]:
            kind=self.attachment(target,a,0x8CD0)
            result['attachments'][name]={'type':kind,'object_id':self.attachment(target,a,0x8CD1) if kind else 0}
        return result
    def resources(self,key,ids,current,bindings):
        actual=self.capture()['key']
        if key is None or key!=current or key!=actual:
            return {'owner_context':key,'state':'NOT_MEASURED_WRONG_CONTEXT','ids':ids}
        if not self.live(key):return {'owner_context':key,'state':'NOT_MEASURED_OWNER_DESTROYED','ids':ids}
        fbo={n:{'id':v,'is_framebuffer':bool(self.gl.glIsFramebuffer(v))} for n,v in ids.items() if n in FBO_FIELDS and v}
        rbo={n:{'id':v,'is_renderbuffer':bool(self.gl.glIsRenderbuffer(v))} for n,v in ids.items() if n in RBO_FIELDS and v}
        for n,item in rbo.items():
            if item['id']==bindings['renderbuffer']:
                dimensions={}
                for label,code in [('width',0x8D42),('height',0x8D43),('samples',0x8CAB)]:
                    value=ctypes.c_int();self.gl.glGetRenderbufferParameteriv(0x8D41,code,ctypes.byref(value));dimensions[label]=int(value.value)
                item['bound_dimensions']=dimensions
            else:item['dimensions']='NOT_MEASURED_NOT_BOUND'
        if self.capture()['key']!=key:return {'owner_context':key,'state':'NOT_MEASURED_CONTEXT_CHANGED','ids':ids}
        return {'owner_context':key,'state':'MEASURED_IN_OWNER_CONTEXT','framebuffers':fbo,'renderbuffers':rbo,'ids':ids}
    def observe(self,label,renderer=None,ids=None,**extra):
        current=self.capture();key=current['key'];owner=self.owner(getattr(renderer,'gl_ctx',None)) if renderer is not None else None
        ownerids=self.ids(getattr(renderer,'con',None)) if ids is None and renderer is not None else (ids or {})
        record={'utc':utc(),'monotonic':time.monotonic(),'thread_id':threading.get_ident(),'event':label,'entry':self.entry,
          'worker':self.worker,'current_context':key,'current_present':bool(current['context']),'owner_context':owner,**extra}
        if not current['context']:
            record.update(gl=None,owner_objects={'state':'NOT_MEASURED_WRONG_CONTEXT','owner_context':owner,'ids':ownerids},active_objects=None)
        else:
            bindings={'draw':self.integer(0x8CA6),'read':self.integer(0x8CAA),'renderbuffer':self.integer(0x8CA7)}
            draw=self.bound_fbo(0x8CA9,bindings['draw']);readback=self.bound_fbo(0x8CA8,bindings['read'])
            ownerobjects=self.resources(owner,ownerids,key,bindings)
            active=self.renderers.get(key) if key is not None else None
            activeids=self.ids(getattr(active,'con',None)) if active is not None else {}
            activeobjects=self.resources(key,activeids,key,bindings) if active is not None else {'state':'NO_ACTIVE_RENDERER_IDENTITY'}
            del active
            record.update(gl={'bindings':bindings,'draw_bound_object':draw,'read_bound_object':readback,'errors':self.errors()},
                          owner_objects=ownerobjects,active_objects=activeobjects)
            if self.capture()['key']!=key:
                record.update(measurement_window='CONTEXT_CHANGED_DISCARD_OBJECT_VALUES',
                   owner_objects={'state':'NOT_MEASURED_CONTEXT_CHANGED','owner_context':owner,'ids':ownerids},
                   active_objects={'state':'NOT_MEASURED_CONTEXT_CHANGED'})
        append(self.out/'events.jsonl',record)
        return record
    def note(self,label,**extra):return self.observe(label,**extra)
    def failure(self,label,error_type):
        item={'utc':utc(),'label':label,'error_type':error_type,'entry':self.entry};self.fatal.append(item)
        write(self.out/'fatal.json',self.fatal)
    def bind_owner(self,glctx):
        glctx.make_current()
        key=self.owner(glctx)
        if key is None or self.capture()['key']!=key:raise RuntimeError('owner make_current failed')
    def restore(self,previous):
        if not self.live(previous['key']):raise RuntimeError('previous identity no longer live')
        e=self.ec.EGL
        def handle(name,value):return ctypes.cast(ctypes.c_void_p(value),getattr(e,name))
        ok=e.eglMakeCurrent(handle('EGLDisplay',previous['display']),handle('EGLSurface',previous['draw']),
           handle('EGLSurface',previous['read']),handle('EGLContext',previous['context']))
        self.note('restore_native_return',returned=bool(ok),previous_context=previous['key'])
        if not ok or self.capture()['key']!=previous['key']:raise RuntimeError('previous restore failed')
    def check(self):
        if self.fatal:raise RuntimeError('visible lifecycle error; stop worker')
