# Probe Navigation & Planet Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Masquer les planètes par défaut, les révéler par proximité (fog of war), donner à la Probe une navigation libre et une portée de détection étendue, renommer "Patrouille" → "Naviguer" dans l'UI.

**Architecture:** On ajoute `planet.discovered` (bool) distinct de `planet.explored`. La découverte est déclenchée chaque frame par `Game._update_discovered_planets()` en comparant la distance des assets joueur aux planètes non encore découvertes. La Probe gagne `"navigate"` dans ses missions et `detection_range: 2400` dans `SHIP_DEFS`, lu dans `Ship.__init__`. Les labels UI sont des changements de chaînes de caractères, sans modification de la logique.

**Tech Stack:** Python 3, Pygame 2, pytest (tests logique pure uniquement)

**Spec de référence :** `docs/superpowers/specs/2026-05-14-probe-navigation-discovery-design.md`

---

### Task 1 : Attribut `discovered` sur Planet

**Files:**
- Modify: `planet.py` (lignes 39–56, 253–257, 273–284)
- Test: `tests/test_planet_discovery.py` (à créer)

- [ ] **Créer le fichier de test**

```python
# tests/test_planet_discovery.py
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
```

- [ ] **Lancer les tests — vérifier qu'ils passent (logique stub seulement)**

```bash
pytest tests/test_planet_discovery.py -v
```

Résultat attendu : 3 PASSED (tests sur FakePlanet, pas encore sur Planet réel).

- [ ] **Ajouter `self.discovered` dans `Planet.__init__`**

Dans `planet.py`, ligne 49, après `self.explored = is_home` :

```python
        self.colonized = is_home
        self.explored = is_home
        self.discovered = is_home   # ← ajouter cette ligne
        self.is_home = is_home
```

- [ ] **Modifier `Planet.draw()` pour ne rien dessiner si non découverte**

Dans `planet.py`, remplacer le début de `draw()` (ligne 273) :

```python
    def draw(self, surface, camera):
        if not self.discovered:
            return
        sx, sy = camera.world_to_screen(self.x, self.y)
```

- [ ] **Modifier `Planet.colonize()` — forcer `discovered = True`**

Dans `planet.py`, ligne 253 :

```python
    def colonize(self):
        self.colonized = True
        self.discovered = True
        self.explored = True
        for res, amt in START_RESOURCES.items():
            self.resources[res] = self.resources.get(res, 0) + amt
```

- [ ] **Commit**

```bash
git add planet.py tests/test_planet_discovery.py
git commit -m "feat: add planet.discovered attribute, hide undiscovered planets on draw"
```

---

### Task 2 : `detection_range` dans SHIP_DEFS et Ship

**Files:**
- Modify: `constants.py` (ligne 114 — définition Probe)
- Modify: `ship.py` (ligne ~117 — `__init__`)
- Test: `tests/test_ship_detection_range.py` (à créer)

- [ ] **Créer le fichier de test**

```python
# tests/test_ship_detection_range.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import types
pygame_stub = types.ModuleType("pygame")
sys.modules.setdefault("pygame", pygame_stub)

from constants import SHIP_DEFS, DETECTION_RANGE


def test_probe_has_custom_detection_range():
    assert "detection_range" in SHIP_DEFS["Probe"]
    assert SHIP_DEFS["Probe"]["detection_range"] == 2400

def test_probe_has_navigate_mission():
    assert "navigate" in SHIP_DEFS["Probe"]["missions"]
    assert "explore" in SHIP_DEFS["Probe"]["missions"]

def test_other_ships_have_no_detection_range_override():
    for stype in ("Miner", "Fighter", "Destroyer", "Scout"):
        assert "detection_range" not in SHIP_DEFS[stype], \
            f"{stype} should not have detection_range override"

def test_detection_range_defaults_to_constant():
    assert SHIP_DEFS.get("Miner", {}).get("detection_range", DETECTION_RANGE) == DETECTION_RANGE
```

- [ ] **Lancer les tests — vérifier qu'ils échouent**

```bash
pytest tests/test_ship_detection_range.py -v
```

Résultat attendu : FAILED (Probe n'a pas encore `detection_range` ni `"navigate"`).

- [ ] **Mettre à jour `SHIP_DEFS["Probe"]` dans `constants.py`**

Remplacer la ligne 114 :

```python
    "Probe":      {"cost": {"iron": 50,  "gold": 10},                        "time": 15, "speed": 180, "capacity": 0,    "missions": ["explore", "navigate"],   "shipyard_level": 1, "fuel_type": "oil",       "fuel_rate": 0.003, "detection_range": 2400},
```

- [ ] **Lancer les tests — vérifier qu'ils passent**

```bash
pytest tests/test_ship_detection_range.py -v
```

Résultat attendu : 4 PASSED.

- [ ] **Ajouter `self.detection_range` dans `Ship.__init__`**

Dans `ship.py`, dans `__init__`, après la ligne `self.fuel_remaining = 0.0` (ligne ~119), ajouter :

```python
        self.fuel_remaining = 0.0
        self.detection_range = defn.get("detection_range", DETECTION_RANGE)
```

- [ ] **Commit**

```bash
git add constants.py ship.py tests/test_ship_detection_range.py
git commit -m "feat: add detection_range to SHIP_DEFS, Probe gets 2400px range and navigate mission"
```

---

### Task 3 : Logique de découverte dans Game

**Files:**
- Modify: `game.py` — ajouter `_update_discovered_planets()`, mettre à jour `_update()`, `_compute_visible_enemies()`, `_compute_visible_debris()`, `_draw_detection_radii()`

- [ ] **Ajouter la méthode `_update_discovered_planets()` dans `game.py`**

Insérer après `_compute_visible_debris()` (ligne ~160), avant `_update_enemies()` :

```python
    def _update_discovered_planets(self):
        r2_base = DETECTION_RANGE * DETECTION_RANGE
        for planet in self.planets:
            if planet.discovered:
                continue
            for asset_p in self.planets:
                if asset_p.colonized:
                    if math.hypot(planet.x - asset_p.x, planet.y - asset_p.y) <= DETECTION_RANGE:
                        planet.discovered = True
                        break
            if planet.discovered:
                continue
            for ship in self.ships:
                dr = ship.detection_range
                if math.hypot(planet.x - ship.x, planet.y - ship.y) <= dr:
                    planet.discovered = True
                    break
```

- [ ] **Appeler `_update_discovered_planets()` dans `_update()`**

Dans `game.py`, dans `_update()`, ajouter l'appel après la mise à jour des ennemis (ligne ~392) :

```python
        self._update_enemies(dt, all_ships)
        self._update_discovered_planets()   # ← ajouter ici
        for s in self.ships:
```

- [ ] **Mettre à jour `_compute_visible_enemies()` pour utiliser `ship.detection_range`**

Remplacer la méthode complète (lignes 356–371) :

```python
    def _compute_visible_enemies(self):
        r2 = DETECTION_RANGE * DETECTION_RANGE
        visible = set()
        for s in self.enemy_ships:
            for p in self.planets:
                if p.colonized and (s.x - p.x) ** 2 + (s.y - p.y) ** 2 <= r2:
                    visible.add(s)
                    break
            if s in visible:
                continue
            for ps in self.ships:
                dr2 = ps.detection_range * ps.detection_range
                if (s.x - ps.x) ** 2 + (s.y - ps.y) ** 2 <= dr2:
                    visible.add(s)
                    break
        return visible
```

- [ ] **Mettre à jour `_compute_visible_debris()` pour utiliser `ship.detection_range`**

Remplacer la méthode complète (lignes 146–159) :

```python
    def _compute_visible_debris(self):
        r2 = DETECTION_RANGE * DETECTION_RANGE
        visible = set()
        for d in self.debris_list:
            for pl in self.planets:
                if pl.colonized and (d.x - pl.x) ** 2 + (d.y - pl.y) ** 2 <= r2:
                    visible.add(d)
                    break
            if d in visible:
                continue
            for ps in self.ships:
                dr2 = ps.detection_range * ps.detection_range
                if (d.x - ps.x) ** 2 + (d.y - ps.y) ** 2 <= dr2:
                    visible.add(d)
                    break
        return visible
```

- [ ] **Mettre à jour `_draw_detection_radii()` pour utiliser `ship.detection_range`**

Remplacer la boucle sur les vaisseaux dans `_draw_detection_radii()` (lignes 586–590) :

```python
        for s in self.ships:
            if not s.is_docked:
                s_r_px = int(s.detection_range * self.camera.zoom)
                if s_r_px < 2:
                    continue
                sx, sy = self.camera.world_to_screen(s.x, s.y)
                pygame.draw.circle(surf, (110, 110, 110, 18), (sx, sy), s_r_px)
                pygame.draw.circle(surf, (140, 140, 140, 55), (sx, sy), s_r_px, 1)
        self.screen.blit(surf, (0, 0))
```

- [ ] **Test manuel — lancer le jeu**

```bash
python main.py
```

Vérifier :
- Au démarrage, seule la planète Home est visible (et les planètes dans son rayon de détection de 800 px).
- Les planètes hors rayon sont totalement absentes de la carte.
- En construisant une Probe et en la laissant immobile, vérifier que son cercle de détection est visiblement plus grand (3×) que celui de la planète Home ou d'un autre vaisseau.

- [ ] **Commit**

```bash
git add game.py
git commit -m "feat: implement planet discovery via detection range, Probe reveals 2400px radius"
```

---

### Task 4 : Filtrer les planètes non découvertes dans les interactions souris

**Files:**
- Modify: `game.py` — hover planète, clic planète, mode mission

- [ ] **Filtrer le hover planète dans `_update()` — ajouter `p.discovered`**

Dans `game.py`, dans `_update()`, remplacer la ligne du hover planète (~ligne 410) :

```python
        # Avant
        self._hovered_planet = next(
            (p for p in self.planets if p.is_clicked(mx, my, self.camera)), None)

        # Après
        self._hovered_planet = next(
            (p for p in self.planets if p.discovered and p.is_clicked(mx, my, self.camera)), None)
```

- [ ] **Filtrer le clic planète dans `_handle_events()` — ajouter `p.discovered`**

Dans `game.py`, dans `_handle_events()`, remplacer la ligne du clic planète (~ligne 343) :

```python
        # Avant
                clicked_planet = next(
                    (p for p in self.planets if p.is_clicked(mx, my, self.camera)), None)

        # Après
                clicked_planet = next(
                    (p for p in self.planets if p.discovered and p.is_clicked(mx, my, self.camera)), None)
```

- [ ] **Filtrer la sélection de cible en mode mission — ajouter `p.discovered`**

Dans `game.py`, dans `_handle_events()`, dans le bloc `if self.ui._mission_mode:` (~ligne 318) :

```python
            # Avant
                    for p in self.planets:
                        if p.is_clicked(mx, my, self.camera) and p is not self.ui.planet:
                            self.ui.dispatch_mission(p, self.highways)
                            break

            # Après
                    for p in self.planets:
                        if p.discovered and p.is_clicked(mx, my, self.camera) and p is not self.ui.planet:
                            self.ui.dispatch_mission(p, self.highways)
                            break
```

- [ ] **Test manuel**

```bash
python main.py
```

Vérifier :
- Impossible de cliquer sur une planète non encore découverte (aucun panel ne s'ouvre, aucun hover).
- En mode mission (clic sur "Explorer" ou "Miner"), impossible de sélectionner une planète non découverte.
- Une planète dans le rayon de la Home est bien cliquable dès le début.

- [ ] **Commit**

```bash
git add game.py
git commit -m "feat: restrict planet hover/click/mission targeting to discovered planets"
```

---

### Task 5 : UI — bouton "Naviguer" dans ShipUI + renommage labels

**Files:**
- Modify: `ui_ship.py` — condition bouton navigate, labels état, textes boutons
- Modify: `ui_planet.py` — occurrences de "Patrouille" aux lignes 1036, 1070, 1124

- [ ] **Mettre à jour `_compute_panel_h` dans `ui_ship.py` — nouvelle condition**

Dans `ui_ship.py`, remplacer dans `_compute_panel_h()` (~ligne 36) :

```python
        # Avant
        if s.fire_range > 0:
            h += 26  # patrol row (always reserved for combat ships)

        # Après
        _can_navigate = s.fire_range > 0 or "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
        if _can_navigate:
            h += 26  # navigate row
```

- [ ] **Mettre à jour `STATE_LABELS` dans `draw()` de `ui_ship.py`**

Dans `ui_ship.py`, dans la méthode `draw()`, remplacer :

```python
        # Avant
            MISSION_PATROL:   "En patrouille",

        # Après
            MISSION_PATROL:   "En navigation",
```

- [ ] **Remplacer le bloc du bouton patrol par le bouton "Naviguer" dans `draw()`**

Dans `ui_ship.py`, remplacer le bloc conditionnel combat ship (~ligne 271) :

```python
        # Avant
        if s.fire_range > 0:
            has_patrol_cancel = s.state in (MISSION_PATROL, MISSION_COMBAT)
            bx = pr.x + 10
            bw = 140
            patrol_btn = Button((bx, y + 2, bw, 20), "Patrouille", tooltip="patrol_request")
            patrol_btn.handle_mouse(pygame.mouse.get_pos())
            patrol_btn.draw(surface)
            self._buttons.append(patrol_btn)
            if has_patrol_cancel:
                cancel_btn = Button((pr.x + pr.w - 150, y + 2, 140, 20),
                                    "Annuler patrouille", tooltip="cancel_mission")
                cancel_btn.handle_mouse(pygame.mouse.get_pos())
                cancel_btn.draw(surface)
                self._buttons.append(cancel_btn)
            y += 26  # always advance

        # Après
        _can_navigate = s.fire_range > 0 or "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
        if _can_navigate:
            has_nav_cancel = s.state in (MISSION_PATROL, MISSION_COMBAT)
            bx = pr.x + 10
            bw = 140
            nav_btn = Button((bx, y + 2, bw, 20), "Naviguer", tooltip="patrol_request")
            nav_btn.handle_mouse(pygame.mouse.get_pos())
            nav_btn.draw(surface)
            self._buttons.append(nav_btn)
            if has_nav_cancel:
                cancel_btn = Button((pr.x + pr.w - 150, y + 2, 140, 20),
                                    "Annuler navigation", tooltip="cancel_mission")
                cancel_btn.handle_mouse(pygame.mouse.get_pos())
                cancel_btn.draw(surface)
                self._buttons.append(cancel_btn)
            y += 26  # always advance
```

- [ ] **Renommer "Patrouille" dans `ui_planet.py` — ligne 1036**

Dans `ui_planet.py`, remplacer :

```python
        # Avant
                           "colonize": "Coloniser", "patrol": "Patrouille",

        # Après
                           "colonize": "Coloniser", "patrol": "Naviguer",
```

- [ ] **Renommer "Patrouille" dans `ui_planet.py` — ligne 1070**

Dans `ui_planet.py`, remplacer :

```python
        # Avant
                st_txt = f"Patrouille → {dp.name}" if dp and dp is not p else "Patrouille"

        # Après
                st_txt = f"Navigation → {dp.name}" if dp and dp is not p else "Naviguer"
```

- [ ] **Renommer "Patrouille" dans `ui_planet.py` — ligne 1124**

Dans `ui_planet.py`, remplacer :

```python
        # Avant
                                    "Patrouille", tooltip=f"patrol:{ship.id}",

        # Après
                                    "Naviguer", tooltip=f"patrol:{ship.id}",
```

- [ ] **Test manuel**

```bash
python main.py
```

Vérifier :
- Sélectionner une Probe : le bouton "Naviguer" apparaît (pas "Patrouille").
- Cliquer "Naviguer" → le curseur passe en mode navigation (overlay "Cliquez sur la carte..."), clic sur la carte → la Probe se déplace.
- Sélectionner un Fighter : le bouton s'appelle aussi "Naviguer" (pas "Patrouille").
- L'état affiché dans ShipUI pendant le déplacement est "En navigation" (pas "En patrouille").
- Dans l'onglet Flotte de PlanetUI, les boutons de navigation s'appellent "Naviguer".

- [ ] **Lancer la suite de tests complète**

```bash
pytest tests/ -v
```

Résultat attendu : tous les tests PASSED.

- [ ] **Commit final**

```bash
git add ui_ship.py ui_planet.py
git commit -m "feat: rename Patrouille to Naviguer in all UI, show Naviguer button for Probe"
```
