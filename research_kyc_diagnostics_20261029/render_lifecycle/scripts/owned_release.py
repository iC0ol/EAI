"""Pure-Python, mockable owner-context release transaction. No GL imports."""
import ctypes

FIELDS=('con','gl_ctx','scn','cam','vopt','pert')

def pointer_value(value):
    if value is None or not bool(value):return 0
    if isinstance(value,int):return value
    try:return int(ctypes.cast(value,ctypes.c_void_p).value or 0)
    except (TypeError,ValueError,ctypes.ArgumentError):
        try:return int(value.address or 0)
        except (AttributeError,ValueError):return 0

def release_owned(renderer,api):
    state=getattr(renderer,'_owned_release_state','NEW')
    if state in ('DONE','RUNNING'):
        api.note('release_skip_'+state);return
    if state=='ERROR':
        api.note('release_skip_previous_error');return
    renderer._owned_release_state='RUNNING'
    con=getattr(renderer,'con',None);gl=getattr(renderer,'gl_ctx',None)
    previous=api.capture();owner=api.owner(gl);ids=api.ids(con)
    error=None
    try:
        if con is not None and (owner is None or not api.live(owner)):
            raise RuntimeError('owner missing/dead while con still needs release')
        if gl is not None and owner is not None:
            if not api.live(owner):raise RuntimeError('owner not live')
            if previous['key'] is not None and previous['key']!=owner and not api.live(previous['key']):
                raise RuntimeError('previous context identity/liveness unknown')
            api.bind_owner(gl)
            if api.capture()['key']!=owner:raise RuntimeError('owner bind verification failed')
            api.observe('owner_bound_before_con_free',renderer,ids)
            if con is not None:con.free()
            api.observe('owner_bound_after_con_free',renderer,ids)
            gl.free()
            if api.live(owner):raise RuntimeError('owner destruction not confirmed')
            api.observe('after_owner_egl_free',renderer,ids)
        elif con is not None:
            raise RuntimeError('con ownership unknown')
    except BaseException as exc:
        error=exc
        api.failure('owned_release',type(exc).__name__)
    finally:
        try:
            key=previous['key']
            if key is not None and key!=owner:
                if not api.live(key):raise RuntimeError('previous no longer live; cannot restore')
                api.restore(previous)
                if api.capture()['key']!=key:raise RuntimeError('restore verification failed')
                api.observe('previous_restored',None,None)
            elif previous['key'] is None or previous['key']==owner:
                if error is None and api.capture()['key'] is not None:
                    raise RuntimeError('destroyed owner/null previous must not be rebound')
        except BaseException as exc:
            api.failure('restore_previous',type(exc).__name__)
            if error is None:error=exc
    if error is not None:
        renderer._owned_release_state='ERROR'
        raise error
    for field in FIELDS:
        if hasattr(renderer,field):delattr(renderer,field)
    renderer._owned_release_state='DONE'
    api.note('owned_release_DONE')
