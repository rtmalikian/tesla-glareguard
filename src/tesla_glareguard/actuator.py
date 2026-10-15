"""Mirror actuation seam for Tesla GlareGuard.

Honest architecture note (verified 2026-10-14 against
https://developer.tesla.com/docs/fleet-api/endpoints/vehicle-commands):
the official Tesla Fleet API has NO side-mirror command — "mirror" appears
zero times in the vehicle-commands docs. So:

* GuideActuator (default, works TODAY): prints precise per-mirror
  instructions ("tilt UP 3.8°, pan OUT 1.1°") so you — or a passenger —
  nudge the mirror by hand, pushes the same text to your phone/watch via
  ntfy, and arms the restore timer.
* FleetApiActuator: the seam for the day Tesla exposes mirror control.
  Today it raises NotImplementedError with a clear explanation instead of
  inventing an endpoint that does not exist.
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from .notifier import NotifierError, send_ntfy


class MirrorActuator(ABC):
    @abstractmethod
    def deflect(self, plan: dict, *, state_file: str, restore_seconds: int,
                ntfy_topic: str = "") -> str:
        """Apply the deflection plan. Returns a human-readable summary."""

    @abstractmethod
    def restore(self, *, state_file: str) -> str:
        """Undo the active deflection. Returns a human-readable summary."""


def _state_path(state_file: str) -> str:
    return os.path.expanduser(state_file)


def _write_state(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)


def _read_state(path: str) -> dict | None:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def guide_text(plan: dict) -> str:
    """Human instructions for one deflection plan, per mirror."""
    lines = []
    for name, p in plan["mirrors"].items():
        tilt_dir = "UP" if p["tilt_deg"] >= 0 else "DOWN"
        pan_dir = "OUT" if p["pan_deg"] >= 0 else "IN"
        side = "driver-side" if name == "driver" else "passenger-side"
        line = (f"{side} mirror: tilt {tilt_dir} {abs(p['tilt_deg']):.1f}°, "
                f"pan {pan_dir} {abs(p['pan_deg']):.1f}°")
        if p["clamped"]:
            line += "  [geometry beyond ±8° — re-aim by hand]"
        lines.append(line)
    return "\n".join(lines)


def restore_text(plan: dict) -> str:
    """Inverse instructions to return mirrors to their original aim."""
    lines = []
    for name, p in plan["mirrors"].items():
        tilt_dir = "DOWN" if p["tilt_deg"] >= 0 else "UP"
        pan_dir = "IN" if p["pan_deg"] >= 0 else "OUT"
        side = "driver-side" if name == "driver" else "passenger-side"
        lines.append(f"{side} mirror: tilt {tilt_dir} {abs(p['tilt_deg']):.1f}°, "
                     f"pan {pan_dir} {abs(p['pan_deg']):.1f}°  (back to normal)")
    return "\n".join(lines)


class GuideActuator(MirrorActuator):
    """Manual guide mode: tells you exactly how to nudge each mirror.

    Works fully offline — no car connection, no API calls, $0.00 cost.
    """

    def deflect(self, plan: dict, *, state_file: str, restore_seconds: int,
                ntfy_topic: str = "") -> str:
        text = guide_text(plan)
        expires = datetime.now(timezone.utc) + timedelta(seconds=restore_seconds)
        path = _state_path(state_file)
        state = _read_state(path) or {}
        state.update({
            "active": True,
            "plan": plan,
            "deflected_at": datetime.now(timezone.utc).isoformat(),
            "restore_at": expires.isoformat(),
            "restore_seconds": restore_seconds,
        })
        _write_state(path, state)
        if ntfy_topic:
            try:
                send_ntfy(ntfy_topic, "GlareGuard: deflect mirrors",
                          text + f"\n\nAuto-restore in {restore_seconds}s "
                                 f"(or run `tgg restore` now).")
            except NotifierError as exc:
                text += f"\n[ntfy push failed: {exc}]"
        return text

    def restore(self, *, state_file: str) -> str:
        path = _state_path(state_file)
        state = _read_state(path)
        plan = (state or {}).get("plan")
        if not plan:
            return "No active deflection to restore."
        state.update({"active": False, "plan": None})
        _write_state(path, state)
        return restore_text(plan)

    def status(self, *, state_file: str) -> str:
        state = _read_state(_state_path(state_file)) or {}
        if not state.get("active") or not state.get("plan"):
            return "No active deflection."
        remaining = ""
        try:
            restore_at = datetime.fromisoformat(state["restore_at"])
            secs = int((restore_at - datetime.now(timezone.utc)).total_seconds())
            remaining = f" (auto-restore in ~{max(secs, 0)}s — overdue means tap `tgg restore`)"
        except (KeyError, ValueError):
            pass
        return "ACTIVE deflection:\n" + guide_text(state["plan"]) + remaining


class FleetApiActuator(MirrorActuator):
    """Seam for future Fleet API mirror actuation.

    Raises NotImplementedError TODAY because the official Tesla Fleet API
    (checked 2026-10-14) exposes no side-mirror command. When Tesla adds one,
    implement deflect()/restore() here against tesla_client.TeslaClient and
    flip the default in cli.py — the rest of the app is already shaped for it.
    """

    def deflect(self, plan: dict, *, state_file: str, restore_seconds: int,
                ntfy_topic: str = "") -> str:
        raise NotImplementedError(
            "Automatic mirror actuation is not possible yet: the official Tesla "
            "Fleet API exposes no side-mirror command (verified 2026-10-14 — "
            "'mirror' appears zero times in the vehicle-commands docs). "
            "GlareGuard runs in guide mode: it computes the exact pan/tilt and "
            "tells you (or your passenger) how to nudge the mirror by hand. "
            "This class is the seam for that future — implement deflect() here "
            "once Tesla exposes the command."
        )

    def restore(self, *, state_file: str) -> str:
        raise NotImplementedError(
            "Automatic mirror actuation is not possible yet (no Fleet API "
            "mirror command as of 2026-10-14). Use guide mode: `tgg restore`."
        )


def load_gain(state_file: str) -> float:
    """Calibration gain persisted by `tgg calibrate` (default 1.0)."""
    state = _read_state(_state_path(state_file)) or {}
    try:
        return float(state.get("gain", 1.0))
    except (TypeError, ValueError):
        return 1.0


def save_gain(state_file: str, gain: float) -> None:
    path = _state_path(state_file)
    state = _read_state(path) or {}
    state["gain"] = gain
    state["gain_updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_state(path, state)
