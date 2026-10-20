"""Deterministic Pillow renderers: public originals and explicitly private QC views."""
from io import BytesIO
from math import hypot
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

FONT_PATH = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')


def font(size):
    return ImageFont.truetype(str(FONT_PATH), size)


def center(geometry):
    return list(shape(geometry).centroid.coords[0])


def edit_descriptions(scene):
    out = {}
    for name in ['A', 'B']:
        edit = scene['edits'][name]
        obj = next(o for o in scene['objects'] if o['id'] == edit['object_id'])
        old, new = center(obj['geometry']), center(edit['target_geometry'])
        minx, miny, maxx, maxy = shape(obj['geometry']).bounds
        out[name] = (
            f"Translate object {obj['display_id']} (footprint {maxx-minx:.2f} x {maxy-miny:.2f} m) "
            f"from center ({old[0]:.2f}, {old[1]:.2f}) to ({new[0]:.2f}, {new[1]:.2f}) m; keep orientation."
        )
    return out


def public_text(scene):
    text = ['Hypothetical final-pose edits', f"Circular robot r={scene['robot_radius_m']:.2f} m | axes in meters",
            'Start', 'Goal', 'Dashed outlines: candidate final footprints']
    for name in ['A', 'B']:
        edit = scene['edits'][name]
        obj = next(o for o in scene['objects'] if o['id'] == edit['object_id'])
        old, new = center(obj['geometry']), center(edit['target_geometry'])
        text += [obj['display_id'], name + "'", f"{name}: ({old[0]:.2f},{old[1]:.2f}) -> ({new[0]:.2f},{new[1]:.2f}) m"]
    return text


def _render(scene, *, qc_state=None, result=None):
    size = scene['render']['size_px']
    scale = size / 768
    image = Image.new('RGB', (size, size), '#FFFFFF')
    draw = ImageDraw.Draw(image)
    left, top, span = 72*scale, 44*scale, 624*scale
    minx, miny, maxx, maxy = shape(scene['workspace']).bounds
    def xy(point):
        return (left+(point[0]-minx)/(maxx-minx)*span, top+(maxy-point[1])/(maxy-miny)*span)
    def text_at(point, text, fill='#182332', pixels=16, anchor=None):
        draw.text(point, text, fill=fill, font=font(round(pixels*scale)), anchor=anchor)
    def poly(g, color):
        if g.is_empty:
            return
        if g.geom_type == 'Polygon':
            draw.polygon([xy(p) for p in g.exterior.coords], fill=color)
            for hole in g.interiors:
                draw.polygon([xy(p) for p in hole.coords], fill='#F3F5F8')
        else:
            for part in g.geoms:
                poly(part, color)
    draw.rectangle([left, top, left+span, top+span], fill='#F3F5F8')
    for wall in scene['walls']:
        poly(shape(wall), '#445060')
    draw.rectangle([left, top, left+span, top+span], outline='#182332', width=max(1, round(scale*2)))
    for tick in range(0, 13, 2):
        px, py = xy((tick, 0))
        text_at((px, py+6*scale), str(tick), pixels=12, anchor='mt')
        px, py = xy((0, tick))
        text_at((px-12*scale, py), str(tick), pixels=12, anchor='rm')
    def dashed_ring(coords, color):
        coords = list(coords)
        for p, q in zip(coords[:-1], coords[1:]):
            x1,y1 = xy(p); x2,y2 = xy(q)
            length = hypot(x2-x1,y2-y1)
            offset = 0
            while offset < length:
                end = min(length, offset+7*scale)
                draw.line([(x1+(x2-x1)*offset/length, y1+(y2-y1)*offset/length),
                           (x1+(x2-x1)*end/length, y1+(y2-y1)*end/length)],
                          fill=color, width=max(2, round(3*scale)))
                offset += 12*scale
    for obj in scene['objects']:
        poly(shape(obj['geometry']), obj['color'])
        pt = xy(center(obj['geometry']))
        text_at(pt, obj['display_id'], '#111827', pixels=18, anchor='mm')
    if qc_state is None:
        for name, edit in scene['edits'].items():
            obj = next(o for o in scene['objects'] if o['id'] == edit['object_id'])
            target = shape(edit['target_geometry'])
            dashed_ring(target.exterior.coords, obj['color'])
            text_at(xy(center(edit['target_geometry'])), name+"'", '#17202C', pixels=17, anchor='mm')
    elif result and result['passable']:
        draw.line([xy(p) for p in result['path']], fill='#16A085', width=max(2, round(3*scale)))
    radius_px = scene['robot_radius_m']/(maxx-minx)*span
    for key, label, color in [('start', 'Start', '#2475C4'), ('goal', 'Goal', '#16805B')]:
        cx,cy = xy(scene[key])
        draw.ellipse([cx-radius_px,cy-radius_px,cx+radius_px,cy+radius_px], fill=color, outline='#FFFFFF', width=max(1,round(2*scale)))
        text_at((cx,cy-20*scale), label, '#111827', pixels=15, anchor='mb')
    if qc_state is None:
        text_at((left,7*scale), 'Hypothetical final-pose edits', pixels=19)
        text_at((left+span,14*scale), f"r={scene['robot_radius_m']:.2f} m", pixels=14, anchor='rt')
        for name, y in [('A', 704), ('B', 725)]:
            edit = scene['edits'][name]
            obj = next(o for o in scene['objects'] if o['id'] == edit['object_id'])
            old,new = center(obj['geometry']), center(edit['target_geometry'])
            text_at((left,y*scale), f"{name}: ({old[0]:.2f},{old[1]:.2f}) -> ({new[0]:.2f},{new[1]:.2f}) m", pixels=15)
        text_at((left,749*scale), 'Dashed outlines: candidate final footprints | axes in meters', pixels=12)
    else:
        label = result['passable']
        text_at((left,7*scale), f"PRIVATE QC | {qc_state} | F={int(label)}", pixels=19)
        text_at((left,710*scale), 'Edited final geometry; green line = private oracle witness', pixels=15)
        text_at((left,739*scale), 'Grid result only; edit motion is not evaluated', pixels=14)
    return image


def render_public(scene):
    """No label, family, sample ID, private result, or post-edit state is consumed."""
    return _render(scene)


def render_private(scene, state, result):
    from .edits import apply_edits
    from .scenes import STATES
    return _render(apply_edits(scene, STATES[state]), qc_state=state, result=result)


def png_bytes(image):
    stream = BytesIO()
    image.save(stream, format='PNG', optimize=False)
    return stream.getvalue()


def montage(scenes, labels, destination):
    width, height = 1536, 1404
    out = Image.new('RGB', (width,height), '#EDF1F5')
    draw = ImageDraw.Draw(out)
    draw.text((24,14), 'PRIVATE QC | original inputs + computed finite-grid labels', font=font(24), fill='#182332')
    draw.text((24,47), 'NONE / A / B / AB; each family has 2 base layouts and 2 controlled views', font=font(18), fill='#4A5568')
    for i, scene in enumerate(scenes):
        row, col = divmod(i,4)
        x, y = col*384, 88+row*438
        thumb = render_public(scene).resize((384,384), Image.Resampling.LANCZOS)
        out.paste(thumb, (x,y))
        truth = labels[scene['sample_id']]['labels']
        values = '/'.join('?' if v is None else str(int(v)) for v in truth.values())
        draw.text((x+12,y+386), f"{scene['family']} v{scene['variant']} | {values}", font=font(17), fill='#17202C')
        draw.text((x+12,y+410), scene['sample_id'], font=font(14), fill='#5A6778')
    out.save(destination)
