"""Real CPU import audit; blocks device and env/model construction attempts."""
from .common import *
import importlib.abc
import sys


class CPUDeviceAttempt(RuntimeError):
    pass


class CPUAudit:
    def __init__(self):
        self.events = []; self.blocked = []; self.cuda_before = None

    def stop(self, name):
        record = dict(utc=utc(), operation=name)
        self.blocked.append(record); write(P/'cpu_preflight/device_attempt.json', self.blocked)
        raise CPUDeviceAttempt(name)

    def install_before_torch(self):
        audit = self
        class NoGLImports(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in ['robosuite', 'mujoco', 'OpenGL', 'glfw']:
                    audit.stop('CPU_DEFERRED_GL_IMPORT:'+fullname)
        sys.meta_path.insert(0, NoGLImports())

    def install_torch(self, torch):
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU process must have no visible GPU')
        self.cuda_before = torch.cuda.is_initialized()
        require(not self.cuda_before, 'CUDA initialized before real loader')
        for obj, name in [(torch.cuda, '_lazy_init'), (torch.cuda, 'init'),
                          (torch._C, '_cuda_init'), (torch.Tensor, 'cuda'), (torch.nn.Module, 'cuda')]:
            setattr(obj, name, lambda *a, _name=name, **kw: self.stop('CUDA_INIT_OR_TRANSFER:'+_name))
        original_available = torch.cuda.is_available
        def available():
            result = original_available()
            self.events.append(dict(operation='cuda.is_available', result=bool(result),
                                    initialized=torch.cuda.is_initialized()))
            if result or torch.cuda.is_initialized():
                self.stop('unexpected CUDA availability/initialization in CPU probe')
            return result
        torch.cuda.is_available = available
        def profile(frame, event, arg):
            if event == 'call':
                file = Path(frame.f_code.co_filename)
                if (file == K/'models/act.py' and frame.f_code.co_name == '__init__') or (
                    file == R/'scripts/experiment_lib.py' and frame.f_code.co_name == 'make_env'):
                    self.stop('FORBIDDEN_CONSTRUCTION:'+str(file)+':'+frame.f_code.co_name)
        sys.setprofile(profile)

    def finish(self, torch):
        sys.setprofile(None)
        return dict(blocked=self.blocked, safe_queries=self.events,
                    CUDA_initialized_before=self.cuda_before,
                    CUDA_initialized_after=torch.cuda.is_initialized(),
                    GL_modules_imported=[n for n in sys.modules if n.split('.')[0] in
                                         ['robosuite','mujoco','OpenGL','glfw']],
                    ACT_constructed=False, device_constructor_attempts=len(self.blocked))
