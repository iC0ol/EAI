"""Square-MH collision-geometry measurements for B2.

This module deliberately uses the live MuJoCo collision geoms, not visual
meshes and not hand-entered nominal dimensions.  The authoritative frame is the
SquareNut body frame (``nut-local``).  All axial quantities are expressed along
nut-local +z; the signed projected clearance is expressed in nut-local XY and
never folds the axial gap into the XY value.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np


STAGE_GATE_VERSION = "B2_GEOMETRY_GATE_V1_20261116"
_MJ_GEOM_BOX = 6
_MJ_JNT_FREE = 0
_GEOM_TOL = 1e-7
_AXIS_TOL = 1e-6


class GeometryError(RuntimeError):
    """Raised when live collision geometry cannot be identified unambiguously."""


def _box_corners(center: np.ndarray, rotation: np.ndarray, half_size: np.ndarray) -> np.ndarray:
    signs = np.asarray(
        [[-1, -1, -1], [-1, -1, 1], [-1, 1, -1], [-1, 1, 1],
         [1, -1, -1], [1, -1, 1], [1, 1, -1], [1, 1, 1]], dtype=np.float64
    )
    local = signs * np.asarray(half_size, dtype=np.float64)[None, :]
    return np.asarray(center, dtype=np.float64)[None, :] + local.dot(
        np.asarray(rotation, dtype=np.float64).T
    )


def _geom_world_corners(sim: Any, geom_id: int) -> np.ndarray:
    data = sim.data
    model = sim.model
    center = np.asarray(data.geom_xpos[geom_id], dtype=np.float64)
    rotation = np.asarray(data.geom_xmat[geom_id], dtype=np.float64).reshape(3, 3)
    half_size = np.asarray(model.geom_size[geom_id], dtype=np.float64)[:3]
    return _box_corners(center, rotation, half_size)


def _frame_pose(sim: Any, body_id: int) -> Tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray(sim.data.body_xpos[body_id], dtype=np.float64),
        np.asarray(sim.data.body_xmat[body_id], dtype=np.float64).reshape(3, 3),
    )


def _world_to_local(points: np.ndarray, frame_pos: np.ndarray, frame_rot: np.ndarray) -> np.ndarray:
    values = np.asarray(points, dtype=np.float64)
    single = values.ndim == 1
    rows = values[None, :] if single else values
    local = (rows - frame_pos[None, :]).dot(frame_rot)
    return local[0] if single else local


def _local_geom_bbox(sim: Any, frame_body_id: int, geom_id: int) -> Tuple[np.ndarray, np.ndarray]:
    corners_world = _geom_world_corners(sim, geom_id)
    frame_pos, frame_rot = _frame_pose(sim, frame_body_id)
    local = _world_to_local(corners_world, frame_pos, frame_rot)
    return local.min(axis=0), local.max(axis=0)


def _geom_record(sim: Any, geom_id: int) -> Dict[str, Any]:
    model = sim.model
    body_id = int(model.geom_bodyid[geom_id])
    try:
        body_name = str(model.body_id2name(body_id))
    except Exception:
        body_name = None
    record: Dict[str, Any] = {
        "geom_id": int(geom_id),
        "body_id": body_id,
        "body_name": body_name,
        "geom_type": int(model.geom_type[geom_id]),
        "size": np.asarray(model.geom_size[geom_id], dtype=np.float64).tolist(),
        "pos": np.asarray(model.geom_pos[geom_id], dtype=np.float64).tolist()
        if hasattr(model, "geom_pos") else None,
    }
    for key in ("geom_quat", "geom_contype", "geom_conaffinity", "geom_group",
                "geom_friction", "geom_solimp", "geom_solref"):
        if hasattr(model, key):
            value = getattr(model, key)[geom_id]
            if isinstance(value, np.ndarray):
                record[key] = value.astype(np.float64).tolist()
            else:
                record[key] = int(value)
    return record


def _square_nut(rs_env: Any) -> Any:
    if not hasattr(rs_env, "nuts") or not hasattr(rs_env, "obj_body_id") or not hasattr(rs_env, "obj_geom_id"):
        raise GeometryError("Environment does not expose robosuite NutAssembly geometry references")
    nuts = [nut for nut in rs_env.nuts if "square" in str(getattr(nut, "name", "")).lower()]
    if len(nuts) != 1:
        raise GeometryError("Expected exactly one SquareNut, found {}".format(len(nuts)))
    return nuts[0]


def _nut_collision_boxes(rs_env: Any) -> Tuple[Any, int, List[Dict[str, Any]]]:
    nut = _square_nut(rs_env)
    nut_body_id = int(rs_env.obj_body_id[nut.name])
    sim = rs_env.sim
    boxes: List[Dict[str, Any]] = []
    for geom_id in list(rs_env.obj_geom_id[nut.name]):
        geom_id = int(geom_id)
        if int(sim.model.geom_type[geom_id]) != _MJ_GEOM_BOX:
            continue
        lower, upper = _local_geom_bbox(sim, nut_body_id, geom_id)
        boxes.append({
            "geom_id": geom_id,
            "lower": lower,
            "upper": upper,
            "center": 0.5 * (lower + upper),
            "extent": 0.5 * (upper - lower),
            "record": _geom_record(sim, geom_id),
        })
    if len(boxes) < 4:
        raise GeometryError(
            "SquareNut exposes {} collision boxes; four aperture bars are required".format(len(boxes))
        )
    return nut, nut_body_id, boxes


def _symmetric_pairs(boxes: Sequence[Mapping[str, Any]]) -> List[Tuple[int, int]]:
    """Pair identical boxes whose local centers are mirror images.

    The SquareNut model has four aperture bars (two mirror pairs) plus a handle
    that has no mirror partner.  This identifies the aperture without relying on
    hand-entered coordinates or geometry-name suffixes.
    """
    used = set()
    pairs: List[Tuple[int, int]] = []
    for i in range(len(boxes)):
        if i in used:
            continue
        for j in range(i + 1, len(boxes)):
            if j in used:
                continue
            a, b = boxes[i], boxes[j]
            if (
                np.allclose(a["extent"], b["extent"], atol=_GEOM_TOL)
                and np.allclose(a["center"], -np.asarray(b["center"]), atol=_GEOM_TOL)
            ):
                pairs.append((i, j))
                used.update((i, j))
                break
    return pairs


def square_nut_aperture(rs_env: Any) -> Dict[str, Any]:
    """Identify the four live aperture bars and derive the frozen geometry values."""
    nut, nut_body_id, boxes = _nut_collision_boxes(rs_env)
    pairs = _symmetric_pairs(boxes)
    if len(pairs) != 2:
        raise GeometryError(
            "Could not identify exactly two mirror-paired SquareNut aperture bar pairs; "
            "found {} pairs from {} collision boxes".format(len(pairs), len(boxes))
        )

    x_pair = None
    y_pair = None
    for pair in pairs:
        centers = [boxes[index]["center"] for index in pair]
        if all(abs(c[2]) <= _AXIS_TOL for c in centers):
            if all(abs(c[1]) <= _AXIS_TOL for c in centers) and all(abs(c[0]) > _AXIS_TOL for c in centers):
                if x_pair is None:
                    x_pair = pair
                else:
                    raise GeometryError("More than one x-axis aperture bar pair")
            elif all(abs(c[0]) <= _AXIS_TOL for c in centers) and all(abs(c[1]) > _AXIS_TOL for c in centers):
                if y_pair is None:
                    y_pair = pair
                else:
                    raise GeometryError("More than one y-axis aperture bar pair")
    if x_pair is None or y_pair is None:
        raise GeometryError("Could not distinguish x-axis and y-axis SquareNut aperture bar pairs")

    def pair_half_gap(pair: Sequence[int], axis: int) -> float:
        values = []
        for index in pair:
            values.append(abs(float(boxes[index]["center"][axis])) - float(boxes[index]["extent"][axis]))
        if max(values) - min(values) > 1e-6:
            raise GeometryError("Aperture bars in one pair are asymmetric: {}".format(values))
        return float(np.mean(values))

    hole_half_x = pair_half_gap(x_pair, 0)
    hole_half_y = pair_half_gap(y_pair, 1)
    if hole_half_x <= 0 or hole_half_y <= 0:
        raise GeometryError("Inferred non-positive SquareNut aperture: {}".format([hole_half_x, hole_half_y]))

    aperture_indices = sorted(set(x_pair + y_pair))
    aperture_boxes = [boxes[index] for index in aperture_indices]
    z_lowers = [float(box["lower"][2]) for box in aperture_boxes]
    z_uppers = [float(box["upper"][2]) for box in aperture_boxes]
    if max(z_lowers) - min(z_lowers) > 1e-9 or max(z_uppers) - min(z_uppers) > 1e-9:
        raise GeometryError(
            "Four aperture bars do not share a consistent nut-local z extent: lower={}, upper={}".format(
                z_lowers, z_uppers
            )
        )
    t_nut = float(max(z_uppers) - min(z_lowers))
    if t_nut <= 0:
        raise GeometryError("SquareNut collision thickness is non-positive: {}".format(t_nut))

    handle_indices = [index for index in range(len(boxes)) if index not in aperture_indices]
    handle_records = [boxes[index]["record"] for index in handle_indices]
    bar_records = []
    for index in aperture_indices:
        role = "x" if index in x_pair else "y"
        box = boxes[index]
        bar_records.append({
            "geom_id": int(box["geom_id"]),
            "role": role,
            "center_local": box["center"].tolist(),
            "extent_local": box["extent"].tolist(),
            "lower_local": box["lower"].tolist(),
            "upper_local": box["upper"].tolist(),
            "record": box["record"],
        })

    return {
        "nut_name": str(nut.name),
        "nut_body_id": int(nut_body_id),
        "nut_geom_ids": [int(item["geom_id"]) for item in boxes],
        "aperture_bar_geom_ids": [int(boxes[index]["geom_id"]) for index in aperture_indices],
        "aperture_bars": bar_records,
        "handle_geom_ids": [int(boxes[index]["geom_id"]) for index in handle_indices],
        "handle_geoms": handle_records,
        "x_pair_geom_ids": [int(boxes[index]["geom_id"]) for index in x_pair],
        "y_pair_geom_ids": [int(boxes[index]["geom_id"]) for index in y_pair],
        "hole_half_x_m": float(hole_half_x),
        "hole_half_y_m": float(hole_half_y),
        "hole_half_extents_m": [float(hole_half_x), float(hole_half_y)],
        "nut_collision_thickness_m": t_nut,
        "t_nut_m": t_nut,
        "nut_bottom_local_z_m": float(min(z_lowers)),
        "nut_top_local_z_m": float(max(z_uppers)),
        "aperture_center_local_m": [0.0, 0.0],
        "identification": "four mirror-paired collision boxes; handle boxes excluded by lack of mirror partner",
    }


def infer_square_nut_hole_half_extents(rs_env: Any) -> np.ndarray:
    """Compatibility wrapper returning [hole_half_x, hole_half_y]."""
    info = square_nut_aperture(rs_env)
    return np.asarray([info["hole_half_x_m"], info["hole_half_y_m"]], dtype=np.float64)


def _square_peg_info(rs_env: Any) -> Dict[str, Any]:
    if not hasattr(rs_env, "peg1_body_id"):
        raise GeometryError("Square peg body reference peg1_body_id is unavailable")
    body_id = int(rs_env.peg1_body_id)
    sim = rs_env.sim
    model = sim.model
    body_ids = np.asarray(model.geom_bodyid)
    types = np.asarray(model.geom_type)
    contype = np.asarray(getattr(model, "geom_contype", np.ones_like(types)))
    conaffinity = np.asarray(getattr(model, "geom_conaffinity", np.ones_like(types)))
    groups = np.asarray(getattr(model, "geom_group", np.zeros_like(types)))

    on_body = [int(i) for i in np.where(body_ids == body_id)[0]]
    collision = [
        i for i in on_body
        if int(types[i]) == _MJ_GEOM_BOX
        and (int(contype[i]) != 0 or int(conaffinity[i]) != 0 or int(groups[i]) == 0)
    ]
    if not collision:
        raise GeometryError("No collision box geom found on Square peg body {}".format(body_id))
    sizes = [np.asarray(model.geom_size[i], dtype=np.float64)[:3] for i in collision]
    for item in sizes[1:]:
        if not np.allclose(sizes[0], item, atol=1e-6):
            raise GeometryError("Multiple non-identical collision boxes found on Square peg: {}".format(sizes))
    visual = [
        int(i) for i in on_body
        if int(types[i]) == _MJ_GEOM_BOX and i not in collision
    ]
    visual_sizes = [np.asarray(model.geom_size[i], dtype=np.float64)[:3] for i in visual]
    return {
        "peg_body_id": body_id,
        "peg_geom_id": int(collision[0]),
        "peg_collision_geom_ids": [int(i) for i in collision],
        "peg_visual_geom_ids": visual,
        "peg_size_m": sizes[0].tolist(),
        "peg_half_x_m": float(sizes[0][0]),
        "peg_half_y_m": float(sizes[0][1]),
        "peg_half_z_m": float(sizes[0][2]),
        "peg_visual_sizes_m": [item.tolist() for item in visual_sizes],
        "visual_collision_identical": (
            all(np.allclose(sizes[0], item, atol=1e-9) for item in visual_sizes) if visual_sizes else None
        ),
        "geom_records": [_geom_record(sim, int(i)) for i in on_body],
    }


def _geometry_fingerprint(aperture: Mapping[str, Any], peg: Mapping[str, Any], sim: Any) -> str:
    payload = {
        "nut_body_id": aperture["nut_body_id"],
        "nut_geom_ids": aperture["nut_geom_ids"],
        "aperture_bar_geom_ids": aperture["aperture_bar_geom_ids"],
        "aperture_bars": [
            {
                "geom_id": bar["geom_id"],
                "role": bar["role"],
                "center_local": bar["center_local"],
                "extent_local": bar["extent_local"],
                "record": bar["record"],
            }
            for bar in aperture["aperture_bars"]
        ],
        "handle_geom_ids": aperture["handle_geom_ids"],
        "peg_body_id": peg["peg_body_id"],
        "peg_geom_id": peg["peg_geom_id"],
        "peg_collision_geom_ids": peg["peg_collision_geom_ids"],
        "peg_size_m": peg["peg_size_m"],
        "model_xml_sha256": hashlib.sha256(
            str(sim.model.get_xml()).encode("utf-8")
        ).hexdigest() if hasattr(sim.model, "get_xml") else None,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_square_geometry(rs_env: Any) -> Dict[str, Any]:
    """Return the frozen B2 geometry measurement for the live simulator state."""
    sim = rs_env.sim
    aperture = square_nut_aperture(rs_env)
    peg = _square_peg_info(rs_env)
    nut_body_id = int(aperture["nut_body_id"])
    peg_body_id = int(peg["peg_body_id"])
    nut_pos, nut_rot = _frame_pose(sim, nut_body_id)

    peg_geom_id = int(peg["peg_geom_id"])
    peg_center = np.asarray(sim.data.geom_xpos[peg_geom_id], dtype=np.float64)
    peg_rot = np.asarray(sim.data.geom_xmat[peg_geom_id], dtype=np.float64).reshape(3, 3)
    peg_half = np.asarray(sim.model.geom_size[peg_geom_id], dtype=np.float64)[:3]
    peg_corners_world = _box_corners(peg_center, peg_rot, peg_half)
    peg_corners_local = _world_to_local(peg_corners_world, nut_pos, nut_rot)
    peg_xy = peg_corners_local[:, :2]

    hole_half_x = float(aperture["hole_half_x_m"])
    hole_half_y = float(aperture["hole_half_y_m"])
    gaps = {
        "x_positive": float(hole_half_x - np.max(peg_xy[:, 0])),
        "x_negative": float(hole_half_x + np.min(peg_xy[:, 0])),
        "y_positive": float(hole_half_y - np.max(peg_xy[:, 1])),
        "y_negative": float(hole_half_y + np.min(peg_xy[:, 1])),
    }
    clearance = float(min(gaps.values()))

    peg_center_local = _world_to_local(peg_center, nut_pos, nut_rot)
    peg_top_local_z = float(np.max(peg_corners_local[:, 2]))
    nut_bottom_local_z = float(aperture["nut_bottom_local_z_m"])
    z_gap = float(nut_bottom_local_z - peg_top_local_z)

    relative_rot = nut_rot.T.dot(peg_rot)
    yaw = float(np.arctan2(relative_rot[1, 0], relative_rot[0, 0]))

    # The old world-z quantity is retained only for the audit comparison; it is
    # not used by the stage gate.
    bar_world_corners = [
        _geom_world_corners(sim, int(bar["geom_id"]))
        for bar in aperture["aperture_bars"]
    ]
    nut_bottom_world = float(min(np.min(corners[:, 2]) for corners in bar_world_corners))
    peg_top_world = float(np.max(peg_corners_world[:, 2]))
    world_z_gap = float(nut_bottom_world - peg_top_world)

    r_hole = float(np.hypot(hole_half_x, hole_half_y))
    r_peg = float(np.hypot(peg["peg_half_x_m"], peg["peg_half_y_m"]))
    d_xy = float(np.hypot(peg_center_local[0], peg_center_local[1]))

    geometry: Dict[str, Any] = {
        "stage_gate_version": STAGE_GATE_VERSION,
        "clearance_m": clearance,
        "clearance_x_positive_m": gaps["x_positive"],
        "clearance_x_negative_m": gaps["x_negative"],
        "clearance_y_positive_m": gaps["y_positive"],
        "clearance_y_negative_m": gaps["y_negative"],
        "dx_m": float(peg_center_local[0]),
        "dy_m": float(peg_center_local[1]),
        "d_xy_m": d_xy,
        "relative_yaw_rad": yaw,
        "z_gap_m": z_gap,
        "nut_bottom_local_z_m": nut_bottom_local_z,
        "peg_top_local_z_m": peg_top_local_z,
        "t_nut_m": float(aperture["t_nut_m"]),
        "nut_collision_thickness_m": float(aperture["nut_collision_thickness_m"]),
        "r_hole_m": r_hole,
        "r_peg_m": r_peg,
        "hole_half_x_m": hole_half_x,
        "hole_half_y_m": hole_half_y,
        "peg_half_x_m": float(peg["peg_half_x_m"]),
        "peg_half_y_m": float(peg["peg_half_y_m"]),
        "peg_half_z_m": float(peg["peg_half_z_m"]),
        "xy_center_distance_m": d_xy,
        "world_z_gap_naive_m": world_z_gap,
        "world_vs_local_z_gap_difference_m": float(world_z_gap - z_gap),
        "nut_body_id": nut_body_id,
        "peg_body_id": peg_body_id,
        "peg_geom_id": peg_geom_id,
        "aperture_bar_geom_ids": list(aperture["aperture_bar_geom_ids"]),
        "handle_geom_ids": list(aperture["handle_geom_ids"]),
        "nut_geom_ids": list(aperture["nut_geom_ids"]),
        "geometry_fingerprint": _geometry_fingerprint(aperture, peg, sim),
    }
    for key, value in geometry.items():
        if isinstance(value, float) and not np.isfinite(value):
            raise GeometryError("Non-finite geometry value {}={}".format(key, value))
    return geometry


def compute_square_clearance(rs_env: Any) -> Dict[str, float]:
    """Backward-compatible alias for the full B2 geometry measurement."""
    return compute_square_geometry(rs_env)


def evaluate_stage_gate(
    current: Mapping[str, Any],
    previous_z_gap_m: Optional[float] = None,
) -> Dict[str, Any]:
    """Apply the frozen geometry-derived pre-insertion stage gate.

    All conditions must hold:
        0 < z_gap_m <= t_nut_m
        d_xy_m <= r_hole_m + r_peg_m
        z_gap_current < z_gap_previous
    """
    z_gap = float(current["z_gap_m"])
    t_nut = float(current["t_nut_m"])
    d_xy = float(current["d_xy_m"])
    radius_sum = float(current["r_hole_m"]) + float(current["r_peg_m"])
    previous = None if previous_z_gap_m is None else float(previous_z_gap_m)
    conditions = {
        "positive_axial_gap": bool(0.0 < z_gap),
        "within_nut_thickness": bool(z_gap <= t_nut),
        "within_projected_envelope": bool(d_xy <= radius_sum),
        "approaching": bool(previous is not None and z_gap < previous),
    }
    return {
        "stage_gate_version": STAGE_GATE_VERSION,
        "eligible": bool(all(conditions.values())),
        "conditions": conditions,
        "z_gap_m": z_gap,
        "previous_z_gap_m": previous,
        "t_nut_m": t_nut,
        "d_xy_m": d_xy,
        "r_hole_m": float(current["r_hole_m"]),
        "r_peg_m": float(current["r_peg_m"]),
        "r_hole_plus_r_peg_m": radius_sum,
        "clearance_m": float(current["clearance_m"]),
    }


def _free_joint_qpos_address(sim: Any, body_id: int) -> int:
    model = sim.model
    joint_count = int(model.body_jntnum[body_id])
    if joint_count < 1:
        raise GeometryError("Nut body {} has no free joint".format(body_id))
    joint_id = int(model.body_jntadr[body_id])
    if int(model.jnt_type[joint_id]) != _MJ_JNT_FREE:
        raise GeometryError("Nut body {} is not attached by a free joint".format(body_id))
    return int(model.jnt_qposadr[joint_id])


def _set_nut_pose(sim: Any, body_id: int, position: Sequence[float], quat_wxyz: Sequence[float]) -> None:
    address = _free_joint_qpos_address(sim, body_id)
    qpos = np.array(sim.data.qpos, copy=True)
    qpos[address:address + 3] = np.asarray(position, dtype=np.float64)
    qpos[address + 3:address + 7] = np.asarray(quat_wxyz, dtype=np.float64)
    sim.data.qpos[:] = qpos
    sim.forward()


def _quat_z(yaw: float) -> List[float]:
    return [float(np.cos(yaw / 2.0)), 0.0, 0.0, float(np.sin(yaw / 2.0))]


def _quat_x(angle: float) -> List[float]:
    return [float(np.cos(angle / 2.0)), float(np.sin(angle / 2.0)), 0.0, 0.0]


def _live_sign_checks(rs_env: Any, aperture: Mapping[str, Any], peg: Mapping[str, Any]) -> Dict[str, Any]:
    sim = rs_env.sim
    nut_body_id = int(aperture["nut_body_id"])
    peg_geom_id = int(peg["peg_geom_id"])
    peg_center = np.asarray(sim.data.geom_xpos[peg_geom_id], dtype=np.float64)
    peg_corners = _geom_world_corners(sim, peg_geom_id)
    peg_top_world = float(np.max(peg_corners[:, 2]))
    t_nut = float(aperture["t_nut_m"])
    hole_half_x = float(aperture["hole_half_x_m"])
    peg_half_x = float(peg["peg_half_x_m"])

    qpos_before = np.array(sim.data.qpos, copy=True)
    qvel_before = np.array(sim.data.qvel, copy=True)
    checks: Dict[str, Any] = {}
    try:
        center_z = peg_top_world + 0.05 + 0.5 * t_nut
        safe_x = float(peg_center[0])
        safe_y = float(peg_center[1])

        # c_xy positive / zero / negative.
        lateral = {}
        for label, offset in (
            ("positive", 0.0),
            ("zero", hole_half_x - peg_half_x),
            ("negative", hole_half_x - peg_half_x + 0.01),
        ):
            _set_nut_pose(sim, nut_body_id, [safe_x + offset, safe_y, center_z], _quat_z(0.0))
            geometry = compute_square_geometry(rs_env)
            lateral[label] = {
                "nut_x_offset_m": float(offset),
                "clearance_m": float(geometry["clearance_m"]),
                "dx_m": float(geometry["dx_m"]),
                "dy_m": float(geometry["dy_m"]),
                "z_gap_m": float(geometry["z_gap_m"]),
            }
        checks["c_xy_sign"] = lateral

        # z_gap positive / zero / negative.
        axial = {}
        for label, gap in (("positive", 0.01), ("zero", 0.0), ("negative", -0.01)):
            _set_nut_pose(
                sim, nut_body_id,
                [safe_x, safe_y, peg_top_world + 0.5 * t_nut + gap],
                _quat_z(0.0),
            )
            geometry = compute_square_geometry(rs_env)
            axial[label] = {
                "requested_z_gap_m": float(gap),
                "z_gap_m": float(geometry["z_gap_m"]),
                "world_z_gap_naive_m": float(geometry["world_z_gap_naive_m"]),
            }
        checks["z_gap_sign"] = axial

        # Tilted nut: the nut-local formula must differ from the old world-z
        # shortcut.  This is the frame-convention audit required by the protocol.
        _set_nut_pose(
            sim, nut_body_id,
            [safe_x, safe_y, peg_top_world + 0.08],
            _quat_x(np.deg2rad(30.0)),
        )
        tilted = compute_square_geometry(rs_env)
        checks["tilted_frame"] = {
            "tilt_deg": 30.0,
            "z_gap_nut_local_m": float(tilted["z_gap_m"]),
            "z_gap_world_naive_m": float(tilted["world_z_gap_naive_m"]),
            "difference_m": float(tilted["world_vs_local_z_gap_difference_m"]),
            "clearance_m": float(tilted["clearance_m"]),
        }
    finally:
        sim.data.qpos[:] = qpos_before
        sim.data.qvel[:] = qvel_before
        sim.forward()

    checks["interpretation"] = {
        "positive_clearance": "projected peg rectangle fits inside the aperture",
        "zero_clearance": "projected boundary contact",
        "negative_clearance": "at least one projected aperture half-space is violated",
        "positive_z_gap": "peg tip below and separated from the nut lower aperture plane",
        "negative_z_gap": "axial overlap",
        "frame": "nut-local +z; z_gap = nut_bottom_local_z - peg_top_local_z",
    }
    return checks


def _finite_checks(rs_env: Any, steps: int = 5) -> Dict[str, Any]:
    records = []
    for index in range(int(steps)):
        geometry = compute_square_geometry(rs_env)
        records.append({
            "step": int(index),
            "clearance_m": float(geometry["clearance_m"]),
            "z_gap_m": float(geometry["z_gap_m"]),
            "d_xy_m": float(geometry["d_xy_m"]),
            "finite": bool(all(np.isfinite(float(geometry[key])) for key in (
                "clearance_m", "z_gap_m", "d_xy_m", "relative_yaw_rad",
                "t_nut_m", "r_hole_m", "r_peg_m",
            ))),
        })
        rs_env.step(np.zeros(7, dtype=np.float64))
    return {
        "n_states": len(records),
        "all_finite": bool(all(item["finite"] for item in records)),
        "states": records,
    }


def run_live_geometry_audit(
    rs_env: Any,
    output_path: Any,
    representative_states: Optional[Sequence[Mapping[str, Any]]] = None,
    finite_steps: int = 5,
) -> Dict[str, Any]:
    """Run the hard B2 live geometry audit and write ``b2_geometry_audit.json``.

    Any ambiguous collision-geom identification, frame convention or sign test
    produces ``status=BLOCKED``; no center-distance approximation is used.
    """
    from pathlib import Path

    audit: Dict[str, Any] = {
        "audit": "B2_LIVE_GEOMETRY_AUDIT",
        "marker": "PREFLIGHT",
        "stage_gate_version": STAGE_GATE_VERSION,
        "scientific_data": False,
        "status": "BLOCKED",
    }
    try:
        sim = rs_env.sim
        aperture = square_nut_aperture(rs_env)
        peg = _square_peg_info(rs_env)
        reset_geometry = compute_square_geometry(rs_env)
        sign_checks = _live_sign_checks(rs_env, aperture, peg)
        finite = _finite_checks(rs_env, steps=finite_steps)

        audit.update({
            "environment": {
                "env_name": type(rs_env).__name__,
                "robosuite_version": getattr(__import__("robosuite"), "__version__", "unknown")
                if __import__("sys").modules.get("robosuite") else "unknown",
                "mujoco_py_version": getattr(__import__("mujoco_py"), "__version__", "unknown")
                if __import__("sys").modules.get("mujoco_py") else "unknown",
                "nbody": int(sim.model.nbody),
                "ngeom": int(sim.model.ngeom),
                "model_xml_sha256": hashlib.sha256(
                    str(sim.model.get_xml()).encode("utf-8")
                ).hexdigest() if hasattr(sim.model, "get_xml") else None,
            },
            "nut": aperture,
            "peg": peg,
            "frame_convention": {
                "frame": "SquareNut body frame (nut-local)",
                "z_axis": "nut-local +z",
                "projected_clearance": (
                    "min(hole_half_x - max(peg_xy_x), hole_half_x + min(peg_xy_x), "
                    "hole_half_y - max(peg_xy_y), hole_half_y + min(peg_xy_y))"
                ),
                "axial_gap": "nut_bottom_local_z - peg_top_local_z",
                "positive_z": "peg tip below the nut lower aperture plane",
                "negative_z": "axial overlap",
                "world_z_retained_as": "world_z_gap_naive_m (audit comparison only; not used by the gate)",
            },
            "collision_geometry": {
                "nut_collision_boxes": aperture["nut_geom_ids"],
                "aperture_bars_exactly_four": len(aperture["aperture_bar_geom_ids"]) == 4,
                "handle_boxes_excluded": aperture["handle_geom_ids"],
                "peg_collision_geoms": peg["peg_collision_geom_ids"],
                "peg_geom_correctly_identified": len(peg["peg_collision_geom_ids"]) >= 1,
                "visual_collision_identical": peg["visual_collision_identical"],
                "visual_geom_sizes_m": peg["peg_visual_sizes_m"],
                "collision_geom_sizes_m": peg["peg_size_m"],
            },
            "reset_geometry": reset_geometry,
            "sign_checks": sign_checks,
            "finite_checks": finite,
            "representative_states": list(representative_states or []),
        })

        expected = {
            "clearance_positive": sign_checks["c_xy_sign"]["positive"]["clearance_m"] > 0.0,
            "clearance_zero": abs(sign_checks["c_xy_sign"]["zero"]["clearance_m"]) <= 1e-9,
            "clearance_negative": sign_checks["c_xy_sign"]["negative"]["clearance_m"] < 0.0,
            "z_positive": sign_checks["z_gap_sign"]["positive"]["z_gap_m"] > 0.0,
            "z_zero": abs(sign_checks["z_gap_sign"]["zero"]["z_gap_m"]) <= 1e-9,
            "z_negative": sign_checks["z_gap_sign"]["negative"]["z_gap_m"] < 0.0,
            "tilted_local_differs_from_world": abs(
                sign_checks["tilted_frame"]["difference_m"]
            ) > 1e-4,
            "finite": bool(finite["all_finite"]),
        }
        audit["sign_checks"]["expected"] = {key: bool(value) for key, value in expected.items()}
        audit["status"] = "PASS" if all(expected.values()) else "BLOCKED"
        if audit["status"] != "PASS":
            audit["reason"] = "One or more live geometry sign/finiteness checks failed"
    except Exception as exc:
        audit["status"] = "BLOCKED"
        audit["reason"] = "{}: {}".format(type(exc).__name__, exc)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return audit
