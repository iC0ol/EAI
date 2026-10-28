import subprocess,sys,pathlib,os
from common import ROOT,own_env,atomic_json,utc,sha
def main():
    py=str(ROOT/'env/bin/python');env=own_env()
    constraints=ROOT/'manifests/constraints.txt'
    constraints.write_text('numpy==1.26.4\ntorch==2.6.0+cu124\ntorchvision==0.21.0+cu124\nscipy==1.14.1\nh5py==3.12.1\nmujoco==3.3.0\nnumba==0.61.2\nopencv-python==4.11.0.86\n')
    cmd=[py,'-m','pip','install','--retries','2','--timeout','60','-c',str(constraints),'mujoco==3.3.0','numba==0.61.2','opencv-python==4.11.0.86','mink','qpsolvers[quadprog]','pynput','termcolor','pytest','imageio','imageio-ffmpeg','PyOpenGL','glfw','pyyaml']
    subprocess.run(cmd,check=True,env=env)
    # Use exact extracted fixed source, avoiding a build or pip metadata rewrite of that source.
    site=ROOT/'env/lib/python3.11/site-packages'
    (site/'kyc_reproduction_source.pth').write_text(str(ROOT/'vendor/robosuite')+'\n')
    frozen=subprocess.check_output([py,'-m','pip','freeze'],text=True,env=env)
    (ROOT/'requirements.freeze').write_text(frozen)
    atomic_json(ROOT/'dependency_install.json',{'utc':utc(),'command':cmd,'freeze_sha256':sha(ROOT/'requirements.freeze'),'robosuite_import_source':str(ROOT/'vendor/robosuite'),'optional_DP_SmolVLA':'not imported; experiment imports official ACT directly'})
if __name__=='__main__':main()
