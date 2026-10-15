"""End-to-end simulation test for Tesla GlareGuard.

Replays the virtual night drive independently of the simulator's own
printing and asserts the core invariant: every deflect moves the computed
glare spot at least drop_cm below the eye point, and restore returns the
deltas to zero.
"""
import re

import pytest

from tesla_glareguard import glare_geometry as G
from tesla_glareguard.simulator import TIMELINE, run_simulation


def test_simulation_passes():
    assert run_simulation() == "PASS"


def test_simulation_needs_no_network_or_credentials(monkeypatch):
    monkeypatch.delenv("TESLA_CLIENT_ID", raising=False)
    monkeypatch.delenv("TESLA_CLIENT_SECRET", raising=False)
    assert run_simulation() == "PASS"


def test_core_invariant_independent_replay():
    """Independent replay of every dazzle event in TIMELINE."""
    band = G.band_for("y", 2023)
    eye = G.eye_point(1.75, 0.5, "LHD", band)
    centers = G.mirror_centers(band, "LHD")
    for ev in TIMELINE:
        if "dazzl" not in ev.note or "no dazzle" in ev.note:
            continue  # only the three real dazzle events
        mirrors = ("driver", "passenger") if ev.mirror == "both" else (ev.mirror,)
        plan = G.deflection_plan(model="y", year=2023, driver_height_cm=175.0,
                                 seat_rail=0.5, drive_side="LHD",
                                 follow_distance_m=ev.follow_m, drop_cm=15.0,
                                 mirrors=mirrors)
        for name in mirrors:
            m = centers[name]
            h = G.headlight_point(eye, m, ev.follow_m)
            n1 = G.apply_plan(h, m, eye, plan["mirrors"][name])
            spot = G.beam_spot_z(h, m, n1, eye[0])
            assert spot <= eye[2] - 0.15 + 0.001, (
                f"{ev.at} {name}: spot {spot:.3f} not >= 15cm below eye {eye[2]:.3f}")


def test_restore_zeroes_deltas():
    plan = G.deflection_plan(model="y", year=2023, driver_height_cm=175.0,
                             seat_rail=0.5, drive_side="LHD",
                             follow_distance_m=8.0, drop_cm=15.0,
                             gain=0.0, mirrors=("driver", "passenger"))
    for p in plan["mirrors"].values():
        assert abs(p["pan_deg"]) < 1e-9 and abs(p["tilt_deg"]) < 1e-9


def test_timeline_covers_both_mirrors_and_restore():
    notes = " ".join(ev.note for ev in TIMELINE)
    assert "LEFT mirror" in notes and "RIGHT mirror" in notes
    assert any("restore" in ev.note for ev in TIMELINE)
