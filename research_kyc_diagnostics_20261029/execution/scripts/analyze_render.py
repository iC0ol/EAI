"""Saved-array analysis only. No renderer, environment, CUDA or model imports."""
from diag_common import *
import numpy as np
from PIL import Image

def main():
    rows=[]
    for j in range(8):
        with np.load(E/f'inputs/sample_{j:02d}.npz') as z:
            images=[z['rgb_uint8']]+[np.rint(z[k][0,0,:3].transpose(1,2,0)*255).astype(np.uint8) for k in ['eval_image','custom_image']]
            pairs={}
            for k,l in [(0,1),(0,2),(1,2)]:
                delta=abs(images[k].astype(np.float64)-images[l].astype(np.float64))
                flip=abs(images[k].astype(np.float64)-np.flipud(images[l]).astype(np.float64))
                pairs[f'{k}_vs_{l}']={'different_pixels':int(np.any(delta>0,axis=2).sum()),
                    'pixel_count':256*256,'meanabs_uint8':float(delta.mean()),'maxabs_uint8':float(delta.max()),
                    'medianabs_uint8':float(np.median(delta)),'flipud_meanabs_uint8':float(flip.mean()),
                    'a_rgb_sha256':hashlib.sha256(images[k].tobytes()).hexdigest(),
                    'b_rgb_sha256':hashlib.sha256(images[l].tobytes()).hexdigest()}
            rows.append({'sample':j,'order':['Dataset/id','official Evaluator helper','custom helper'],
                         'pairs':pairs,'visible_scene_integrity':'FAILED_ON_VISUAL_INSPECTION' if j in [0,4] else 'NOT_VISUALLY_INSPECTED; RGB_DISAGREEMENT_RECORDED',
                         'source_npz_sha256':sha(E/f'inputs/sample_{j:02d}.npz')})
            if j in [0,4]:Image.fromarray(np.concatenate(images,axis=1)).save(E/f'results/sample_{j:02d}_entry_rgb.png')
    result={'utc':utc(),'analysis_scope':'saved arrays only; no new render/model/simulation',
            'state':'CURRENT_RENDER_PREREQUISITE_FAILED','rows':rows,
            'visual_observation':'severe high-frequency colored pixel patterns instead of a recognizable Lift scene in inspected triptychs; raw arrays preserved',
            'entry_numerical_test_limitation':'fresh renders did not satisfy common-raw-image prerequisite; these differences do not isolate preprocessing. No matched-common-RGB policy comparison was run.',
            'historical_boundary':'old saved expert/dev PNGs visually recognizable; no historic training batch RGB/framebuffer logs. Present corruption does not establish historic training corruption.',
            'root_cause_boundary':'No GL framebuffer status, GL errors or context lifecycle telemetry captured during this short attempt. Do not identify a framebuffer leak, driver issue, historical cause, or specific repair as proven.',
            'all_next_running_work':'STOPPED; no rerender, inference, rollout, installation or fix attempted'}
    write(E/'results/render_audit.json',result)
    print(json.dumps({'state':result['state'],'samples':len(rows),'added_model_or_render_calls':0}))

if __name__=='__main__':main()
