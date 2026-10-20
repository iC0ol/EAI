"""Metric planar geometry. Object boundary contact is allowed; robot contact is collision."""
from dataclasses import dataclass
from math import cos, pi
import numpy as np
import shapely
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union


class InvalidGeometry(ValueError):
    pass


def geo(geometry):
    """JSON-native GeoJSON, rounded for deterministic transforms."""
    import json
    return json.loads(json.dumps(mapping(geometry)))


def obstacles(scene):
    return unary_union([shape(w) for w in scene['walls']] +
                       [shape(o['geometry']) for o in scene['objects']])


def validate_scene(scene):
    world = shape(scene['workspace'])
    if world.is_empty or not world.is_valid or world.area <= 0:
        raise InvalidGeometry('Invalid workspace')
    if scene['robot_radius_m'] <= 0:
        raise InvalidGeometry('Robot radius must be positive')
    ids = [o['id'] for o in scene['objects']]
    if len(ids) != len(set(ids)):
        raise InvalidGeometry('Duplicate object ID')
    walls = [shape(w) for w in scene['walls']]
    for wall in walls:
        if wall.is_empty or not wall.is_valid or not world.covers(wall):
            raise InvalidGeometry('Invalid/outside wall')
    for index, obj in enumerate(scene['objects']):
        geom = shape(obj['geometry'])
        if geom.is_empty or not geom.is_valid or geom.area <= 0 or not world.covers(geom):
            raise InvalidGeometry(f"Invalid/outside object: {obj['id']}")
        if any(geom.intersection(w).area > 1e-10 for w in walls):
            raise InvalidGeometry(f"Object inside wall: {obj['id']}")
        if any(geom.intersection(shape(other['geometry'])).area > 1e-10
               for other in scene['objects'][:index]):
            raise InvalidGeometry(f"Overlapping objects: {obj['id']}")
    # Markers specify exact center coordinates, never snapped silently.
    for key in ['start', 'goal']:
        pt = Point(scene[key])
        if not world.contains(pt):
            raise InvalidGeometry(f'{key} outside workspace')
    return True


@dataclass
class CollisionModel:
    workspace: object
    raw_obstacles: object
    safe_workspace: object
    inflated_obstacles: object
    radius: float
    effective_radius: float

    @classmethod
    def from_scene(cls, scene, quad_segs=32, epsilon=1e-6):
        validate_scene(scene)
        world = shape(scene['workspace'])
        raw = obstacles(scene)
        radius = scene['robot_radius_m']
        # GEOS approximates round buffers by chords. Circumscribe the circle
        # so that a tiny arc approximation cannot create unsafe corner paths.
        effective = radius / cos(pi / (4 * quad_segs)) + epsilon
        inflated = raw.buffer(effective, quad_segs=quad_segs)
        safe = world.buffer(-effective, quad_segs=quad_segs)
        return cls(world, raw, safe, inflated, radius, effective)

    def point_free(self, point):
        p = Point(point)
        return self.safe_workspace.contains(p) and not self.inflated_obstacles.intersects(p)

    def segment_free(self, first, second):
        from shapely.geometry import LineString
        if np.allclose(first, second, atol=1e-12, rtol=0):
            return self.point_free(first)
        line = LineString([first, second])
        return self.safe_workspace.contains(line) and not self.inflated_obstacles.intersects(line)

    def free_points(self, xs, ys):
        return (shapely.contains_xy(self.safe_workspace, xs, ys) &
                ~shapely.intersects_xy(self.inflated_obstacles, xs, ys))

    def free_segments(self, starts, ends):
        if len(starts) == 0:
            return np.empty(0, dtype=bool)
        lines = shapely.linestrings(np.stack([starts, ends], axis=1))
        return (shapely.contains(self.safe_workspace, lines) &
                ~shapely.intersects(self.inflated_obstacles, lines))

    def path_clearance(self, path):
        from shapely.geometry import LineString
        line = LineString(path) if len(path) > 1 else Point(path[0])
        wall_margin = line.distance(self.workspace.boundary) - self.radius
        obstacle_margin = line.distance(self.raw_obstacles) - self.radius
        return float(min(wall_margin, obstacle_margin))
