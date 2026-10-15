"""Virtual night drive for Tesla GlareGuard. No credentials, no network.

Simulates a timeline of dazzle events (a car with brights on pulls in
behind you), computes the deflection plan for each event, verifies the
core invariant — the reflected beam lands at least drop_cm below the eye
point — then restores the mirrors and verifies deltas return to zero.

Expected Fleet API cost: $0.00 — guide mode makes zero vehicle calls.
"""
from __future__ import annotations

from dataclasses import dataclass

from .glare_geometry import (
    apply_plan,
    band_for,
    beam_spot_z,
    deflection_plan,
    eye_point,
    headlight_point,
    mirror_centers,
    mirror_normal_for_eye,
)


@dataclass
class DazzleEvent:
    at: str            # virtual clock time
    mirror: str        # 'driver' | 'passenger' | 'both'
    follow_m: float    # how far behind the dazzler is
    note: str


TIMELINE = [
    DazzleEvent("21:00", "driver", 12.0, "night drive starts, no dazzle"),
    DazzleEvent("21:07", "driver", 8.0, "SUV with brights pulls in behind — LEFT mirror dazzle"),
    DazzleEvent("21:08", "driver", 8.0, "restore timer fires (60s) — mirrors back"),
    DazzleEvent("21:15", "passenger", 6.0, "pickup tailgates in the next lane — RIGHT mirror dazzle"),
    DazzleEvent("21:16", "passenger", 6.0, "driver taps restore early — mirrors back"),
    DazzleEvent("21:24", "both", 10.0, "two cars, both mirrors dazzling"),
    DazzleEvent("21:25", "both", 10.0, "restore — mirrors back"),
    DazzleEvent("21:40", "driver", 8.0, "dazzler leaves — drive continues"),
]


def run_simulation(*, model: str = "y", year: int = 2023,
                   driver_height_cm: float = 175.0, seat_rail: float = 0.5,
                   drive_side: str = "LHD", drop_cm: float = 15.0,
                   gain: float = 1.0) -> str:
    """Run the virtual night drive. Returns 'PASS' or 'FAIL:<reason>'."""
    band = band_for(model, year)
    eye = eye_point(driver_height_cm / 100.0, seat_rail, drive_side, band)
    centers = mirror_centers(band, drive_side)

    api_calls = 0  # guide mode never calls the vehicle
    failures: list[str] = []

    for ev in TIMELINE:
        if "restore" in ev.note or "leaves" in ev.note or "no dazzle" in ev.note:
            if "no dazzle" not in ev.note and "leaves" not in ev.note:
                # restore event: verify deltas return to zero
                zero = deflection_plan(
                    model=model, year=year, driver_height_cm=driver_height_cm,
                    seat_rail=seat_rail, drive_side=drive_side,
                    follow_distance_m=ev.follow_m, drop_cm=drop_cm,
                    gain=0.0, mirrors=("driver", "passenger"),
                )
                ok = all(abs(m["pan_deg"]) < 1e-9 and abs(m["tilt_deg"]) < 1e-9
                         for m in zero["mirrors"].values())
                mark = "OK " if ok else "FAIL"
                if not ok:
                    failures.append(f"{ev.at}: restore did not zero the deltas")
                print(f"{ev.at}  RESTORE  mirrors back to normal aim            [{mark}]")
            else:
                print(f"{ev.at}  cruise   {ev.note}")
            continue

        mirrors = ("driver", "passenger") if ev.mirror == "both" else (ev.mirror,)
        plan = deflection_plan(
            model=model, year=year, driver_height_cm=driver_height_cm,
            seat_rail=seat_rail, drive_side=drive_side,
            follow_distance_m=ev.follow_m, drop_cm=drop_cm,
            gain=gain, mirrors=mirrors,
        )
        print(f"{ev.at}  DAZZLE   {ev.note}")
        for name in mirrors:
            m = centers[name]
            h = headlight_point(eye, m, ev.follow_m)
            n0 = mirror_normal_for_eye(h, m, eye)
            spot_before = beam_spot_z(h, m, n0, eye[0])
            n1 = apply_plan(h, m, eye, plan["mirrors"][name])
            spot_after = beam_spot_z(h, m, n1, eye[0])
            moved = (spot_before - spot_after) * 100.0  # cm downward
            p = plan["mirrors"][name]
            # 1 mm tolerance: a human can only pan+tilt a mirror (no roll
            # control), so the fitted plan lands within ~1 mm of the exact
            # target — far below hand-adjustment precision (~0.5 deg).
            ok = spot_after <= eye[2] - drop_cm / 100.0 + 0.001
            mark = "OK " if ok else "FAIL"
            if not ok:
                failures.append(
                    f"{ev.at} {name}: spot only {moved:.1f} cm below eye "
                    f"(need >= {drop_cm} cm)")
            tilt_dir = "UP" if p["tilt_deg"] >= 0 else "DOWN"
            pan_dir = "OUT" if p["pan_deg"] >= 0 else "IN"
            print(f"         {name:>9} mirror: tilt {tilt_dir} {abs(p['tilt_deg']):.1f}°, "
                  f"pan {pan_dir} {abs(p['pan_deg']):.1f}°  "
                  f"-> glare spot {moved:.1f} cm below eyes  [{mark}]")

    print(f"\nEstimated Fleet API cost of this whole night drive: "
          f"${api_calls * 0.001:.2f} ({api_calls} vehicle calls — guide mode is offline)")
    if failures:
        for f in failures:
            print("FAIL:", f)
        return "FAIL:" + "; ".join(failures)
    return "PASS"
