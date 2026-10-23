"""Seal all deliverable files, excluding this manifest itself and Git-ignored assets."""
import subprocess

from live_screen.io import ROOT,OUT,BASE,sha256,write_json,read_json,git,now


repo=ROOT.parent.parent
paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard','--','m_direction_pilot/live_screen'],cwd=repo).decode().split('\0')
paths=sorted(set(p for p in paths if p and p!='m_direction_pilot/live_screen/outputs/sha256_manifest.json'))
assert all('/local/' not in p and '/.cache/' not in p and not p.endswith(('.npz','.pt','.hdf5','.pyc')) for p in paths)
assert read_json(OUT/'final_audit.json')['passed']
assert all(p.startswith('m_direction_pilot/live_screen/') for p in git('diff','--name-only',BASE).splitlines())
manifest={'utc':now(),'protocol_commit':read_json(OUT/'registration.json')['protocol_commit'],
          'execution_commits':sorted({read_json(p)['execution_commit'] for p in (OUT/'branches').glob('*.json')}),
          'exclude':'this SHA manifest itself; ignored local NPZ/runtimes/weights/raw dataset/caches',
          'files':{p:{'sha256':sha256(repo/p),'bytes':(repo/p).stat().st_size} for p in paths}}
write_json(OUT/'sha256_manifest.json',manifest)
for p,spec in manifest['files'].items():assert sha256(repo/p)==spec['sha256']
print(f"Sealed {len(paths)} files; {sum(v['bytes'] for v in manifest['files'].values())} bytes")
