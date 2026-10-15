"""Config parsing tests for Tesla GlareGuard."""
import os

import pytest

from tesla_glareguard.config import ConfigError, load_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in list(os.environ):
        if var.startswith("TGG_"):
            monkeypatch.delenv(var, raising=False)


def test_defaults(monkeypatch):
    s = load_settings()
    assert s.model == "3"
    assert s.year == 2022
    assert s.driver_height_cm == 175.0
    assert s.seat_rail == 0.5
    assert s.drive_side == "LHD"
    assert s.follow_distance_m == 8.0
    assert s.drop_cm == 15.0
    assert s.restore_seconds == 60
    assert s.mirror == "driver"
    assert s.ntfy_topic == ""
    assert s.gain == 1.0


def test_model_normalization(monkeypatch):
    monkeypatch.setenv("TGG_MODEL", "Model Y")
    assert load_settings().model == "y"
    monkeypatch.setenv("TGG_MODEL", "CYBERTRUCK")
    assert load_settings().model == "cybertruck"


def test_invalid_model(monkeypatch):
    monkeypatch.setenv("TGG_MODEL", "roadster")
    with pytest.raises(ConfigError):
        load_settings()


def test_year_bounds(monkeypatch):
    monkeypatch.setenv("TGG_YEAR", "2011")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("TGG_YEAR", "2026")
    assert load_settings().year == 2026


def test_height_bounds(monkeypatch):
    monkeypatch.setenv("TGG_DRIVER_HEIGHT_CM", "139")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("TGG_DRIVER_HEIGHT_CM", "221")
    with pytest.raises(ConfigError):
        load_settings()


def test_seat_rail_bounds(monkeypatch):
    monkeypatch.setenv("TGG_SEAT_RAIL", "1.5")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("TGG_SEAT_RAIL", "-0.1")
    with pytest.raises(ConfigError):
        load_settings()


def test_drive_side(monkeypatch):
    monkeypatch.setenv("TGG_DRIVE_SIDE", "rhd")
    assert load_settings().drive_side == "RHD"
    monkeypatch.setenv("TGG_DRIVE_SIDE", "middle")
    with pytest.raises(ConfigError):
        load_settings()


def test_mirror_selection(monkeypatch):
    monkeypatch.setenv("TGG_MIRROR", "both")
    assert load_settings().mirror == "both"
    monkeypatch.setenv("TGG_MIRROR", "all")
    with pytest.raises(ConfigError):
        load_settings()


def test_follow_distance_and_drop_bounds(monkeypatch):
    monkeypatch.setenv("TGG_FOLLOW_DISTANCE_M", "1")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("TGG_FOLLOW_DISTANCE_M", "61")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.delenv("TGG_FOLLOW_DISTANCE_M")
    monkeypatch.setenv("TGG_DROP_CM", "4")
    with pytest.raises(ConfigError):
        load_settings()


def test_gain_bounds(monkeypatch):
    monkeypatch.setenv("TGG_GAIN", "0.24")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("TGG_GAIN", "3.01")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("TGG_GAIN", "1.5")
    assert load_settings().gain == 1.5


def test_non_numeric_rejected(monkeypatch):
    monkeypatch.setenv("TGG_DRIVER_HEIGHT_CM", "tall")
    with pytest.raises(ConfigError):
        load_settings()
