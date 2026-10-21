"""Fixed public RGB legend -> conservative disk grid -> BFS/A*.

No scene, oracle, label or generator imports. Geometry is inferred from image pixels.
Frame and marker locations are detected, not supplied as hidden coordinates.
The same collision graph is used by both searches; four neighbors, no corner crossing.
"""
from collections import deque
import heapq
import math
import time
from PIL import Image
import numpy as np

VERSION='rgb-grid-v1'
PALETTE={'frame':(24,35,50),'wall':(68,80,96),'obstacle':(221,147,80),
         'start':(36,117,196),'goal':(22,128,91),'floor':(243,245,248)}


class ExtractionFailure(ValueError):pass


def color_mask(rgb, color, tolerance=4):
    return np.max(np.abs(rgb.astype(np.int16)-np.array(color)),axis=2)<=tolerance


def dilate_disk(mask,radius):
    """Integer Euclidean disk dilation using row prefix sums, NumPy only."""
    h,w=mask.shape;out=np.zeros_like(mask);prefix=np.pad(np.cumsum(mask,axis=1,dtype=np.int32),((0,0),(1,0)))
    xs=np.arange(w)
    for dy in range(-math.ceil(radius),math.ceil(radius)+1):
        if dy*dy>radius*radius:continue
        dx=int(math.floor(math.sqrt(radius*radius-dy*dy)))
        row=(prefix[:,np.minimum(w,xs+dx+1)]-prefix[:,np.maximum(0,xs-dx)])>0
        if dy<0:out[:dy]|=row[-dy:]
        elif dy>0:out[dy:]|=row[:-dy]
        else:out|=row
    return out


def segment_safe(safe,a,b):
    # Full conservative supercover of a short endpoint connector, no silent snapping.
    count=max(2,int(math.ceil(max(abs(a[0]-b[0]),abs(a[1]-b[1]))*4))+1)
    points=np.linspace(a,b,count)
    for x,y in points:
        for xx in {math.floor(x),math.ceil(x)}:
            for yy in {math.floor(y),math.ceil(y)}:
                if yy<0 or xx<0 or yy>=safe.shape[0] or xx>=safe.shape[1] or not safe[yy,xx]:return False
    return True


def extract(image_path,context,stride=2,margin=2.0):
    started=time.perf_counter()
    with Image.open(image_path) as image:
        rgb=np.array(image.convert('RGB'))
    masks={name:color_mask(rgb,c) for name,c in PALETTE.items()}
    fy,fx=np.nonzero(masks['frame'])
    if len(fx)<100:raise ExtractionFailure('Workspace frame not detected')
    left,right,top,bottom=int(fx.min()),int(fx.max()),int(fy.min()),int(fy.max())
    if right-left<200 or bottom-top<200:raise ExtractionFailure('Invalid frame extent')
    w_m,h_m=context['workspace_dimensions_m'];sx=(right-left)/w_m;sy=(bottom-top)/h_m
    if abs(sx-sy)>.01:raise ExtractionFailure('Nonuniform metric scale')
    scale=(sx+sy)/2
    markers={}
    for key in ['start','goal']:
        yy,xx=np.nonzero(masks[key][top:bottom+1,left:right+1])
        if len(xx)<20:raise ExtractionFailure(f'{key} marker missing')
        # Reject multiple separated markers rather than substituting private coordinates.
        if (xx.max()-xx.min())>2*context['robot_radius_m']*scale+8 or (yy.max()-yy.min())>2*context['robot_radius_m']*scale+8:
            raise ExtractionFailure(f'{key} color is not a compact marker')
        markers[key]=(float(xx.mean()),float(yy.mean()))
    occupancy=(masks['wall']|masks['obstacle']|masks['frame'])[top:bottom+1,left:right+1]
    # Outer frame is observed, and its interior is the allowed workspace. Contact blocked.
    occupancy[[0,-1],:]=True;occupancy[:,[0,-1]]=True
    radius=context['robot_radius_m']*scale
    safe=~dilate_disk(occupancy,radius+margin)
    # Grid edges traverse every intervening pixel, not just their endpoints.
    height,width=safe.shape;xs=np.arange(0,width,stride);ys=np.arange(0,height,stride)
    free=safe[np.ix_(ys,xs)]
    horizontal=np.ones((len(ys),len(xs)-1),dtype=bool)
    vertical=np.ones((len(ys)-1,len(xs)),dtype=bool)
    for offset in range(stride+1):
        horizontal&=safe[np.ix_(ys,xs[:-1]+offset)]
        vertical&=safe[np.ix_(ys[:-1]+offset,xs)]
    endpoints={}
    for key,(px,py) in markers.items():
        choices=[]
        for xx in sorted({math.floor(px/stride),math.ceil(px/stride)}):
            for yy in sorted({math.floor(py/stride),math.ceil(py/stride)}):
                if 0<=xx<len(xs) and 0<=yy<len(ys) and free[yy,xx] and segment_safe(safe,(px,py),(int(xs[xx]),int(ys[yy]))):choices.append((xx,yy))
        if not choices:raise ExtractionFailure(f'{key} has no collision-free grid connector')
        endpoints[key]=choices
    return {'safe':safe,'occupancy':occupancy,'free':free,'horizontal':horizontal,'vertical':vertical,
            'xs':xs,'ys':ys,'endpoints':endpoints,'markers':markers,'scale':scale,
            'workspace_m':(w_m,h_m),'frame_px':[left,top,right,bottom],
            'robot_radius_px':radius,'conservative_margin_px':margin,'stride_px':stride,
            'extraction_seconds':time.perf_counter()-started}


def search(grid,algorithm):
    if algorithm not in ['bfs','astar']:raise ValueError('Unknown search')
    started=time.perf_counter();free=grid['free'];ny,nx=free.shape
    sources=grid['endpoints']['start'];targets=set(grid['endpoints']['goal'])
    def heuristic(p):return min(abs(p[0]-t[0])+abs(p[1]-t[1]) for t in targets)
    parent={p:None for p in sources};cost={p:0 for p in sources};expanded=0;found=None
    queue=deque(sources) if algorithm=='bfs' else [(heuristic(p),0,p) for p in sources]
    if algorithm=='astar':heapq.heapify(queue)
    while queue:
        if algorithm=='bfs':p=queue.popleft()
        else:
            _,g,p=heapq.heappop(queue)
            if g!=cost[p]:continue
        x,y=p;expanded+=1
        if p in targets:found=p;break
        for xx,yy in [(x+1,y),(x,y+1),(x-1,y),(x,y-1)]:
            if not(0<=xx<nx and 0<=yy<ny):continue
            edge=grid['horizontal'][y,min(x,xx)] if y==yy else grid['vertical'][min(y,yy),x]
            if not edge:continue
            nxt=(xx,yy);newcost=cost[p]+1
            if nxt in cost and (algorithm=='bfs' or newcost>=cost[nxt]):continue
            cost[nxt]=newcost;parent[nxt]=p
            if algorithm=='bfs':queue.append(nxt)
            else:heapq.heappush(queue,(newcost+heuristic(nxt),newcost,nxt))
    pixels=[]
    if found is not None:
        p=found
        while p is not None:
            pixels.append((int(grid['xs'][p[0]]),int(grid['ys'][p[1]])));p=parent[p]
        pixels=[grid['markers']['start']]+list(reversed(pixels))+[grid['markers']['goal']]
    path=[[float(x/grid['scale']),float(grid['workspace_m'][1]-y/grid['scale'])] for x,y in pixels]
    seconds=time.perf_counter()-started
    return {'passable':found is not None,'status':'reachable_on_extracted_grid' if found else 'unreachable_on_extracted_grid',
            'failure_reason':None,'path_m':path,'path_pixels':pixels,'expanded_nodes':expanded,
            'search_seconds':seconds,'extraction_seconds':grid['extraction_seconds'],
            'end_to_end_seconds':grid['extraction_seconds']+seconds,
            'preprocessing_charged_in_full_to_each_method':True,'continuous_unreachability_claimed':False}
