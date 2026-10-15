"""Actuator + calibration-state tests for Tesla GlareGuard."""
import json
import os

import pytest

from tesla_glareguard.actuator import (
    FleetApiActuator,
    GuideActuator,
    guide_text,
    load_gain,
    restore_text,
    save_gain,
)


def _plan():
    return {"mirrors": {
        "driver": {"pan_deg": 0.3, "tilt_deg": 5.0, "clamped": False},
        "passenger": {"pan_deg": -1.2, "tilt_deg": -2.5, "clamped": True},
    }}


def test_guide_text_directions():
    text = guide_text(_plan())
    assert "driver-side mirror: tilt UP 5.0°, pan OUT 0.3°" in text
    assert "passenger-side mirror: tilt DOWN 2.5°, pan IN 1.2°" in text
    assert "re-aim by hand" in text  # clamped warning shown


def test_restore_text_is_inverse():
    text = restore_text(_plan())
    assert "driver-side mirror: tilt DOWN 5.0°, pan IN 0.3°" in text
    assert "back to normal" in text


def test_deflect_restore_cycle(tmp_path):
    state = str(tmp_path / "state.json")
    act = GuideActuator()
    out = act.deflect(_plan(), state_file=state, restore_seconds=60)
    assert "tilt UP 5.0°" in out
    saved = json.loads(open(state).read())
    assert saved["active"] is True
    assert saved["plan"]["mirrors"]["driver"]["tilt_deg"] == 5.0
    assert "restore" in act.status(state_file=state).lower()

    out = act.restore(state_file=state)
    assert "tilt DOWN 5.0°" in out
    assert json.loads(open(state).read())["active"] is False


def test_restore_without_deflect(tmp_path):
    state = str(tmp_path / "state.json")
    assert "No active deflection" in GuideActuator().restore(state_file=state)


def test_deflect_preserves_calibrated_gain(tmp_path):
    state = str(tmp_path / "state.json")
    save_gain(state, 1.5)
    GuideActuator().deflect(_plan(), state_file=state, restore_seconds=60)
    GuideActuator().restore(state_file=state)
    assert load_gain(state) == pytest.approx(1.5)


def test_gain_round_trip(tmp_path):
    state = str(tmp_path / "state.json")
    assert load_gain(state) == 1.0  # default when no state file
    save_gain(state, 1.25)
    assert load_gain(state) == pytest.approx(1.25)


def test_fleet_actuator_is_honest():
    act = FleetApiActuator()
    with pytest.raises(NotImplementedError) as exc:
        act.deflect({}, state_file="/tmp/x.json", restore_seconds=60)
    msg = str(exc.value).lower()
    assert "no" in msg and "mirror" in msg and "fleet api" in msg
    with pytest.raises(NotImplementedError):
        act.restore(state_file="/tmp/x.json")
