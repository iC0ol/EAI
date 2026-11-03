"""Installed only inside an authorized worker; no framework imports here."""
from .common import *
import socket
import sys


def forbidden(*args, **kwargs):
    raise RuntimeError('forbidden training/download/rollout operation')


def isolation():
    original = socket.socket.connect
    def connect(self, address):
        if self.family in [socket.AF_INET, socket.AF_INET6]:
            raise RuntimeError('network prohibited in frozen diagnostic')
        return original(self, address)
    socket.socket.connect = connect
    socket.create_connection = forbidden
    def write_path(path):
        if isinstance(path, int) or path is None:
            return
        require(Path(os.fsdecode(path)).resolve().is_relative_to(P),
                'write outside new diagnostic scope')
    def audit(event, args):
        if event == 'open':
            path, mode, flags = args
            if (mode and any(x in mode for x in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                write_path(path)
        elif event in ['os.remove', 'os.rmdir', 'os.mkdir']:
            write_path(args[0])
        elif event in ['os.rename', 'os.link', 'os.symlink']:
            write_path(args[0]); write_path(args[1])
    sys.addaudithook(audit)


def torch_guards(torch):
    # The shared actual loader imports experiment_lib, which owns thread setup.
    torch.set_grad_enabled(False)
    torch.Tensor.backward = forbidden
    torch.autograd.backward = forbidden
    torch.autograd.grad = forbidden
    torch.hub.download_url_to_file = forbidden
    torch.hub.load = forbidden


def cached_backbone_only(torch):
    path = R/'cache/torch/hub/checkpoints/resnet18-f37072fd.pth'
    expected = read(P/'candidate_manifest.json')['sources'][str(path)]
    def load(url, *args, **kwargs):
        require(url == 'https://download.pytorch.org/models/resnet18-f37072fd.pth'
                and sha(path) == expected, 'unapproved/missing cached pretrained resource')
        append(P/'model_events.jsonl', dict(utc=utc(), event='READ_CACHED_PRETRAINED',
                path=str(path), sha256=expected, network=False))
        return torch.load(path, map_location='cpu', weights_only=True)
    torch.hub.load_state_dict_from_url = load
    return load
