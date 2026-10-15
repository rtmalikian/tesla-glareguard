# Tesla GlareGuard — One-Tap Anti-Dazzle Side-Mirror Deflector for Model 3, Model Y, Model S, Model X & Cybertruck

**Free & open source: when the driver behind you has their brights on and your Tesla's side mirror is throwing the glare straight into your eyes, one tap computes exactly how many degrees to pivot the mirror to steer the beam away — from your seat position, your height, and your exact Tesla model and year.**

> ⚠️ **Safety first.** GlareGuard computes from *estimated* vehicle geometry — have a passenger tap `tgg deflect`, or pull over. Never fiddle with mirrors while driving. The deflection is small (a few degrees) and auto-restores after 60 seconds or on a second tap.

## Why?

- "The guy behind me had his brights on and my side mirror was beaming it straight into my eyes — I had to fold the mirror in."
- Tesla's auto-dimming mirror helps, but dimming only cuts *intensity* — the bright blob is still sitting right on your eyes.
- Model Y Highland's frameless side mirrors **don't auto-dim at all** (widely reported by owners) — you're on your own.
- Manually hunting for the right mirror angle at 70 mph, blinded, is how people get hurt. A computed nudge — "tilt UP 5.0°, pan IN 0.3°" — takes one second to apply.
- Works on Apple Watch / Galaxy Watch: bind the command to a shortcut button and tap without looking at your phone.

**The key insight:** dimming and deflection stack. Auto-dim cuts how *bright* the reflection is; GlareGuard moves *where* it lands — 15 cm below your eyes, onto the road. Together they solve the problem neither solves alone.

## How it works

```
21:07  SUV with brights pulls in 8 m behind you
       → you (or your passenger) tap the shortcut: `tgg deflect`
       → GlareGuard computes, from YOUR seat position + Model Y geometry:
          driver-side mirror: tilt UP 5.0°, pan IN 0.3°
       → passenger nudges the mirror; the glare spot drops 15 cm below your eyes
       → (optional) the same instruction is pushed to your watch via ntfy
21:08  60 s later (or second tap: `tgg restore`)
       → mirrors guided back to their normal aim
```

The math: your eye point is derived from your height (sitting eye height ≈ 0.46 × standing height), seat-rail position, and drive side. The follower's headlight is modeled 8 m behind at headlight height. From the law of reflection, the mirror must rotate by half the required swing of the reflected beam (the doubling law); that 3-D rotation is fitted to the pan + tilt a human can actually apply and clamped to ±8°. The whole plan is verified in-simulation: the reflected beam provably lands at least `TGG_DROP_CM` below your eyes.

**Works without any car connection.** Guide mode is pure geometry computed on your phone/laptop — zero Tesla API calls, zero credentials, works in a tunnel, works with the car asleep.

**Expected API cost:** **$0.00** — guide mode makes zero vehicle calls. (Auto-actuation would cost ~$0.001 per deflect *if* Tesla ever exposes a mirror command — see below.)

## Quickstart

```bash
git clone https://github.com/rtmalikian/tesla-glareguard.git
cd tesla-glareguard
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 1. Describe your car and your seat (no secrets — .env is git-ignored)
cp .env.example .env
# edit .env: TGG_MODEL, TGG_YEAR, TGG_DRIVER_HEIGHT_CM, TGG_SEAT_RAIL

# 2. Watch it work on a virtual night drive — no credentials, no network
tgg simulate

# 3. Real dazzle event: tap (bind to a phone/watch shortcut button)
tgg deflect
# → "driver-side mirror: tilt UP 5.0°, pan IN 0.3°"
#    nudge the mirror, glare drops below your eyes

# 4. Mirrors back to normal (or wait 60 s for the auto-restore timer)
tgg restore

# 5. Tune it to YOUR body with one question after a real event
tgg calibrate
```

**Watch/phone shortcut:** point a Shortcuts (iOS) / Bixby Routines or Tasker (Android) button at `tgg deflect` over SSH, or wrap it in a Termux widget — one tap from the steering wheel, eyes on the road. Pair with `TGG_NTFY_TOPIC` so the instruction lands on the watch face for your passenger to read.

## What it can't do (yet) — honest section

**The official Tesla Fleet API has no side-mirror command.** Verified 2026-10-14 against the [vehicle-commands docs](https://developer.tesla.com/docs/fleet-api/endpoints/vehicle-commands): "mirror" appears zero times. So GlareGuard cannot move your mirrors for you today — anyone claiming otherwise is inventing an endpoint.

What ships instead: **guide mode** (works fully, today) + an honest seam. `MirrorActuator` is the interface; `GuideActuator` prints/pushes the exact instruction; `FleetApiActuator` raises a clear `NotImplementedError` explaining the gap instead of faking it. The day Tesla exposes mirror control, auto-deflect gets implemented behind that interface and guide mode stays as the offline fallback.

Related honesty: mirror anchor positions per model/year are **estimates** derived from published overall dimensions, not measured CAD data. Per-driver differences (torso length, how you aim your mirrors) dominate the residual — that's what `tgg calibrate` is for: it tunes a gain multiplier against your own "did the glare clear? y/n/too far" feedback.

## Configuration (`.env` reference)

| Variable | Default | Meaning |
|---|---|---|
| `TGG_MODEL` | `3` | `3` \| `y` \| `s` \| `x` \| `cybertruck` |
| `TGG_YEAR` | `2022` | Model year — picks the geometry band (e.g. Model 3 Highland = 2024+) |
| `TGG_DRIVER_HEIGHT_CM` | `175` | Your height in cm — sets the eye point |
| `TGG_SEAT_RAIL` | `0.5` | Seat rail: `0` = fully back, `1` = fully forward |
| `TGG_DRIVE_SIDE` | `LHD` | `LHD` \| `RHD` |
| `TGG_FOLLOW_DISTANCE_M` | `8` | How far behind the dazzling car is (m) |
| `TGG_DROP_CM` | `15` | Move the glare spot this far below your eyes (cm) |
| `TGG_RESTORE_SECONDS` | `60` | Auto-restore timer (s); second tap restores immediately |
| `TGG_MIRROR` | `driver` | `driver` \| `both` — deflect one mirror or both |
| `TGG_NTFY_TOPIC` | — | ntfy.sh topic: pushes the guide text to your phone/watch |
| `TGG_GAIN` | `1.0` | Calibration multiplier (tuned by `tgg calibrate`) |
| `TGG_STATE_FILE` | `~/.config/tesla-glareguard/state.json` | Deflection state + calibration gain |

Geometry bands: Model 3 2017–2023 / 2024+ (Highland), Model Y 2020–2024 / 2025+ (Juniper), Model S 2012–2020 / 2021+, Model X 2015–2020 / 2021+, Cybertruck 2024+. All anchors estimated — run `tgg calibrate`.

## FAQ

**How do I stop headlights blinding me in my Tesla's side mirror at night?**
Run `tgg deflect` (one tap from a phone/watch shortcut). It tells you exactly how far to pivot the mirror — e.g. "tilt UP 5.0°, pan IN 0.3°" — moving the reflected beam ~15 cm below your eyes. Small nudge, auto-restores in 60 seconds.

**My Tesla's auto-dim mirror isn't enough — the glare is still blinding. Now what?**
Auto-dim only reduces *intensity*; the bright spot stays on your eyes. GlareGuard is complementary: it changes *where* the beam lands. Use both — dimming + deflection stack.

**My Model Y's side mirrors don't auto-dim. Is that normal?**
Yes — the Model Y Highland's frameless side mirrors don't auto-dim (widely reported by owners; only the driver-side mirror auto-dims on some trims, "in proportion to the level of glare" per Tesla's manual). GlareGuard was built partly for exactly this gap.

**Can the Tesla Fleet API control side mirrors?**
No — as of 2026-10-14 the official Fleet API exposes no mirror command at all. That's why GlareGuard ships in guide mode (computed instructions you apply by hand) with a clean actuator seam ready for the day Tesla adds one.

**Is it legal / safe to tilt my mirrors while driving?**
Adjusting mirrors isn't illegal, but doing it *while blinded at speed* is unsafe — that's the whole point of the one-tap flow: have a passenger tap and nudge, or pull over. The deflection is a few degrees and auto-restores, so your normal mirror aim is never lost.

**Does it work for right-hand-drive Teslas?**
Yes — set `TGG_DRIVE_SIDE=RHD`. The geometry mirrors exactly (verified by a symmetry test in the suite).

## Roadmap

- **Light-sensor auto-trigger (experimental):** phone ambient-light sensor in a dash cradle as a dazzle detector — sudden lux spike at night behind you → auto-suggest the deflect tap. Needs real-world validation against streetlights.
- **Fleet-API auto-deflect:** the moment Tesla exposes a side-mirror command, `FleetApiActuator` gets a real implementation and guide mode becomes the offline fallback.
- **Per-driver calibration profiles:** store gain per car/seat-memory profile.

## Development

```bash
pip install -e .          # install (adds pytest for dev)
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
PYTHONPATH=src .venv/bin/python -m tesla_glareguard.cli simulate
```

The physics lives in `src/tesla_glareguard/glare_geometry.py` — pure functions, no network. The honest-actuation seam is `actuator.py` (`GuideActuator` today, `FleetApiActuator` stubbed for the future). `tesla_client.py` is the reused chassis OAuth client, used only by the future actuator — guide mode never touches it.

---
*Built from a real 11pm-night-drive pain point. MIT licensed — free forever.*
