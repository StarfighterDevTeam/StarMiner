# Fleets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an OGame-inspired fleet system: group navigate-capable ships into a selectable entity with a bottom Fleet Bar, a FleetUI panel, and map-click navigation.

**Architecture:** New `Fleet` class in `fleet.py` (data + behavior). Ships get a `fleet` field; non-navigate missions are blocked for fleet members. Two new UI modules (`ui_fleet.py`, `ui_fleet_bar.py`). `game.py` wires everything via `game.fleets: dict[int, Fleet]`. `PlanetUI` gets a fleet section at the top of the Fleet tab.

**Tech Stack:** Python 3 / Pygame 2. Follows existing patterns: `_font()`, `Button`, `set_clip`, `dispatch_modes`, `pygame_stub` for tests.

**Spec:** `docs/superpowers/specs/2026-05-19-fleets-design.md`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `fleet.py` | Fleet class: state machine, navigation, membership |
| Create | `ui_fleet.py` | FleetUI: panel for inspection / modification |
| Create | `ui_fleet_bar.py` | FleetBar: horizontal bar at bottom of screen |
| Create | `tests/test_fleet.py` | Logic tests for Fleet (no pygame) |
| Modify | `ship.py` | Add `fleet` field; guard `send_*` missions; use `_fleet_nav_speed` |
| Modify | `ui_planet.py` | Fleet section in Fleet tab; `_create_fleet_request` signal |
| Modify | `game.py` | Imports, attributes, update, draw, event handling |
| Modify | `.claude/CLAUDE.md` | Document fleet system |

---

## Task 1: Fleet core class

**Files:**
- Create: `fleet.py`
- Create: `tests/test_fleet.py`

- [ ] **Step 1: Write failing tests for Fleet logic**

```python
# tests/test_fleet.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import types
pygame_stub = types.ModuleType("pygame")
pygame_stub.font = types.SimpleNamespace(SysFont=lambda *a, **k: None, Font=lambda *a, **k: None)
pygame_stub.Surface = lambda *a, **k: None
pygame_stub.image = types.SimpleNamespace(load=lambda *a: None)
pygame_stub.transform = types.SimpleNamespace(smoothscale=lambda *a: None)
pygame_stub.draw = types.SimpleNamespace(polygon=lambda *a, **k: None)
sys.modules.setdefault("pygame", pygame_stub)

import pytest

class FakePlanet:
    _ctr = 0
    def __init__(self, name="Home"):
        FakePlanet._ctr += 1
        self.id = FakePlanet._ctr
        self.x = 0.0; self.y = 0.0; self.name = name
        self.colonized = True; self.ships = []
        self.resources = {"oil": 1000}

class FakeShip:
    _ctr = 0
    def __init__(self, speed=100, ship_type="Fighter", home=None):
        FakeShip._ctr += 1
        self.id = FakeShip._ctr
        self.speed = speed; self.type = ship_type
        self.fleet = None; self.state = "idle"
        self._destroyed = False
        self.x = 0.0; self.y = 0.0
        self.fuel_remaining = 500.0; self.pnr_advisory = False
        self.fuel_rate = 0.004
        self._navigate_dest = None; self._dock_planet = None
        self._pre_combat_dest = None; self._target_enemy = None
        self.home = home
    def fuel_cost_navigate(self, wx, wy):
        import math
        return math.hypot(self.x - wx, self.y - wy) * self.fuel_rate
    def _fuel_to_nearest_colony(self, wx, wy, planets):
        return 0.0
    def send_navigate(self, wx, wy, dock_planet=None, planets=None):
        self._navigate_dest = (wx, wy)
        self._dock_planet = dock_planet
        self.state = "navigate"
        return True


def test_fleet_creation():
    from fleet import Fleet
    p = FakePlanet("Mars")
    f = Fleet(p)
    assert f.name == "Flotte de Mars"
    assert f.state == "docked"
    assert f.ships == []
    assert f.home is p


def test_add_ship_success():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p)
    p.ships.append(s)
    f = Fleet(p)
    assert f.add_ship(s) is True
    assert s.fleet is f
    assert s in f.ships


def test_add_ship_wrong_home():
    from fleet import Fleet
    p1 = FakePlanet(); p2 = FakePlanet()
    s = FakeShip(home=p2)
    f = Fleet(p1)
    assert f.add_ship(s) is False


def test_add_ship_already_in_fleet():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f2 = Fleet(p)
    assert f2.add_ship(s) is False


def test_add_ship_fleet_not_docked():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.state = "navigate"
    assert f.add_ship(s) is False


def test_add_ship_not_idle():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    s.state = "navigate"
    f = Fleet(p)
    assert f.add_ship(s) is False


def test_remove_ship():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    assert f.remove_ship(s) is True
    assert s.fleet is None
    assert s not in f.ships


def test_remove_ship_fleet_not_docked():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f.state = "navigate"
    assert f.remove_ship(s) is False


def test_send_navigate():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    assert f.send_navigate(1000, 2000) is True
    assert f.state == "navigate"
    assert f._nav_target == (1000, 2000)
    assert s.state == "navigate"
    assert s._navigate_dest == (1000, 2000)


def test_send_navigate_empty_fleet():
    from fleet import Fleet
    p = FakePlanet()
    f = Fleet(p)
    assert f.send_navigate(1000, 2000) is False


def test_send_navigate_not_docked():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f.state = "navigate"
    assert f.send_navigate(500, 500) is False


def test_cancel():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f.send_navigate(1000, 2000)
    assert f.cancel() is True
    assert f.state == "docked"
    assert s.state == "idle"
    assert s._navigate_dest is None


def test_dissolve():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    fleets = {p.id: f}
    f.dissolve(fleets)
    assert s.fleet is None
    assert p.id not in fleets


def test_update_cleans_destroyed():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    s._destroyed = True
    f.update(0.016, [], None, [])
    assert s not in f.ships
    assert s.fleet is None
    assert f.state == "docked"


def test_update_navigate_to_docked():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f.send_navigate(100, 200)
    # Simulate ship arriving
    s.state = "idle"
    f.update(0.016, [], None, [])
    assert f.state == "docked"
    assert f._nav_target is None


def test_update_combat_detection():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f.send_navigate(100, 200)
    s.state = "combat"
    f.update(0.016, [], None, [])
    assert f.state == "combat"
    assert f._pre_combat_state == "navigate"


def test_update_combat_resume():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    f.state = "combat"
    f._pre_combat_state = "navigate"
    s.state = "navigate"
    f.update(0.016, [], None, [])
    assert f.state == "navigate"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd c:\GitHub\Python\StarMiner
python -m pytest tests/test_fleet.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'fleet'` (or similar import error)

- [ ] **Step 3: Create `fleet.py`**

```python
# fleet.py
import math
import pygame
from constants import CYAN, SHIP_DEFS
from ui_common import _font


class Fleet:
    _id_counter = 0

    def __init__(self, home):
        Fleet._id_counter += 1
        self.id    = Fleet._id_counter
        self.name  = f"Flotte de {home.name}"
        self.home  = home
        self.ships : list = []
        self.state : str  = "docked"        # "docked"|"navigate"|"combat"|"returning"
        self._pre_combat_state : str = "docked"
        self.x : float = float(home.x)
        self.y : float = float(home.y)
        self._nav_target = None             # (wx, wy) | None

    # ── membership ───────────────────────────────────────────────
    def add_ship(self, ship):
        if self.state != "docked":
            return False
        if ship.state != "idle":
            return False
        if ship.home is not self.home:
            return False
        if "navigate" not in SHIP_DEFS.get(ship.type, {}).get("missions", []):
            return False
        if ship.fleet is not None:
            return False
        ship.fleet = self
        self.ships.append(ship)
        return True

    def remove_ship(self, ship):
        if self.state != "docked":
            return False
        if ship not in self.ships:
            return False
        ship.fleet = None
        ship.__dict__.pop("_fleet_nav_speed", None)
        self.ships.remove(ship)
        return True

    def dissolve(self, game_fleets):
        for s in list(self.ships):
            s.fleet = None
            s.__dict__.pop("_fleet_nav_speed", None)
        self.ships.clear()
        game_fleets.pop(self.home.id, None)

    # ── missions ─────────────────────────────────────────────────
    def send_navigate(self, wx, wy, planets=None):
        if self.state != "docked" or not self.ships:
            return False
        planets = planets or []
        for s in self.ships:
            if not s.pnr_advisory:
                fuel_leg    = s.fuel_cost_navigate(wx, wy)
                fuel_return = s._fuel_to_nearest_colony(wx, wy, planets)
                if s.fuel_remaining < fuel_leg + fuel_return:
                    return False
        for s in self.ships:
            s.send_navigate(wx, wy, planets=planets)
        self._nav_target = (wx, wy)
        self.state = "navigate"
        return True

    def send_return(self, planets=None):
        if self.state not in ("navigate", "docked") or not self.ships:
            return False
        planets = planets or []
        for s in self.ships:
            s.send_navigate(self.home.x, self.home.y,
                            dock_planet=self.home, planets=planets)
        self.state = "returning"
        return True

    def cancel(self):
        if self.state not in ("navigate", "returning", "combat"):
            return False
        for s in self.ships:
            if s.state == "navigate":
                s._navigate_dest    = None
                s._dock_planet      = None
                s._target_enemy     = None
                s.state             = "idle"
                s.__dict__.pop("_fleet_nav_speed", None)
        self.state       = "docked"
        self._nav_target = None
        return True

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, planets, highways, all_ships):
        # Cleanup destroyed members
        for s in list(self.ships):
            if s._destroyed:
                s.fleet = None
                s.__dict__.pop("_fleet_nav_speed", None)
                self.ships.remove(s)

        if not self.ships:
            self.state       = "docked"
            self._nav_target = None
            self.x           = float(self.home.x)
            self.y           = float(self.home.y)
            return

        # Update barycentre position
        self.x = sum(s.x for s in self.ships) / len(self.ships)
        self.y = sum(s.y for s in self.ships) / len(self.ships)

        fleet_speed = min(s.speed for s in self.ships)

        # Detect combat entry
        if self.state != "combat" and any(s.state == "combat" for s in self.ships):
            self._pre_combat_state = self.state
            self.state = "combat"

        if self.state == "combat":
            if not any(s.state == "combat" for s in self.ships):
                self.state = self._pre_combat_state
            return

        if self.state in ("navigate", "returning"):
            # Override speed for navigating members
            for s in self.ships:
                if s.state == "navigate":
                    s._fleet_nav_speed = fleet_speed
            # Transition to docked when all members idle
            if all(s.state == "idle" for s in self.ships):
                for s in self.ships:
                    s.__dict__.pop("_fleet_nav_speed", None)
                self.state       = "docked"
                self._nav_target = None

    # ── map interaction ───────────────────────────────────────────
    def is_clicked(self, mx, my, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        return abs(mx - sx) + abs(my - sy) < 12

    def draw(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        sx, sy = int(sx), int(sy)
        r = 10
        pts = [(sx, sy - r), (sx + r, sy), (sx, sy + r), (sx - r, sy)]
        pygame.draw.polygon(surface, CYAN, pts, 2)
        label = _font(9).render(self.name, True, CYAN)
        surface.blit(label, (sx - label.get_width() // 2, sy - r - 12))
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_fleet.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add fleet.py tests/test_fleet.py
git commit -m "feat: add Fleet core class with logic tests"
```

---

## Task 2: Ship fleet field and navigation speed override

**Files:**
- Modify: `ship.py`

**Context:** `ship.py` is the Ship class. We need to:
1. Add `self.fleet = None` after line 120 (`self.pnr_advisory = ...`)
2. Guard 6 `send_*` methods with `if self.fleet is not None: return False`
3. In the MISSION_NAVIGATE branch (~line 445), replace `self.speed` with `self.__dict__.get("_fleet_nav_speed", self.speed)`

- [ ] **Step 1: Add `fleet` field to `Ship.__init__`**

In `ship.py`, after line 120 (`self.pnr_advisory = defn.get("pnr_advisory", False)`), add:

```python
        self.fleet = None           # Fleet | None — set by Fleet.add_ship / remove_ship
```

The block should read:
```python
        self.fuel_remaining = 0.0
        self.pnr_advisory   = defn.get("pnr_advisory", False)  # PNR shown but not enforced
        self.fleet = None           # Fleet | None — set by Fleet.add_ship / remove_ship

        # Animation
```

- [ ] **Step 2: Guard `send_explore`, `send_mine`, `send_colonize`, `send_highway`, `send_transport`, `send_collect`**

Each of the six methods gets a fleet guard as its very first check. Find each `def send_X` and insert `if self.fleet is not None: return False` before the existing state check.

`send_explore` (currently starts at ~line 184):
```python
    def send_explore(self, target):
        if self.fleet is not None: return False
        if self.state not in (MISSION_IDLE, MISSION_NAVIGATE): return False
```

`send_mine` (~line 195):
```python
    def send_mine(self, target):
        if self.fleet is not None: return False
        if self.state not in (MISSION_IDLE, MISSION_NAVIGATE): return False
```

`send_colonize` (~line 207):
```python
    def send_colonize(self, target):
        if self.fleet is not None: return False
        if self.state not in (MISSION_IDLE, MISSION_NAVIGATE): return False
```

`send_highway` (~line 219):
```python
    def send_highway(self, target):
        if self.fleet is not None: return False
        if self.state not in (MISSION_IDLE, MISSION_NAVIGATE): return False
```

`send_transport` (~line 242):
```python
    def send_transport(self, target, outbound_res, inbound_res=None):
        if self.fleet is not None: return False
        if self.state not in (MISSION_IDLE, MISSION_NAVIGATE): return False
```

`send_collect` (~line 260):
```python
    def send_collect(self, debris):
        if self.fleet is not None: return False
        if self.state not in (MISSION_IDLE, MISSION_NAVIGATE): return False
```

- [ ] **Step 3: Use `_fleet_nav_speed` in MISSION_NAVIGATE branch**

Find line ~445 in `ship.update`:
```python
            self._move_toward(wx, wy, dt, self.speed)
```

Change to:
```python
            self._move_toward(wx, wy, dt, self.__dict__.get("_fleet_nav_speed", self.speed))
```

- [ ] **Step 4: Extend test to verify guard**

Add to `tests/test_fleet.py`:
```python
def test_ship_send_mine_blocked_in_fleet():
    import sys, types
    # pygame already stubbed at top of file
    from fleet import Fleet
    p = FakePlanet()

    class MinimalShip(FakeShip):
        def send_mine(self, target):
            if self.fleet is not None:
                return False
            return True

    s = MinimalShip(home=p); p.ships.append(s)
    f = Fleet(p)
    f.add_ship(s)
    assert s.send_mine(FakePlanet()) is False

    f.remove_ship(s)
    assert s.send_mine(FakePlanet()) is True
```

- [ ] **Step 5: Run tests**

```
python -m pytest tests/test_fleet.py -v
```

Expected: all tests PASS (including new `test_ship_send_mine_blocked_in_fleet`).

- [ ] **Step 6: Commit**

```
git add ship.py tests/test_fleet.py
git commit -m "feat: add fleet field to Ship, guard send_* missions, fleet nav speed"
```

---

## Task 3: FleetUI panel

**Files:**
- Create: `ui_fleet.py`

**Context:** Follows `ShipUI` (`ui_ship.py`) as template. Panel at right side of screen. Shows fleet name (editable), state, member list with Retirer/Ajouter buttons, and mission buttons (Naviguer / Annuler / Dissoudre).

Manual test: launch game, create fleet via planet UI, click fleet icon → panel opens, shows members, Naviguer button dispatches navigate mode.

- [ ] **Step 1: Create `ui_fleet.py`**

```python
# ui_fleet.py
import pygame
from constants import *
from ui_common import _font, Button


class FleetUI:
    PANEL_W = 300

    def __init__(self):
        self.fleet    = None
        self.visible  = False
        self._buttons : list[Button] = []
        self._add_mode  = False
        self._renaming  = False
        self._name_buf  = ""

    def open(self, fleet):
        self.fleet      = fleet
        self.visible    = True
        self._add_mode  = False
        self._renaming  = False
        self._name_buf  = fleet.name

    def close(self):
        self.visible   = False
        self.fleet     = None
        self._add_mode = False
        self._renaming = False

    # ── helpers ──────────────────────────────────────────────────
    def _get_addable(self, fleet):
        return [s for s in fleet.home.ships
                if s.state == "idle"
                and s.fleet is None
                and "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])]

    def _compute_panel_h(self, fleet):
        h = 10 + 20 + 14 + 8   # pad + name + home/state + sep
        h += max(1, len(fleet.ships)) * 20 + 8  # member rows
        if self._add_mode:
            h += 24 + max(1, len(self._get_addable(fleet))) * 18
        h += 24 + 28            # Ajouter btn + mission buttons
        return h

    @property
    def panel_rect(self):
        h = getattr(self, "_panel_h", 280)
        return pygame.Rect(SCREEN_W - self.PANEL_W - 10, 50, self.PANEL_W, h)

    # ── events ───────────────────────────────────────────────────
    def handle_event(self, event):
        if not self.visible or not self.fleet:
            return False
        pos   = pygame.mouse.get_pos()
        fleet = self.fleet

        # Inline rename mode
        if self._renaming:
            if event.type == pygame.TEXTINPUT:
                self._name_buf += event.text
                return True
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    fleet.name     = self._name_buf.strip() or fleet.name
                    self._renaming = False
                elif event.key == pygame.K_BACKSPACE:
                    self._name_buf = self._name_buf[:-1]
                elif event.key == pygame.K_ESCAPE:
                    self._renaming = False
                    self._name_buf = fleet.name
                return True

        for btn in self._buttons:
            if btn.is_clicked(pos, event):
                tip = btn.tooltip
                if tip == "fleet_navigate_request":
                    return "fleet_navigate_requested"
                if tip == "fleet_cancel":
                    fleet.cancel()
                    return True
                if tip == "fleet_dissolve":
                    return "fleet_dissolve"
                if tip == "fleet_add_toggle":
                    self._add_mode = not self._add_mode
                    return True
                if tip == "fleet_rename":
                    self._renaming = True
                    self._name_buf = fleet.name
                    return True
                if tip.startswith("fleet_remove:"):
                    sid = int(tip.split(":")[1])
                    s = next((s for s in fleet.ships if s.id == sid), None)
                    if s:
                        fleet.remove_ship(s)
                    return True
                if tip.startswith("fleet_add_ship:"):
                    sid = int(tip.split(":")[1])
                    s = next((s for s in fleet.home.ships if s.id == sid), None)
                    if s:
                        fleet.add_ship(s)
                    self._add_mode = False
                    return True
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(pos):
                self.close()
                return False
        return self.panel_rect.collidepoint(pos)

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, dispatch_modes=None):
        if not self.visible or not self.fleet:
            return
        fleet = self.fleet
        self._panel_h = self._compute_panel_h(fleet)
        pr  = self.panel_rect
        self._buttons.clear()
        mx, my = pygame.mouse.get_pos()

        panel = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        panel.fill((10, 14, 30, 225))
        pygame.draw.rect(panel, CYAN, (0, 0, pr.w, pr.h), 2, border_radius=8)
        surface.blit(panel, pr.topleft)

        y = pr.y + 10

        # ── Name (editable) ───────────────────────────────────────
        disp_name  = (self._name_buf + "|") if self._renaming else fleet.name
        name_color = GOLD if self._renaming else CYAN
        nt = _font(13).render(disp_name, True, name_color)
        surface.blit(nt, (pr.x + 12, y))
        # Invisible click zone over the name label → triggers rename
        rename_btn = Button(pygame.Rect(pr.x + 12, y, nt.get_width(), nt.get_height()),
                            "", tooltip="fleet_rename", enabled=not self._renaming)
        rename_btn.handle_mouse((mx, my))
        self._buttons.append(rename_btn)
        y += 20

        STATE_LABELS = {
            "docked":    ("En orbite",   CYAN),
            "navigate":  ("En route",    ORANGE),
            "returning": ("Retour base", GREEN),
            "combat":    ("Au combat",   RED),
        }
        slabel, scolor = STATE_LABELS.get(fleet.state, (fleet.state, WHITE))
        info_t = _font(10).render(f"{slabel}  —  Base : {fleet.home.name}", True, scolor)
        surface.blit(info_t, (pr.x + 12, y))
        y += 14

        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8

        # ── Member list ───────────────────────────────────────────
        can_modify = (fleet.state == "docked")
        sf = _font(10)

        if not fleet.ships:
            surface.blit(sf.render("Aucun membre", True, GRAY), (pr.x + 14, y))
            y += 20
        else:
            STATE_SHORT = {
                "idle": "Ancré", "navigate": "En route", "combat": "Combat",
                "travel": "Transit", "returning": "Retour",
                "discovering": "Exploration", "mining": "Extraction",
            }
            for s in fleet.ships:
                st_str = STATE_SHORT.get(s.state, s.state)
                row_t  = sf.render(
                    f"{s.type} #{s.id}  Niv.{s._upgrade_level}  —  {st_str}", True, UI_TEXT)
                surface.blit(row_t, (pr.x + 14, y))
                if can_modify:
                    rem = Button((pr.x + pr.w - 62, y - 1, 50, 16),
                                 "Retirer", tooltip=f"fleet_remove:{s.id}")
                    rem.handle_mouse((mx, my)); rem.draw(surface)
                    self._buttons.append(rem)
                y += 20

        # ── Add-ship sub-list ─────────────────────────────────────
        if self._add_mode:
            addable = self._get_addable(fleet)
            pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
            y += 4
            surface.blit(sf.render("Disponibles :", True, GOLD), (pr.x + 14, y))
            y += 18
            if not addable:
                surface.blit(sf.render("Aucun vaisseau disponible", True, GRAY),
                             (pr.x + 14, y))
                y += 18
            for s in addable:
                a_t = sf.render(f"  {s.type} #{s.id}  Niv.{s._upgrade_level}", True, GREEN)
                surface.blit(a_t, (pr.x + 14, y))
                add_s = Button((pr.x + pr.w - 62, y - 1, 50, 16),
                               "Ajouter", tooltip=f"fleet_add_ship:{s.id}")
                add_s.handle_mouse((mx, my)); add_s.draw(surface)
                self._buttons.append(add_s)
                y += 18

        # ── Ajouter/Fermer toggle ─────────────────────────────────
        if can_modify:
            lbl = "▲ Fermer" if self._add_mode else "+ Ajouter"
            add_toggle = Button((pr.x + 12, y + 2, 110, 18), lbl,
                                tooltip="fleet_add_toggle")
            add_toggle.handle_mouse((mx, my)); add_toggle.draw(surface)
            self._buttons.append(add_toggle)
        y += 24

        # ── Mission buttons ───────────────────────────────────────
        if fleet.state == "docked":
            nav_active = (dispatch_modes or {}).get(fleet) == "fleet_navigate"
            nav_btn = Button((pr.x + 12, y + 2, 120, 22), "Naviguer",
                             tooltip="fleet_navigate_request",
                             enabled=bool(fleet.ships), active=nav_active)
            nav_btn.handle_mouse((mx, my)); nav_btn.draw(surface)
            self._buttons.append(nav_btn)
        else:
            cancel_btn = Button((pr.x + 12, y + 2, 120, 22), "Annuler",
                                tooltip="fleet_cancel")
            cancel_btn.handle_mouse((mx, my)); cancel_btn.draw(surface)
            self._buttons.append(cancel_btn)

        dissolve_btn = Button((pr.x + pr.w - 132, y + 2, 120, 22), "Dissoudre",
                              tooltip="fleet_dissolve")
        dissolve_btn.handle_mouse((mx, my)); dissolve_btn.draw(surface)
        self._buttons.append(dissolve_btn)

    @property
    def panel_rect(self):
        h = getattr(self, "_panel_h", 280)
        return pygame.Rect(SCREEN_W - self.PANEL_W - 10, 50, self.PANEL_W, h)
```

> **Note:** `panel_rect` is defined twice — remove the first occurrence (the one without `_panel_h` default) and keep only the property at the bottom of the class.

Corrected `panel_rect` — only one definition at the end of the class body:
```python
    @property
    def panel_rect(self):
        h = getattr(self, "_panel_h", 280)
        return pygame.Rect(SCREEN_W - self.PANEL_W - 10, 50, self.PANEL_W, h)
```

The full file should have `panel_rect` defined **once**, as a `@property` — remove the initial `def _compute_panel_h` helper that has a duplicate `panel_rect` at the top of the class.

- [ ] **Step 2: Manual test — verify file runs without syntax error**

```
python -c "from ui_fleet import FleetUI; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add ui_fleet.py
git commit -m "feat: add FleetUI panel"
```

---

## Task 4: FleetBar

**Files:**
- Create: `ui_fleet_bar.py`

**Context:** Horizontal bar at the bottom of the screen, to the right of the minimap (which occupies x=10..170 at the bottom). Cards show fleet name, state dot, member count.

Manual test: after creating a fleet, the bar appears with the fleet card.

- [ ] **Step 1: Create `ui_fleet_bar.py`**

```python
# ui_fleet_bar.py
import pygame
from constants import *
from ui_common import _font

BAR_H   = 44
BAR_Y   = SCREEN_H - BAR_H   # = 756  (minimap is at y=630..790, x=10..170)
CARD_W  = 160
CARD_H  = 36
CARD_PAD = 6
START_X = 175   # right of minimap (minimap ends at x=170)


class FleetBar:
    def contains_point(self, pos):
        return pos[1] >= BAR_Y and pos[0] >= START_X

    def handle_event(self, event, fleets):
        """Returns ('select', fleet) | ('consume', None) | (None, None)."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None, None
        mx, my = pygame.mouse.get_pos()
        if my < BAR_Y or mx < START_X:
            return None, None
        x = START_X + CARD_PAD
        for fleet in fleets.values():
            card_rect = pygame.Rect(x, BAR_Y + (BAR_H - CARD_H) // 2, CARD_W, CARD_H)
            if card_rect.collidepoint((mx, my)):
                return "select", fleet
            x += CARD_W + CARD_PAD
        return "consume", None

    def draw(self, surface, fleets, selected_fleet=None):
        # Background band (right of minimap)
        bar_w = SCREEN_W - START_X
        band = pygame.Surface((bar_w, BAR_H), pygame.SRCALPHA)
        band.fill((10, 14, 30, 200))
        surface.blit(band, (START_X, BAR_Y))
        pygame.draw.line(surface, UI_BORDER, (START_X, BAR_Y), (SCREEN_W, BAR_Y), 1)

        if not fleets:
            t = _font(10).render("Aucune flotte", True, GRAY)
            surface.blit(t, (START_X + 12, BAR_Y + (BAR_H - t.get_height()) // 2))
            return

        mx, my = pygame.mouse.get_pos()
        STATE_COLORS = {
            "docked":    CYAN,
            "navigate":  ORANGE,
            "returning": GREEN,
            "combat":    RED,
        }
        STATE_LABELS = {
            "docked":    "En orbite",
            "navigate":  "En route",
            "returning": "Retour",
            "combat":    "Combat",
        }
        x = START_X + CARD_PAD
        for fleet in fleets.values():
            card_rect = pygame.Rect(x, BAR_Y + (BAR_H - CARD_H) // 2, CARD_W, CARD_H)
            hov = card_rect.collidepoint((mx, my))
            sel = fleet is selected_fleet

            bg = (20, 36, 68) if hov else (14, 20, 38)
            pygame.draw.rect(surface, bg, card_rect, border_radius=4)
            border_col = CYAN if sel else UI_BORDER
            pygame.draw.rect(surface, border_col, card_rect, 1, border_radius=4)

            dot_color = STATE_COLORS.get(fleet.state, WHITE)
            cy = card_rect.centery
            pygame.draw.circle(surface, dot_color, (card_rect.x + 10, cy), 4)

            name = fleet.name[:18] + ("…" if len(fleet.name) > 18 else "")
            nt = _font(10).render(name, True, WHITE if hov else UI_TEXT)
            surface.blit(nt, (card_rect.x + 20, card_rect.y + 6))

            sl  = STATE_LABELS.get(fleet.state, fleet.state)
            cnt = _font(9).render(f"{sl}  [{len(fleet.ships)}]", True, dot_color)
            surface.blit(cnt, (card_rect.x + 20, card_rect.y + 20))

            x += CARD_W + CARD_PAD
```

- [ ] **Step 2: Verify syntax**

```
python -c "from ui_fleet_bar import FleetBar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add ui_fleet_bar.py
git commit -m "feat: add FleetBar bottom bar"
```

---

## Task 5: PlanetUI fleet section

**Files:**
- Modify: `ui_planet.py`

**Context:** `PlanetUI._draw_fleet` currently shows all ships on the planet. We add:
1. Two new signal fields: `_create_fleet_request` and `_open_fleet_request`
2. `self.fleets = {}` attribute (set from game.py, same pattern as `ship_upgrades`)
3. A fleet section at the top of `_draw_fleet`: shows fleet info + Gérer button, or "Créer une flotte" button
4. For fleet member ships: show `[Flotte]` badge, grey mission buttons

- [ ] **Step 1: Add signal fields and `fleets` attribute to `PlanetUI.__init__`**

In `ui_planet.py`, find `PlanetUI.__init__` (around line 60). After `self._collect_request = None` add:

```python
        self._create_fleet_request = None   # Planet | None — signal to game.py
        self._open_fleet_request   = None   # Planet | None — signal to game.py
        self.fleets = {}                    # shared ref from game.fleets
```

Also add these two resets in `open()` and `close()` methods (find where `self._collect_request = None` is reset and add the two lines below it):

```python
        self._create_fleet_request = None
        self._open_fleet_request   = None
```

- [ ] **Step 2: Add fleet section at top of `_draw_fleet`**

In `_draw_fleet(self, surface, pr, y, p, pending_modes=None)`, at the very top of the method body (before the `if not p.ships:` check), add the fleet section block:

```python
        # ── Fleet section ─────────────────────────────────────────
        fleet = self.fleets.get(p.id)
        f_sec_h = 0
        if fleet is not None:
            STATE_LABELS_F = {
                "docked":    ("En orbite",   CYAN),
                "navigate":  ("En route",    ORANGE),
                "returning": ("Retour",      GREEN),
                "combat":    ("Au combat",   RED),
            }
            slabel, scolor = STATE_LABELS_F.get(fleet.state, (fleet.state, WHITE))
            fleet_line = f.render(
                f"{fleet.name}  —  {slabel}  [{len(fleet.ships)} vaisseaux]",
                True, scolor)
            surface.blit(fleet_line, (pr.x + 12, y + 4))
            manage_btn = Button((right - 80, y + 2, 76, 20),
                                "Gérer", tooltip=f"fleet_manage:{fleet.id}")
            manage_btn.handle_mouse(mouse_pos); manage_btn.draw(surface)
            self._buttons.append(manage_btn)
            f_sec_h = 28
        else:
            # Show "Créer une flotte" if eligible
            eligible = any(
                s.state == "idle" and s.fleet is None
                and "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
                for s in p.ships
            )
            if eligible:
                create_btn = Button((pr.x + 12, y + 2, 160, 20),
                                    "+ Créer une flotte",
                                    tooltip="fleet_create")
                create_btn.handle_mouse(mouse_pos); create_btn.draw(surface)
                self._buttons.append(create_btn)
                f_sec_h = 28

        y += f_sec_h
        if f_sec_h > 0:
            pygame.draw.line(surface, (40, 80, 120),
                             (pr.x + 8, y), (pr.x + pr.w - 8, y))
            y += 4
```

- [ ] **Step 3: Add `[Flotte]` badge and grey mission buttons for fleet members**

In `_draw_fleet`, inside the `for ship in p.ships:` loop, find the block that draws the ship name badge (around line 1165: `if here: badge = ...`). Add a fleet badge right after the `is_docked` badge:

```python
            if ship.fleet is not None:
                fleet_badge = sf.render("[Flotte]", True, CYAN)
                badge_x = right - fleet_badge.get_width() - 4
                # shift left if docked badge also shown
                if here:
                    badge_x -= badge.get_width() + 8
                surface.blit(fleet_badge, (badge_x, ry + 8))
```

Then, in the `if ship.state in (MISSION_IDLE, MISSION_NAVIGATE):` block that draws mission buttons, wrap the entire missions button rendering in a check:

```python
            if ship.state in (MISSION_IDLE, MISSION_NAVIGATE):
                if ship.fleet is not None:
                    # Ship is in a fleet — mission buttons disabled
                    pass
                else:
                    # existing button rendering code (unchanged)
                    missions = SHIP_DEFS[ship.type]["missions"]
                    ...
```

- [ ] **Step 4: Handle tooltip clicks for `fleet_create` and `fleet_manage`**

In `PlanetUI.handle_event`, find the section that processes button clicks (look for the loop over `self._buttons` and tooltip checks). Add handlers for the new tooltips:

```python
                if tooltip == "fleet_create":
                    self._create_fleet_request = p
                    return True
                if tooltip.startswith("fleet_manage:"):
                    self._open_fleet_request = p
                    return True
```

These signals are picked up by `game.py` after `self.ui.handle_event(event, ...)` returns True.

- [ ] **Step 5: Manual test — verify syntax**

```
python -c "from ui_planet import PlanetUI; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```
git add ui_planet.py
git commit -m "feat: add fleet section to PlanetUI Fleet tab"
```

---

## Task 6: Game integration

**Files:**
- Modify: `game.py`

**Context:** Wire fleet into game loop. Imports, new attributes, update, draw, event handling (ESC priority, FleetBar, FleetUI, pending_fleet_dispatch, map click on fleet).

- [ ] **Step 1: Add imports and attributes**

At the top of `game.py`, after the existing `from ui_map import ColonyBar` import, add:

```python
from fleet import Fleet
from ui_fleet import FleetUI
from ui_fleet_bar import FleetBar
```

In `Game.__init__`, after `self.colony_bar = ColonyBar()`, add:

```python
        self.fleets: dict     = {}              # planet.id → Fleet
        self.fleet_ui         = FleetUI()
        self.fleet_bar        = FleetBar()
        self._pending_fleet_dispatch = None     # Fleet | None awaiting map click
        self.ui.fleets        = self.fleets     # shared ref for PlanetUI fleet section
```

- [ ] **Step 2: Update fleet in `_update`**

In `_update(self, dt)`, after `self._update_enemies(dt, all_ships)`, add:

```python
        for fleet in list(self.fleets.values()):
            fleet.update(dt, self.planets, self.highways,
                         self.ships + self.enemy_ships)
        # Close FleetUI if fleet was dissolved
        if self.fleet_ui.visible and self.fleet_ui.fleet not in self.fleets.values():
            self.fleet_ui.close()
```

- [ ] **Step 3: Update hover logic in `_update`**

In `_update`, the hover section checks `in_planet_panel`, `in_ship_panel`, `in_colony_bar`. Add `in_fleet_bar` and `in_fleet_panel`:

Find:
```python
        in_planet_panel = self.ui.visible and self.ui.panel_rect.collidepoint(mx, my)
        in_ship_panel   = self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint(mx, my)
        in_colony_bar   = self.colony_bar.contains_point((mx, my), self.planets)
```

Add after those three lines:
```python
        in_fleet_panel  = self.fleet_ui.visible and self.fleet_ui.panel_rect.collidepoint(mx, my)
        in_fleet_bar    = self.fleet_bar.contains_point((mx, my))
```

Then add `or in_fleet_panel or in_fleet_bar` to every `if not in_planet_panel and not in_ship_panel and not in_colony_bar:` guard in the hover block.

- [ ] **Step 4: Add fleet draw in `_draw`**

In `_draw(self)`, after the line `for d in self._visible_debris:` block (around line 492), before `if self.ship_ui.visible ...`, add fleet icons on the map:

```python
        for fleet in self.fleets.values():
            fleet.draw(self.screen, self.camera)
```

Then, after `self.ship_ui.draw(self.screen, dispatch_modes=dispatch_modes)` (around line 532), add fleet UI and fleet bar draws:

```python
        # Fleet bar (bottom) and FleetUI panel
        if self._pending_fleet_dispatch:
            dispatch_modes[self._pending_fleet_dispatch] = "fleet_navigate"
        self.fleet_bar.draw(self.screen, self.fleets,
                            selected_fleet=self.fleet_ui.fleet if self.fleet_ui.visible else None)
        self.fleet_ui.draw(self.screen, dispatch_modes=dispatch_modes)
```

Also add a fleet navigate overlay message. After `_draw_collect_overlay` call, add:

```python
        self._draw_fleet_navigate_overlay()
```

And define the method:
```python
    def _draw_fleet_navigate_overlay(self):
        if not self._pending_fleet_dispatch:
            return
        try:
            font = pygame.font.SysFont("consolas", 14)
        except Exception:
            font = pygame.font.Font(None, 16)
        msg = ">> Cliquez sur la carte pour définir la destination de la flotte  |  ESC pour annuler <<"
        t = font.render(msg, True, CYAN)
        x = SCREEN_W // 2 - t.get_width() // 2
        surf = pygame.Surface((t.get_width() + 20, t.get_height() + 8), pygame.SRCALPHA)
        surf.fill((10, 10, 30, 180))
        self.screen.blit(surf, (x - 10, 56))
        self.screen.blit(t, (x, 60))
```

- [ ] **Step 5: Handle ESC for fleet**

In `_handle_events`, find the ESC block:
```python
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self._pending_dispatch:
                    self._pending_dispatch = None
```

Add fleet ESC handling right after `_pending_dispatch` cancel:
```python
                elif self._pending_fleet_dispatch:
                    self._pending_fleet_dispatch = None
```

And add fleet_ui close after `elif self.ship_ui.visible:` close:
```python
                elif self.fleet_ui.visible:
                    self.fleet_ui.close()
```

- [ ] **Step 6: Handle FleetBar and FleetUI events**

In `_handle_events`, after the colony bar block (`if cb_action is not None: ... continue`), add:

```python
            # Fleet bar
            fb_action, fb_fleet = self.fleet_bar.handle_event(event, self.fleets)
            if fb_action == "select" and fb_fleet:
                self.fleet_ui.open(fb_fleet)
                self.ship_ui.close()
                self.ui.close()
                continue
            if fb_action in ("select", "consume"):
                continue

            # Fleet UI events
            fleet_ev = self.fleet_ui.handle_event(event)
            if fleet_ev == "fleet_navigate_requested":
                self._pending_fleet_dispatch = self.fleet_ui.fleet
                continue
            if fleet_ev == "fleet_dissolve":
                f = self.fleet_ui.fleet
                if f:
                    f.dissolve(self.fleets)
                self.fleet_ui.close()
                continue
            if fleet_ev:
                continue
```

- [ ] **Step 7: Handle `_pending_fleet_dispatch` map click**

In `_handle_events`, after the recycle mode block (after `if self._pending_dispatch and self._pending_dispatch[1] == "recycle": ... continue`), add:

```python
            # Fleet navigate mode: click map to send fleet to destination
            if self._pending_fleet_dispatch:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    on_ui = (
                        (self.ui.visible and self.ui.panel_rect.collidepoint((mx, my)))
                        or (self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint((mx, my)))
                        or (self.fleet_ui.visible and self.fleet_ui.panel_rect.collidepoint((mx, my)))
                        or self.colony_bar.contains_point((mx, my), self.planets)
                        or self.fleet_bar.contains_point((mx, my))
                    )
                    if not on_ui:
                        wx, wy = self.camera.screen_to_world(mx, my)
                        fleet  = self._pending_fleet_dispatch
                        self._pending_fleet_dispatch = None
                        ok = fleet.send_navigate(wx, wy, planets=self.planets)
                        if not ok:
                            self._hud_msg       = "Carburant insuffisant pour la flotte"
                            self._hud_msg_timer = 3.0
                    continue
                else:
                    self.camera.handle_event(event)
                continue
```

- [ ] **Step 8: Handle fleet signals from PlanetUI**

In `_handle_events`, find the block where `self.ui.handle_event` is called and where `_navigate_request` and `_collect_request` are promoted:

```python
            if self.ui.handle_event(event, self.planets, self.ships):
                if self.ui._navigate_request:
                    ...
                if self.ui._collect_request:
                    ...
                continue
```

Add after `_collect_request` handling:

```python
                if self.ui._create_fleet_request:
                    p = self.ui._create_fleet_request
                    self.ui._create_fleet_request = None
                    if p.id not in self.fleets:
                        new_fleet = Fleet(p)
                        self.fleets[p.id] = new_fleet
                        self.fleet_ui.open(new_fleet)
                        self.ship_ui.close()
                if self.ui._open_fleet_request:
                    p = self.ui._open_fleet_request
                    self.ui._open_fleet_request = None
                    f = self.fleets.get(p.id)
                    if f:
                        self.fleet_ui.open(f)
                        self.ship_ui.close()
```

- [ ] **Step 9: Add fleet click on map (left-click section)**

In `_handle_events`, find the left-click section (where `clicked_ship` is resolved):

```python
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_ship = next(
                    (s for s in self.ships
                     if not s.is_docked and s.is_clicked(mx, my, self.camera)), None)
```

Add fleet click detection before `clicked_ship`:

```python
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Fleets take priority over ships on map
                if not self.fleet_bar.contains_point((mx, my)):
                    clicked_fleet = next(
                        (f for f in self.fleets.values()
                         if f.is_clicked(mx, my, self.camera)), None)
                    if clicked_fleet:
                        if self.fleet_ui.visible and self.fleet_ui.fleet is clicked_fleet:
                            self.fleet_ui.close()
                        else:
                            self.fleet_ui.open(clicked_fleet)
                            self.ship_ui.close()
                            self.ui.close()
                        continue

                clicked_ship = next(
                    (s for s in self.ships
                     if not s.is_docked and s.is_clicked(mx, my, self.camera)), None)
```

- [ ] **Step 10: Manual smoke test**

Launch the game:
```
python main.py
```

Verify in order:
1. Game launches without errors
2. Colony bar still works (click on colony → PlanetUI opens)
3. Fleet tab of home planet shows "+ Créer une flotte" button
4. Click "+ Créer une flotte" → FleetUI panel opens on the right
5. Click "+ Ajouter" → shows available ships, click "Ajouter" → ship added to fleet
6. FleetBar at bottom shows fleet card
7. Click "Naviguer" in FleetUI → overlay message appears
8. Click on map → fleet icon moves toward destination
9. Fleet reaches destination → state returns to "docked"
10. Click fleet icon on map → FleetUI opens
11. Click "Dissoudre" → fleet removed, FleetBar empty

- [ ] **Step 11: Commit**

```
git add game.py
git commit -m "feat: integrate fleet system into game loop"
```

---

## Task 7: CLAUDE.md update

**Files:**
- Modify: `.claude/CLAUDE.md`

- [ ] **Step 1: Add Fleet section to CLAUDE.md**

In `.claude/CLAUDE.md`, add a new section after the `## Vaisseaux` section and before `## Débris`:

```markdown
## Flottes (`Fleet`)

`fleet.py` — 1 flotte max par planète colonisée. `game.fleets: dict[int, Fleet]` keyed par `planet.id`.

```
Fleet
  id, name, home, ships: list[Ship]
  state: "docked" | "navigate" | "combat" | "returning"
  _pre_combat_state: str
  x, y: float  (barycentre des membres)
  _nav_target: (wx, wy) | None
```

### Missions
- `fleet.send_navigate(wx, wy, planets)` — navigation formation rigide, vitesse = min des membres
- `fleet.send_return(planets)` — renvoie tous les membres vers `home`
- `fleet.cancel()` — annule navigation / retour

### Membership
- `fleet.add_ship(ship)` — conditions : flotte docked, ship idle sur home, "navigate" dans missions, pas déjà en flotte
- `fleet.remove_ship(ship)` — condition : flotte docked
- `fleet.dissolve(game_fleets)` — retire tous les ships, supprime de `game.fleets`
- `ship.fleet: Fleet | None` — référence à la flotte du vaisseau. Bloque `send_mine`, `send_explore`, `send_colonize`, `send_highway`, `send_transport`, `send_collect` si non-None
- `ship._fleet_nav_speed` — vitesse override (px/s) injectée par `fleet.update()` pendant navigation

### Vitesse de formation
Chaque frame : `fleet.update()` set `s._fleet_nav_speed = min(s.speed)` sur les membres en MISSION_NAVIGATE.
`ship.update()` lit `self.__dict__.get("_fleet_nav_speed", self.speed)` au lieu de `self.speed` dans la branche MISSION_NAVIGATE.

### UI Flotte
- `FleetUI` (`ui_fleet.py`) : panneau droit, activé via clic sur icône carte ou Fleet Bar. Boutons Naviguer / Annuler / Dissoudre. Nom cliquable pour renommer (TEXTINPUT inline). Renvoie `"fleet_navigate_requested"` / `"fleet_dissolve"` à `game.py`.
- `FleetBar` (`ui_fleet_bar.py`) : barre horizontale bas d'écran, `BAR_Y = SCREEN_H - 44`, `START_X = 175` (à droite de la minimap). Cards cliquables → ouvrent FleetUI.
- `game._pending_fleet_dispatch: Fleet | None` — même flow que `_pending_dispatch` pour les vaisseaux.
- Onglet Fleet de `PlanetUI` : section en haut avec bouton "Gérer" (si flotte existe) ou "+ Créer une flotte". Ships membres : badge `[Flotte]` cyan, boutons de mission grisés.
```

- [ ] **Step 2: Commit**

```
git add .claude/CLAUDE.md
git commit -m "docs: document fleet system in CLAUDE.md"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Fleet class with state machine (`fleet.py`)
- ✅ `ship.fleet` field + guards on `send_*`
- ✅ Formation speed (`_fleet_nav_speed`)
- ✅ FleetUI panel (name edit, member list, Ajouter/Retirer, Navigate/Cancel/Dissolve)
- ✅ FleetBar (bottom horizontal bar, START_X=175 clears minimap)
- ✅ Map icon (diamond, CYAN, clickable)
- ✅ PlanetUI Fleet tab section (Créer / Gérer, [Flotte] badge)
- ✅ game.py integration (update, draw, events, ESC, map click)
- ✅ 1 fleet per planet enforced via `game.fleets.get(p.id)` check
- ✅ Combat state preserved via `_pre_combat_state`
- ✅ Destroyed ship cleanup in `fleet.update()`
- ✅ Tests for core logic

**Placeholder scan:** None found.

**Type consistency:** All references to `fleet.state` use string literals matching the spec (`"docked"`, `"navigate"`, `"returning"`, `"combat"`). `MISSION_NAVIGATE = "navigate"` matches. Ship state `"idle"` = `MISSION_IDLE`. Consistent throughout.
