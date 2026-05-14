# Spec : Mécanique de découverte de planètes & navigation Probe

**Date :** 2026-05-14  
**Statut :** Approuvé

---

## Contexte

Avant ce changement, toutes les planètes étaient visibles dès le début de la partie (même non explorées, elles apparaissaient sous forme de silhouette "???"). La Probe avait une seule mission : `explore` (voyage vers une planète cible, scanne 10 s, marque `planet.explored = True`, se détruit). Il n'existait pas de navigation libre pour les vaisseaux civils.

---

## Objectifs

1. Masquer les planètes par défaut — seule la planète Home est visible au départ.
2. Introduire le statut `discovered` : une planète entre dans le champ de détection d'un asset joueur → elle devient visible de façon permanente et peut être ciblée par des missions.
3. Étendre la Probe : elle gagne la mission `navigate` (navigation libre identique au patrol des vaisseaux de combat) et une portée de détection supérieure.
4. Renommer "Patrouille" en "Naviguer" dans toutes les UI (les constantes code restent inchangées).

---

## Modèle de données — Planet

### Attributs

| Attribut | Type | Valeur initiale | Description |
|---|---|---|---|
| `discovered` | `bool` | `is_home` | Planète visible sur la carte, ciblable par des missions |
| `explored` | `bool` | `is_home` | Planète scannée par une Probe — affiche image réelle, nom, ressources |

### Matrice d'états

| `discovered` | `explored` | Rendu | Ciblable |
|---|---|---|---|
| `False` | `False` | Non dessinée | Non |
| `True` | `False` | Silhouette "???" + label "???" | Oui |
| `True` | `True` | Image réelle + nom + couleur faction | Oui |

La transition `discovered → True` est permanente (jamais réversie).  
La transition `explored → True` se produit uniquement via la mission `explore` de la Probe (inchangée).

---

## Découverte de planètes — logique de jeu

### Déclencheur

À chaque frame, `Game._update_discovered_planets()` parcourt toutes les planètes non encore découvertes et les compare aux assets joueur :

- **Planètes colonisées** : portée `DETECTION_RANGE` (800 px)
- **Vaisseaux joueur** : portée `ship.detection_range` (attribut lu depuis `SHIP_DEFS`, défaut `DETECTION_RANGE`)

Si la distance entre l'asset et la planète ≤ portée → `planet.discovered = True`.

### Implémentation

```python
# game.py
def _update_discovered_planets(self):
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
            if math.hypot(planet.x - ship.x, planet.y - ship.y) <= ship.detection_range:
                planet.discovered = True
                break
```

Appelé dans `Game._update()` à chaque frame.

---

## Probe — extensions

### SHIP_DEFS mis à jour

```python
"Probe": {
    "cost": {"iron": 50, "gold": 10},
    "time": 15, "speed": 180, "capacity": 0,
    "missions": ["explore", "navigate"],
    "shipyard_level": 1,
    "fuel_type": "oil", "fuel_rate": 0.003,
    "detection_range": 2400,
}
```

- `detection_range: 2400` = 3 × `DETECTION_RANGE` (800 px)
- `"navigate"` ajouté dans `missions`
- Tous les autres types de vaisseau n'ont pas de champ `detection_range` → défaut `DETECTION_RANGE`

### Ship.__init__

```python
self.detection_range = defn.get("detection_range", DETECTION_RANGE)
```

### Mission Navigate

La mission `navigate` utilise exactement `send_patrol(wx, wy)` — aucune nouvelle logique de déplacement.

- La Probe a `fuel_capacity = None` → branche "non-combat" de `send_patrol` : emprunte le carburant sur `home.resources[fuel_type]`, rembourse le surplus à l'arrivée.
- La Probe a `fire_range = 0` → ne peut jamais entrer en `MISSION_COMBAT`.
- À l'arrivée à destination : `state = MISSION_IDLE`.

---

## Changements UI

### ShipUI (`ui_ship.py`)

**Condition d'affichage du bouton de navigation :**

```python
# Avant
if s.fire_range > 0:
    # bouton "Patrouille"

# Après
_can_navigate = s.fire_range > 0 or "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
if _can_navigate:
    # bouton "Naviguer"
```

**Labels mis à jour :**

| Élément | Avant | Après |
|---|---|---|
| Bouton | "Patrouille" | "Naviguer" |
| Bouton annulation | "Annuler patrouille" | "Annuler navigation" |
| `STATE_LABELS[MISSION_PATROL]` | "En patrouille" | "En navigation" |

### game.py — sélection de cible mission

```python
# Filtre ajouté dans _handle_events, mode _mission_mode
if p.is_clicked(mx, my, self.camera) and p is not self.ui.planet and p.discovered:
```

### planet.draw()

```python
def draw(self, surface, camera):
    if not self.discovered:
        return
    # ... reste inchangé
```

### _draw_detection_radii()

Utilise `ship.detection_range` par vaisseau :

```python
for s in self.ships:
    if not s.is_docked:
        r_px = int(s.detection_range * self.camera.zoom)
        # draw circle
```

### _compute_visible_enemies() et _compute_visible_debris()

Utilisent `ship.detection_range` à la place de `DETECTION_RANGE` pour la contribution des vaisseaux.

---

## Fichiers modifiés

| Fichier | Changements |
|---|---|
| `constants.py` | `SHIP_DEFS["Probe"]` : ajouter `detection_range`, `"navigate"` dans missions |
| `planet.py` | Ajouter `self.discovered = is_home` ; `draw()` : retour si `not discovered` |
| `ship.py` | `__init__` : lire `detection_range` depuis SHIP_DEFS |
| `game.py` | Ajouter `_update_discovered_planets()` ; mettre à jour `_compute_visible_enemies`, `_compute_visible_debris`, `_draw_detection_radii`, filtre cible mission |
| `ui_ship.py` | Condition bouton navigate ; labels "Naviguer" / "En navigation" / "Annuler navigation" |

---

## Ce qui ne change pas

- Constantes code : `MISSION_PATROL`, `send_patrol`, `_patrol_dest` — inchangés
- Mission `explore` de la Probe : comportement identique
- Scout : non modifié (garde `detection_range` par défaut)
- `ColonyBar` : affiche uniquement les colonisées — non affectée
- Vaisseaux ennemis : utilisent `DETECTION_RANGE` dans `_compute_visible_enemies` (côté assets joueur)
