"""Build sanitized Phase 3.5 derivatives; never change original data or renderers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from shapely.geometry import shape
import yaml
from .edits import apply_edits
from .render import font, png_bytes

STATES = {'NONE':[],'A':['A'],'B':['B'],'AB':['A','B']}


def query_id(kind,sid,state=''):
    return 'q_'+hashlib.sha256(f'phase3.5/{kind}/{sid}/{state}'.encode()).hexdigest()[:16]


def render_poststate(scene):
    """Only metric geometry, obstacles, Start and Goal. No edit/state/answer text."""
    size = scene['render']['size_px']
    k = size/768
    image = Image.new('RGB',(size,size),'#FFFFFF')
    draw = ImageDraw.Draw(image)
    left,top,span = 72*k,44*k,624*k
    minx,miny,maxx,maxy = shape(scene['workspace']).bounds
    def xy(point):
        return (left+(point[0]-minx)/(maxx-minx)*span,top+(maxy-point[1])/(maxy-miny)*span)
    def polygon(geom,color):
        if geom.geom_type=='Polygon':
            draw.polygon([xy(p) for p in geom.exterior.coords],fill=color)
            for hole in geom.interiors:
                draw.polygon([xy(p) for p in hole.coords],fill='#F3F5F8')
        else:
            for part in geom.geoms:
                polygon(part,color)
    draw.rectangle([left,top,left+span,top+span],fill='#F3F5F8')
    for wall in scene['walls']:
        polygon(shape(wall),'#445060')
    draw.rectangle([left,top,left+span,top+span],outline='#182332',width=max(1,round(2*k)))
    for obj in scene['objects']:
        polygon(shape(obj['geometry']),obj['color'])
    r = scene['robot_radius_m']/(maxx-minx)*span
    for key,label,color in [('start','Start','#2475C4'),('goal','Goal','#16805B')]:
        cx,cy = xy(scene[key])
        draw.ellipse([cx-r,cy-r,cx+r,cy+r],fill=color,outline='#FFFFFF',width=max(1,round(2*k)))
        draw.text((cx,cy-20*k),label,font=font(round(15*k)),fill='#111827',anchor='mb')
    return image


def build(root):
    root = Path(root)
    cfg = yaml.safe_load((root/'configs/phase3_5.yaml').read_text())
    target = root/'diagnostics/phase3_5'
    if target.exists():
        raise FileExistsError('Preserve existing diagnostic derivative set')
    for sub in ['images','inputs','private']:
        (target/sub).mkdir(parents=True,exist_ok=False)
    public = {r['sample_id']:r for r in map(json.loads,(root/'data/public_inputs.jsonl').read_text().splitlines())}
    records = {'poststate':[],'overlap':[]}
    mapping = {}
    for sid in cfg['sample_ids']:
        scene = json.loads((root/f'data/scenes/{sid}/scene.json').read_text())
        minx,miny,maxx,maxy = shape(scene['workspace']).bounds
        for state,names in STATES.items():
            after = apply_edits(scene,names)
            qid = query_id('poststate',sid,state)
            data = png_bytes(render_poststate(after))
            relative = f'diagnostics/phase3_5/images/{qid}.png'
            (root/relative).write_bytes(data)
            context = {'units':'m','workspace_dimensions_m':[maxx-minx,maxy-miny],
                       'robot_radius_m':scene['robot_radius_m']}
            records['poststate'].append({'query_id':qid,'image':relative,
                'input_image_sha256':hashlib.sha256(data).hexdigest(),'context':context})
            mapping[qid] = {'sample_id':sid,'state':state,'kind':'poststate'}
        original = public[sid]
        qid = query_id('overlap',sid)
        context = {key:deepcopy(original[key]) for key in ['units','robot_radius_m',
                  'candidate_edits','candidate_geometry','image_legend']}
        records['overlap'].append({'query_id':qid,'image':'data/'+original['image'],
            'input_image_sha256':original['input_image_sha256'],'context':context})
        mapping[qid] = {'sample_id':sid,'kind':'overlap'}
    for kind,rows in records.items():
        (target/f'inputs/{kind}.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    (target/'private/query_map.json').write_text(json.dumps(mapping,indent=2)+'\n')
    info = {'derivative_only':True,'base_samples':6,'poststate_images':24,'overlap_queries':6,
            'render_version':'poststate-clean-v1','rendered_text':['Start','Goal'],
            'no_labels_paths_state_or_family_on_images':True}
    (root/'reports/phase3_5/input_build.json').write_text(json.dumps(info,indent=2)+'\n')
    return info


if __name__=='__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2]),indent=2))
