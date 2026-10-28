from common import ROOT,atomic_json,utc,sha
from experiment_lib import *
from PIL import Image
def main():
    e=make_env(42)
    with h5py.File(DATA) as f:s=f['data/demo_0/states'][0]
    e.sim.set_state_from_flattened(s);e.sim.forward()
    T=np.array(json.loads((ROOT/'vendor/kyc/policy_robosuite/camera_poses/train_cameras.json').read_text())['poses'][0]);original=e.model.get_xml();compiled=e.sim.model.get_xml()
    out=ROOT/'results/restore_diagnosis';out.mkdir(exist_ok=True)
    rgb=render(e,T);Image.fromarray(rgb).save(out/'before.png');details={}
    for name,xml in [('compiled',compiled),('original',original)]:
        e.reset_from_xml_string(xml);e.sim.set_state_from_flattened(s);e.sim.forward();im=render(e,T);Image.fromarray(im).save(out/(name+'.png'))
        diff=np.abs(rgb.astype(float)-im.astype(float));details[name]={'max_abs':float(diff.max()),'mae':float(diff.mean()),'fraction_changed':float(np.mean(np.any(diff>0,axis=-1))),'fraction_changed_gt10':float(np.mean(np.any(diff>10,axis=-1)))}
        (out/(name+'.xml')).write_text(xml)
    atomic_json(out/'diagnosis.json',{'utc':utc(),'comparisons':details,'zero_actions_executed':True});print(details,flush=True);e.close()
if __name__=='__main__':main()
