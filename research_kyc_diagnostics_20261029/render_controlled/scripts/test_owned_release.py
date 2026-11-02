"""CPU-only behavioral mocks; no torch, simulator, EGL or GL imports."""
from pathlib import Path
from types import SimpleNamespace
import json,ctypes,unittest
from owned_release import release_owned,pointer_value,FIELDS,one_shot_release

class NullOpaque:
    def __bool__(self):return False
    @property
    def address(self):raise ValueError('NULL pointer access')

class API:
    def __init__(self,current='other',bind_fail=False,restore_fail=False,con_fail=False,egl_fail=False,kill_previous=False):
        self.current=current;self.alive={'owner':True,'other':True};self.resources={'owner':{1,2},'other':{1,2}}
        self.bind_fail=bind_fail;self.restore_fail=restore_fail;self.con_fail=con_fail;self.egl_fail=egl_fail;self.kill_previous=kill_previous
        self.log=[];self.failures=[];self.con_calls=0;self.gl_calls=0
    def capture(self):return {'key':self.current,'context':{'owner':101,'other':102,None:0}.get(self.current,103),'display':11,'draw':12,'read':13}
    def owner(self,gl):return gl.key if gl is not None else None
    def live(self,key):return self.alive.get(key,False)
    def ids(self,con):return {'offFBO':1,'offFBO_r':2} if con is not None else {}
    def bind_owner(self,gl):
        if self.bind_fail:raise RuntimeError('bind failure')
        self.current=gl.key;self.log.append('bind_owner')
    def observe(self,label,renderer,ids):self.log.append(label)
    def restore(self,s):
        self.log.append('restore')
        if self.restore_fail:raise RuntimeError('restore failure')
        assert s['display']==11 and s['draw']==12 and s['read']==13
        self.current=s['key']
    def note(self,label,**kw):self.log.append(label)
    def failure(self,*value):self.failures.append(value)
    def con_free(self):
        self.con_calls+=1
        assert self.current=='owner', 'must free resources in their owner context'
        if self.con_fail:raise RuntimeError('con failure')
        self.resources[self.current].clear()
    def gl_free(self):
        self.gl_calls+=1
        if self.egl_fail:raise RuntimeError('egl failure')
        self.alive['owner']=False;self.current=None
        if self.kill_previous:self.alive['other']=False

def renderer(api,with_con=True,with_owner=True):
    r=SimpleNamespace()
    if with_con:r.con=SimpleNamespace(free=api.con_free)
    if with_owner:r.gl_ctx=SimpleNamespace(key='owner',free=api.gl_free)
    for f in ['scn','cam','vopt','pert']:setattr(r,f,object())
    return r

class Tests(unittest.TestCase):
    def test_null_pointer(self):
        for x in [None,NullOpaque(),ctypes.c_void_p(),0]:self.assertEqual(pointer_value(x),0)
    def test_normal_pointer(self):self.assertEqual(pointer_value(ctypes.c_void_p(1234)),1234)
    def test_other_live_preserved(self):
        a=API();r=renderer(a);release_owned(r,a)
        self.assertEqual(a.current,'other');self.assertEqual(a.resources['other'],{1,2});self.assertEqual(a.resources['owner'],set())
        self.assertEqual((a.con_calls,a.gl_calls),(1,1));self.assertTrue(all(not hasattr(r,f) for f in FIELDS))
    def test_previous_owner_not_restored(self):
        a=API('owner');release_owned(renderer(a),a);self.assertIsNone(a.current);self.assertNotIn('restore',a.log)
    def test_previous_null_not_restored(self):
        a=API(None);release_owned(renderer(a),a);self.assertIsNone(a.current);self.assertNotIn('restore',a.log)
    def test_duplicate_and_reentrant(self):
        a=API();r=renderer(a);r._owned_release_state='RUNNING';release_owned(r,a);self.assertEqual(a.con_calls,0)
        r._owned_release_state='NEW';release_owned(r,a);release_owned(r,a);self.assertEqual((a.con_calls,a.gl_calls),(1,1))
    def test_partial_empty(self):
        a=API();r=renderer(a,False,False);release_owned(r,a);self.assertEqual((a.con_calls,a.gl_calls),(0,0));self.assertEqual(a.current,'other')
    def test_partial_only_gl(self):
        a=API();release_owned(renderer(a,False,True),a);self.assertEqual((a.con_calls,a.gl_calls),(0,1));self.assertEqual(a.current,'other')
    def test_missing_owner_stops_before_free(self):
        a=API();r=renderer(a,True,False)
        with self.assertRaises(RuntimeError):release_owned(r,a)
        self.assertEqual(a.con_calls,0);self.assertTrue(a.failures)
    def test_dead_owner_stops(self):
        a=API();a.alive['owner']=False
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertEqual(a.con_calls,0)
    def test_unknown_previous_stops(self):
        a=API('unknown')
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertEqual(a.con_calls,0)
    def test_bind_failure_visible(self):
        a=API(bind_fail=True)
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertEqual(a.con_calls,0);self.assertTrue(a.failures)
    def test_con_exception_restores_previous(self):
        a=API(con_fail=True);r=renderer(a)
        with self.assertRaises(RuntimeError):release_owned(r,a)
        self.assertEqual(a.current,'other');self.assertTrue(a.alive['owner']);self.assertEqual(r._owned_release_state,'ERROR')
        release_owned(r,a);self.assertEqual(a.con_calls,1)
    def test_egl_failure_visible(self):
        a=API(egl_fail=True)
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertEqual(a.current,'other');self.assertTrue(a.failures)
    def test_restore_failure_visible(self):
        a=API(restore_fail=True);r=renderer(a)
        with self.assertRaises(RuntimeError):release_owned(r,a)
        self.assertFalse(a.alive['owner']);self.assertEqual(r._owned_release_state,'ERROR');self.assertTrue(a.failures)
    def test_destroyed_previous_not_rebound(self):
        a=API(kill_previous=True)
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertNotIn('restore',a.log)
    def test_telemetry_owner_mismatch_makes_no_gl_queries(self):
        from telemetry import Telemetry
        t=Telemetry.__new__(Telemetry);t.capture=lambda:{'key':'active'}
        t.gl=SimpleNamespace()  # any accidental GL query would fail this mock
        result=t.resources('old',{'offFBO':1},'active',{})
        self.assertEqual(result['state'],'NOT_MEASURED_WRONG_CONTEXT')
    def test_telemetry_stale_current_is_rechecked(self):
        from telemetry import Telemetry
        t=Telemetry.__new__(Telemetry);t.capture=lambda:{'key':'changed'};t.gl=SimpleNamespace()
        result=t.resources('old',{'offFBO':1},'old',{})
        self.assertEqual(result['state'],'NOT_MEASURED_WRONG_CONTEXT')
    def test_real_adapter_restores_display_surfaces_and_context(self):
        from telemetry import Telemetry
        t=Telemetry.__new__(Telemetry);t.live=lambda key:key=='other';seen={}
        def restore(display,draw,read,context):
            seen.update(display=pointer_value(display),draw=pointer_value(draw),read=pointer_value(read),context=pointer_value(context));return True
        handle=ctypes.POINTER(ctypes.c_int)
        t.ec=SimpleNamespace(EGL=SimpleNamespace(EGLDisplay=handle,EGLSurface=handle,EGLContext=handle,eglMakeCurrent=restore))
        t.note=lambda *a,**k:None;t.capture=lambda:{'key':'other'}
        t.restore({'key':'other','display':11,'draw':12,'read':13,'context':14})
        self.assertEqual(seen,{'display':11,'draw':12,'read':13,'context':14})
    def test_real_adapter_false_restore_is_not_success(self):
        from telemetry import Telemetry
        t=Telemetry.__new__(Telemetry);t.live=lambda key:True;handle=ctypes.POINTER(ctypes.c_int)
        t.ec=SimpleNamespace(EGL=SimpleNamespace(EGLDisplay=handle,EGLSurface=handle,EGLContext=handle,eglMakeCurrent=lambda *a:False))
        t.note=lambda *a,**k:None;t.capture=lambda:{'key':None}
        with self.assertRaises(RuntimeError):t.restore({'key':'other','display':11,'draw':0,'read':0,'context':14})
    def test_nonzero_context_key_none_rejected_before_actions(self):
        a=API();a.capture=lambda:{'context':999,'key':None,'display':11,'draw':0,'read':0};r=renderer(a)
        with self.assertRaises(RuntimeError):release_owned(r,a)
        self.assertEqual((a.con_calls,a.gl_calls),(0,0));self.assertNotIn('bind_owner',a.log);self.assertNotIn('restore',a.log);self.assertTrue(a.failures)
    def test_actual_telemetry_capture_unregistered_context(self):
        from telemetry import Telemetry
        t=Telemetry.__new__(Telemetry);t.address_to_key={}
        t.raw_capture=lambda:{'context':999,'display':11,'draw':0,'read':0}
        a=API();a.capture=t.capture
        self.assertEqual(a.capture()['context'],999);self.assertIsNone(a.capture()['key'])
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertEqual((a.con_calls,a.gl_calls),(0,0));self.assertNotIn('bind_owner',a.log);self.assertNotIn('restore',a.log);self.assertTrue(a.failures)
    def test_null_context_with_nonnull_key_rejected(self):
        a=API();a.capture=lambda:{'context':0,'key':'other'}
        with self.assertRaises(RuntimeError):release_owned(renderer(a),a)
        self.assertEqual((a.con_calls,a.gl_calls),(0,0));self.assertNotIn('bind_owner',a.log)
    def test_capture_preparation_exception_visible(self):
        a=API()
        def bad():raise ValueError('capture failure')
        a.capture=bad;r=renderer(a)
        with self.assertRaises(ValueError):release_owned(r,a)
        self.assertEqual(r._owned_release_state,'ERROR');self.assertTrue(a.failures);self.assertEqual((a.con_calls,a.gl_calls),(0,0));self.assertNotIn('bind_owner',a.log)
    def test_owner_preparation_exception_visible(self):
        a=API()
        def bad(gl):raise ValueError('owner failure')
        a.owner=bad
        with self.assertRaises(ValueError):release_owned(renderer(a),a)
        self.assertTrue(a.failures);self.assertNotIn('bind_owner',a.log);self.assertNotIn('restore',a.log)
    def test_ids_preparation_exception_visible(self):
        a=API()
        def bad(con):raise ValueError('ids failure')
        a.ids=bad
        with self.assertRaises(ValueError):release_owned(renderer(a),a)
        self.assertTrue(a.failures);self.assertEqual((a.con_calls,a.gl_calls),(0,0));self.assertNotIn('bind_owner',a.log)
    def test_common_one_shot_first_and_duplicate(self):
        a=API();r=renderer(a);calls=[]
        self.assertTrue(one_shot_release(r,lambda obj:calls.append('first'),a))
        self.assertFalse(one_shot_release(r,lambda obj:calls.append('duplicate'),a));self.assertEqual(calls,['first'])
    def test_common_one_shot_reentrant(self):
        a=API();r=renderer(a);calls=[]
        def action(obj):
            calls.append('first');self.assertFalse(one_shot_release(obj,lambda o:calls.append('wrong'),a))
        self.assertTrue(one_shot_release(r,action,a));self.assertEqual(calls,['first'])
    def test_common_one_shot_failure_cannot_be_retried(self):
        a=API();r=renderer(a);calls=[]
        def bad(obj):calls.append('first');raise RuntimeError('fail')
        with self.assertRaises(RuntimeError):one_shot_release(r,bad,a)
        with self.assertRaises(RuntimeError):one_shot_release(r,lambda obj:calls.append('retry'),a)
        self.assertEqual(calls,['first']);self.assertTrue(a.failures)
    def test_common_one_shot_front_logging_exception_visible(self):
        a=API();r=renderer(a);calls=[]
        def bad(*args,**kw):raise ValueError('front capture/log failure')
        a.note=bad
        with self.assertRaises(ValueError):one_shot_release(r,lambda obj:calls.append('must not execute'),a)
        self.assertEqual(calls,[]);self.assertTrue(a.failures);self.assertEqual(r._controlled_release_state,'ERROR')

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=1).run(suite)
    p=Path(__file__).resolve().parents[1]
    (p/'cpu_mock.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'passed':result.wasSuccessful(),'GL_contexts_created':0,'envs_created':0,'CUDA_initialized':False,
      'scope':'pure CPU lifecycle/error semantics; not evidence of actual GL repair'},indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
