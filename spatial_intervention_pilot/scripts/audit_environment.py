"""Read-only workstation audit. Write reports only inside this project."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def protected_manifest():
    files = []
    src = Path('/home/asus/inspection_robot_ws/src')
    if src.exists():
        files.extend(p for p in src.rglob('*') if p.is_file() and '.git' not in p.parts)
    for p in ['/opt/ros/humble/setup.bash', '/usr/local/cuda-11.8/version.json',
              '/usr/local/cuda-11.8/bin/nvcc', '/usr/bin/python3.10',
              '/home/asus/.bashrc', '/home/asus/.profile',
              '/home/asus/anaconda3/conda-meta/history']:
        if Path(p).is_file():
            files.append(Path(p))
    out = {}
    for p in sorted(files):
        out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main():
    logs = ROOT/'reports/logs'
    logs.mkdir(parents=True, exist_ok=True)
    baseline = ROOT/'reports/protected_before.json'
    now_manifest = protected_manifest()
    if not baseline.exists():
        baseline.write_text(json.dumps(now_manifest, indent=2) + '\n')
    else:
        old = json.loads(baseline.read_text())
        changed = sorted(k for k in set(old) | set(now_manifest) if old.get(k) != now_manifest.get(k))
        (ROOT/'reports/protected_comparison.json').write_text(json.dumps({
            'checked_files': len(now_manifest), 'changed_files': changed,
            'scope': 'robot workspace src and selected ROS/CUDA/shell/system/base-conda files; not a full filesystem audit'
        }, indent=2)+'\n')
    commands = [
        ['uname', '-a'], ['cat', '/etc/os-release'], ['nvidia-smi'],
        ['python3', '--version'], ['/usr/bin/python3', '--version'],
        ['/home/asus/anaconda3/bin/conda', '--version'],
        ['df', '-h', '/home/asus'], ['free', '-h'],
        ['/usr/local/cuda-11.8/bin/nvcc', '--version'],
    ]
    results = []
    for cmd in commands:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            results.append({'command': cmd, 'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr})
        except Exception as exc:
            results.append({'command': cmd, 'error': str(exc), 'traceback': traceback.format_exc()})
    cuda = {}
    try:
        lib = ctypes.CDLL('libcuda.so.1')
        cuda['cuInit_returncode'] = lib.cuInit(0)
        count = ctypes.c_int()
        cuda['cuDeviceGetCount_returncode'] = lib.cuDeviceGetCount(ctypes.byref(count))
        cuda['device_count'] = count.value
        version = ctypes.c_int()
        cuda['cuDriverGetVersion_returncode'] = lib.cuDriverGetVersion(ctypes.byref(version))
        cuda['driver_api_version'] = version.value
    except Exception as exc:
        cuda['error'] = str(exc)
        cuda['traceback'] = traceback.format_exc()
    network = []
    for url in ['https://huggingface.co/api/models/Qwen/Qwen3-VL-4B-Instruct', 'https://pypi.org/simple/shapely/']:
        try:
            with urlopen(Request(url, method='HEAD'), timeout=20) as response:
                network.append({'url': url, 'method': 'HEAD', 'status': response.status})
        except Exception as exc:
            network.append({'url': url, 'method': 'HEAD', 'error': str(exc), 'traceback': traceback.format_exc()})
    report = {
        'time': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'audit_python': platform.python_version(),
        'conda_path': shutil.which('conda'),
        'commands': results, 'cuda_driver_api': cuda, 'network': network,
        'protected_file_count': len(now_manifest),
        'note': 'CUDA driver API tested only; no PyTorch/kernel/model inference test. Network HEAD only, no weights.'
    }
    (logs/'environment_raw.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'commands'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
