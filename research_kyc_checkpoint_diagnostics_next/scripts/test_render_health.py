"""CPU-only regression for pre/post native GL health gates; no GL imports executed."""
import copy
import datetime
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import input_runtime as module


def probe(fault=None, kind='render'):
    calls = []
    ids = {str(i): i for i in range(1, 8)}
    healthy = {'current_context': 'ctx', 'gl': {'errors': {'codes': [0]}},
        'active_objects': {'state': 'MEASURED_IN_OWNER_CONTEXT', 'owner_context': 'ctx',
            'ids': ids, 'framebuffers': {str(i): {'is_framebuffer': True} for i in range(3)},
            'renderbuffers': {str(i): {'is_renderbuffer': True} for i in range(4)}}}
    class API:
        def note(self, event, **kw):
            value = copy.deepcopy(healthy)
            if event == fault:
                value['gl']['errors']['codes'] = [1286, 0]
            return value
    class Context:
        def __init__(self, *a, **kw): pass
    class Renderer:
        def __init__(self, *a, **kw): pass
    def native(*a, **kw): calls.append(kind)
    ec = SimpleNamespace(EGLGLContext=Context, EGL=SimpleNamespace(**{
        k: (lambda *a, **kw: True) for k in ['eglMakeCurrent','eglReleaseThread','eglDestroyContext']}))
    lock = threading.Lock(); lock.acquire()
    bu = SimpleNamespace(MjRenderContext=Renderer, _MjSim_render_lock=lock,
        mujoco=SimpleNamespace(mjr_render=native, mjr_readPixels=native))
    r = module.InputRuntime.__new__(module.InputRuntime)
    r.api=API(); r.ec=ec; r.bu=bu; r.np=np; r.entry='s00_dataset'; r.per_sample={}
    r.sentinel=False; r.frames={}; r.expected_context='ctx'; r.expected_ids=ids
    r.save_array=lambda *a: {'file':'MOCK_ARRAY'}
    error=None
    try:
        with patch.object(module, 'reserve', return_value=1):
            r.install()
            if kind=='render': bu.mujoco.mjr_render()
            else: bu.mujoco.mjr_readPixels(rgb=np.zeros((256,256,3),np.uint8),depth=None,viewport=None,con=None)
    except RuntimeError as exc: error=str(exc)
    finally: lock.release()
    return error, len(calls)


if __name__=='__main__':
    cases=[(None,'render',None,1),
           ('mjr_render_before','render','STOP_UNHEALTHY_RENDER_BEFORE',0),
           ('mjr_render_after','render','STOP_UNHEALTHY_RENDER_AFTER',1),
           ('mjr_readPixels_before','read','STOP_UNHEALTHY_READ_BEFORE',0),
           ('mjr_readPixels_after','read','STOP_UNHEALTHY_READ_AFTER',1)]
    for fault,kind,error,count in cases:
        assert probe(fault,kind)==(error,count), (fault,kind)
    result={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'tests':len(cases),'passed':True,'new_GL_model_observations':0,
            'scope':'CPU fake native functions and telemetry only; no real context/model'}
    p=Path(__file__).resolve().parents[1]
    (p/'artifacts/parent_render_gate_regression_v2.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
