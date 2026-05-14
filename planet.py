import pygame
import random
import os
from constants import *
from constants import QUEUE_MAX
from building import Building

_planet_images = {}

def _load_img(path, size):
    key = (path, size)
    if key not in _planet_images:
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (size, size))
        except Exception:
            img = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(img, (100, 100, 200), (size//2, size//2), size//2)
        _planet_images[key] = img
    return _planet_images[key]


PLANET_IMGS = {
    "rocky":    "assets/2D/Planet1.png",
    "gas":      "assets/2D/GazPlanet1.png",
    "asteroid": "assets/2D/Field1.png",
}
UNKNOWN_IMGS = {
    "rocky":    "assets/2D/UnknownPlanet.png",
    "gas":      "assets/2D/UnknownPlanet.png",
    "asteroid": "assets/2D/UnknownField.png",
}
PLANET_SIZES = {"rocky": 80, "gas": 96, "asteroid": 72}


class Planet:
    _id_counter = 0

    def __init__(self, x, y, planet_type, name, is_home=False, habitable=False,
                 available_resources=None):
        Planet._id_counter += 1
        self.id = Planet._id_counter
        self.x = x
        self.y = y
        self.type = planet_type
        self.name = name
        self.size = PLANET_SIZES[planet_type]
        self.colonized = is_home
        self.explored = is_home
        self.discovered = is_home
        self.is_home = is_home
        self.habitable = is_home or habitable

        # Resources
        self.resources = {r: 0.0 for r in RESOURCE_NAMES}
        if is_home:
            self.resources.update(START_RESOURCES)

        # Available resource types on this planet (procedurally assigned by generate_planets)
        self.available_resources = available_resources if available_resources is not None \
                                   else PLANET_RESOURCES[planet_type]

        # Buildings and construction queue
        self.buildings: list[Building] = []
        self.build_queue: list[dict] = []   # {"name": str, "time_left": float}

        # Ship construction queue (only if Shipyard built)
        self.ship_queue: list[dict] = []    # {"ship_type": str, "time_left": float}

        # Ships docked here
        self.ships = []

    # ── properties ───────────────────────────────────────────────
    @property
    def solid_storage_cap(self):
        silo = self.get_building("Silo")
        return STORAGE_BASE + (silo.level * STORAGE_PER_SILO_LEVEL if silo else 0)

    @property
    def fluid_storage_cap(self):
        tank = self.get_building("Fuel Tank")
        return FLUID_BASE + (tank.level * STORAGE_PER_TANK_LEVEL if tank else 0)

    def storage_cap_for(self, res):
        return self.fluid_storage_cap if res in FLUID_RESOURCES else self.solid_storage_cap

    @property
    def storage_cap(self):
        return self.solid_storage_cap

    @property
    def has_shipyard(self):
        return any(b.name == "Shipyard" for b in self.buildings)

    @property
    def shipyard_level(self):
        sy = next((b for b in self.buildings if b.name == "Shipyard"), None)
        return sy.level if sy else 0

    def building_names(self):
        return [b.name for b in self.buildings]

    def get_building(self, bname):
        return next((b for b in self.buildings if b.name == bname), None)

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, all_ships):
        if not self.colonized:
            return

        # Buildings produce resources
        for b in self.buildings:
            b.update(dt, self.resources)

        # Cap resources to storage limit (solids and fluids have separate caps)
        for res in RESOURCE_NAMES:
            cap = self.storage_cap_for(res)
            if self.resources[res] > cap:
                self.resources[res] = cap

        # Auto-refuel combat ships docked here whenever fuel is available
        for s in self.ships:
            if (s.fuel_capacity is not None and s.is_docked
                    and s.fuel_remaining < s.fuel_capacity):
                needed = s.fuel_capacity - s.fuel_remaining
                available = self.resources.get(s.fuel_type, 0)
                amount = min(needed, available)
                if amount > 0:
                    self.resources[s.fuel_type] -= amount
                    s.fuel_remaining += amount

        # Build / upgrade queue
        if self.build_queue:
            entry = self.build_queue[0]
            entry["time_left"] -= dt
            if entry["time_left"] <= 0:
                self.build_queue.pop(0)
                if entry.get("upgrade"):
                    b = self.get_building(entry["name"])
                    if b:
                        b.level_up()
                else:
                    self.buildings.append(Building(entry["name"]))

        # Ship queue — apply shipyard time factor
        if self.ship_queue and self.has_shipyard:
            entry = self.ship_queue[0]
            entry["time_left"] -= dt
            if entry["time_left"] <= 0:
                self.ship_queue.pop(0)
                self._spawn_ship(entry["ship_type"], all_ships)

    def _spawn_ship(self, ship_type, all_ships):
        from ship import Ship
        s = Ship(ship_type, self)
        if s.fuel_capacity is not None:
            available = self.resources.get(s.fuel_type, 0)
            amount = min(s.fuel_capacity, available)
            self.resources[s.fuel_type] -= amount
            s.fuel_remaining = amount
        all_ships.append(s)
        self.ships.append(s)

    # ── actions ──────────────────────────────────────────────────
    def can_build(self, bname):
        defn = BUILDING_DEFS[bname]
        if bname in self.building_names(): return False, "Already built"
        if any(e["name"] == bname for e in self.build_queue): return False, "Already in queue"
        if len(self.build_queue) >= QUEUE_MAX: return False, "Queue full"
        if self.type not in BUILDING_PLANET_TYPES[bname]: return False, "Wrong planet type"
        for res, amt in defn["cost"].items():
            if self.resources.get(res, 0) < amt: return False, f"Need {amt} {res}"
        return True, ""

    def start_build(self, bname):
        ok, _ = self.can_build(bname)
        if not ok: return False
        defn = BUILDING_DEFS[bname]
        cost = dict(defn["cost"])
        for res, amt in cost.items():
            self.resources[res] -= amt
        self.build_queue.append({"name": bname, "time_left": defn["time"],
                                 "time_total": defn["time"], "cost": cost})
        return True

    def can_upgrade(self, bname):
        b = self.get_building(bname)
        if not b: return False, "Not built"
        if b.level >= LEVEL_MAX: return False, "Niveau max"
        if any(e["name"] == bname and e.get("upgrade") for e in self.build_queue):
            return False, "Déjà en upgrade"
        if len(self.build_queue) >= QUEUE_MAX: return False, "Queue full"
        for res, amt in b.upgrade_cost().items():
            if self.resources.get(res, 0) < amt: return False, f"Need {amt} {res}"
        return True, ""

    def start_upgrade(self, bname):
        ok, _ = self.can_upgrade(bname)
        if not ok: return False
        b = self.get_building(bname)
        cost = b.upgrade_cost()
        for res, amt in cost.items():
            self.resources[res] -= amt
        t = b.upgrade_time()
        self.build_queue.append({
            "name": bname, "upgrade": True, "to_level": b.level + 1,
            "time_left": t, "time_total": t, "cost": cost,
        })
        return True

    def can_build_ship(self, stype):
        if not self.has_shipyard: return False, "No Shipyard"
        if len(self.ship_queue) >= QUEUE_MAX: return False, "Queue full"
        defn = SHIP_DEFS[stype]
        req = defn.get("shipyard_level", 1)
        if self.shipyard_level < req: return False, f"Chantier Niv.{req} requis"
        for res, amt in defn["cost"].items():
            if self.resources.get(res, 0) < amt: return False, f"Need {amt} {res}"
        return True, ""

    def start_ship(self, stype):
        ok, _ = self.can_build_ship(stype)
        if not ok: return False
        defn = SHIP_DEFS[stype]
        for res, amt in defn["cost"].items():
            self.resources[res] -= amt
        cost = dict(defn["cost"])
        sy = self.get_building("Shipyard")
        factor = sy.ship_time_factor() if sy else 1.0
        t = defn["time"] * factor
        self.ship_queue.append({"ship_type": stype, "time_left": t, "time_total": t, "cost": cost})
        return True

    def _refund(self, entry):
        for res, amt in entry.get("cost", {}).items():
            self.resources[res] = self.resources.get(res, 0) + amt

    def cancel_build(self):
        if self.build_queue:
            self._refund(self.build_queue.pop(0))

    def cancel_all_builds(self):
        while self.build_queue:
            self._refund(self.build_queue.pop(0))

    def cancel_ship(self):
        if self.ship_queue:
            self._refund(self.ship_queue.pop(0))

    def cancel_all_ships(self):
        while self.ship_queue:
            self._refund(self.ship_queue.pop(0))

    def colonize(self):
        self.colonized = True
        self.discovered = True
        self.explored = True
        for res, amt in START_RESOURCES.items():
            self.resources[res] = self.resources.get(res, 0) + amt

    def debug_complete_all(self, all_ships):
        while self.build_queue:
            entry = self.build_queue.pop(0)
            if entry.get("upgrade"):
                b = self.get_building(entry["name"])
                if b:
                    b.level_up()
            else:
                self.buildings.append(Building(entry["name"]))
        while self.ship_queue:
            entry = self.ship_queue.pop(0)
            self._spawn_ship(entry["ship_type"], all_ships)

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, camera):
        if not self.discovered:
            return
        sx, sy = camera.world_to_screen(self.x, self.y)
        draw_size = max(10, int(self.size * camera.zoom))
        half = draw_size // 2

        if sx + half < 0 or sx - half > SCREEN_W: return
        if sy + half < 0 or sy - half > SCREEN_H: return

        img_path = PLANET_IMGS[self.type] if self.explored else UNKNOWN_IMGS[self.type]
        img = _load_img(img_path, draw_size)
        surface.blit(img, (sx - half, sy - half))

        # Name label (fixed size, unaffected by zoom)
        if camera.zoom >= ZOOM_MIN:
            try:
                font = pygame.font.SysFont("consolas", 11)
            except Exception:
                font = pygame.font.Font(None, 13)
            label = self.name if self.explored else "???"
            if self.colonized:
                name_color = GREEN
            else:
                name_color = WHITE
            txt = font.render(label, True, name_color)
            surface.blit(txt, (sx - txt.get_width() // 2, sy + half + 4))

        # Home marker
        if self.is_home and camera.zoom >= 0.4:
            pygame.draw.circle(surface, GOLD, (sx, sy - half - 6), max(3, int(4 * camera.zoom)))

    def draw_selected(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        half = max(10, int(self.size * camera.zoom)) // 2
        pygame.draw.circle(surface, GREEN, (sx, sy), half + 8, 2)

    def draw_hover(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        half = max(10, int(self.size * camera.zoom)) // 2
        pygame.draw.circle(surface, CYAN, (sx, sy), half + 8, 2)

    def is_clicked(self, mx, my, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        half = max(10, int(self.size * camera.zoom)) // 2
        return (mx - sx) ** 2 + (my - sy) ** 2 <= (half + 8) ** 2

def generate_planets(num=NUM_PLANETS):
    rng = random.Random(7)
    types = ["rocky", "gas", "asteroid"]
    type_weights = [0.5, 0.3, 0.2]
    planets = []
    margin = 300
    names_used = set()

    def rand_name():
        prefixes = ["Aros", "Belta", "Crion", "Duras", "Elis", "Feron",
                    "Gala",  "Hive",  "Isar",  "Juno",  "Kael", "Lyra",
                    "Mora",  "Nexus", "Oryn",  "Plex",  "Quon", "Ryke",
                    "Sera",  "Tyco",  "Ulvax", "Vega",  "Wyx",  "Xen"]
        suffixes = ["Prime", "II", "III", "Alpha", "Beta", "Minor", "Major", ""]
        for _ in range(200):
            n = rng.choice(prefixes) + (" " + rng.choice(suffixes) if rng.random() > 0.4 else "")
            n = n.strip()
            if n not in names_used:
                names_used.add(n)
                return n
        return f"P-{len(planets)+1}"

    _GAS_RESOURCE_OPTS = [["oil"], ["deuterium"], ["oil", "deuterium"]]
    _SOLID_THIRD       = ["silver", "gold", "deuterium"]

    # First planet is home (center-ish) — always iron + oil + silver
    home_x = WORLD_W // 2 + rng.randint(-200, 200)
    home_y = WORLD_H // 2 + rng.randint(-200, 200)
    planets.append(Planet(home_x, home_y, "rocky", "Terra Nova", is_home=True,
                          available_resources=["iron", "oil", "silver"]))

    attempts = 0
    while len(planets) < num and attempts < 5000:
        attempts += 1
        px = rng.randint(margin, WORLD_W - margin)
        py = rng.randint(margin, WORLD_H - margin)
        too_close = any(
            (px - p.x)**2 + (py - p.y)**2 < PLANET_MIN_DIST**2
            for p in planets
        )
        too_far = all(
            (px - p.x)**2 + (py - p.y)**2 > PLANET_MAX_DIST**2
            for p in planets
        )
        if too_close or too_far:
            continue
        ptype = rng.choices(types, type_weights)[0]
        habitable = rng.random() < HABITABLE_RATIO
        if ptype == "gas":
            avail = rng.choice(_GAS_RESOURCE_OPTS)
        else:
            avail = ["iron", "oil", rng.choice(_SOLID_THIRD)]
        planets.append(Planet(px, py, ptype, rand_name(), habitable=habitable,
                              available_resources=avail))

    return planets
