"""Configuration for Tesla GlareGuard. All settings come from the environment
(see .env.example). Copy .env.example to .env — .env is git-ignored so
nothing sensitive leaves your machine.

Guide mode needs NO car connection and NO Tesla credentials: the deflection
plan is pure geometry computed locally. TGG_* vars describe YOUR car, YOUR
seat, and YOUR driving position.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


VALID_MODELS = ("3", "y", "s", "x", "cybertruck")


@dataclass
class Settings:
    model: str = "3"                 # 3 | y | s | x | cybertruck
    year: int = 2022
    driver_height_cm: float = 175.0
    seat_rail: float = 0.5          # 0 = fully back .. 1 = fully forward
    drive_side: str = "LHD"         # LHD | RHD
    follow_distance_m: float = 8.0  # how far behind the dazzling car is (m)
    drop_cm: float = 15.0           # move the glare spot this far below the eyes (cm)
    restore_seconds: int = 60       # auto-restore after this long
    mirror: str = "driver"          # driver | both
    ntfy_topic: str = ""            # optional: push the guide text to your phone/watch
    gain: float = 1.0               # calibration multiplier (tuned by `tgg calibrate`)
    state_file: str = "~/.config/tesla-glareguard/state.json"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a number")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not an integer")


def load_settings() -> Settings:
    """Read TGG_* vars from the environment. Raises ConfigError on bad values."""
    model = os.environ.get("TGG_MODEL", "3").strip().lower().replace("model", "").strip()
    if model not in VALID_MODELS:
        raise ConfigError(
            f"TGG_MODEL={model!r} invalid — choose from: {', '.join(VALID_MODELS)}"
        )
    year = _env_int("TGG_YEAR", 2022)
    if not 2012 <= year <= 2030:
        raise ConfigError(f"TGG_YEAR={year} is outside the plausible range 2012-2030")

    height = _env_float("TGG_DRIVER_HEIGHT_CM", 175.0)
    if not 140 <= height <= 220:
        raise ConfigError(f"TGG_DRIVER_HEIGHT_CM={height} is outside 140-220 cm")

    rail = _env_float("TGG_SEAT_RAIL", 0.5)
    if not 0.0 <= rail <= 1.0:
        raise ConfigError(f"TGG_SEAT_RAIL={rail} must be between 0 and 1")

    side = os.environ.get("TGG_DRIVE_SIDE", "LHD").strip().upper()
    if side not in ("LHD", "RHD"):
        raise ConfigError(f"TGG_DRIVE_SIDE={side!r} must be LHD or RHD")

    mirror = os.environ.get("TGG_MIRROR", "driver").strip().lower()
    if mirror not in ("driver", "both"):
        raise ConfigError(f"TGG_MIRROR={mirror!r} must be driver or both")

    follow = _env_float("TGG_FOLLOW_DISTANCE_M", 8.0)
    if not 2 <= follow <= 60:
        raise ConfigError(f"TGG_FOLLOW_DISTANCE_M={follow} must be 2-60 m")

    drop = _env_float("TGG_DROP_CM", 15.0)
    if not 5 <= drop <= 60:
        raise ConfigError(f"TGG_DROP_CM={drop} must be 5-60 cm")

    gain = _env_float("TGG_GAIN", 1.0)
    if not 0.25 <= gain <= 3.0:
        raise ConfigError(f"TGG_GAIN={gain} must be 0.25-3.0")

    return Settings(
        model=model,
        year=year,
        driver_height_cm=height,
        seat_rail=rail,
        drive_side=side,
        follow_distance_m=follow,
        drop_cm=drop,
        restore_seconds=_env_int("TGG_RESTORE_SECONDS", 60),
        mirror=mirror,
        ntfy_topic=os.environ.get("TGG_NTFY_TOPIC", "").strip(),
        gain=gain,
        state_file=os.environ.get(
            "TGG_STATE_FILE", "~/.config/tesla-glareguard/state.json"
        ),
    )
