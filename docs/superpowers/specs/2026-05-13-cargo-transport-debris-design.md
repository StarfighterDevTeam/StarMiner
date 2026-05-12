# Cargo Transport & Debris Collection — Design Spec
**Date:** 2026-05-13
**Status:** Approved

## Overview

Two linked features sharing the "ships with cargo capacity" mechanic:

1. **Inter-planet cargo transport** — ships with `capacity > 0` (Miner, Tanker, Freighter) can shuttle chosen resource types between two colonized planets, with optional bidirectional Repeat mode.
2. **Debris collection** — floating wreckage objects in world space, generated on ship destruction and at game start, collectable via explicit mission.

Both features follow Approach A: extend existing mission patterns without new abstractions.

---

## 1. Data Model

### Ship additions (`ship.py`)

New mission constant:
```python
MISSION_TRANSPORT = "transport"
```

New fields in `Ship.__init__`:
```python
self._transport_target   = None  # planet B
self._transport_outbound = []    # resource type names to carry A→B
self._transport_inbound  = []    # resource type names to carry B→A (repeat only)
self._transport_leg      = "out" # "out" | "in"
self._collect_debris     = None  # Debris reference for collect mission
```

Eligible ships: any ship with `capacity > 0` — Miner (200), Tanker (600), Freighter (800).

### Debris class (new file `debris.py`)

```python
class Debris:
    def __init__(self, x, y, resources: dict)
    # resources: {res_name: float}
    # _collected: bool — marked True when picked up, purged each frame in game.py

    def is_clicked(self, mx, my, camera) -> bool
    def draw(self, surface, camera)
```

Visual: cluster of 3–5 small gray/gold pixel squares. At zoom ≥ 0.4, a compact resource label is drawn below (e.g. `iron:45 gold:12`). Cyan selection circle on hover.

### Game additions (`game.py`)

```python
self.debris_list: list[Debris] = []
self._visible_debris: set = set()
self._collect_mode_ship = None   # analogous to _patrol_mode_ship
```

---

## 2. Transport Mission Flow

### `ship.send_transport(target, outbound_res, inbound_res)`

- Validates: `capacity > 0`, ship is idle, target is colonized and not home planet
- Calculates fuel for round trip (same formula as `mine`), debits from `home.resources[fuel_type]`
- **Loads outbound cargo immediately at departure**: capacity split equally across selected resource types, capped by what home planet holds. Resources deducted from `home.resources`.
- Sets `_transport_target`, `_transport_leg = "out"`
- State → `MISSION_TRAVEL`, `_mission_type = "transport"`

### State machine

```
MISSION_TRAVEL (leg "out")
  → arrive at B (dist < 40)
      → deposit all cargo into target.resources
      → if repeat=True and _transport_inbound non-empty:
            load inbound cargo from target.resources
            _transport_leg = "in"
            state → MISSION_RETURN
        else:
            state → MISSION_RETURN (empty)

MISSION_RETURN (leg "in" or empty)
  → arrive at home (dist < 40)
      → deposit inbound cargo into home.resources
      → _refund_fuel()
      → if repeat=True: call send_transport(...) again
        else: state → MISSION_IDLE
```

### Cancellation

`cancel_mission()` during `MISSION_TRAVEL` or `MISSION_RETURN` → state `MISSION_RETURN`. Ship returns and restores cargo + remaining fuel to home planet on arrival (existing behavior).

### ETA

`_mission_eta()` extended for `"transport"`: total = travel_to + travel_back (no dwell time — loading is instantaneous).

---

## 3. Debris System

### Generation on ship destruction

In `game.py`, after removing a destroyed ship from `ships` or `enemy_ships`:
```python
resources = {}
for res, amt in SHIP_DEFS[ship.type]["cost"].items():
    if res in RESOURCE_NAMES:
        resources[res] = amt * 0.3   # 30% recovery rate
for res, amt in ship.cargo.items():
    if amt > 0:
        resources[res] = resources.get(res, 0) + amt  # full cargo
if resources:
    self.debris_list.append(Debris(ship.x, ship.y, resources))
```

### Initial random debris

At game start: 10 debris scattered across the map (seeded), avoiding the player start zone (radius 2000). Each has 1–3 random resource types with amounts 10–80 units.

### Fog of war

`_compute_visible_debris()` — same detection logic as `_compute_visible_enemies()`:
visible if within `DETECTION_RANGE` of any colonized planet or any player ship.
Computed once per frame; result stored in `self._visible_debris`.

### Collection mission

#### Triggering
From the Fleet tab, ships with `capacity > 0` and state idle show a **"Collecter"** button. Click → sets `self._collect_mode_ship` in `game.py`. Overlay shows `">> Cliquez sur un débris visible pour le collecter <<"`. Visible debris are highlighted with a pulsing yellow circle.

Next left-click on a visible `Debris` object (not on a UI panel) → dispatches `ship.send_collect(debris)`.

#### `ship.send_collect(debris)`
- Calculates fuel: distance(ship → debris) + distance(debris → home), debits from home
- Sets `self._collect_debris = debris`, `_mission_type = "collect"`, `self.target_planet = None`
- State → `MISSION_TRAVEL` (traveling toward `debris.x, debris.y`)

In `Ship.update()`, the `MISSION_TRAVEL` branch must check `_mission_type == "collect"` and navigate toward `_collect_debris.x/y` instead of `target_planet`.

#### On arrival at debris
- Transfers `debris.resources` into `ship.cargo` (capped by `capacity`)
- Marks `debris._collected = True`
- State → `MISSION_RETURN`

#### On return home
- Deposits cargo into `home.resources`, calls `_refund_fuel()`
- State → `MISSION_IDLE`
- No auto-repeat (debris is consumed — no stable target). The Repeat toggle button is hidden for ships in collect mission state.

#### Movement toward debris
`_move_toward(debris.x, debris.y, dt, speed)` — reuses existing helper. Travel line: dashed cyan (same as other missions).

---

## 4. UI Changes

### Fleet tab — Transport configuration

Ships with `capacity > 0` get a **"Transport"** button when idle. Clicking it expands the ship row inline (row_h increases to ~120px when active) to show:

```
── Ressources A→B ──
[IRO] [GOL] [SIL] [OIL] [DEU]   ← colored toggle buttons 28×16
── Ressources B→A (visible only if Repeat ON) ──
[IRO] [GOL] [SIL] [OIL] [DEU]
        [Repeat ON/OFF]   [► Confirmer destination]
```

- Toggle buttons use `RESOURCE_COLORS` for their color
- "Confirmer destination" is enabled only when ≥ 1 A→B resource is selected
- Clicking "Confirmer destination" activates mission mode

### Mission mode (transport)

Overlay: `">> Cliquez sur une planète colonisée pour la destination <<"`.
Valid targets: colonized planets other than home.
Hover tooltip: aller/retour ETA + fuel cost (same style as existing mission hover).

### Fleet tab — In-progress transport display

When `_mission_type == "transport"`:
```
En transit → [Planet Name]  [A→B]
Cargo: GOL:120  SIL:80
ETA: 1m23s  ████████░░░░
[Annuler]
```

Leg badge `[A→B]` / `[B→A]` indicates current direction.

### Fleet tab — Collect button

**"Collecter"** button shown alongside existing mission buttons for capacity ships when idle.
Click → `_collect_mode_ship` set, overlay shown, visible debris highlighted.

### ESC handling

ESC cancels `_collect_mode_ship` (same priority as `_patrol_mode_ship` in existing ESC chain).

### ShipUI panel

No structural changes. The existing ShipUI already shows state and cargo. A leg label is added to the status line when `_mission_type == "transport"`.

---

## 5. Out of Scope

- Debris visible to enemy factions or contested by them
- Multiple ships assigned to the same trade route
- Resource priority weighting within a single load (equal split only)
- Debris decay / expiry timer
