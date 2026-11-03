"""Natural owner-release integration; no held renderer fixture or forced GC."""
from .common import *
from .gates import reserve
from .owned_release import release_owned, pointer_value
from .telemetry import Telemetry


class InputRuntime:
    def __init__(self, ec, bu, numpy):
        self.ec = ec; self.bu = bu; self.np = numpy
        self.out = P/'results/input'
        self.out.mkdir(exist_ok=False)
        self.api = Telemetry(ec, self.out, 1)
        self.entry = 'INIT'; self.frames = {}; self.sentinel = False
        self.per_sample = {}; self.normal = None
        self.expected_context = None; self.expected_ids = None

    def label(self, label):
        self.entry = label; self.api.entry = label

    def save_array(self, name, array):
        path = self.out/(name+'.npy')
        require(not path.exists(), 'array overwrite/retry')
        value = self.np.array(array, copy=True, order='C')
        self.np.save(path, value, allow_pickle=False)
        return dict(file=str(path.relative_to(P)), sha256=sha(path),
                    content_sha256=hashlib.sha256(value.tobytes()).hexdigest(),
                    shape=list(value.shape), dtype=str(value.dtype))

    def install(self):
        api, ec, bu = self.api, self.ec, self.bu
        old_init = ec.EGLGLContext.__init__
        def gl_init(obj, *args, **kwargs):
            api.note('EGL_constructor_enter')
            result = old_init(obj, *args, **kwargs)
            api.register(obj); api.note('EGL_constructor_exit', actor_context=api.owner(obj))
            return result
        ec.EGLGLContext.__init__ = gl_init
        old_renderer = bu.MjRenderContext.__init__
        def renderer_init(obj, *args, **kwargs):
            result = old_renderer(obj, *args, **kwargs)
            api.register_renderer(obj)  # weak references only, no HELD list
            api.observe('renderer_constructed', obj)
            return result
        bu.MjRenderContext.__init__ = renderer_init
        def destructor(obj):
            try:
                owner = api.owner(getattr(obj, 'gl_ctx', None))
                previous = api.capture()
                api.observe('natural_renderer_release_enter', obj,
                            releasing_owner=owner, previous_context=previous['key'])
                release_owned(obj, api)
                api.note('natural_renderer_release_exit', releasing_owner=owner,
                         previous_context=previous['key'])
            except BaseException as exc:
                api.failure('natural_destructor', type(exc).__name__)
                raise
        bu.MjRenderContext.__del__ = destructor
        for name in ['eglMakeCurrent', 'eglReleaseThread', 'eglDestroyContext']:
            original = getattr(ec.EGL, name)
            def factory(name, original):
                def wrapper(*args, **kwargs):
                    address = pointer_value(args[1]) if name == 'eglDestroyContext' else 0
                    actor = api.address_to_key.get(address)
                    api.note(name+'_enter', actor_context=actor)
                    result = original(*args, **kwargs)
                    if name == 'eglDestroyContext' and bool(result):
                        api.destroyed(address)
                    api.note(name+'_exit', actor_context=actor, returned=bool(result))
                    return result
                return wrapper
            setattr(ec.EGL, name, factory(name, original))
        old_render = bu.mujoco.mjr_render
        def render(*args, **kwargs):
            ordinal = reserve('renders', 'input', self.entry)
            sample = self.entry.split('_')[0]
            self.per_sample[sample] = self.per_sample.get(sample, 0) + 1
            require(self.entry.startswith('s') and self.per_sample[sample] <= 3,
                    'unexpected/implicit render consumed budget')
            before = api.note('mjr_render_before', ordinal=ordinal)
            require(bu._MjSim_render_lock.locked() and self.healthy_event(before),
                    'STOP_UNHEALTHY_RENDER_BEFORE')
            try:
                return old_render(*args, **kwargs)
            finally:
                after = api.note('mjr_render_after', ordinal=ordinal)
                require(bu._MjSim_render_lock.locked() and self.healthy_event(after),
                        'STOP_UNHEALTHY_RENDER_AFTER')
        bu.mujoco.mjr_render = render
        old_read = bu.mujoco.mjr_readPixels
        def read_pixels(*args, **kwargs):
            ordinal = reserve('readPixels', 'input', self.entry)
            require(self.entry.startswith('s') and bu._MjSim_render_lock.locked(),
                    'unexpected/unlocked native readPixels')
            before = api.note('mjr_readPixels_before', ordinal=ordinal, sentinel=self.sentinel)
            require(self.healthy_event(before), 'STOP_UNHEALTHY_READ_BEFORE')
            result = old_read(*args, **kwargs)
            raw = self.np.array(kwargs['rgb'], copy=True)
            meta = self.save_array('read_%02d_%s' % (ordinal, 'sentinel' if self.sentinel else 'raw'), raw)
            after = api.note('mjr_readPixels_after', ordinal=ordinal, sentinel=self.sentinel, array=meta)
            require(self.healthy_event(after), 'STOP_UNHEALTHY_READ_AFTER')
            if not self.sentinel:
                require(self.entry not in self.frames, 'second normal read in one entry')
                require(raw.shape == (256, 256, 3) and raw.dtype == self.np.uint8,
                        'unexpected native RGB buffer')
                sentinel = self.np.full(raw.shape, 165, self.np.uint8)
                self.sentinel = True
                try:
                    bu.mujoco.mjr_readPixels(rgb=sentinel, depth=None,
                                            viewport=kwargs['viewport'], con=kwargs['con'])
                finally:
                    self.sentinel = False
                events = [before, after] + self.last_sentinel
                good = all(self.healthy_event(e) for e in events)
                row = dict(entry=self.entry, normal_ordinal=ordinal, normal=meta,
                           sentinel=self.last_sentinel[-1]['array'], normal_events=[before, after],
                           sentinel_events=self.last_sentinel, original_lock_held=True,
                           independent_buffer=not self.np.shares_memory(sentinel, kwargs['rgb']),
                           equal_preflip_raw=bool(self.np.array_equal(raw, sentinel)),
                           sentinel_165_fraction=float(self.np.mean(sentinel == 165)),
                           raw_165_fraction=float(self.np.mean(raw == 165)),
                           readback_healthy=bool(good and self.np.array_equal(raw, sentinel)))
                self.frames[self.entry] = row
                write(self.out/'readback.json', self.frames)
                require(row['readback_healthy'], 'STOP_UNHEALTHY_READBACK')
            else:
                self.last_sentinel = [before, after]
            return result
        bu.mujoco.mjr_readPixels = read_pixels

    def healthy_event(self, event):
        objects = event.get('active_objects') or {}
        if not (event['current_context'] == self.expected_context and self.expected_context and event['gl']
                and event['gl']['errors']['codes'] == [0]
                and objects.get('state') == 'MEASURED_IN_OWNER_CONTEXT'
                and objects.get('owner_context') == event['current_context']
                and objects.get('ids') == self.expected_ids):
            return False
        return all(len(objects.get(category, {})) == number
                   and all(v[flag] for v in objects[category].values())
                   for category, number, flag in [('framebuffers', 3, 'is_framebuffer'),
                                                   ('renderbuffers', 4, 'is_renderbuffer')])
