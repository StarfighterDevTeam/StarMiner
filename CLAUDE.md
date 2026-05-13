# StarMiner — Contexte projet

Jeu de stratégie spatiale 2D en Python 3 / Pygame 2, tournant sous Windows.
Point d'entrée : `main.py` → `Game` dans `game.py`.
Résolution : 1280 × 800 px, 60 FPS.

---

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `main.py` | Init Pygame, crée `Game`, lance la boucle |
| `game.py` | Boucle principale, update, rendu, gestion des événements |
| `constants.py` | Toutes les constantes : monde, couleurs, `BUILDING_DEFS`, `SHIP_DEFS`, `FACTION_DEFS` |
| `camera.py` | Zoom + scroll ; `world_to_screen` / `screen_to_world` |
| `space_map.py` | Fond étoilé, nébuleuses, étoiles filantes, grille de secteurs |
| `planet.py` | Classe `Planet` + `generate_planets()` |
| `building.py` | Classe `Building` (production, upgrade, prix) |
| `ship.py` | Classe `Ship` : missions, IA, fuel, combat, animations |
| `debris.py` | Classe `Debris` : épaves collectables après destruction |
| `ui_common.py` | Helpers partagés : `_font()`, `_fmt_time()`, `Button`, constantes boutons actifs |
| `ui_planet.py` | `PlanetUI` : panneaux planète (onglets Ressources / Bâtiments / Vaisseaux) |
| `ui_ship.py` | `ShipUI` : panneau de sélection d'un vaisseau |
| `ui_map.py` | `ColonyBar` : barre latérale gauche listant les colonies |

---

## Monde

- Taille : 24 000 × 24 000 px monde.
- 30 planètes générées ; la première (`planets[0]`) est la planète de départ (`is_home=True`).
- Fog of war : `DETECTION_RANGE = 800 px` autour des assets joueur.
- Types de planètes : `"rocky"`, `"gas"`, `"asteroid"`.

---

## Ressources

5 ressources : `iron`, `gold`, `silver`, `oil`, `deuterium`.
- Solides (`SOLID_RESOURCES`) : iron, silver, gold → cap = `STORAGE_BASE + Silo.level × STORAGE_PER_SILO_LEVEL`.
- Fluides (`FLUID_RESOURCES`) : oil, deuterium → cap = `FLUID_BASE + FuelTank.level × STORAGE_PER_TANK_LEVEL`.
- `planet.storage_cap_for(res)` retourne le bon cap selon le type.

---

## Bâtiments (`Building`)

Définis dans `BUILDING_DEFS` (constants.py). Catégories : `mine`, `storage`, `factory`.
- `building.upgrade_cost()` → coût `base × 2^level` (doublement par niveau).
- `building.upgrade_time()` → temps `base × 1.5^level`.
- `Shipyard.ship_time_factor()` → `0.9^(level-1)` (−10 % par niveau).
- `planet.build_queue` : liste `{"name": str, "time_left": float}`.
- `planet.ship_queue` : liste `{"ship_type": str, "time_left": float}`.
- Max niveau : `LEVEL_MAX = 10`. Max items en queue : `QUEUE_MAX = 10`.

---

## Vaisseaux (`Ship`)

Définis dans `SHIP_DEFS` (constants.py). Champs clés :
`cost`, `time`, `speed`, `capacity`, `missions`, `shipyard_level`,
`fuel_type`, `fuel_rate`, `fuel_capacity` (None = pas de réservoir dédié),
`hp`, `damage`, `fire_range`, `fire_rate` (combattants seulement).

### Missions
| État | Description |
|---|---|
| `MISSION_IDLE` | En attente sur planète home |
| `MISSION_TRAVEL` | En route vers une cible |
| `MISSION_MINE` / `MISSION_DISCOVER` | Mining ou exploration sur place |
| `MISSION_RETURN` | Retour à home |
| `MISSION_PATROL` | Patrouille vers une position monde |
| `MISSION_COMBAT` | Engagement ennemi |

Méthodes d'envoi : `send_explore`, `send_mine`, `send_pump`, `send_colonize`,
`send_highway`, `send_transport`, `send_collect`, `send_patrol`.

### Carburant
- Vaisseaux civils : empruntent le carburant sur `home.resources[fuel_type]`.
- Vaisseaux combattants (`fuel_capacity is not None`) : réservoir dédié `fuel_remaining`, rechargé au dock.
- `ship.fuel_cost(mtype, target)` : coût aller-retour pour missions cycliques, aller simple sinon.

### Mode Repeat
`ship.repeat = True` → relance automatique de la mission à l'arrivée (mine, pump, transport).

### Transport inter-planètes
`send_transport(target, outbound_res, inbound_res)` — charge `outbound_res` à l'aller, `inbound_res` au retour si `repeat=True`.

### Collect (débris)
`send_collect(debris)` — vole vers un `Debris`, charge son contenu dans `cargo`, revient à home.

### Upgrades de vaisseaux
- `game.ship_upgrades: dict[str, int]` — niveau d'upgrade par type, partagé par référence avec `ui.ship_upgrades`.
- Niveaux 1–10 ; multiplicateur : `1.0 + (level - 1) * 0.15` (+15 %/niveau sur hp, damage, fire_range, fuel_capacity, capacity).
- `ship.apply_upgrade(level)` recalcule les stats depuis `SHIP_DEFS` × multiplicateur.
- `ship._upgrade_level` stocke le niveau courant (affiché `★Niv.X` en gold dans les UI).
- Coût d'upgrade : `level_actuel × base_ship_cost` (escalade).

---

## Débris (`Debris`)

Spawné dans `game.debris_list` :
- 10 débris initiaux (seed 99) loin de la planète home.
- Nouveaux débris lors de la destruction d'un vaisseau (`_spawn_debris_from_ship`) : 30 % du coût de construction + le cargo embarqué.
- Visibilité : `_visible_debris` — même logique que fog of war.
- `debris._collected = True` → supprimé de la liste au prochain nettoyage.

---

## Factions

`FACTION_DEFS` : `player`, `krell` (enemy), `vexari` (enemy), `nexus` (enemy), `neutral`.
- 5 vaisseaux ennemis spawned au démarrage (seed 42), répartis angulairement autour de home.
- Combattants ennemis patrouillent et attaquent les vaisseaux joueur à portée.

---

## UI

### `PlanetUI` (ui_planet.py)
- Activée par clic sur une planète colonisée.
- 3 onglets : **Ressources** (stocks + jauges), **Bâtiments** (queue + upgrade), **Vaisseaux** (construction + upgrade).
- Onglet Vaisseaux : `row_h = 64`, bouton **Construire** (haut) + bouton **↑ Niv.X** (bas), info + missions clippées pour ne pas déborder sur les boutons.
- Tooltip d'upgrade au survol du bouton Niv.
- Accès à `ship_upgrades` via `self.ship_upgrades` (référence partagée avec `game.py`).

### `ShipUI` (ui_ship.py)
- Activée par clic sur un vaisseau joueur.
- Affiche type, `Niv.X` (gold), état, stats, fuel, cargo, bouton Annuler mission.

### `ColonyBar` (ui_map.py)
- Barre latérale gauche repliable (`◀`/`▶`).
- Liste les planètes colonisées ; simple clic = ouvre PlanetUI, double clic = centre caméra + ouvre PlanetUI.
- Indicateurs : dot gold (home), orange (queue active), green (idle) ; `!` rouge si ressource ≥ 95 % cap.

### `Button` (ui_common.py)
- `Button(rect, text, enabled, tooltip, active)`.
- État `active` : affiche `>> texte` avec fond orange.
- `is_clicked(pos, event)` pour la détection clic.

---

## Caméra

- Zoom molette (zoom vers curseur).
- Scroll : flèches / ZQSD, ou drag clic-droit.
- `camera.world_to_screen(wx, wy)` / `camera.screen_to_world(sx, sy)`.

---

## Patterns importants

- `_font(size)` — toujours utiliser cette fonction (ui_common.py) pour les polices ; tente Consolas, sinon fallback pygame.
- `surface.set_clip(rect)` — utilisé dans ui_planet pour éviter que le texte déborde sur les boutons.
- `_upg_tooltip` — pattern : collecter les données tooltip pendant le draw loop, rendre après la boucle pour apparaître au-dessus.
- Toutes les constantes de couleur (`CYAN`, `GOLD`, `RED`, etc.) et `SHIP_DEFS`, `BUILDING_DEFS` sont importées via `from constants import *`.
