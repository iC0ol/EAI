"""Public-only RGB inference process. No private geometry imports or fallbacks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback
from PIL import Image, ImageDraw
import numpy as np
import yaml
from .scale_io import firewall, load_inputs, verify_frozen, digest
from .scale_rgb import extract, search, VERSION

ROOT=Path(__file__).resolve().parents[2]


def main():
    cfg=yaml.safe_load((ROOT/'configs/phase3_7.yaml').read_text())['image_planner']
    out=ROOT/'outputs/phase3_7/rgb';out.mkdir(parents=True,exist_ok=False)
    events=firewall(ROOT);verify_frozen(ROOT)
    session={'started_at':datetime.now(timezone.utc).isoformat(),'status':'running','version':VERSION,
             'configuration':cfg,'records':0,'same_graph_for_both_searches':True}
    try:
        with (out/'predictions.jsonl').open('x') as stream:
            for dataset in ['old16','new24']:
                for record,path in load_inputs(ROOT,dataset):
                    qid=record['query_id'];start=time.perf_counter()
                    shared={'query_id':qid,'dataset':dataset,'image_sha256':record['input_image_sha256'],'version':VERSION}
                    try:
                        grid=extract(path,record['context'],cfg['grid_stride_pixels'],cfg['conservative_margin_pixels'])
                        # Timings charge all decode/segmentation/inflation/connector work to each algorithm.
                        grid['extraction_seconds']=time.perf_counter()-start
                        results={algorithm:search(grid,algorithm) for algorithm in ['bfs','astar']}
                        metadata={key:grid[key] for key in ['frame_px','markers','scale','robot_radius_px','conservative_margin_px','stride_px']}
                        (out/f'{qid}_extraction.json').write_text(json.dumps(metadata,indent=2)+'\n')
                        Image.fromarray(np.uint8(grid['occupancy'])*255).save(out/f'{qid}_occupancy.png')
                        Image.fromarray(np.uint8(grid['safe'])*255).save(out/f'{qid}_safe.png')
                        for algorithm,result in results.items():
                            if result['passable']:
                                with Image.open(path) as source:image=source.convert('RGB')
                                left,top,_,_=grid['frame_px'];draw=ImageDraw.Draw(image)
                                draw.line([(left+p[0],top+p[1]) for p in result['path_pixels']],fill='#9E28CC',width=3)
                                image.save(out/f'{qid}_{algorithm}_path.png')
                    except Exception as exc:
                        elapsed=time.perf_counter()-start
                        results={a:{'passable':None,'status':'pipeline_error','failure_reason':repr(exc),'traceback':traceback.format_exc(),
                                    'path_m':[],'path_pixels':[],'end_to_end_seconds':elapsed,'extraction_seconds':elapsed,'search_seconds':None} for a in ['bfs','astar']}
                    for algorithm,result in results.items():
                        row={**shared,'algorithm':algorithm,**result};stream.write(json.dumps(row)+'\n');stream.flush();session['records']+=1
                        print(json.dumps({k:row[k] for k in ['query_id','dataset','algorithm','passable','status','end_to_end_seconds']}),flush=True)
        session['status']='completed'
    finally:
        session.update(finished_at=datetime.now(timezone.utc).isoformat(),data_read_events=sorted(set(events)))
        (out/'session.json').write_text(json.dumps(session,indent=2)+'\n')


if __name__=='__main__':main()
