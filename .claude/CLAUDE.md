# StarMiner — Contexte projet

Jeu de stratégie spatiale 2D Python 3 / Pygame 2. Point d'entrée : `main.py` → `Game` (`game.py`). Résolution 1280×800, 60 FPS, monde 24 000×24 000 px.

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `constants.py` | `BUILDING_DEFS`, `SHIP_DEFS`, `FACTION_DEFS`, couleurs, constantes |
| `game.py` | Boucle principale, update, rendu, événements |
| `planet.py` | `Planet` + `generate_planets()` — 30 planètes, `planets[0]` = home |
| `ship.py` | `Ship` : missions, IA, fuel, combat, animations |
| `fleet.py` | `Fleet` : 1 max/planète, `game.fleets: dict[int, Fleet]` |
| `building.py` | `Building` : production, upgrade, prix |
| `debris.py` | `Debris` : épaves collectables |
| `camera.py` | Zoom/scroll ; `world_to_screen` / `screen_to_world` |
| `ui_planet.py` | `PlanetUI` : onglets Ressources / Bâtiments / Fleet |
| `ui_ship.py` | `ShipUI` : panneau vaisseau sélectionné |
| `ui_fleet.py` / `ui_fleet_bar.py` | `FleetUI` + `FleetBar` (barre bas d'écran) |
| `ui_map.py` | `ColonyBar` : barre gauche repliable des colonies |
| `ui_common.py` | `_font()`, `_fmt_time()`, `Button(rect, text, enabled, tooltip, active)` |

## Ressources & Stockage

5 ressources : `iron`, `gold`, `silver` (solides), `oil`, `deuterium` (fluides).
- Solides : cap = `STORAGE_BASE + Silo.level × STORAGE_PER_SILO_LEVEL`
- Fluides : cap = `FLUID_BASE + FuelTank.level × STORAGE_PER_TANK_LEVEL`
- `planet.storage_cap_for(res)` retourne le bon cap.

## Bâtiments

Catégories : `mine`, `storage`, `factory` (définis dans `BUILDING_DEFS`).
- `upgrade_cost()` = `base × 2^level` ; `upgrade_time()` = `base × 1.5^level`
- `Shipyard.ship_time_factor()` = `0.9^(level-1)` (−10 %/niveau)
- `planet.build_queue` / `planet.ship_queue` — `LEVEL_MAX = 10`, `QUEUE_MAX = 10`

## Vaisseaux

Définis dans `SHIP_DEFS`. Missions : `IDLE`, `TRAVEL`, `MINE`, `DISCOVER`, `RETURN`, `NAVIGATE`, `COMBAT`.
- Envoi : `send_explore/mine/colonize/highway/transport/collect/navigate`
- Fuel civils : prélevé sur `home.resources` ; combattants : réservoir dédié `fuel_remaining`
- `ship.repeat = True` → relance automatique (mine, transport)
- Upgrades : `game.ship_upgrades: dict[str, int]`, multiplicateur `1.0 + (level-1)*0.15`, `ship.apply_upgrade(level)`, affiché `★Niv.X`
- `ship.fleet` non-None bloque `send_mine/explore/colonize/highway/transport/collect`

## Flottes

```
Fleet: id, name, home, ships, state ("docked"|"navigate"|"combat"|"returning"), x, y, _nav_target
```
- `add_ship` / `remove_ship` (flotte docked) ; `dissolve(game_fleets)` supprime la flotte
- Navigation formation rigide : vitesse = min des membres (`ship._fleet_nav_speed` injecté par `fleet.update()`)
- UI : `FleetUI` (panneau droit) + `FleetBar` (`BAR_Y = SCREEN_H - 44`, `START_X = 175`)

## Débris & Factions

- Débris : 10 initiaux (seed 99) + spawn à la destruction (30 % coût + cargo) ; `debris._collected = True` pour supprimer
- Factions : `player`, `krell`, `vexari`, `nexus`, `neutral` — 5 ennemis au démarrage (seed 42)
- Fog of war : `DETECTION_RANGE = 800 px`

## UI — Comportements clés

- **PlanetUI** — onglet Fleet : `IDLE`/`NAVIGATE` → boutons mission + Annuler si NAVIGATE ; `COMBAT` → Naviguer + Annuler ; autres → Annuler seul
- **ShipUI** — Naviguer toujours affiché ; Explorer si `can_do("explore")` ; Annuler si NAVIGATE ou COMBAT
- **ColonyBar** — clic = PlanetUI, double clic = centrer caméra ; indicateurs : gold (home), orange (queue), green (idle), `!` rouge (≥ 95 % cap)
- **Button** — état `active` : affiche `>> texte` fond orange ; `is_clicked(pos, event)`

## Patterns & règles

- Toujours `_font(size)` (ui_common.py) pour les polices
- `surface.set_clip(rect)` pour éviter les débordements de texte
- `_upg_tooltip` : collecter pendant le draw loop, rendre après la boucle
- `from constants import *` pour couleurs et defs
- **Ne jamais faire de commit git à la place de l'utilisateur**
