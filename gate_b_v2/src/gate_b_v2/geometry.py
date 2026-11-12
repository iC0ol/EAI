from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np


_MJ_GEOM_BOX = 6


def _box_corners(center: np.ndarray, rotation: np.ndarray, half_size: np.ndarray) -> np.ndarray:
    signs = np.asarray(
        [[-1, -1, -1], [-1, -1, 1], [-1, 1, -1], [-1, 1, 1],
         [1, -1, -1], [1, -1, 1], [1, 1, -1], [1, 1, 1]], dtype=np.float64
    )
    local = signs * np.asarray(half_size, dtype=np.float64)[None, :]
    return np.asarray(center, dtype=np.float64)[None, :] + local.dot(np.asarray(rotation, dtype=np.float64).T)


def _geom_world_corners(sim: Any, geom_id: int) -> np.ndarray:
    data = sim.data
    model = sim.model
    center = np.asarray(data.geom_xpos[geom_id], dtype=np.float64)
    rotation = np.asarray(data.geom_xmat[geom_id], dtype=np.float64).reshape(3, 3)
    half_size = np.asarray(model.geom_size[geom_id], dtype=np.float64)[:3]
    return _box_corners(center, rotation, half_size)


def _nut_local_geom_bbox(sim: Any, nut_body_id: int, geom_id: int) -> Tuple[np.ndarray, np.ndarray]:
    corners_world = _geom_world_corners(sim, geom_id)
    nut_pos = np.asarray(sim.data.body_xpos[nut_body_id], dtype=np.float64)
    nut_rot = np.asarray(sim.data.body_xmat[nut_body_id], dtype=np.float64).reshape(3, 3)
    local = (corners_world - nut_pos[None, :]).dot(nut_rot)
    return local.min(axis=0), local.max(axis=0)


def infer_square_nut_hole_half_extents(rs_env: Any) -> np.ndarray:
    """Infer the inner square aperture from the four live collision-box geoms.

    The expected SquareNut model has two x-side bars and two y-side bars. If the
    installed model differs or the geometry cannot be identified symmetrically,
    fail closed instead of substituting a guessed clearance.
    """
    if not hasattr(rs_env, "nuts") or not hasattr(rs_env, "obj_body_id") or not hasattr(rs_env, "obj_geom_id"):
        raise RuntimeError("Environment does not expose robosuite NutAssembly geometry references")
    nuts = [nut for nut in rs_env.nuts if "square" in str(getattr(nut, "name", "")).lower()]
    if len(nuts) != 1:
        raise RuntimeError("Expected exactly one SquareNut, found {}".format(len(nuts)))
    nut = nuts[0]
    nut_body_id = int(rs_env.obj_body_id[nut.name])
    geom_ids = list(rs_env.obj_geom_id[nut.name])
    sim = rs_env.sim
    x_gaps: List[float] = []
    y_gaps: List[float] = []
    for geom_id in geom_ids:
        if int(sim.model.geom_type[geom_id]) != _MJ_GEOM_BOX:
            continue
        lower, upper = _nut_local_geom_bbox(sim, nut_body_id, int(geom_id))
        center = 0.5 * (lower + upper)
        extent = 0.5 * (upper - lower)
        # Side bars: centered near +/-x with a narrow x thickness and long y span.
        if abs(center[0]) > 0.02 and abs(center[1]) < 0.01 and extent[0] < extent[1]:
            if abs(center[0]) < 0.05 and extent[1] > 0.03:
                x_gaps.append(abs(float(center[0])) - float(extent[0]))
        # Top/bottom bars: centered near +/-y with a narrow y thickness and long x span.
        if abs(center[1]) > 0.02 and abs(center[0]) < 0.01 and extent[1] < extent[0]:
            if abs(center[1]) < 0.05 and extent[0] > 0.03:
                y_gaps.append(abs(float(center[1])) - float(extent[1]))
    if len(x_gaps) != 2 or len(y_gaps) != 2:
        raise RuntimeError(
            "Could not identify the four SquareNut aperture bars from collision geoms "
            "(x bars={}, y bars={}); inspect robosuite version/model".format(len(x_gaps), len(y_gaps))
        )
    if np.std(x_gaps) > 1e-3 or np.std(y_gaps) > 1e-3:
        raise RuntimeError("SquareNut aperture bars are asymmetric beyond 1 mm: x={}, y={}".format(x_gaps, y_gaps))
    half_extents = np.asarray([np.mean(x_gaps), np.mean(y_gaps)], dtype=np.float64)
    if np.any(half_extents <= 0):
        raise RuntimeError("Inferred non-positive SquareNut aperture: {}".format(half_extents))
    return half_extents


def _find_square_peg_geom(rs_env: Any) -> int:
    sim = rs_env.sim
    if not hasattr(rs_env, "peg1_body_id"):
        raise RuntimeError("Square peg body reference peg1_body_id is unavailable")
    body_id = int(rs_env.peg1_body_id)
    model = sim.model
    body_ids = np.asarray(model.geom_bodyid)
    types = np.asarray(model.geom_type)
    contype = np.asarray(getattr(model, "geom_contype", np.ones_like(types)))
    conaffinity = np.asarray(getattr(model, "geom_conaffinity", np.ones_like(types)))
    candidates = [
        int(i) for i in np.where((body_ids == body_id) & (types == _MJ_GEOM_BOX))[0]
        if int(contype[i]) != 0 or int(conaffinity[i]) != 0
    ]
    if not candidates:
        # Some older MuJoCo wrappers omit contype arrays; group 0 is the collision group.
        groups = np.asarray(getattr(model, "geom_group", np.zeros_like(types)))
        candidates = [int(i) for i in np.where((body_ids == body_id) & (types == _MJ_GEOM_BOX) & (groups == 0))[0]]
    if not candidates:
        raise RuntimeError("No collision box geom found on Square peg body")
    sizes = [np.asarray(model.geom_size[i], dtype=np.float64)[:3] for i in candidates]
    # The Square peg has one collision box; if visual/collision duplicates survive,
    # their dimensions must agree and one representative is sufficient.
    if any(not np.allclose(sizes[0], item, atol=1e-6) for item in sizes[1:]):
        raise RuntimeError("Multiple non-identical box geoms found on Square peg: {}".format(sizes))
    return candidates[0]


def compute_square_clearance(rs_env: Any) -> Dict[str, float]:
    """Compute signed projected peg-to-hole clearance from live collision geometry.

    Positive means the projected peg rectangle fits inside the SquareNut aperture;
    negative means at least one aperture half-space is violated. Axial z gap is
    returned separately and is not folded into the signed XY clearance.
    """
    sim = rs_env.sim
    hole_half = infer_square_nut_hole_half_extents(rs_env)
    square_nut = [nut for nut in rs_env.nuts if "square" in str(getattr(nut, "name", "")).lower()][0]
    nut_body_id = int(rs_env.obj_body_id[square_nut.name])
    nut_pos = np.asarray(sim.data.body_xpos[nut_body_id], dtype=np.float64)
    nut_rot = np.asarray(sim.data.body_xmat[nut_body_id], dtype=np.float64).reshape(3, 3)

    peg_geom_id = _find_square_peg_geom(rs_env)
    peg_center = np.asarray(sim.data.geom_xpos[peg_geom_id], dtype=np.float64)
    peg_rot = np.asarray(sim.data.geom_xmat[peg_geom_id], dtype=np.float64).reshape(3, 3)
    peg_half = np.asarray(sim.model.geom_size[peg_geom_id], dtype=np.float64)[:3]
    peg_corners_world = _box_corners(peg_center, peg_rot, peg_half)
    peg_corners_nut = (peg_corners_world - nut_pos[None, :]).dot(nut_rot)
    xy = peg_corners_nut[:, :2]

    gaps = {
        "x_positive": float(hole_half[0] - np.max(xy[:, 0])),
        "x_negative": float(hole_half[0] + np.min(xy[:, 0])),
        "y_positive": float(hole_half[1] - np.max(xy[:, 1])),
        "y_negative": float(hole_half[1] + np.min(xy[:, 1])),
    }
    clearance = min(gaps.values())

    nut_geom_ids = list(rs_env.obj_geom_id[square_nut.name])
    nut_bottom = float("inf")
    for geom_id in nut_geom_ids:
        if int(sim.model.geom_type[geom_id]) != _MJ_GEOM_BOX:
            continue
        corners = _geom_world_corners(sim, int(geom_id))
        nut_bottom = min(nut_bottom, float(np.min(corners[:, 2])))
    if not np.isfinite(nut_bottom):
        raise RuntimeError("Could not compute SquareNut collision bottom from box geoms")
    peg_top = float(np.max(peg_corners_world[:, 2]))
    peg_center_nut = (peg_center - nut_pos).dot(nut_rot)
    relative_rot = nut_rot.T.dot(peg_rot)
    yaw = float(np.arctan2(relative_rot[1, 0], relative_rot[0, 0]))

    return {
        "clearance_m": float(clearance),
        "clearance_x_positive_m": gaps["x_positive"],
        "clearance_x_negative_m": gaps["x_negative"],
        "clearance_y_positive_m": gaps["y_positive"],
        "clearance_y_negative_m": gaps["y_negative"],
        "dx_m": float(peg_center_nut[0]),
        "dy_m": float(peg_center_nut[1]),
        "relative_yaw_rad": yaw,
        "z_gap_m": float(nut_bottom - peg_top),
        "xy_center_distance_m": float(np.linalg.norm(peg_center_nut[:2])),
        "hole_half_x_m": float(hole_half[0]),
        "hole_half_y_m": float(hole_half[1]),
        "peg_half_x_m": float(peg_half[0]),
        "peg_half_y_m": float(peg_half[1]),
    }
