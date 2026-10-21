"""Phase 3.7: 24 predeclared fresh controls; no model-result-dependent selection."""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time
import traceback
from PIL import Image, ImageDraw
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
import yaml
from .control_scenes import signature, validate_control, qc_image
from .diagnostic_data import render_poststate
from .geometry import geo
from .render import png_bytes, font

ROOT = Path(__file__).resolve().parents[2]


def layouts():
    w = box(0, 0, 12, 12)
    z = unary_union([box(1,1,4,5), box(1,3,10,6), box(7,3,10,11)])
    ring = Point(6,6).buffer(3,quad_segs=64).difference(Point(6,6).buffer(2.2,quad_segs=64))
    hexagon = Polygon([(3,2),(8,2),(10,6),(8,10),(3,10),(1.5,6)])
    diamond = Polygon([(6,1.5),(10.5,6),(6,10.5),(1.5,6)])
    hourglass = Polygon([(2,2),(10,2),(10,5),(8,5),(8,8),(10,8),(10,10),(2,10),(2,7),(4,7),(4,5),(2,5)])
    def band(points, width):
        return LineString(points).buffer(width,cap_style=2,join_style=2).intersection(w)
    def enclosure(p, thickness):
        return p.difference(p.buffer(-thickness,join_style=2))
    return [
        ('A','horizontal foreground with two rear towers',(1.2,3),(10.8,3),[],[box(3,6,4,9),box(7,7,9,10)],None),
        ('A','descending diagonal among three corner banks',(1.5,10.5),(10.5,1.5),[],[box(1,1,3,3),box(9,9,11,11),box(5,9,7,11)],None),
        ('A','vertical traverse beside branching shelves and disk',(3,1.5),(3,10.5),[box(6,4,12,5),box(8,8,12,9),Point(8,2).buffer(1,quad_segs=64)],[],None),
        ('A','oblique passage between triangular and rectangular banks',(1.5,4),(10.5,5.5),[Polygon([(2,0),(8,0),(5,2)]),box(4,8,10,10),box(1,9,2,11)],[],None),
        ('A','straight diagonal corridor between slanted walls',(2,2),(10,9),[w.difference(LineString([(0,.25),(12,10.75)]).buffer(1.5,cap_style=2).intersection(w))],[],None),
        ('A','straight route above four unequal pillars',(1.5,8.5),(10.5,8.5),[],[box(2,1,3,5),box(4.5,2,5.5,6.5),box(7,0,8,4),box(9,2,10,6)],None),
        ('B','top bypass around two separated central blocks',(1.5,5),(10.5,5),[],[box(3,3,5,7.5),box(7,4,9,8)],[(1.5,5),(1.5,10),(10.5,10),(10.5,5)]),
        ('B','right-hand bypass around triangular island',(2,2),(10,10),[Polygon([(3,4),(8,4),(5.5,9)])],[],[(2,2),(10,2),(10,10)]),
        ('B','three-leg dogleg corridor',(2.5,2.5),(8.5,9.5),[w.difference(z)],[],[(2.5,2.5),(2.5,4.5),(8.5,4.5),(8.5,9.5)]),
        ('B','three alternating horizontal shelves',(2,1.2),(10,10.7),[box(0,2.5,8,3.3),box(4,5.5,12,6.3),box(0,8.5,8,9.3)],[],[(2,1.2),(10,1.2),(10,4.4),(2,4.4),(2,7.4),(10,7.4),(10,10.7)]),
        ('B','escape through left opening of circular C wall',(6,6),(10.5,6),[ring.difference(box(0,4.6,6,7.4))],[],[(6,6),(1.5,6),(1.5,1.5),(10.5,1.5),(10.5,6)]),
        ('B','two chambers connected above partition with side island',(2,3),(10,3),[box(5.4,0,6.6,8.5)],[box(8,5,9,7)],[(2,3),(2,10.2),(10,10.2),(10,3)]),
        ('C','sloped multi-bend left-right separator',(2,2),(10,10),[band([(0,8),(3,8),(6,4),(9,7),(12,7)],.45)],[],None),
        ('C','offset vertical dogleg separator',(1.5,8),(10.5,2),[band([(3,0),(3,4),(8,4),(8,12)],.4)],[],None),
        ('C','cross partitions four quadrants',(2,2),(10,10),[unary_union([box(5.5,0,6.5,12),box(0,5.5,12,6.5)])],[],None),
        ('C','two full-width bands separating three regions',(2,1.5),(10,10.5),[box(0,2.6,12,3.4),box(0,8,12,8.8)],[],None),
        ('C','full-height partition with opposite side branches',(2,6),(10,6),[unary_union([box(6.1,0,6.9,12),box(0,3.5,6.1,4.3),box(6.9,8,12,8.8)])],[],None),
        ('C','angled staircase bottom-top separator',(2,3),(10,9),[band([(8,0),(8,3),(5,6),(5,9),(2,12)],.45)],[],None),
        ('D','closed asymmetric hexagonal court',(10.5,1.5),(5.5,6),[enclosure(hexagon,.8)],[],None),
        ('D','closed diamond court',(1.2,10.8),(6,6),[enclosure(diamond,.8)],[],None),
        ('D','nested closed square rings',(1.2,1.2),(6.5,6.5),[enclosure(box(2.5,2.5,10,10),.8),enclosure(box(5,5,8,8),.8)],[],None),
        ('D','goal in one of two disjoint closed courts',(6,10.5),(9,4.5),[enclosure(box(2,3,5,9),.7),enclosure(box(7,2,11,7),.8)],[],None),
        ('D','rounded outer wall with rectangular inner court',(1.5,6),(6.5,6),[box(4,3,9,9).buffer(.5,quad_segs=32).difference(box(4.7,3.7,8.3,8.3))],[],None),
        ('D','closed hourglass court with opposing recesses',(1,10.8),(6,6),[enclosure(hourglass,.65)],[],None),
    ]


def candidates(cfg):
    for i,(cat,name,s,g,walls,objects,route) in enumerate(layouts()):
        sid='p_'+hashlib.sha256(f"phase3.7/{cfg['generation_seed']}/{i}".encode()).hexdigest()[:16]
        scene={'sample_id':sid,'seed':cfg['generation_seed'],'workspace':geo(box(0,0,12,12)),
               'robot_radius_m':cfg['robot_radius_m'],'start':list(s),'goal':list(g),
               'walls':[geo(w) for w in walls], 'objects':[{'id':f'o{j}','geometry':geo(o),'color':'#DD9350'} for j,o in enumerate(objects)],
               'render':{'size_px':768}}
        info={'category':cat,'layout_description':name,'reference_path':[list(p) for p in (route or [s,g])] if cat in 'AB' else None}
        yield scene,info


def montage(images, captions, path):
    tile=320; cell=348
    im=Image.new('RGB',(6*tile,4*cell),'white'); d=ImageDraw.Draw(im)
    for i,(image,caption) in enumerate(zip(images,captions)):
        x,y=i%6*tile,i//6*cell;im.paste(image.resize((tile,tile)),(x,y))
        d.text((x+4,y+tile+3),caption,font=font(11),fill='#111827')
    path.write_bytes(png_bytes(im))


def build(root=ROOT):
    cfg=yaml.safe_load((root/'configs/phase3_7.yaml').read_text())['geometry']
    target=root/'diagnostics/phase3_7';target.mkdir(exist_ok=False)
    for sub in ['inputs','images','private/scenes']:(target/sub).mkdir(parents=True,exist_ok=False)
    reports=root/'reports/phase3_7';(reports/'private_qc').mkdir(exist_ok=False)
    old_paths=[*(root/'data/scenes').glob('*/scene.json'),*(root/'diagnostics/phase3_6/private/scenes').glob('*.json')]
    historical={signature(json.loads(p.read_text())) for p in old_paths}
    seen=set();attempts=[];labels=[];rows=[];clean=[];qcs=[];start=time.perf_counter()
    try:
        for scene,info in candidates(cfg):
            sid=scene['sample_id'];a={'attempt':len(attempts)+1,'sample_id':sid,'category':info['category'],'status':'running'};attempts.append(a)
            try:
                (target/f'private/scenes/{sid}.json').write_text(json.dumps(scene,indent=2)+'\n')
                sig=signature(scene)
                if sig in historical or sig in seen:raise ValueError('Historical/self D4 geometry duplicate')
                seen.add(sig);label=validate_control(scene,info,cfg);label['D4_geometry_signature']=sig
                image=render_poststate(scene);raw=png_bytes(image);rel=f'diagnostics/phase3_7/images/{sid}.png';(root/rel).write_bytes(raw)
                rows.append({'query_id':sid,'image':rel,'input_image_sha256':hashlib.sha256(raw).hexdigest(),
                             'context':{'units':'m','workspace_dimensions_m':[12,12],'robot_radius_m':.25}})
                qc=qc_image(scene,label);(reports/f'private_qc/{sid}.png').write_bytes(png_bytes(qc))
                labels.append(label);clean.append(image);qcs.append(qc);a['status']='verified'
                print(json.dumps({'sample_id':sid,'category':info['category'],'passable':label['passable'],'margin':label['reference_path_min_clearance_m']}),flush=True)
            except Exception as exc:
                a.update(status='failed',error=repr(exc),traceback=traceback.format_exc());raise
        assert len(labels)==24 and sum(l['passable'] for l in labels)==12
        random.Random(cfg['generation_seed']).shuffle(rows)
        (target/'inputs/new24.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
        # Exact old image bytes, neutral records and frozen order are reused, never regenerated.
        (target/'inputs/old16.jsonl').write_bytes((root/'diagnostics/phase3_6/inputs/public_inputs.jsonl').read_bytes())
        (target/'private/new24_labels.jsonl').write_text(''.join(json.dumps(l,sort_keys=True)+'\n' for l in labels))
        montage(clean,[l['category']+' / '+l['sample_id'] for l in labels],reports/'new24_overview.png')
        montage(qcs,[l['category']+' PRIVATE / '+l['sample_id'] for l in labels],reports/'new24_private_paths.png')
    finally:
        (target/'private/generation_attempts.jsonl').write_text(''.join(json.dumps(a,sort_keys=True)+'\n' for a in attempts))
        result={'attempted':len(attempts),'verified':sum(a['status']=='verified' for a in attempts),'failed':sum(a['status']=='failed' for a in attempts),
                'not_attempted':24-len(attempts),'automatic_replacements':0,'seed':cfg['generation_seed'],
                'status':'completed' if len(labels)==24 else 'stopped','seconds':time.perf_counter()-start,
                'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
        (reports/'generation_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(build(),indent=2))
