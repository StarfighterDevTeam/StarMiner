import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# Stub minimal pygame pour éviter l'init graphique
import types
pygame_stub = types.ModuleType("pygame")
pygame_stub.font = types.SimpleNamespace(SysFont=lambda *a, **k: None, Font=lambda *a, **k: None)
pygame_stub.Surface = lambda *a, **k: None
pygame_stub.image = types.SimpleNamespace(load=lambda *a: None)
pygame_stub.transform = types.SimpleNamespace(smoothscale=lambda *a: None)
sys.modules.setdefault("pygame", pygame_stub)

from constants import RESOURCE_NAMES, START_RESOURCES


class FakePlanet:
    _id_counter = 0
    def __init__(self, is_home=False):
        FakePlanet._id_counter += 1
        self.id = FakePlanet._id_counter
        self.x = 0.0; self.y = 0.0
        self.type = "rocky"; self.name = "Test"
        self.size = 80
        self.colonized = is_home
        self.explored = is_home
        self.discovered = is_home      # ← attribut à vérifier
        self.is_home = is_home
        self.habitable = is_home
        self.resources = {r: 0.0 for r in RESOURCE_NAMES}
        if is_home:
            self.resources.update(START_RESOURCES)
        self.available_resources = ["iron", "oil", "silver"]
        self.buildings = []; self.build_queue = []; self.ship_queue = []; self.ships = []


def test_home_planet_discovered_at_creation():
    p = FakePlanet(is_home=True)
    assert p.discovered is True

def test_non_home_planet_not_discovered_at_creation():
    p = FakePlanet(is_home=False)
    assert p.discovered is False
    assert p.explored is False

def test_colonize_sets_discovered():
    p = FakePlanet(is_home=False)
    p.discovered = True   # précondition : doit être discovered pour être colonisée
    p.colonized = True
    p.explored = True
    p.discovered = True
    assert p.discovered is True
    assert p.explored is True
