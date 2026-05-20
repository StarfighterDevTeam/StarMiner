# Fleets — Design Spec

## Goal

Ajouter un système de flottes inspiré d'OGame : regrouper plusieurs vaisseaux nav-capables en une entité sélectionnable, pilotable comme un vaisseau, avec une barre d'accès rapide horizontale en bas d'écran. Limite : 1 flotte par planète colonisée.

## Architecture

Nouvelle classe `Fleet` dans `fleet.py`. Les Ships membres gardent un champ `fleet` pointant vers leur flotte. Deux nouveaux modules UI : `ui_fleet.py` (panneau d'inspection/modification) et `ui_fleet_bar.py` (barre horizontale bas d'écran). `game.py` maintient `game.fleets: dict[int, Fleet]` keyed par `planet.id`.

**Tech Stack :** Python 3 / Pygame 2 — suit les patterns existants (même style `_font()`, `Button`, `set_clip`, `dispatch_modes`).

---

## Modèle de données

### `Fleet` (`fleet.py`)

```python
class Fleet:
    _id_counter = 0

    def __init__(self, home: Planet):
        Fleet._id_counter += 1
        self.id       = Fleet._id_counter
        self.name     = f"Flotte de {home.name}"
        self.home     = home
        self.ships    : list[Ship] = []
        self.state    : str = "docked"   # "docked" | "navigate" | "combat" | "returning"
        self._pre_combat_state : str = "docked"  # état à restaurer après combat
        self.x        : float = float(home.x)
        self.y        : float = float(home.y)
        self._nav_target : tuple[float, float] | None = None
```

**États :**
| État | Description |
|---|---|
| `"docked"` | Tous les membres sont idle sur `home` (ou à la position actuelle) |
| `"navigate"` | En route vers `_nav_target` |
| `"combat"` | Au moins un membre en `MISSION_COMBAT` |
| `"returning"` | En route vers `home` |

### Champ ajouté à `Ship`

```python
self.fleet: Fleet | None = None
```

Un ship dans une flotte ne peut pas recevoir de mission individuelle (`send_*`) tant que `ship.fleet is not None`, sauf `send_navigate` délégué par la flotte elle-même.

### `game.fleets`

```python
self.fleets: dict[int, Fleet] = {}   # planet.id → Fleet
```

Contrainte : au plus 1 flotte par planète colonisée. La création est refusée si `game.fleets.get(planet.id)` existe déjà.

---

## Comportement de la flotte

### Vitesse de formation

Vitesse effective = `min(s.speed for s in fleet.ships)`. Chaque membre se déplace à cette vitesse pendant la navigation en flotte (override temporaire, `_effective_speed` n'est pas persisté).

### `fleet.update(dt, planets, highways, all_ships)`

- Met à jour `x, y` (barycentre des membres ou position commune en transit).
- Si `state == "navigate"` : déplace chaque membre vers `_nav_target` à `fleet_speed`. Quand tous arrivent → `state = "docked"`, `_nav_target = None`.
- Si `state == "returning"` : déplace vers `home.x, home.y`. À l'arrivée → `state = "docked"`, ships passent `MISSION_IDLE`.
- Détecte si un membre passe `MISSION_COMBAT` → sauvegarde `_pre_combat_state = state`, `state = "combat"`. Quand plus aucun membre en combat → `state = _pre_combat_state`.
- Nettoie les ships détruits : `self.ships = [s for s in self.ships if not s._destroyed]` (et `s.fleet = None` pour chacun). Ne pas déléguer cette logique à `ship.update()` (évite un import circulaire `ship` → `fleet`).

### `fleet.send_navigate(wx, wy)`

Conditions : `state == "docked"` et au moins 1 ship membre. Définit `_nav_target = (wx, wy)`, `state = "navigate"`, tous les membres passent `MISSION_TRAVEL`.

### `fleet.send_return()`

`state = "returning"`, tous les membres passent `MISSION_TRAVEL` vers `home`.

### `fleet.cancel()`

Annule la navigation / retour en cours. Tous les membres passent `MISSION_IDLE` sur leur position actuelle. `state = "docked"`.

### Ajout d'un ship (`fleet.add_ship(ship)`)

Conditions : `fleet.state == "docked"` ET `ship.state == MISSION_IDLE` ET `ship.home is fleet.home` ET `"navigate"` dans `SHIP_DEFS[ship.type]["missions"]` ET `ship.fleet is None`.

```python
ship.fleet = self
self.ships.append(ship)
```

### Retrait d'un ship (`fleet.remove_ship(ship)`)

Condition : `fleet.state == "docked"`.

```python
ship.fleet = None
self.ships.remove(ship)
```

La flotte peut rester vide (elle n'est pas auto-détruite).

### Dissolution (`fleet.dissolve()`)

Retire tous les ships (`ship.fleet = None`), supprime `game.fleets[fleet.home.id]`.

---

## UI : FleetUI (`ui_fleet.py`)

Panneau inspiré de `ShipUI`. Activé par clic sur la flotte (carte) ou via la Fleet Bar. Fermé par ESC ou clic hors panneau (même logique que ShipUI).

### En-tête

- Nom de la flotte : texte cliquable → passe en mode édition (champ texte inline, `pygame.TEXTINPUT` events, confirmé par Entrée ou clic hors champ).
- État coloré : `CYAN` = docked, `ORANGE` = navigate/returning, `RED` = combat.
- Planète home (gris).

### Liste des membres

- Une ligne par ship : `[type] Niv.X — [état]`.
- Quand `fleet.state == "docked"` : bouton **Retirer** (16px, gris) en fin de ligne.
- En bas de liste : bouton **+ Ajouter** → ouvre une sous-liste des ships `MISSION_IDLE` sur `home` et `"navigate"` dans leurs missions et `ship.fleet is None`. Clic sur un ship de la sous-liste → `fleet.add_ship(ship)`.

### Boutons de mission (bas du panneau)

| État flotte | Boutons affichés |
|---|---|
| `"docked"` | **Naviguer** (tooltip `"fleet_navigate_request"`), **Dissoudre** |
| `"navigate"` / `"returning"` | **Annuler** (tooltip `"fleet_cancel"`), **Dissoudre** |
| `"combat"` | **Annuler**, **Dissoudre** |

**Naviguer** : déclenche `game._pending_fleet_dispatch = fleet` → même flow que `_pending_dispatch` pour un ship.

### Renommage inline

Quand le nom est cliqué : `_renaming = True`, un curseur s'affiche, les TEXTINPUT events remplissent `_name_buf`. Entrée ou clic hors du champ valide (`fleet.name = _name_buf`). ESC annule.

---

## UI : FleetBar (`ui_fleet_bar.py`)

Barre horizontale fixe en bas de l'écran.

```
BAR_H    = 44
BAR_Y    = SCREEN_H - BAR_H
CARD_W   = 160
CARD_H   = 36
CARD_PAD = 6
```

### Contenu

- Une card par flotte dans `game.fleets`.
- Card : `[nom]` (tronqué à 18 chars) + indicateur état (dot coloré) + `[n] vaisseaux`.
- Card survolée : fond légèrement plus clair.
- Card sélectionnée (flotte dont FleetUI est ouvert) : bordure CYAN.
- Clic sur card → ouvre FleetUI de cette flotte, ferme PlanetUI / ShipUI.

### Fond

Bande semi-transparente `(10, 14, 30, 200)` sur toute la largeur. Toujours visible (pas de toggle). Si aucune flotte : affiche `"Aucune flotte"` en gris centré.

### Collision

`fleet_bar.contains_point(pos)` : retourne `True` si `pos.y >= BAR_Y`. Utilisé dans `game.py` pour bloquer les clics traversants vers la carte.

---

## Représentation sur la carte

- Icône : losange cyan (dessiné en `pygame.draw.polygon`, 12px) à la position `(fleet.x, fleet.y)`.
- Label : `fleet.name` en `_font(9)`, couleur `CYAN`, au-dessus de l'icône.
- Cliquable : `fleet.is_clicked(mx, my, camera)` → `abs(sx - fx) + abs(sy - fy) < 10` (hitbox losange).
- Visible : toujours (flotte joueur).
- Rendu dans `game._draw()` après les ships civils, avant les ships ennemis.

---

## Intégration `game.py`

### Nouveaux attributs

```python
self.fleets: dict[int, Fleet] = {}
self.fleet_ui = FleetUI()
self.fleet_bar = FleetBar()
self._pending_fleet_dispatch: Fleet | None = None
```

### `_update(dt)`

```python
for fleet in self.fleets.values():
    fleet.update(dt, self.planets, self.highways, self.ships + self.enemy_ships)
```

### `_draw()`

```python
# Flottes sur la carte
for fleet in self.fleets.values():
    fleet.draw(self.screen, self.camera)
# Fleet Bar
self.fleet_bar.draw(self.screen, self.fleets, selected_fleet=self.fleet_ui.fleet if self.fleet_ui.visible else None)
# FleetUI
if self.fleet_ui.visible:
    self.fleet_ui.draw(self.screen, dispatch_modes=dispatch_modes)
```

### `_handle_events()` — ordre de priorité

1. ESC : ferme FleetUI avant ShipUI (nouveau palier).
2. FleetBar : `fleet_bar.handle_event()` — intercept avant les clics carte.
3. FleetUI : `fleet_ui.handle_event()`.
4. `_pending_fleet_dispatch` : même flow que `_pending_dispatch` navigate mais pour une flotte.
5. Clic carte : flottes avant ships avant planètes (priorité ordre existant).

### Création de flotte

Depuis l'onglet Fleet de PlanetUI : bouton **Créer une flotte** si :
- `planet.id not in game.fleets`
- Au moins 1 ship `MISSION_IDLE` sur `home` avec `"navigate"` dans ses missions

Clic → `fleet = Fleet(planet)`, `game.fleets[planet.id] = fleet`, ouvre FleetUI.

### `dispatch_modes` étendu

```python
if self._pending_fleet_dispatch:
    # highlight bouton Naviguer dans FleetUI
    dispatch_modes[self._pending_fleet_dispatch] = "fleet_navigate"
```

---

## Onglet Fleet de PlanetUI (modifications)

- Section "Flotte de la planète" en haut de l'onglet.
  - Si flotte existante : nom + état + `[n] membres` + bouton **Gérer** (ouvre FleetUI).
  - Si pas de flotte : bouton **Créer une flotte** (conditions ci-dessus).
- Ships membres de la flotte : affichés dans la liste mais boutons de mission grisés (non-cliquables), indicateur `[Flotte]` à droite du nom.

---

## Contraintes et règles

- Un ship dans une flotte : `ship.fleet is not None` → `send_mine`, `send_explore`, `send_colonize`, `send_transport`, `send_collect` refusées (retournent `False` sans effet).
- Flotte vide en état `"docked"` : affichée dans la Fleet Bar, modifiable, mais **Naviguer** désactivé.
- Destruction d'un ship membre (combat) : `ship.fleet.remove_ship(ship)` automatique dans `ship.update()` quand `_destroyed = True`.
- Ship retiré de la flotte quand elle n'est pas docked : non autorisé (bouton **Retirer** grisé).
- Ne pas commiter à la place de l'utilisateur.