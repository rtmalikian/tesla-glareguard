"""CLI: tgg deflect | restore | status | calibrate | simulate | version

Guide mode needs NO car connection and NO Tesla credentials: the deflection
plan is pure geometry computed locally from TGG_* settings. There is no
`auth`, `pairing`, or `run` — see README "What it can't do (yet)".
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from . import __version__
from .actuator import (
    FleetApiActuator,
    GuideActuator,
    guide_text,
    load_gain,
    save_gain,
)
from .config import ConfigError, Settings, load_settings
from .glare_geometry import (
    MIRROR_GEOMETRY,
    GeometryError,
    band_for,
    deflection_plan,
    eye_point,
    mirror_centers,
)
from .simulator import run_simulation

DISCLAIMER = (
    "GlareGuard computes mirror adjustments from ESTIMATED vehicle geometry. "
    "Have a passenger tap `tgg deflect`, or pull over — never fiddle with "
    "mirrors while driving. Deflection is small and auto-restores."
)


def _settings_with_gain() -> Settings:
    settings = load_settings()
    # Calibrated gain wins over the env default, unless TGG_GAIN was set explicitly.
    if not os.environ.get("TGG_GAIN", "").strip():
        settings.gain = load_gain(settings.state_file)
    return settings


def _plan(settings: Settings) -> dict:
    mirrors = ("driver", "passenger") if settings.mirror == "both" else ("driver",)
    return deflection_plan(
        model=settings.model,
        year=settings.year,
        driver_height_cm=settings.driver_height_cm,
        seat_rail=settings.seat_rail,
        drive_side=settings.drive_side,
        follow_distance_m=settings.follow_distance_m,
        drop_cm=settings.drop_cm,
        gain=settings.gain,
        mirrors=mirrors,
    )


def cmd_deflect(_args, settings: Settings) -> int:
    print(f"GlareGuard v{__version__} — {DISCLAIMER}\n")
    try:
        plan = _plan(settings)
    except GeometryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    actuator = GuideActuator()
    text = actuator.deflect(
        plan,
        state_file=settings.state_file,
        restore_seconds=settings.restore_seconds,
        ntfy_topic=settings.ntfy_topic,
    )
    print("DAZZLE DETECTED (your tap) — deflect the beam:\n")
    print(text)
    print(f"\nMirrors restore in {settings.restore_seconds}s "
          f"(auto-timer armed) or run `tgg restore` now.")
    print("Estimated Fleet API cost of this action: $0.00 (zero vehicle calls).")
    return 0


def cmd_restore(_args, settings: Settings) -> int:
    print(GuideActuator().restore(state_file=settings.state_file))
    return 0


def cmd_status(_args, settings: Settings) -> int:
    band = band_for(settings.model, settings.year)
    eye = eye_point(settings.driver_height_cm / 100.0, settings.seat_rail,
                    settings.drive_side, band)
    centers = mirror_centers(band, settings.drive_side)
    print(f"GlareGuard v{__version__}")
    print(f"Car: {MIRROR_GEOMETRY[settings.model]['label']} {settings.year} "
          f"(geometry: ESTIMATED, see README)")
    print(f"Driver: {settings.driver_height_cm:.0f} cm, seat rail {settings.seat_rail:.2f}, "
          f"{settings.drive_side}")
    print(f"Eye point (x,y,z): {eye[0]:.2f}, {eye[1]:.2f}, {eye[2]:.2f} m")
    for name, m in centers.items():
        print(f"{name.capitalize()} mirror center: {m[0]:.2f}, {m[1]:.2f}, {m[2]:.2f} m")
    print(f"Dazzler assumed at {settings.follow_distance_m:.0f} m behind, "
          f"target {settings.drop_cm:.0f} cm below eyes, gain {settings.gain:.2f}")
    try:
        plan = _plan(settings)
    except GeometryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("\nComputed deflection (no action taken):")
    print(guide_text(plan))
    print()
    print(GuideActuator().status(state_file=settings.state_file))
    print(f"\nntfy: {'set' if settings.ntfy_topic else 'NOT SET — guide text prints only'}")
    print("Fleet API: guide mode (no mirror command exists as of 2026-10-14).")
    return 0


def cmd_calibrate(_args, settings: Settings) -> int:
    print("GlareGuard calibration — tune the geometry to YOUR body and car.\n")
    print("Drive at night, wait for a dazzle event, run `tgg deflect`, nudge the")
    print("mirror exactly as instructed, then answer honestly:\n")
    gain = settings.gain
    print(f"Current gain: {gain:.2f}\n")
    ans = input("Did the glare clear your eyes? [y]es / [n]o, still dazzled / [t]oo far: "
                ).strip().lower()
    if ans in ("y", "yes"):
        print(f"Gain stays {gain:.2f} — geometry matches you. Nice.")
        return 0
    if ans in ("t", "too", "too far", "far"):
        gain = round(gain * 0.8, 2)
        print(f"Beam moved too far — gain reduced to {gain:.2f}.")
    elif ans in ("n", "no"):
        gain = round(gain * 1.25, 2)
        print(f"Beam didn't move enough — gain raised to {gain:.2f}.")
    else:
        print("Unrecognized answer — calibration unchanged.")
        return 1
    save_gain(settings.state_file, gain)
    print(f"Saved to {settings.state_file}. Re-run `tgg deflect` on the next dazzle.")
    return 0


def cmd_simulate(_args, _settings: Settings) -> int:
    print(f"GlareGuard v{__version__} — virtual night drive (no credentials, no network)\n")
    verdict = run_simulation()
    print(f"\nSIMULATION: {verdict}")
    return 0 if verdict == "PASS" else 1


def cmd_version(_args, _settings) -> int:
    print(f"tgg {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tgg",
        description="One-tap anti-dazzle side-mirror deflector for Teslas "
                    "(guide mode — no car connection needed).",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("deflect", help="Compute + show the mirror deflection, arm restore")
    sub.add_parser("restore", help="Undo the active deflection")
    sub.add_parser("status", help="Show geometry + computed deltas, no action")
    sub.add_parser("calibrate", help="Interactive gain tuning against your feedback")
    sub.add_parser("simulate", help="Virtual night drive with dazzle events (no API calls)")
    sub.add_parser("version", help="Print version")
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        settings = _settings_with_gain()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    cmds = {
        "deflect": cmd_deflect,
        "restore": cmd_restore,
        "status": cmd_status,
        "calibrate": cmd_calibrate,
        "simulate": cmd_simulate,
        "version": cmd_version,
    }
    try:
        return cmds[args.command](args, settings)
    except NotImplementedError as exc:
        # FleetApiActuator path — honest, never silent.
        print(f"Not available: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
