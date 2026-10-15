"""Geometry tests for Tesla GlareGuard.

The physics under test: with the dazzled-state mirror normal (the normal
that reflects the follower's headlight beam exactly at the driver's eye),
applying the plan must move the reflected spot to the target below the eye.
"""
import math

import pytest

from tesla_glareguard import glare_geometry as G


def _std_plan(**kw):
    args = dict(model="y", year=2023, driver_height_cm=175.0, seat_rail=0.5,
                drive_side="LHD", follow_distance_m=8.0, drop_cm=15.0,
                gain=1.0, mirrors=("driver",))
    args.update(kw)
    return G.deflection_plan(**args)


def _scene(model="y", year=2023, follow=8.0, mirror="driver"):
    band = G.band_for(model, year)
    eye = G.eye_point(1.75, 0.5, "LHD", band)
    m = G.mirror_centers(band, "LHD")[mirror]
    h = G.headlight_point(eye, m, follow)
    return eye, m, h


# -- low-level optics -------------------------------------------------------
def test_reflect_straight_on():
    r = G.reflect((0, 0, -1), (0, 0, 1))
    assert r == pytest.approx((0, 0, 1))


def test_reflect_45_deg_hand_computed():
    # Beam along +x hits a 45-degree mirror; must leave along +z.
    n = G._norm((-1, 0, 1))
    r = G.reflect((1, 0, 0), n)
    assert r == pytest.approx((0, 0, 1), abs=1e-9)


def test_dazzled_normal_reflects_to_eye():
    eye, m, h = _scene()
    n = G.mirror_normal_for_eye(h, m, eye)
    spot_z = G.beam_spot_z(h, m, n, eye[0])
    assert spot_z == pytest.approx(eye[2], abs=1e-9)


def test_beam_spot_simple_hand_computed():
    # Headlight 8 m behind mirror, mirror 1 m up, eye level with mirror:
    # beam crosses the eye plane at mirror height.
    h, m, eye = (-8, 0, 0.75), (0, 0, 1.0), (-0.7, 0, 1.0)
    n = G.mirror_normal_for_eye(h, m, eye)
    assert G.beam_spot_z(h, m, n, eye[0]) == pytest.approx(1.0, abs=1e-9)


# -- vehicle table ----------------------------------------------------------
def test_band_for_year_bands():
    assert G.band_for("3", 2022) is G.band_for("3", 2017)
    assert G.band_for("3", 2024) is not G.band_for("3", 2023)  # Highland split
    assert G.band_for("y", 2025) is not G.band_for("y", 2024)  # Juniper split
    assert G.band_for("cybertruck", 2024)["mirror"]["z"] > 1.3


def test_band_for_unknown():
    with pytest.raises(G.GeometryError):
        G.band_for("roadster", 2025)
    with pytest.raises(G.GeometryError):
        G.band_for("3", 2010)


def test_all_bands_marked_estimated():
    plan = _std_plan(mirrors=("driver", "passenger"))
    assert plan["estimated_geometry"] is True


# -- eye point --------------------------------------------------------------
def test_eye_point_height_scales():
    band = G.band_for("y", 2023)
    low = G.eye_point(1.60, 0.5, "LHD", band)
    high = G.eye_point(1.90, 0.5, "LHD", band)
    assert high[2] - low[2] == pytest.approx(0.46 * 0.30, abs=1e-9)


def test_eye_point_rail_moves_forward():
    band = G.band_for("y", 2023)
    back = G.eye_point(1.75, 0.0, "LHD", band)
    fwd = G.eye_point(1.75, 1.0, "LHD", band)
    assert fwd[0] > back[0]


def test_eye_point_drive_side_lateral():
    band = G.band_for("y", 2023)
    lhd = G.eye_point(1.75, 0.5, "LHD", band)
    rhd = G.eye_point(1.75, 0.5, "RHD", band)
    assert lhd[1] == pytest.approx(0.38)
    assert rhd[1] == pytest.approx(-0.38)


# -- plan properties --------------------------------------------------------
def test_plan_moves_beam_down_not_up():
    plan = _std_plan()
    assert plan["mirrors"]["driver"]["tilt_deg"] > 0  # face tips UP -> beam goes down


def test_reflection_doubling_law():
    # The mirror rotates ~half the reflected ray's swing (psi ~= theta/2).
    eye, m, h = _scene()
    plan = _std_plan()
    p = plan["mirrors"]["driver"]
    n0 = G.mirror_normal_for_eye(h, m, eye)
    n1 = G.apply_plan(h, m, eye, p)
    psi = math.acos(max(-1.0, min(1.0, G._dot(n0, n1))))
    theta = math.radians(p["ray_swing_deg"])
    assert psi / theta == pytest.approx(0.5, abs=0.05)


def test_lhd_rhd_symmetry():
    lhd = _std_plan(drive_side="LHD")["mirrors"]["driver"]
    rhd = _std_plan(drive_side="RHD")["mirrors"]["driver"]
    assert lhd["pan_deg"] == pytest.approx(rhd["pan_deg"], abs=1e-9)
    assert lhd["tilt_deg"] == pytest.approx(rhd["tilt_deg"], abs=1e-9)


def test_gain_multiplier_effect():
    base = _std_plan(gain=1.0)["mirrors"]["driver"]
    doubled = _std_plan(gain=2.0)["mirrors"]["driver"]
    # raw values are rounded to 2 dp for display; allow that rounding noise
    assert doubled["tilt_raw_deg"] == pytest.approx(2 * base["tilt_raw_deg"], abs=0.02)
    assert doubled["pan_raw_deg"] == pytest.approx(2 * base["pan_raw_deg"], abs=0.02)


def test_clamp_at_8_deg():
    plan = _std_plan(follow_distance_m=2.0, drop_cm=60.0, gain=3.0)
    p = plan["mirrors"]["driver"]
    assert p["clamped"] is True
    assert abs(p["tilt_deg"]) == 8.0
    assert abs(p["pan_deg"]) <= 8.0


def test_no_clamp_for_normal_case():
    plan = _std_plan()
    assert plan["mirrors"]["driver"]["clamped"] is False


def test_zero_gain_gives_zero_plan():
    plan = _std_plan(gain=0.0, mirrors=("driver", "passenger"))
    for p in plan["mirrors"].values():
        assert p["pan_deg"] == 0.0 and p["tilt_deg"] == 0.0


def test_invalid_mirror_name():
    with pytest.raises(G.GeometryError):
        _std_plan(mirrors=("rearview",))


def test_target_below_eye():
    plan = _std_plan()
    assert plan["target"][2] == pytest.approx(plan["eye"][2] - 0.15, abs=1e-9)


# -- core invariant: spot lands at/below target --------------------------------
@pytest.mark.parametrize("model,year,mirror,follow", [
    ("3", 2022, "driver", 8.0),
    ("3", 2024, "driver", 8.0),
    ("y", 2023, "driver", 8.0),
    ("y", 2025, "passenger", 6.0),
    ("s", 2023, "driver", 10.0),
    ("x", 2022, "passenger", 12.0),
    ("cybertruck", 2025, "driver", 8.0),
])
def test_deflect_moves_spot_below_eye(model, year, mirror, follow):
    band = G.band_for(model, year)
    eye = G.eye_point(1.75, 0.5, "LHD", band)
    m = G.mirror_centers(band, "LHD")[mirror]
    h = G.headlight_point(eye, m, follow)
    plan = G.deflection_plan(model=model, year=year, driver_height_cm=175.0,
                             seat_rail=0.5, drive_side="LHD",
                             follow_distance_m=follow, drop_cm=15.0,
                             mirrors=(mirror,))
    n1 = G.apply_plan(h, m, eye, plan["mirrors"][mirror])
    spot = G.beam_spot_z(h, m, n1, eye[0])
    assert spot <= eye[2] - 0.15 + 0.001  # 1 mm tolerance, see _fit_pan_tilt


def test_restore_returns_spot_to_eye():
    eye, m, h = _scene()
    n0 = G.mirror_normal_for_eye(h, m, eye)
    assert G.beam_spot_z(h, m, n0, eye[0]) == pytest.approx(eye[2], abs=1e-9)
