"""Pure dazzle-deflection geometry for Tesla GlareGuard. No network, no I/O.

Car frame: x = forward, y = left, z = up. Origin at ground level under the
driver's hip reference point.

Problem: a driver behind you has their brights on. The beam enters your side
mirror at M from the following car's headlight at H, and the mirror (as you
have it adjusted) reflects it into your eye at E. We compute how to pivot the
mirror so the beam lands at target T = E shifted DOWN by TGG_DROP_CM instead.

Law of reflection: rotating a mirror by angle psi rotates its reflected ray
by ~2*psi about the same axis (the doubling law). So to swing the reflected
beam from the eye E to the target T, the mirror normal must rotate from the
bisector of (incident, E) to the bisector of (incident, T) — the code
computes that rotation exactly and decomposes it into human-friendly pan
(about the vertical z axis, positive = outward, away from the car) and tilt
(about the lateral y axis, positive = face tips UP, the same motion as a
manual day/night rearview tab — tilting the face up sends the bright
reflection down to the road instead of your eyes).

IMPORTANT HONESTY NOTE: every mirror anchor in MIRROR_GEOMETRY is an
ESTIMATE derived from published overall vehicle dimensions (width/height),
not a measured CAD value. Per-driver differences (seat height, torso length,
how you adjusted your mirrors) dominate the residual error, which is why
`tgg calibrate` exists — it tunes TGG_GAIN against your own feedback.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Vehicle geometry table (ESTIMATES — see module docstring).
# mirror: center of the side-mirror glass (x fwd, y left, z up), meters.
# eye: seat-cushion height above ground + fore-aft travel of the eye point
#      as the seat rail moves 0 (fully back) -> 1 (fully forward).
# ---------------------------------------------------------------------------
# Band format: (first_year, last_year_or_None, band_dict)
MIRROR_GEOMETRY = {
    "3": {
        "label": "Model 3",
        "bands": [
            (2017, 2023, {
                "mirror": {"x": 0.55, "y": 0.98, "z": 1.16, "half_width_m": 0.085},
                "eye": {"cushion_z": 0.60, "x_fwd": 0.02, "x_back": -0.28},
            }),
            (2024, None, {  # Highland — frameless mirrors, no auto-dim per owner reports
                "mirror": {"x": 0.55, "y": 0.98, "z": 1.16, "half_width_m": 0.085},
                "eye": {"cushion_z": 0.60, "x_fwd": 0.02, "x_back": -0.28},
            }),
        ],
    },
    "y": {
        "label": "Model Y",
        "bands": [
            (2020, 2024, {
                "mirror": {"x": 0.58, "y": 1.01, "z": 1.24, "half_width_m": 0.09},
                "eye": {"cushion_z": 0.66, "x_fwd": 0.02, "x_back": -0.28},
            }),
            (2025, None, {  # Juniper refresh
                "mirror": {"x": 0.58, "y": 1.01, "z": 1.24, "half_width_m": 0.09},
                "eye": {"cushion_z": 0.66, "x_fwd": 0.02, "x_back": -0.28},
            }),
        ],
    },
    "s": {
        "label": "Model S",
        "bands": [
            (2012, 2020, {
                "mirror": {"x": 0.60, "y": 1.04, "z": 1.20, "half_width_m": 0.095},
                "eye": {"cushion_z": 0.58, "x_fwd": 0.03, "x_back": -0.27},
            }),
            (2021, None, {  # Palladium refresh
                "mirror": {"x": 0.60, "y": 1.04, "z": 1.20, "half_width_m": 0.095},
                "eye": {"cushion_z": 0.58, "x_fwd": 0.03, "x_back": -0.27},
            }),
        ],
    },
    "x": {
        "label": "Model X",
        "bands": [
            (2015, 2020, {
                "mirror": {"x": 0.62, "y": 1.08, "z": 1.32, "half_width_m": 0.095},
                "eye": {"cushion_z": 0.70, "x_fwd": 0.03, "x_back": -0.27},
            }),
            (2021, None, {  # Palladium refresh
                "mirror": {"x": 0.62, "y": 1.08, "z": 1.32, "half_width_m": 0.095},
                "eye": {"cushion_z": 0.70, "x_fwd": 0.03, "x_back": -0.27},
            }),
        ],
    },
    "cybertruck": {
        "label": "Cybertruck",
        "bands": [
            (2024, None, {
                "mirror": {"x": 0.66, "y": 1.10, "z": 1.46, "half_width_m": 0.10},
                "eye": {"cushion_z": 0.78, "x_fwd": 0.04, "x_back": -0.26},
            }),
        ],
    },
}

# Maximum single adjustment we will ever suggest, per axis. Beyond this the
# beam geometry has changed enough that the driver should just look away /
# re-aim the mirror themselves; the plan flags a warning instead.
MAX_ADJUST_DEG = 8.0

# Headlight height of a typical following car (m).
HEADLIGHT_Z = 0.75

# Lateral position of the dazzling headlight, as a fraction of the mirror's
# lateral offset (the follower is roughly centered behind you; its headlight
# sits inboard of your mirror).
HEADLIGHT_LATERAL_FRACTION = 0.55


class GeometryError(Exception):
    pass


def band_for(model: str, year: int) -> dict:
    """Return the geometry band for a model + year. Raises GeometryError."""
    try:
        bands = MIRROR_GEOMETRY[model]["bands"]
    except KeyError:
        raise GeometryError(f"unknown model {model!r}")
    for first, last, band in bands:
        if year >= first and (last is None or year <= last):
            return band
    raise GeometryError(
        f"no geometry band for model {model!r} year {year} "
        f"(supported: {MIRROR_GEOMETRY[model]['label']})"
    )


def eye_point(height_m: float, rail: float, drive_side: str, band: dict) -> tuple[float, float, float]:
    """Driver eye position (x fwd, y left, z up), meters.

    Sitting eye height ~0.46 x standing height above the seat cushion;
    cushion z + rail 0..1 -> fore-aft; lateral +/-0.38 m by drive side.
    """
    eye = band["eye"]
    z = eye["cushion_z"] + 0.46 * height_m
    x = eye["x_back"] + rail * (eye["x_fwd"] - eye["x_back"])
    y = 0.38 if drive_side == "LHD" else -0.38
    return (x, y, z)


def mirror_centers(band: dict, drive_side: str) -> dict[str, tuple[float, float, float]]:
    """Mirror glass centers keyed 'driver' / 'passenger'."""
    m = band["mirror"]
    driver_y = m["y"] if drive_side == "LHD" else -m["y"]
    return {
        "driver": (m["x"], driver_y, m["z"]),
        "passenger": (m["x"], -driver_y, m["z"]),
    }


def headlight_point(eye: tuple[float, float, float],
                    mirror: tuple[float, float, float],
                    follow_distance_m: float) -> tuple[float, float, float]:
    """Estimated position of the dazzling headlight (behind, inboard, 0.75 m)."""
    side = 1.0 if mirror[1] >= 0 else -1.0
    return (
        eye[0] - follow_distance_m,
        side * HEADLIGHT_LATERAL_FRACTION * abs(mirror[1]),
        HEADLIGHT_Z,
    )


# -- vector helpers ---------------------------------------------------------
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _scale(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
)
def _norm(a):
    n = math.sqrt(_dot(a, a))
    if n == 0:
        raise GeometryError("zero-length vector in glare geometry")
    return _scale(a, 1.0 / n)


def reflect(direction: tuple[float, float, float],
            normal: tuple[float, float, float]) -> tuple[float, float, float]:
    """Reflect an incoming unit vector off a plane with unit `normal`."""
    d, n = _norm(direction), _norm(normal)
    return _sub(d, _scale(n, 2.0 * _dot(d, n)))


def mirror_normal_for_eye(headlight, mirror, eye) -> tuple[float, float, float]:
    """The mirror normal that would reflect the headlight beam exactly at E.

    This models the 'currently dazzled' state: the driver sees the bright
    reflection centered in the mirror, i.e. the mirror normal bisects the
    incoming beam and the eye direction.
    """
    d = _norm(_sub(mirror, headlight))   # headlight -> mirror
    r = _norm(_sub(eye, mirror))          # mirror -> eye
    # reflect(d, norm(d - r)) == r  (sign matters: norm(d + r) reflects to -r)
    return _norm(_sub(d, r))


def rotate_about_axis(vec, axis, angle_rad):
    """Rotate vector `vec` about unit `axis` by `angle_rad` (Rodrigues)."""
    a = _norm(axis)
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return _add(
        _add(_scale(vec, c), _scale(_cross(a, vec), s)),
        _scale(a, _dot(a, vec) * (1.0 - c)),
    )


def _fit_pan_tilt(n0, n1_exact, outward, pan_init_deg, tilt_init_deg):
    """Refine (pan, tilt) so the human-executable adjustment best matches the
    exact required mirror normal.

    A person can only pan (about z) and tilt (about y) a side mirror — there
    is no roll control. The naive rotation-vector decomposition drops the
    roll component of the true 3-D rotation, so we hill-climb from it to the
    (rz, ry) pair minimizing the angle between R_y(ry)R_z(rz)n0 and n1_exact.
    Returns (pan_deg, tilt_deg) in the guide sign convention (gain NOT applied).
    """
    def err(rz, ry):
        n = rotate_about_axis(rotate_about_axis(n0, (0.0, 0.0, 1.0), rz),
                              (0.0, 1.0, 0.0), ry)
        return math.acos(max(-1.0, min(1.0, _dot(n, n1_exact))))

    best = (math.radians(pan_init_deg) / outward, -math.radians(tilt_init_deg))
    best_err = err(*best)
    step = math.radians(0.5)
    # 8-direction moves (incl. diagonals): coordinate descent stalls on ridges.
    dirs = [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
            (1.0, 1.0), (1.0, -1.0), (-1.0, 1.0), (-1.0, -1.0)]
    for _ in range(2000):
        improved = False
        for dx, dy in dirs:
            cand = (best[0] + dx * step, best[1] + dy * step)
            e = err(*cand)
            if e < best_err:
                best, best_err, improved = cand, e, True
        if not improved:
            step *= 0.5
            if step < math.radians(1e-6):
                break
    rz, ry = best
    return outward * math.degrees(rz), -math.degrees(ry)


def beam_spot_z(headlight, mirror, normal, plane_x: float) -> float:
    """Where the reflected beam crosses the vertical plane x = plane_x.

    Returns the z (height) of the spot — the quantity the deflection plan
    moves below the driver's eyes.
    """
    d = _norm(_sub(mirror, headlight))
    r = reflect(d, normal)
    if abs(r[0]) < 1e-9:
        raise GeometryError("reflected beam parallel to eye plane")
    t = (plane_x - mirror[0]) / r[0]
    return mirror[2] + t * r[2]


# -- main plan --------------------------------------------------------------
def deflection_plan(*, model: str, year: int, driver_height_cm: float,
                    seat_rail: float, drive_side: str,
                    follow_distance_m: float, drop_cm: float,
                    gain: float = 1.0, mirrors: tuple[str, ...] = ("driver",),
                    ) -> dict:
    """Compute the per-mirror deflection plan.

    Returns {"mirrors": {"driver": {...}, ...}, "eye": ..., "target": ...}.
    Each mirror entry: pan_deg (positive = outward), tilt_deg (positive =
    face tips UP), clamped to +/-8 deg, with `clamped` flag and the raw
    values. Multiplied by `gain` (calibration).
    """
    band = band_for(model, year)
    eye = eye_point(driver_height_cm / 100.0, seat_rail, drive_side, band)
    target = (eye[0], eye[1], eye[2] - drop_cm / 100.0)
    centers = mirror_centers(band, drive_side)

    plans: dict[str, dict] = {}
    for name in mirrors:
        if name not in centers:
            raise GeometryError(f"unknown mirror {name!r}")
        m = centers[name]
        h = headlight_point(eye, m, follow_distance_m)

        d = _norm(_sub(m, h))             # headlight -> mirror (incident ray)
        r_eye = _norm(_sub(eye, m))       # mirror -> eye (current reflected ray)
        r_tgt = _norm(_sub(target, m))    # mirror -> target (desired reflected ray)

        # Mirror normals that would send the beam at the eye / at the target.
        n0 = _norm(_sub(d, r_eye))
        n1 = _norm(_sub(d, r_tgt))

        cos_psi = max(-1.0, min(1.0, _dot(n0, n1)))
        psi = math.acos(cos_psi)           # required mirror rotation (radians)
        cos_theta = max(-1.0, min(1.0, _dot(r_eye, r_tgt)))
        theta = math.acos(cos_theta)      # required swing of the reflected ray

        if psi < 1e-6:
            pan, tilt = 0.0, 0.0
        else:
            axis = _norm(_cross(n0, n1))
            # Law of reflection (exact form): the mirror rotates from n0 to
            # n1; psi -> theta/2 as the angles shrink (the doubling law).
            rot = _scale(axis, psi)                 # rotation vector, radians
            # Initial guess: decompose the rotation vector — pan about
            # vertical z (positive = outward), tilt about lateral y
            # (positive = face tips up).
            outward = -1.0 if m[1] >= 0 else 1.0    # left mirror: +z rot is inward
            pan0 = outward * math.degrees(rot[2])
            tilt0 = -math.degrees(rot[1])           # +y rot tips face down
            # Refine: a human can only pan+tilt (no roll), so fit the best
            # (pan, tilt) pair against the exact required normal.
            pan, tilt = _fit_pan_tilt(n0, n1, outward, pan0, tilt0)
            pan *= gain
            tilt *= gain

        clamped = False
        pan_raw, tilt_raw = pan, tilt
        if abs(pan) > MAX_ADJUST_DEG:
            pan = math.copysign(MAX_ADJUST_DEG, pan)
            clamped = True
        if abs(tilt) > MAX_ADJUST_DEG:
            tilt = math.copysign(MAX_ADJUST_DEG, tilt)
            clamped = True

        plans[name] = {
            "mirror_xyz": m,
            "pan_deg": round(pan, 1),
            "tilt_deg": round(tilt, 1),
            "pan_raw_deg": round(pan_raw, 2),
            "tilt_raw_deg": round(tilt_raw, 2),
            "ray_swing_deg": round(math.degrees(theta), 2),
            "clamped": clamped,
        }

    return {
        "mirrors": plans,
        "eye": tuple(round(v, 3) for v in eye),
        "target": tuple(round(v, 3) for v in target),
        "estimated_geometry": True,   # always: anchors are estimates, never measured
    }


def apply_plan(headlight, mirror, eye, plan: dict) -> tuple[float, float, float]:
    """Return the mirror normal after applying a plan (for verification).

    Rotates the dazzled-state normal by the plan's pan (about z) and tilt
    (about y), in the same sign convention deflection_plan uses.
    """
    n = mirror_normal_for_eye(headlight, mirror, eye)
    outward = -1.0 if mirror[1] >= 0 else 1.0
    # Use raw (unrounded) values when present — rounding is for display only.
    pan_deg = plan.get("pan_raw_deg", plan["pan_deg"])
    tilt_deg = plan.get("tilt_raw_deg", plan["tilt_deg"])
    # invert the decomposition: pan positive=outward -> z-rotation = pan/outward
    rz = math.radians(pan_deg) / outward
    ry = -math.radians(tilt_deg)          # tilt positive=up -> -y rotation
    n = rotate_about_axis(n, (0.0, 0.0, 1.0), rz)
    n = rotate_about_axis(n, (0.0, 1.0, 0.0), ry)
    return n
