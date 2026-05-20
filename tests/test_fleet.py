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


def test_send_navigate_insufficient_fuel():
    from fleet import Fleet
    p = FakePlanet()
    s = FakeShip(home=p); p.ships.append(s)
    s.fuel_remaining = 0.0   # empty tank
    s.pnr_advisory = False   # NOT a probe — fuel IS checked
    f = Fleet(p)
    f.add_ship(s)
    # Distance to (10000, 10000) is ~14142, fuel cost = 14142 * 0.004 ≈ 56.6
    # With 0 fuel this should fail
    assert f.send_navigate(10000, 10000) is False
    assert f.state == "docked"


def test_ship_send_mine_blocked_in_fleet():
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
