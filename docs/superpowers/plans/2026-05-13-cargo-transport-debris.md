# Cargo Transport & Debris Collection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inter-planet cargo transport missions with bidirectional repeat mode, plus a debris collection system (floating wrecks spawned on ship destruction and at game start).

**Architecture:** Extend `ship.py` with two new mission types (`transport`, `collect`), add a `debris.py` module for the Debris world object, extend `game.py` for debris lifecycle and collect-mode input handling, and extend `ui.py` (PlanetUI Fleet tab) for the transport configuration panel and collect button.

**Tech Stack:** Python 3, Pygame 2, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `debris.py` | **Create** | Debris world object: data, hit-test, draw |
| `ship.py` | **Modify** | New fields, `send_transport`, `send_collect`, `fuel_cost` round-trip fix, `update()` transport/collect branches, `draw()` ETA/travel-line fixes |
| `game.py` | **Modify** | `debris_list`, `_visible_debris`, `_collect_mode_ship`, initial spawn, visibility compute, draw, spawn-on-destruction, collect-mode event handling |
| `ui.py` | **Modify** | `_transport_cfg` state, `_collect_request`, `_on_button` additions, `dispatch_mission` transport case, `_mission_eta` collect fix, `draw_mission_hover` transport case, fleet tab transport config + collect button + status display |
| `tests/conftest.py` | **Create** | Shared FakePlanet, MockCamera, ship fixtures |
| `tests/test_debris.py` | **Create** | Debris unit tests |
| `tests/test_transport.py` | **Create** | Transport and collect mission unit tests |

---

## Task 1: Create `debris.py` with tests

**Files:**
- Create: `debris.py`
- Create: `tests/conftest.py`
- Create: `tests/test_debris.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
# tests/conftest.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class FakePlanet:
    _next_id = 1000

    def __init__(self, x=0.0, y=0.0, colonized=True, name=None):
        FakePlanet._next_id += 1
        self.id = FakePlanet._next_id
        self.x = float(x)
        self.y = float(y)
        self.colonized = colonized
        self.ships = []
        self.resources = {
            "iron": 1000.0, "gold": 500.0, "silver": 300.0,
            "oil": 800.0, "deuterium": 100.0,
        }
        self.name = name or f"Planet{self.id}"
        self.is_home = False


class MockCamera:
    zoom = 1.0

    def world_to_screen(self, x, y):
        return (int(x), int(y))


@pytest.fixture
def home_planet():
    return FakePlanet(x=0.0, y=0.0)


@pytest.fixture
def target_planet():
    return FakePlanet(x=1000.0, y=0.0)


@pytest.fixture
def freighter(home_planet):
    from ship import Ship
    s = Ship("Freighter", home_planet)
    home_planet.ships.append(s)
    return s


@pytest.fixture
def camera():
    return MockCamera()
```

- [ ] **Step 2: Write failing tests in `tests/test_debris.py`**

```python
# tests/test_debris.py
import pytest
from conftest import MockCamera
from debris import Debris


def test_debris_filters_zero_resources():
    d = Debris(100.0, 200.0, {"iron": 50.0, "gold": 0.0, "silver": 10.0})
    assert "gold" not in d.resources
    assert d.resources["iron"] == pytest.approx(50.0)
    assert d.resources["silver"] == pytest.approx(10.0)
    assert not d._collected


def test_debris_is_clicked_center():
    cam = MockCamera()
    d = Debris(100.0, 100.0, {"iron": 10.0})
    assert d.is_clicked(100, 100, cam)


def test_debris_not_clicked_far():
    cam = MockCamera()
    d = Debris(100.0, 100.0, {"iron": 10.0})
    assert not d.is_clicked(200, 200, cam)


def test_debris_is_clicked_edge():
    cam = MockCamera()
    d = Debris(100.0, 100.0, {"iron": 10.0})
    # 12px radius: a point exactly 11px away should be inside
    assert d.is_clicked(100 + 11, 100, cam)
    # a point exactly 13px away should be outside
    assert not d.is_clicked(100 + 13, 100, cam)
```

- [ ] **Step 3: Run tests — verify they FAIL with ImportError**

```
cd c:\GitHub\Python\StarMiner
python -m pytest tests/test_debris.py -v
```

Expected: `ImportError: No module named 'debris'`

- [ ] **Step 4: Create `debris.py`**

```python
# debris.py
import pygame
import math
from constants import RESOURCE_NAMES, SCREEN_W, SCREEN_H


class Debris:
    _click_radius = 12   # screen px for hit-test

    def __init__(self, x, y, resources):
        self.x = float(x)
        self.y = float(y)
        self.resources = {r: float(v) for r, v in resources.items() if v > 0}
        self._collected = False

    def is_clicked(self, mx, my, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        return (mx - sx) ** 2 + (my - sy) ** 2 <= self._click_radius ** 2

    def draw(self, surface, camera, hovered=False):
        sx, sy = camera.world_to_screen(self.x, self.y)
        if sx < -20 or sx > SCREEN_W + 20 or sy < -20 or sy > SCREEN_H + 20:
            return
        # Pixel cluster
        offsets = [(-3, -3), (2, -2), (-1, 2), (3, 1), (0, -1)]
        for i, (dx, dy) in enumerate(offsets):
            color = (200, 175, 60) if i % 2 == 0 else (130, 130, 130)
            pygame.draw.rect(surface, color, (int(sx + dx), int(sy + dy), 3, 3))

        if hovered:
            pygame.draw.circle(surface, (60, 220, 220), (int(sx), int(sy)), 14, 1)

        if camera.zoom >= 0.4 and self.resources:
            try:
                f = pygame.font.SysFont("consolas", 9)
            except Exception:
                f = pygame.font.Font(None, 10)
            label = "  ".join(
                f"{r[:3].upper()}:{int(v)}" for r, v in self.resources.items()
            )
            t = f.render(label, True, (210, 195, 120))
            surface.blit(t, (int(sx) - t.get_width() // 2, int(sy) + 9))
```

- [ ] **Step 5: Run tests — verify they PASS**

```
python -m pytest tests/test_debris.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```
git add debris.py tests/conftest.py tests/test_debris.py
git commit -m "feat: add Debris world object with hit-test and draw"
```

---

## Task 2: Ship — transport fields, `_load_cargo_from`, `send_transport`, `fuel_cost` fix

**Files:**
- Modify: `ship.py`
- Create: `tests/test_transport.py` (partial — transport sending tests)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transport.py
import pytest
from conftest import FakePlanet
from ship import Ship, MISSION_IDLE, MISSION_TRAVEL


def _freighter(home):
    s = Ship("Freighter", home)
    home.ships.append(s)
    return s


# ── send_transport ─────────────────────────────────────────────────────────────

def test_send_transport_sets_travel_state():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0)
    ship   = _freighter(home)
    assert ship.send_transport(target, ["iron", "gold"])
    assert ship.state == MISSION_TRAVEL
    assert ship._mission_type == "transport"
    assert ship._transport_target is target
    assert ship._transport_leg == "out"


def test_send_transport_loads_outbound_cargo():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0)
    ship   = _freighter(home)
    home.resources["iron"]  = 1000.0
    home.resources["gold"]  = 500.0
    ship.send_transport(target, ["iron", "gold"])
    # capacity=800, 2 resources → 400 each
    assert ship.cargo["iron"] == pytest.approx(400.0)
    assert ship.cargo["gold"] == pytest.approx(400.0)


def test_send_transport_deducts_cargo_from_home():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0)
    ship   = _freighter(home)
    home.resources["iron"] = 800.0
    ship.send_transport(target, ["iron"])
    assert home.resources["iron"] == pytest.approx(800.0 - ship.cargo["iron"])


def test_send_transport_rejected_when_not_idle():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0)
    ship   = _freighter(home)
    ship.state = MISSION_TRAVEL
    assert not ship.send_transport(target, ["iron"])


def test_send_transport_rejected_same_planet():
    home = FakePlanet(x=0.0, y=0.0)
    ship = _freighter(home)
    assert not ship.send_transport(home, ["iron"])


def test_send_transport_rejected_not_colonized():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0, colonized=False)
    ship   = _freighter(home)
    assert not ship.send_transport(target, ["iron"])


def test_send_transport_stores_inbound_for_repeat():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0)
    ship   = _freighter(home)
    ship.send_transport(target, ["iron"], ["gold"])
    assert ship._transport_inbound == ["gold"]


def test_fuel_cost_transport_is_round_trip():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=1000.0, y=0.0)
    ship   = _freighter(home)
    cost_transport = ship.fuel_cost("transport", target)
    cost_mine      = ship.fuel_cost("mine", target)
    assert cost_transport == pytest.approx(cost_mine)
```

- [ ] **Step 2: Run tests — verify FAIL**

```
python -m pytest tests/test_transport.py -v
```

Expected: ImportError or AttributeError on `_transport_target`, `_transport_leg`, etc.

- [ ] **Step 3: Add transport fields to `Ship.__init__`**

In `ship.py`, after `self.repeat = False` (line 82), add:

```python
        # Transport mission fields
        self._transport_target   = None   # destination planet B
        self._transport_outbound = []     # resource types to carry A→B
        self._transport_inbound  = []     # resource types to carry B→A (repeat)
        self._transport_leg      = "out"  # "out" | "in"

        # Collect mission field
        self._collect_debris     = None   # Debris reference
```

- [ ] **Step 4: Fix `fuel_cost` to treat "transport" as round-trip**

In `ship.py`, find `fuel_cost` (around line 116) and change:

```python
    def fuel_cost(self, mtype, target):
        dist = math.hypot(self.home.x - target.x, self.home.y - target.y)
        return dist * self.fuel_rate * (2.0 if mtype in ("mine", "pump") else 1.0)
```

to:

```python
    def fuel_cost(self, mtype, target):
        dist = math.hypot(self.home.x - target.x, self.home.y - target.y)
        return dist * self.fuel_rate * (2.0 if mtype in ("mine", "pump", "transport") else 1.0)
```

- [ ] **Step 5: Add `_load_cargo_from` helper and `send_transport` method**

In `ship.py`, after the `send_highway` method (around line 214), add:

```python
    def _load_cargo_from(self, planet, res_types):
        """Load equal share of capacity from planet for each resource type."""
        if not res_types:
            return
        per_res = self.capacity / len(res_types)
        for res in res_types:
            avail = planet.resources.get(res, 0.0)
            amount = min(per_res, avail)
            if amount > 0:
                self.cargo[res] += amount
                planet.resources[res] = planet.resources.get(res, 0.0) - amount

    def send_transport(self, target, outbound_res, inbound_res=None):
        if self.state != MISSION_IDLE:
            return False
        if self.capacity <= 0:
            return False
        if not target.colonized or target is self.home:
            return False
        fuel = self.fuel_cost("transport", target)
        if self.home.resources.get(self.fuel_type, 0) < fuel:
            return False
        self._load_fuel(fuel)
        self._load_cargo_from(self.home, list(outbound_res))
        self._transport_target   = target
        self._transport_outbound = list(outbound_res)
        self._transport_inbound  = list(inbound_res) if inbound_res else []
        self._transport_leg      = "out"
        self.target_planet       = target
        self.state               = MISSION_TRAVEL
        self._mission_type       = "transport"
        return True
```

- [ ] **Step 6: Run tests — verify PASS**

```
python -m pytest tests/test_transport.py -v
```

Expected: 8 tests PASS

- [ ] **Step 7: Commit**

```
git add ship.py tests/test_transport.py
git commit -m "feat: add send_transport and _load_cargo_from to Ship"
```

---

## Task 3: Ship — `update()` transport state machine

**Files:**
- Modify: `ship.py`
- Modify: `tests/test_transport.py` (add arrival tests)

- [ ] **Step 1: Add arrival tests to `tests/test_transport.py`**

Append to `tests/test_transport.py`:

```python
# ── transport state machine ────────────────────────────────────────────────────

def test_transport_arrives_at_target_deposits_cargo():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=50.0, y=0.0)
    ship   = _freighter(home)
    home.resources["iron"] = 1000.0
    ship.send_transport(target, ["iron"])
    ship.x = target.x + 30   # close enough to arrive next tick
    cargo_iron = ship.cargo["iron"]
    target_iron_before = target.resources.get("iron", 0.0)

    ship.update(1.0, [], None, None)

    assert ship.state == "returning"
    assert target.resources["iron"] == pytest.approx(target_iron_before + cargo_iron)
    assert sum(ship.cargo.values()) == pytest.approx(0.0)


def test_transport_repeat_loads_inbound_on_arrival():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=50.0, y=0.0)
    ship   = _freighter(home)
    ship.repeat = True
    ship.send_transport(target, ["iron"], ["gold"])
    ship.x = target.x + 30
    target.resources["gold"] = 300.0

    ship.update(1.0, [], None, None)

    assert ship.state == "returning"
    assert ship._transport_leg == "in"
    assert ship.cargo["gold"] > 0


def test_transport_return_deposits_inbound_cargo():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=50.0, y=0.0)
    ship   = _freighter(home)
    ship.repeat = True
    ship.send_transport(target, ["iron"], ["gold"])
    # Simulate: outbound done, now returning with gold in cargo
    ship.state = "returning"
    ship._mission_type = "transport"
    ship.cargo["gold"] = 200.0
    ship.x = home.x + 30
    home_gold_before = home.resources.get("gold", 0.0)

    ship.update(1.0, [], None, None)

    assert home.resources["gold"] == pytest.approx(home_gold_before + 200.0)


def test_transport_repeat_restarts_after_return():
    home   = FakePlanet(x=0.0, y=0.0)
    target = FakePlanet(x=50.0, y=0.0)
    ship   = _freighter(home)
    ship.repeat = True
    ship.send_transport(target, ["iron"], ["gold"])
    ship.state = "returning"
    ship._mission_type = "transport"
    ship.x = home.x + 30

    ship.update(1.0, [], None, None)

    # Should have restarted: state is travel again
    assert ship.state == MISSION_TRAVEL
    assert ship._mission_type == "transport"
```

- [ ] **Step 2: Run tests — verify FAIL**

```
python -m pytest tests/test_transport.py::test_transport_arrives_at_target_deposits_cargo -v
```

Expected: FAIL — state is still MISSION_TRAVEL (logic not implemented)

- [ ] **Step 3: Update `MISSION_TRAVEL` block in `Ship.update()`**

In `ship.py`, find the `if self.state == MISSION_TRAVEL:` block (around line 285). Replace it entirely with:

```python
        if self.state == MISSION_TRAVEL:
            if self._mission_type == "collect" and self._collect_debris:
                tx, ty = self._collect_debris.x, self._collect_debris.y
            else:
                tx, ty = self.target_planet.x, self.target_planet.y
            speed = self._travel_speed(highways)
            self._move_toward(tx, ty, dt, speed)
            dist = math.hypot(self.x - tx, self.y - ty)
            if dist < 40:
                self.x = tx
                self.y = ty
                if self._mission_type == "collect":
                    space = self.capacity - sum(self.cargo.values())
                    for res, amt in list(self._collect_debris.resources.items()):
                        take = min(amt, space)
                        if take > 0:
                            self.cargo[res] += take
                            space -= take
                    self._collect_debris._collected = True
                    self._collect_debris = None
                    self.state = MISSION_RETURN
                elif self._mission_type == "transport":
                    for res, amt in self.cargo.items():
                        if amt > 0:
                            self._transport_target.resources[res] = (
                                self._transport_target.resources.get(res, 0.0) + amt)
                    self.cargo = {r: 0.0 for r in RESOURCE_NAMES}
                    if self.repeat and self._transport_inbound:
                        self._load_cargo_from(self._transport_target, self._transport_inbound)
                    self._transport_leg = "in"
                    self.state = MISSION_RETURN
                elif self._mission_type == "explore":
                    self.state = MISSION_DISCOVER
                    self._discover_timer = self._discover_duration
                elif self._mission_type in ("mine", "pump"):
                    self.state = MISSION_MINE
                    self._mine_timer = self._mine_duration
                elif self._mission_type == "colonize":
                    self.target_planet.colonize()
                    if self in self.home.ships:
                        self.home.ships.remove(self)
                    self._destroyed = True
                    return
                elif self._mission_type == "highway":
                    if highways is not None:
                        highways.add(frozenset({self.home.id, self.target_planet.id}))
                    if self in self.home.ships:
                        self.home.ships.remove(self)
                    self._destroyed = True
                    return
```

- [ ] **Step 4: Update `MISSION_RETURN` block to add transport repeat**

In `ship.py`, find the `elif self.state == MISSION_RETURN:` block. Replace it entirely with:

```python
        elif self.state == MISSION_RETURN:
            speed = self._travel_speed(highways)
            self._move_toward(self.home.x, self.home.y, dt, speed)
            dist = math.hypot(self.x - self.home.x, self.y - self.home.y)
            if dist < 40:
                self.x = self.home.x
                self.y = self.home.y
                self._refund_fuel()
                for res, amt in self.cargo.items():
                    self.home.resources[res] = self.home.resources.get(res, 0) + amt
                self.cargo = {r: 0.0 for r in RESOURCE_NAMES}
                prev_target = self.target_planet
                prev_mtype  = getattr(self, "_mission_type", None)
                self.state = MISSION_IDLE
                self.target_planet = None
                if self.repeat and prev_mtype in ("mine", "pump") and prev_target:
                    if prev_mtype == "pump":
                        self.send_pump(prev_target)
                    else:
                        self.send_mine(prev_target)
                elif self.repeat and prev_mtype == "transport" and self._transport_target:
                    self.send_transport(
                        self._transport_target,
                        self._transport_outbound,
                        self._transport_inbound,
                    )
```

- [ ] **Step 5: Run all transport tests — verify PASS**

```
python -m pytest tests/test_transport.py -v
```

Expected: 12 tests PASS

- [ ] **Step 6: Commit**

```
git add ship.py tests/test_transport.py
git commit -m "feat: implement transport state machine in Ship.update()"
```

---

## Task 4: Ship — `send_collect`, collect state machine, `draw()` fixes

**Files:**
- Modify: `ship.py`
- Modify: `tests/test_transport.py` (add collect tests)

- [ ] **Step 1: Add collect tests to `tests/test_transport.py`**

Append to `tests/test_transport.py`:

```python
# ── collect mission ────────────────────────────────────────────────────────────

from debris import Debris


def test_send_collect_sets_state():
    home  = FakePlanet(x=0.0, y=0.0)
    ship  = _freighter(home)
    d     = Debris(200.0, 0.0, {"iron": 50.0})
    home.resources["oil"] = 9999.0
    assert ship.send_collect(d)
    assert ship.state == MISSION_TRAVEL
    assert ship._mission_type == "collect"
    assert ship._collect_debris is d


def test_send_collect_rejected_when_busy():
    home  = FakePlanet(x=0.0, y=0.0)
    ship  = _freighter(home)
    d     = Debris(200.0, 0.0, {"iron": 50.0})
    ship.state = MISSION_TRAVEL
    assert not ship.send_collect(d)


def test_collect_arrives_and_loads_cargo():
    home  = FakePlanet(x=0.0, y=0.0)
    ship  = _freighter(home)
    home.resources["oil"] = 9999.0
    d     = Debris(80.0, 0.0, {"iron": 50.0, "gold": 20.0})
    ship.send_collect(d)
    ship.x = d.x + 30  # close enough

    ship.update(1.0, [], None, None)

    assert ship.state == "returning"
    assert d._collected
    assert ship.cargo["iron"] == pytest.approx(50.0)
    assert ship.cargo["gold"] == pytest.approx(20.0)


def test_collect_cargo_capped_by_capacity():
    home  = FakePlanet(x=0.0, y=0.0)
    ship  = _freighter(home)   # capacity=800
    home.resources["oil"] = 9999.0
    d     = Debris(80.0, 0.0, {"iron": 600.0, "gold": 600.0})  # 1200 > 800
    ship.send_collect(d)
    ship.x = d.x + 30

    ship.update(1.0, [], None, None)

    assert sum(ship.cargo.values()) <= ship.capacity + 0.001
```

- [ ] **Step 2: Run tests — verify FAIL**

```
python -m pytest tests/test_transport.py::test_send_collect_sets_state -v
```

Expected: AttributeError `send_collect`

- [ ] **Step 3: Add `send_collect` to `ship.py`**

After the `send_transport` method, add:

```python
    def send_collect(self, debris):
        if self.state != MISSION_IDLE:
            return False
        if self.capacity <= 0:
            return False
        dist_to   = math.hypot(self.home.x - debris.x, self.home.y - debris.y)
        dist_back = math.hypot(debris.x - self.home.x, debris.y - self.home.y)
        fuel = (dist_to + dist_back) * self.fuel_rate
        if self.home.resources.get(self.fuel_type, 0) < fuel:
            return False
        self._load_fuel(fuel)
        self._collect_debris = debris
        self.target_planet   = None
        self.state           = MISSION_TRAVEL
        self._mission_type   = "collect"
        return True
```

- [ ] **Step 4: Fix `draw()` travel line for collect mission**

In `ship.py`, find the travel line section in `draw()` (around line 538):

```python
        # Travel line toward actual destination
        if self.state in (MISSION_TRAVEL, MISSION_MINE) and self.target_planet:
            tx, ty = camera.world_to_screen(self.target_planet.x, self.target_planet.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif self.state == MISSION_RETURN:
```

Replace just the first two lines of that `if` branch:

```python
        # Travel line toward actual destination
        if self.state in (MISSION_TRAVEL, MISSION_MINE) and self.target_planet:
            tx, ty = camera.world_to_screen(self.target_planet.x, self.target_planet.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif (self.state == MISSION_TRAVEL and self._mission_type == "collect"
              and self._collect_debris):
            tx, ty = camera.world_to_screen(
                self._collect_debris.x, self._collect_debris.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif self.state == MISSION_RETURN:
            tx, ty = camera.world_to_screen(self.home.x, self.home.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif self.state == MISSION_PATROL and self._patrol_dest:
```

(Remove the old standalone `elif self.state == MISSION_RETURN:` line for the travel line, as it is now included above.)

- [ ] **Step 5: Fix `draw()` ETA label to handle `target_planet is None`**

In `ship.py`, find the ETA label block in `draw()` (around line 559):

```python
        # ETA label while moving toward a destination
        if self.state in (MISSION_TRAVEL, MISSION_RETURN):
            dest_x = self.target_planet.x if self.state == MISSION_TRAVEL else self.home.x
            dest_y = self.target_planet.y if self.state == MISSION_TRAVEL else self.home.y
```

Replace those two `dest_x/y` lines with:

```python
        if self.state in (MISSION_TRAVEL, MISSION_RETURN):
            if (self.state == MISSION_TRAVEL and self._mission_type == "collect"
                    and self._collect_debris):
                dest_x, dest_y = self._collect_debris.x, self._collect_debris.y
            elif self.state == MISSION_TRAVEL and self.target_planet:
                dest_x, dest_y = self.target_planet.x, self.target_planet.y
            else:
                dest_x, dest_y = self.home.x, self.home.y
```

- [ ] **Step 6: Run all tests — verify PASS**

```
python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```
git add ship.py tests/test_transport.py
git commit -m "feat: add send_collect and fix draw() for collect/transport edge cases"
```

---

## Task 5: `PlanetUI` — transport config state, `_on_button`, `dispatch_mission`

**Files:**
- Modify: `ui.py`

- [ ] **Step 1: Add `_transport_cfg` and `_collect_request` to `PlanetUI.__init__`**

In `ui.py`, inside `PlanetUI.__init__`, after `self._sb_info: dict = {}`, add:

```python
        self._transport_cfg    = None   # {"ship": Ship, "outbound": set, "inbound": set, "repeat": bool}
        self._collect_request  = None   # Ship requesting collect mode (promoted by game.py)
```

- [ ] **Step 2: Reset new fields in `open()` and `close()`**

In `PlanetUI.open()`, after the existing resets, add:

```python
        self._transport_cfg   = None
        self._collect_request = None
```

In `PlanetUI.close()`, after `self._mission_mode = None`, add:

```python
        self._transport_cfg   = None
        self._collect_request = None
```

- [ ] **Step 3: Add transport and collect button handlers to `_on_button()`**

In `ui.py`, inside `_on_button()`, after the `elif tag.startswith("patrol:")` block, add:

```python
        elif tag.startswith("transport_open:"):
            sid  = int(tag[15:])
            ship = next((s for s in p.ships if s.id == sid), None)
            if ship:
                if self._transport_cfg and self._transport_cfg["ship"].id == sid:
                    self._transport_cfg = None
                else:
                    self._transport_cfg = {
                        "ship": ship, "outbound": set(), "inbound": set(), "repeat": False
                    }

        elif tag.startswith("transport_out:"):
            # tag format: "transport_out:sid:res"
            _, sid_s, res = tag.split(":")
            if self._transport_cfg and self._transport_cfg["ship"].id == int(sid_s):
                cfg = self._transport_cfg
                cfg["outbound"].discard(res) if res in cfg["outbound"] else cfg["outbound"].add(res)

        elif tag.startswith("transport_in:"):
            _, sid_s, res = tag.split(":")
            if self._transport_cfg and self._transport_cfg["ship"].id == int(sid_s):
                cfg = self._transport_cfg
                cfg["inbound"].discard(res) if res in cfg["inbound"] else cfg["inbound"].add(res)

        elif tag.startswith("transport_repeat:"):
            sid = int(tag[17:])
            if self._transport_cfg and self._transport_cfg["ship"].id == sid:
                self._transport_cfg["repeat"] = not self._transport_cfg["repeat"]

        elif tag.startswith("transport_confirm:"):
            sid = int(tag[18:])
            if self._transport_cfg and self._transport_cfg["ship"].id == sid:
                cfg  = self._transport_cfg
                ship = cfg["ship"]
                if not cfg["outbound"]:
                    self.show_message("Sélectionnez au moins une ressource A→B")
                    return
                ship.repeat = cfg["repeat"]
                self._mission_mode = ("transport", ship)
                self.show_message("Cliquez sur une planète colonisée pour la destination")

        elif tag.startswith("collect:"):
            sid  = int(tag[8:])
            ship = next((s for s in p.ships if s.id == sid), None)
            if ship:
                self._collect_request = ship
                self.show_message("Cliquez sur un débris visible pour le collecter")
```

- [ ] **Step 4: Add transport case to `dispatch_mission()`**

In `ui.py`, inside `dispatch_mission()`, before the block that calls `ship.send_explore / send_mine / ...`, add:

```python
        if mtype == "transport":
            if target_planet is ship.home:
                self.show_message("Même planète — choisissez une autre")
                return
            if not target_planet.colonized:
                self.show_message("La planète doit être colonisée")
                return
            if self._transport_cfg is None or self._transport_cfg["ship"] is not ship:
                self.show_message("Configuration perdue — recommencez")
                self._mission_mode = None
                return
            cfg      = self._transport_cfg
            outbound = list(cfg["outbound"])
            inbound  = list(cfg["inbound"]) if cfg["repeat"] else []
            self._mission_mode  = None
            self._transport_cfg = None
            ok = ship.send_transport(target_planet, outbound, inbound)
            self.show_message(
                f"Transport → {target_planet.name}" if ok else "Transport impossible (carburant ?)")
            return
```

- [ ] **Step 5: Add transport case to `_mission_ok()`**

In `ui.py`, inside `_mission_ok()`, add before the final `return ship.has_fuel_for(mtype, planet)`:

```python
        elif mtype == "transport":
            if not planet.colonized: return False
            if planet is ship.home:  return False
            return ship.has_fuel_for("transport", planet)
```

- [ ] **Step 6: Add transport error check to `draw_mission_hover()`**

In `ui.py`, inside `draw_mission_hover()`, in the error-checking block, after the `elif mtype == "highway" and has_highway:` check, add:

```python
        elif mtype == "transport" and not planet.colonized:
            error = ("Planète non colonisée", RED)
        elif mtype == "transport" and planet is ship.home:
            error = ("Même planète", RED)
```

Also, in the fuel check block:

```python
        if mtype == "patrol":
            ...
        else:
            fuel = ship.fuel_cost(mtype, planet)
```

`mtype == "transport"` will now correctly return round-trip cost since `fuel_cost` was fixed in Task 2.

- [ ] **Step 7: Fix `_mission_eta()` to not block collect missions**

In `ui.py`, replace the top of `_mission_eta`:

```python
def _mission_eta(ship):
    """Returns (remaining_secs, total_secs) for the full mission, or None."""
    import math
    from ship import MISSION_IDLE, MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE, MISSION_RETURN
    if ship.state == MISSION_IDLE or ship.target_planet is None:
        return None
```

with:

```python
def _mission_eta(ship):
    """Returns (remaining_secs, total_secs) for the full mission, or None."""
    import math
    from ship import MISSION_IDLE, MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE, MISSION_RETURN
    if ship.state == MISSION_IDLE:
        return None
    mtype = getattr(ship, "_mission_type", None)
    if ship.target_planet is None and mtype != "collect":
        return None
    # Collect-specific ETA
    if mtype == "collect":
        spd    = max(getattr(ship, "_effective_speed", ship.speed), 1)
        debris = getattr(ship, "_collect_debris", None)
        if ship.state == MISSION_TRAVEL and debris:
            d_to   = math.hypot(ship.home.x - debris.x, ship.home.y - debris.y) / spd
            total  = d_to * 2
            rem    = math.hypot(ship.x - debris.x, ship.y - debris.y) / spd + d_to
            return (max(0.0, rem), max(total, 0.001))
        if ship.state == MISSION_RETURN:
            rem = math.hypot(ship.x - ship.home.x, ship.y - ship.home.y) / spd
            return (max(0.0, rem), max(rem, 0.001))
        return None
```

Then remove the existing `mtype = getattr(ship, "_mission_type", None)` line that follows (it is now at the top of the function — add it once after the collect early-return block):

```python
    one_way_mission = mtype in MISSION_ONE_WAY
    ...  # (rest of existing function unchanged)
```

- [ ] **Step 8: Commit**

```
git add ui.py
git commit -m "feat: add transport config state and dispatch to PlanetUI"
```

---

## Task 6: `PlanetUI` — fleet tab rendering (transport config + collect button + status)

**Files:**
- Modify: `ui.py`

- [ ] **Step 1: Add `_fleet_row_h()` helper to `PlanetUI`**

In `ui.py`, inside the `PlanetUI` class, add this method before `_draw_fleet`:

```python
    def _fleet_row_h(self, ship):
        """Returns the pixel height for this ship's fleet row."""
        if (self._transport_cfg is not None
                and self._transport_cfg["ship"].id == ship.id):
            return 130
        return 70
```

- [ ] **Step 2: Make `_draw_fleet` use dynamic row heights**

In `ui.py`, inside `_draw_fleet`, replace:

```python
        row_h = 70
        SB_W = 7
        content_w = pr.w - 12 - SB_W - 2
        right = pr.x + 6 + content_w
        total_h = len(p.ships) * row_h
```

with:

```python
        SB_W      = 7
        content_w = pr.w - 12 - SB_W - 2
        right     = pr.x + 6 + content_w
        total_h   = sum(self._fleet_row_h(s) for s in p.ships)
```

And replace:

```python
        max_scroll = max(0, (total_h - visible_h) // row_h + 1)
        self._fleet_scroll = max(0, min(self._fleet_scroll, max_scroll))
        scroll_offset = self._fleet_scroll * row_h
        ry = y - scroll_offset + 4
```

with:

```python
        max_scroll        = max(0, (total_h - visible_h) // 70 + 1)
        self._fleet_scroll = max(0, min(self._fleet_scroll, max_scroll))
        scroll_offset     = self._fleet_scroll * 70
        ry                = y - scroll_offset + 4
```

And in the loop, replace the fixed `row_h` references:

```python
        for ship in p.ships:
            if ry + row_h < y or ry > y + visible_h:
                ry += row_h
                continue
```

with:

```python
        for ship in p.ships:
            rh = self._fleet_row_h(ship)
            if ry + rh < y or ry > y + visible_h:
                ry += rh
                continue
```

And at the end of the ship loop:

```python
            ry += row_h
```

change to:

```python
            ry += rh
```

- [ ] **Step 3: Update transport in-progress state label**

In `_draw_fleet`, inside the loop, find the `elif ship.state in ("patrol", "combat"):` block (around line 993). Before it, modify the existing state detection `if here:` block to intercept transport:

After the `else:` / `st_txt, st_col = {...}.get(ship.state, ...)` dict lookup, add a transport override:

```python
            mission_type_now = getattr(ship, "_mission_type", None)
            if mission_type_now == "transport" and ship.state in ("travel", "returning"):
                tp  = getattr(ship, "_transport_target", None)
                leg = getattr(ship, "_transport_leg", "out")
                badge = "[A→B]" if leg == "out" else "[B→A]"
                if ship.state == "travel" and tp:
                    st_txt = f"Transport → {tp.name} {badge}"
                else:
                    st_txt = f"Retour {badge}"
                st_col = CYAN
```

- [ ] **Step 4: Add "Collecter" and "Transport" buttons for idle capacity ships**

In `_draw_fleet`, inside the `if ship.state == "idle":` block, after the existing mission buttons loop, add a single capacity block:

```python
                if SHIP_DEFS[ship.type].get("capacity", 0) > 0:
                    # "Collecter" button
                    cbtn = Button((right - 80, ry + 32, 76, 16),
                                  "Collecter", tooltip=f"collect:{ship.id}")
                    cbtn.handle_mouse(mouse_pos)
                    cbtn.draw(surface)
                    self._buttons.append(cbtn)
                    # "Transport" button (toggles inline config)
                    is_cfg_open = (self._transport_cfg is not None
                                   and self._transport_cfg["ship"].id == ship.id)
                    tbtn = Button((right - 160, ry + 32, 76, 16),
                                  "Transport",
                                  tooltip=f"transport_open:{ship.id}",
                                  active=is_cfg_open)
                    tbtn.handle_mouse(mouse_pos)
                    tbtn.draw(surface)
                    self._buttons.append(tbtn)
```

- [ ] **Step 6: Render transport config inline panel**

In `_draw_fleet`, add the following block after the existing ship content (before `ry += rh`):

```python
            # Transport config expansion (only when this ship is being configured)
            if rh > 70 and self._transport_cfg and self._transport_cfg["ship"].id == ship.id:
                cfg      = self._transport_cfg
                base_y   = ry + 68   # just below the standard 70px content
                label_f  = _font(10)
                res_list = RESOURCE_NAMES   # ["iron", "gold", "silver", "oil", "deuterium"]
                tog_w, tog_h, tog_gap = 30, 14, 3

                # A→B row
                surface.blit(label_f.render("A→B:", True, CYAN),
                             (pr.x + 10, base_y + 2))
                for ri, res in enumerate(res_list):
                    rx2 = pr.x + 46 + ri * (tog_w + tog_gap)
                    active = res in cfg["outbound"]
                    col = RESOURCE_COLORS.get(res, WHITE)
                    btn_col = col if active else UI_DISABLED
                    tog = Button((rx2, base_y, tog_w, tog_h),
                                 res[:3].upper(),
                                 tooltip=f"transport_out:{ship.id}:{res}",
                                 active=active)
                    tog.handle_mouse(mouse_pos)
                    tog.draw(surface)
                    self._buttons.append(tog)

                # Repeat toggle
                rep_active = cfg["repeat"]
                rep_btn = Button((pr.x + 10, base_y + 18, 60, 14),
                                 "Repeat", tooltip=f"transport_repeat:{ship.id}",
                                 active=rep_active)
                rep_btn.handle_mouse(mouse_pos)
                rep_btn.draw(surface)
                self._buttons.append(rep_btn)

                # B→A row (only if repeat on)
                if rep_active:
                    surface.blit(label_f.render("B→A:", True, ORANGE),
                                 (pr.x + 80, base_y + 20))
                    for ri, res in enumerate(res_list):
                        rx2 = pr.x + 116 + ri * (tog_w + tog_gap)
                        active = res in cfg["inbound"]
                        tog = Button((rx2, base_y + 17, tog_w, tog_h),
                                     res[:3].upper(),
                                     tooltip=f"transport_in:{ship.id}:{res}",
                                     active=active)
                        tog.handle_mouse(mouse_pos)
                        tog.draw(surface)
                        self._buttons.append(tog)

                # Confirm button
                has_outbound = bool(cfg["outbound"])
                conf_btn = Button((right - 100, base_y + 17, 96, 18),
                                  "► Destination",
                                  enabled=has_outbound,
                                  tooltip=f"transport_confirm:{ship.id}")
                conf_btn.handle_mouse(mouse_pos)
                conf_btn.draw(surface)
                self._buttons.append(conf_btn)
```

- [ ] **Step 7: Commit**

```
git add ui.py game.py
git commit -m "feat: fleet tab transport config panel + collect button + status"
```

---

## Task 7: `_mission_eta` transport label and `draw_mission_hover` transport case

**Files:**
- Modify: `ui.py`

- [ ] **Step 1: Add transport label in fleet tab ETA / state**

In `_draw_fleet`, find the existing `Repeat` button logic for Miners (around line 1019):

```python
            if ship.type == "Miner":
                rbtn = Button(...)
```

The Repeat button for Miner stays. The transport Repeat toggle was added in Task 6. No change needed here.

- [ ] **Step 2: Verify `draw_mission_hover` transport fuel line**

`draw_mission_hover` already falls through to the generic `else:` block which shows Aller / Retour / Total / fuel. Transport is not one-way (`MISSION_ONE_WAY` doesn't include it), so it correctly shows both legs. No code change needed.

- [ ] **Step 3: Verify `_mission_ok` transport call**

`_mission_ok` has the transport case added in Task 5. The dashed line in `_draw_mission_dash` calls `self.ui._mission_ok(mtype, ship, planet, highways)` — this will now handle "transport" correctly.

- [ ] **Step 4: Commit**

```
git add ui.py
git commit -m "feat: complete transport hover and ETA display"
```

---

## Task 8: `game.py` — debris list, initial spawn, visibility, draw

**Files:**
- Modify: `game.py`

- [ ] **Step 1: Import `Debris` and add fields in `Game.__init__`**

At top of `game.py`, add:

```python
from debris import Debris
```

In `Game.__init__`, after `self._visible_enemies = set()`, add:

```python
        self.debris_list: list = []
        self._visible_debris: set = set()
        self._collect_mode_ship = None
        self._hovered_debris = None
        self._spawn_initial_debris()
```

- [ ] **Step 2: Add `_spawn_initial_debris()`**

In `game.py`, after `_spawn_initial_enemies()`, add:

```python
    def _spawn_initial_debris(self):
        rng  = random.Random(99)
        home = self.planets[0]
        for _ in range(10):
            for _attempt in range(20):
                x = rng.randint(800, WORLD_W - 800)
                y = rng.randint(800, WORLD_H - 800)
                if math.hypot(x - home.x, y - home.y) > 2000:
                    break
            res_count = rng.randint(1, 3)
            res_names = rng.sample(RESOURCE_NAMES, res_count)
            resources = {r: float(rng.randint(10, 80)) for r in res_names}
            self.debris_list.append(Debris(float(x), float(y), resources))
```

- [ ] **Step 3: Add `_compute_visible_debris()`**

In `game.py`, after `_compute_visible_enemies()`, add:

```python
    def _compute_visible_debris(self):
        r2 = DETECTION_RANGE * DETECTION_RANGE
        visible = set()
        for d in self.debris_list:
            for p in self.planets:
                if p.colonized and (d.x - p.x) ** 2 + (d.y - p.y) ** 2 <= r2:
                    visible.add(d)
                    break
            if d in visible:
                continue
            for ps in self.ships:
                if (d.x - ps.x) ** 2 + (d.y - ps.y) ** 2 <= r2:
                    visible.add(d)
                    break
        return visible
```

- [ ] **Step 4: Call visibility and cleanup in `_update()`**

In `game.py`, inside `_update()`, after `self._visible_enemies = self._compute_visible_enemies()`, add:

```python
        self._visible_debris = self._compute_visible_debris()
        self.debris_list = [d for d in self.debris_list if not d._collected]
```

- [ ] **Step 5: Draw visible debris in `_draw()`**

In `game.py`, inside `_draw()`, after the `for s in self._visible_enemies:` loop, add:

```python
        for d in self._visible_debris:
            d.draw(self.screen, self.camera, hovered=(d is self._hovered_debris))
```

- [ ] **Step 6: Compute hovered debris in `_update()`**

In `game.py`, inside `_update()`, in the hover detection section, after the planet hover block, add:

```python
        self._hovered_debris = None
        if (not self._hovered_ship and not self._hovered_planet
                and not in_planet_panel and not in_ship_panel and not in_colony_bar):
            mx2, my2 = pygame.mouse.get_pos()
            self._hovered_debris = next(
                (d for d in self._visible_debris if d.is_clicked(mx2, my2, self.camera)),
                None,
            )
```

- [ ] **Step 7: Commit**

```
git add game.py debris.py
git commit -m "feat: add debris list, initial spawn, visibility, and draw in game.py"
```

---

## Task 9: `game.py` — spawn debris on destruction + collect mode event handling

**Files:**
- Modify: `game.py`

- [ ] **Step 1: Spawn debris when ships are destroyed**

In `game.py`, inside `_update()`, find:

```python
        self.ships = [s for s in self.ships if not s._destroyed]
```

Replace with:

```python
        for s in self.ships:
            if s._destroyed:
                self._spawn_debris_from_ship(s)
        self.ships = [s for s in self.ships if not s._destroyed]
```

And find:

```python
        self.enemy_ships = [s for s in self.enemy_ships if not s._destroyed]
```

(in `_update_enemies`) Replace with:

```python
        for s in self.enemy_ships:
            if s._destroyed:
                self._spawn_debris_from_ship(s)
        self.enemy_ships = [s for s in self.enemy_ships if not s._destroyed]
```

- [ ] **Step 2: Add `_spawn_debris_from_ship()`**

In `game.py`, add after `_spawn_initial_debris()`:

```python
    def _spawn_debris_from_ship(self, ship):
        resources = {}
        defn = SHIP_DEFS.get(ship.type, {})
        for res, amt in defn.get("cost", {}).items():
            if res in RESOURCE_NAMES:
                resources[res] = resources.get(res, 0.0) + amt * 0.3
        for res, amt in ship.cargo.items():
            if amt > 0:
                resources[res] = resources.get(res, 0.0) + amt
        if resources:
            self.debris_list.append(Debris(ship.x, ship.y, resources))
```

- [ ] **Step 3: Handle collect mode in ESC chain**

In `game.py`, inside `_handle_events()`, in the ESC key block:

```python
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self._patrol_mode_ship:
                    self._patrol_mode_ship = None
                elif self.ui._mission_mode:
```

Add collect mode cancellation:

```python
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self._patrol_mode_ship:
                    self._patrol_mode_ship = None
                elif self._collect_mode_ship:
                    self._collect_mode_ship = None
                elif self.ui._mission_mode:
```

- [ ] **Step 4: Promote `_collect_request` from PlanetUI**

In `game.py`, inside `_handle_events()`, after the patrol request promotion:

```python
                if self.ui._patrol_request:
                    self._patrol_mode_ship = self.ui._patrol_request
                    self.ui._patrol_request = None
```

Add:

```python
                if self.ui._collect_request:
                    self._collect_mode_ship = self.ui._collect_request
                    self.ui._collect_request = None
```

- [ ] **Step 5: Handle collect mode mouse click**

In `game.py`, inside `_handle_events()`, after the patrol mode block, add a collect mode block:

```python
            # Collect mode: next click on visible debris dispatches ship
            if self._collect_mode_ship:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    on_ui = (
                        (self.ui.visible and self.ui.panel_rect.collidepoint((mx, my)))
                        or (self.ship_ui.visible
                            and self.ship_ui.panel_rect.collidepoint((mx, my)))
                        or self.colony_bar.contains_point((mx, my), self.planets)
                    )
                    if not on_ui:
                        clicked_debris = next(
                            (d for d in self._visible_debris
                             if d.is_clicked(mx, my, self.camera)),
                            None,
                        )
                        if clicked_debris:
                            ship = self._collect_mode_ship
                            self._collect_mode_ship = None
                            ok = ship.send_collect(clicked_debris)
                            if not ok:
                                self._hud_msg = "Carburant insuffisant pour collecter"
                                self._hud_msg_timer = 3.0
                        continue
                else:
                    self.camera.handle_event(event)
                continue
```

- [ ] **Step 6: Add `_draw_collect_overlay()` and call it in `_draw()`**

In `game.py`, add this method after `_draw_patrol_overlay()`:

```python
    def _draw_collect_overlay(self):
        if not self._collect_mode_ship:
            return
        try:
            font = pygame.font.SysFont("consolas", 14)
        except Exception:
            font = pygame.font.Font(None, 16)
        msg  = ">> Cliquez sur un débris visible pour le collecter  |  ESC pour annuler <<"
        t    = font.render(msg, True, (200, 180, 60))
        x    = SCREEN_W // 2 - t.get_width() // 2
        surf = pygame.Surface((t.get_width() + 20, t.get_height() + 8), pygame.SRCALPHA)
        surf.fill((10, 10, 30, 180))
        self.screen.blit(surf, (x - 10, 38))
        self.screen.blit(t, (x, 42))
```

In `_draw()`, after `self._draw_patrol_overlay()`, add:

```python
        self._draw_collect_overlay()
```

- [ ] **Step 7: Run the game and verify end-to-end**

```
cd c:\GitHub\Python\StarMiner
python main.py
```

Verify:
1. 10 debris objects appear on the map (visible when zooming near them within detection range)
2. Opening a planet with a Freighter shows "Transport" and "Collecter" buttons
3. Clicking "Transport" expands the inline config with resource toggles
4. Selecting outbound resources and clicking "► Destination" enters planet-select mode
5. Clicking a colonized planet dispatches the transport mission; ship travels, deposits cargo, returns
6. Repeat mode sends the ship back automatically with the inbound cargo
7. Killing an enemy ship spawns debris at its location
8. Clicking "Collecter" and then a visible debris dispatches the collect mission
9. Ship travels to debris, collects it, returns home and deposits resources

- [ ] **Step 8: Run all tests**

```
python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 9: Final commit**

```
git add game.py
git commit -m "feat: spawn debris on ship destruction and wire collect mode in game.py"
```
