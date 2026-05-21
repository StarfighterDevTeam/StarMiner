import pygame
import random
import math
from constants import *
from camera import Camera
from space_map import SpaceMap
from planet import generate_planets
from ship import Ship
from ui_planet import PlanetUI
from ui_ship import ShipUI
from ui_map import ColonyBar
from fleet import Fleet
from ui_fleet import FleetUI
from ui_fleet_bar import FleetBar
from ui_minimap import MiniMap
from debris import Debris

def _draw_dashed_line(surface, color, start, end, dash=8, gap=5, width=1):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    pos, drawing = 0.0, True
    while pos < length:
        seg = dash if drawing else gap
        npos = min(pos + seg, length)
        if drawing:
            pygame.draw.line(surface, color,
                             (int(x1 + ux * pos),  int(y1 + uy * pos)),
                             (int(x1 + ux * npos), int(y1 + uy * npos)), width)
        pos, drawing = npos, not drawing


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.space_map = SpaceMap()
        self.planets = generate_planets(NUM_PLANETS)
        self.ships = []
        self.highways = set()
        self.ui = PlanetUI()
        self.ship_upgrades = {stype: 1 for stype in SHIP_DEFS}
        self.ui.ship_upgrades = self.ship_upgrades
        self.ship_ui = ShipUI()
        self.colony_bar = ColonyBar()
        self.fleets: dict     = {}
        self.fleet_ui         = FleetUI()
        self.fleet_bar        = FleetBar()
        self._pending_fleet_dispatch = None
        self.ui.fleets        = self.fleets
        self.minimap = MiniMap()
        self._hovered_planet = None
        self._hovered_ship = None
        self._time_scale = 1.0
        self._debug_fog_off = False
        self._running = True
        self._pending_dispatch = None   # (ship, mtype) | None — ship waiting for a map/target click

        # Center camera on home planet at initial zoom
        self.camera.zoom = ZOOM_INIT
        home = self.planets[0]
        self.camera.x = home.x - SCREEN_W / (2 * self.camera.zoom)
        self.camera.y = home.y - SCREEN_H / (2 * self.camera.zoom)

        self.enemy_ships = []
        self._faction_homes = self._assign_faction_homes()
        self._spawn_initial_enemies()
        self._visible_enemies = set()
        self._planet_known_ranges: dict = {}  # planet.id → (max_fire_range, faction_relationship)
        self._hud_msg = ""
        self._hud_msg_timer = 0.0
        self.debris_list: list = []
        self._visible_debris: set = set()
        self._hovered_debris = None
        self._spawn_initial_debris()

    # ── enemy management ─────────────────────────────────────────
    def _assign_faction_homes(self):
        """Pick one real planet per enemy/neutral faction as their home base."""
        home = self.planets[0]
        factions = ["krell", "vexari", "nexus", "neutral"]
        n = len(factions)
        assigned = []
        homes = {}

        for i, faction in enumerate(factions):
            target_angle = 2 * math.pi * i / n  # spread uniformly
            best = None
            best_score = -float("inf")
            for p in self.planets[1:]:
                if p in assigned:
                    continue
                dx = p.x - home.x
                dy = p.y - home.y
                d = math.hypot(dx, dy)
                if d < 3500:
                    continue
                adiff = abs((math.atan2(dy, dx) - target_angle + math.pi) % (2 * math.pi) - math.pi)
                score = d * 0.001 - adiff  # favour far + in-sector
                if score > best_score:
                    best_score = score
                    best = p

            if best is None:  # fallback: farthest unassigned
                cands = [p for p in self.planets[1:] if p not in assigned]
                best = max(cands, key=lambda p: math.hypot(p.x - home.x, p.y - home.y)) if cands else None

            if best:
                assigned.append(best)
                best.faction = faction
                best.discovered = False
                best.explored = False
                best.habitable = False
                best.resources["oil"] = 5000
                best.resources["deuterium"] = 1000
                homes[faction] = best

        return homes

    def _spawn_initial_enemies(self):
        rng = random.Random(42)
        _ENEMY_SHIPS = [
            {"faction": "krell",   "type": "Fighter"},
            {"faction": "krell",   "type": "Destroyer"},
            {"faction": "vexari",  "type": "Fighter"},
            {"faction": "nexus",   "type": "Fighter"},
            {"faction": "neutral", "type": "Fighter"},
        ]
        for entry in _ENEMY_SHIPS:
            faction = entry["faction"]
            home_planet = self._faction_homes.get(faction)
            if home_planet is None:
                continue
            angle = rng.uniform(0, 2 * math.pi)
            dist  = rng.uniform(150, 400)
            wx = max(500, min(WORLD_W - 500, home_planet.x + dist * math.cos(angle)))
            wy = max(500, min(WORLD_H - 500, home_planet.y + dist * math.sin(angle)))
            s = Ship(entry["type"], home_planet, faction=faction)
            s.x = float(wx)
            s.y = float(wy)
            s.fuel_remaining = s.fuel_capacity
            self.enemy_ships.append(s)

    def _spawn_initial_debris(self):
        rng  = random.Random(99)
        home = self.planets[0]
        for _ in range(10):
            for _ in range(20):
                x = rng.randint(800, WORLD_W - 800)
                y = rng.randint(800, WORLD_H - 800)
                if math.hypot(x - home.x, y - home.y) > 2000:
                    break
            res_count = rng.randint(1, 3)
            res_names = rng.sample(RESOURCE_NAMES, res_count)
            resources = {r: float(rng.randint(10, 80)) for r in res_names}
            self.debris_list.append(Debris(float(x), float(y), resources))

    def _debug_spawn_enemies_at(self, wx, wy, count=10):
        rng = random.Random()
        faction = rng.choice(["krell", "vexari", "nexus"])
        class _FakePlanet:
            def __init__(self_, x, y):
                self_.x = x; self_.y = y; self_.name = "Enemy"
                self_.ships = []; self_.resources = {}; self_.id = -(len(self.enemy_ships) + 1000)
        for i in range(count):
            jitter_x = rng.uniform(-60, 60)
            jitter_y = rng.uniform(-60, 60)
            ex = max(500, min(WORLD_W - 500, wx + jitter_x))
            ey = max(500, min(WORLD_H - 500, wy + jitter_y))
            fp = _FakePlanet(ex + 9999, ey + 9999)  # home loin → is_docked=False → ciblable
            s = Ship("Fighter", fp, faction=faction)
            s.x = float(ex); s.y = float(ey)
            s.fuel_remaining = s.fuel_capacity
            s._debug_idle = True
            self.enemy_ships.append(s)

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

    def _compute_visible_debris(self):
        r2      = DETECTION_RANGE * DETECTION_RANGE
        visible = set()
        for d in self.debris_list:
            if d.revealed:
                visible.add(d)
                continue
            for pl in self.planets:
                if pl.colonized and (d.x - pl.x) ** 2 + (d.y - pl.y) ** 2 <= r2:
                    visible.add(d)
                    break
            if d in visible:
                d.revealed = True
                continue
            for ps in self.ships:
                dr2 = ps.detection_range * ps.detection_range
                if (d.x - ps.x) ** 2 + (d.y - ps.y) ** 2 <= dr2:
                    visible.add(d)
                    d.revealed = True
                    break
        return visible

    def _update_discovered_planets(self):
        r2_colony = DETECTION_RANGE * DETECTION_RANGE
        for planet in self.planets:
            if planet.discovered:
                continue
            for asset_p in self.planets:
                if asset_p.colonized:
                    dx = planet.x - asset_p.x
                    dy = planet.y - asset_p.y
                    if dx * dx + dy * dy <= r2_colony:
                        planet.discovered = True
                        break
            if planet.discovered:
                continue
            for ship in self.ships:
                if ship.is_docked:
                    continue
                dr2 = ship.detection_range * ship.detection_range
                dx = planet.x - ship.x
                dy = planet.y - ship.y
                if dx * dx + dy * dy <= dr2:
                    planet.discovered = True
                    break

    def _update_enemies(self, dt, all_ships):
        for s in self.enemy_ships:
            if s._destroyed:
                continue
            s.update(dt, self.planets, self.highways, all_ships)
            if s.state == "idle" and not getattr(s, "_debug_idle", False):
                s.fuel_remaining = s.fuel_capacity  # enemies magically refuel when idle
                wx = random.randint(500, WORLD_W - 500)
                wy = random.randint(500, WORLD_H - 500)
                s.send_navigate(wx, wy)

        for s in self.enemy_ships:
            if s._destroyed:
                self._spawn_debris_from_ship(s)
        self.enemy_ships = [s for s in self.enemy_ships if not s._destroyed]

    # ── planetary defense ────────────────────────────────────────
    def _update_planet_defense(self, planet, dt):
        defense_bldgs = [b for b in planet.buildings
                         if b.category == "defense" and b.count > 0]
        if not defense_bldgs:
            return

        for bldg in defense_bldgs:
            fire_range = bldg.unit_range()

            in_range = [s for s in self.enemy_ships
                        if not s._destroyed
                        and math.hypot(s.x - planet.x, s.y - planet.y) <= fire_range]

            if not in_range:
                bldg._no_combat_timer += dt
                if bldg._no_combat_timer >= 3.0:
                    bldg.full_recover()
                    bldg._no_combat_timer = 0.0
                continue

            bldg._no_combat_timer = 0.0
            target = min(in_range, key=lambda s: math.hypot(s.x - planet.x, s.y - planet.y))
            # All ships in range face the planet (their attacker)
            for s in in_range:
                dx = planet.x - s.x; dy = planet.y - s.y
                if math.hypot(dx, dy) > 0:
                    s.angle = math.atan2(dy, dx)
            dmg   = bldg.unit_damage()
            rate  = bldg.unit_rate()

            # Each alive unit fires independently
            for i in range(len(bldg._fire_timers)):
                bldg._fire_timers[i] -= dt
                if bldg._fire_timers[i] <= 0:
                    bldg._fire_timers[i] = 1.0 / rate
                    if target and not target._destroyed:
                        target.hp -= dmg
                        if target.hp <= 0:
                            target._destroyed = True
                            remaining = [s for s in in_range if not s._destroyed]
                            target = (min(remaining,
                                         key=lambda s: math.hypot(s.x - planet.x, s.y - planet.y))
                                      if remaining else None)

            # Enemy combat ships retaliate with continuous DPS
            for s in in_range:
                if s._destroyed:
                    continue
                s_dmg  = getattr(s, "damage", 0)
                s_rate = getattr(s, "fire_rate", 0)
                s_rng  = getattr(s, "fire_range", 0)
                if s_dmg > 0 and s_rate > 0 and math.hypot(s.x - planet.x, s.y - planet.y) <= s_rng:
                    bldg.take_damage(s_dmg * s_rate * dt)

    # ── main loop ────────────────────────────────────────────────
    def run(self):
        while self._running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.1) * self._time_scale
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    # ── events ───────────────────────────────────────────────────
    def _handle_events(self):
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return

            # ESC: cancel active modes in priority order
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self._pending_dispatch:
                    self._pending_dispatch = None
                elif self._pending_fleet_dispatch:
                    self._pending_fleet_dispatch = None
                elif self.ui._mission_mode:
                    self.ui._mission_mode = None
                    self.ui.show_message("Mission annulée")
                elif self.fleet_ui.visible:
                    self.fleet_ui.close()
                elif self.ship_ui.visible:
                    self.ship_ui.close()
                elif self.ui.visible:
                    self.ui.close()
                else:
                    self._running = False
                return

            # F1–F4: switch planet UI tab
            if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4):
                if self.ui.visible:
                    self.ui.switch_tab(
                        ("buildings", "ships", "fleet", "defense")[event.key - pygame.K_F1])
                continue

            # F5 debug: complete all production on selected planet
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F5:
                if self.ui.visible and self.ui.planet:
                    self.ui.planet.debug_complete_all(self.ships)
                    self.ui.show_message("[DEBUG] Toutes les productions terminées")
                continue

            # E debug: spawn 10 enemy Fighters at mouse position
            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                wx, wy = self.camera.screen_to_world(mx, my)
                self._debug_spawn_enemies_at(wx, wy)
                continue

            # Colony bar (tab toggle always works; rows blocked during mission mode)
            cb_action, cb_planet = self.colony_bar.handle_event(
                event, self.planets, mission_mode_active=bool(self.ui._mission_mode))
            if cb_action is not None:
                if cb_action in ('select', 'center') and cb_planet:
                    self.ui.open(cb_planet)
                    self.ship_ui.close()
                    if cb_action == 'center':
                        self.camera.x = cb_planet.x - SCREEN_W / (2 * self.camera.zoom)
                        self.camera.y = cb_planet.y - SCREEN_H / (2 * self.camera.zoom)
                continue

            # Fleet bar
            fb_action, fb_fleet = self.fleet_bar.handle_event(event, self.fleets)
            if fb_action in ("select", "center") and fb_fleet:
                self.fleet_ui.open(fb_fleet)
                self.ship_ui.close()
                self.ui.close()
                if fb_action == "center":
                    self.camera.x = fb_fleet.x - SCREEN_W / (2 * self.camera.zoom)
                    self.camera.y = fb_fleet.y - SCREEN_H / (2 * self.camera.zoom)
                continue
            if fb_action in ("select", "center", "consume"):
                continue

            # Fleet UI events (skipped during pending fleet dispatch to prevent auto-close)
            _fleet_ui_fleet_before = self.fleet_ui.fleet if self.fleet_ui.visible else None
            fleet_ev = None if self._pending_fleet_dispatch else self.fleet_ui.handle_event(event)
            if fleet_ev == "fleet_navigate_requested":
                self._pending_fleet_dispatch = self.fleet_ui.fleet
                continue
            if fleet_ev == "fleet_return_requested":
                f = self.fleet_ui.fleet
                if f:
                    f.send_return(self.planets)
                continue
            if fleet_ev == "fleet_dissolve":
                f = self.fleet_ui.fleet
                if f:
                    f.dissolve(self.fleets)
                self.fleet_ui.close()
                continue
            if fleet_ev:
                continue

            # Minimap: intercept mouse events before navigate/mission modes
            if self.minimap.handle_event(event, self.camera):
                continue

            # Navigate mode: click map to send ship to a destination
            # (checked before ShipUI so an outside click doesn't auto-close the panel)
            if self._pending_dispatch and self._pending_dispatch[1] == "navigate":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    on_ui = ((self.ui.visible and self.ui.panel_rect.collidepoint((mx, my))) or
                             (self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint((mx, my))) or
                             self.colony_bar.contains_point((mx, my), self.planets))
                    if not on_ui:
                        wx, wy = self.camera.screen_to_world(mx, my)
                        ship, mtype = self._pending_dispatch
                        self._pending_dispatch = None
                        # Auto-dispatch: explore if hovering unexplored planet
                        if (self._hovered_planet and not self._hovered_planet.explored
                                and "explore" in SHIP_DEFS.get(ship.type, {}).get("missions", [])):
                            ok = ship.send_explore(self._hovered_planet)
                        elif self._hovered_debris and ship.can_do("recycle"):
                            ok = ship.send_collect(self._hovered_debris)
                        else:
                            dock_planet = next(
                                (p for p in self.planets
                                 if p.colonized
                                 and (wx - p.x) ** 2 + (wy - p.y) ** 2 < (p.size + 10) ** 2),
                                None)
                            if dock_planet:
                                wx, wy = dock_planet.x, dock_planet.y
                            ok = ship.send_navigate(wx, wy, dock_planet=dock_planet,
                                                    planets=self.planets)
                        if not ok:
                            self._pending_dispatch = (ship, mtype)
                            self._hud_msg = f"Carburant insuffisant ({ship.fuel_type})"
                            self._hud_msg_timer = 3.0
                        continue
                else:
                    self.camera.handle_event(event)
                continue

            # Collect/recycle mode: next click on visible debris dispatches ship
            if self._pending_dispatch and self._pending_dispatch[1] == "recycle":
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
                            ship, _ = self._pending_dispatch
                            self._pending_dispatch = None
                            ok = ship.send_collect(clicked_debris)
                            if not ok:
                                self._hud_msg = "Carburant insuffisant pour collecter"
                                self._hud_msg_timer = 3.0
                        continue
                else:
                    self.camera.handle_event(event)
                continue

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

            # Ship UI events (intercepts clicks on its panel)
            ship_ev = self.ship_ui.handle_event(event)
            if ship_ev == "navigate_requested":
                _s = self.ship_ui.ship
                self._pending_dispatch = (_s, "navigate")
                continue
            if ship_ev == "explore_requested":
                _s = self.ship_ui.ship
                self.ui._mission_mode = ("explore", _s)
                self._hud_msg = "Cliquez sur une planète à explorer"
                self._hud_msg_timer = 3.0
                continue
            if ship_ev == "collect_requested":
                self._pending_dispatch = (self.ship_ui.ship, "recycle")
                continue
            if ship_ev:
                continue

            # Planet UI events
            if self.ui.handle_event(event, self.planets, self.ships):
                # Promote navigate request immediately so the navigate block
                # can protect subsequent events within the same frame.
                if self.ui._navigate_request:
                    _s = self.ui._navigate_request
                    self._pending_dispatch = (_s, "navigate")
                    self.ui._navigate_request = None
                if self.ui._collect_request:
                    self._pending_dispatch = (self.ui._collect_request, "recycle")
                    self.ui._collect_request = None
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
                    if f and f is not _fleet_ui_fleet_before:
                        self.fleet_ui.open(f)
                        self.ship_ui.close()
                continue

            # Mission target selection: only left-click picks a planet
            if self.ui._mission_mode:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for p in self.planets:
                        if p.discovered and p.is_clicked(mx, my, self.camera) and p is not self.ui.planet:
                            self.ui.dispatch_mission(p, self.highways)
                            break
                else:
                    self.camera.handle_event(event)
                continue

            # Camera (zoom, pan)
            self.camera.handle_event(event)

            # Left click: fleets > ships > planets
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
                     if not s.is_docked and s.fleet is None
                     and s.is_clicked(mx, my, self.camera)), None)
                if clicked_ship:
                    if self.ship_ui.visible and self.ship_ui.ship is clicked_ship:
                        self.ship_ui.close()
                    else:
                        self.ship_ui.open(clicked_ship)
                        self.ui.close()
                        self.fleet_ui.close()
                    continue

                clicked_planet = next(
                    (p for p in self.planets if p.discovered and p.is_clicked(mx, my, self.camera)), None)
                if clicked_planet:
                    if self.ui.visible and self.ui.planet is clicked_planet:
                        self.ui.close()
                    else:
                        self.ui.open(clicked_planet)
                        self.ship_ui.close()

        keys = pygame.key.get_pressed()
        self.camera.update(keys)
        self._time_scale = 10.0 if keys[pygame.K_KP_PLUS] else 1.0
        self._debug_fog_off = bool(keys[pygame.K_r])

    # ── fog of war ───────────────────────────────────────────────
    def _compute_visible_enemies(self):
        """Non-player ships visible only within SECTOR_SIZE of a colonized planet or player ship."""
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

    # ── planet threat knowledge ──────────────────────────────────
    def _update_planet_known_ranges(self):
        """Persist last-known max weapon range per discovered planet (fog-of-war memory)."""
        for planet in self.planets:
            if not planet.discovered:
                continue
            if planet.colonized:
                max_r = max(
                    (b.unit_range() for b in planet.buildings
                     if b.category == "defense" and b.count > 0),
                    default=0.0)
                if max_r > 0:
                    self._planet_known_ranges[planet.id] = (max_r, "player")
                else:
                    self._planet_known_ranges.pop(planet.id, None)
            else:
                for s in self._visible_enemies:
                    if s.fire_range <= 0:
                        continue
                    if math.hypot(s.x - planet.x, s.y - planet.y) > SECTOR_SIZE:
                        continue
                    cur_r, _ = self._planet_known_ranges.get(planet.id, (0.0, None))
                    if s.fire_range >= cur_r:
                        self._planet_known_ranges[planet.id] = (s.fire_range, s.faction_relationship)

    def _draw_planet_threat_circles(self):
        if not self._planet_known_ranges:
            return
        _REL_COLOR = {"player": GREEN, "ally": CYAN, "enemy": RED, "neutral": ORANGE}
        surf = pygame.Surface((int(SCREEN_W), int(SCREEN_H)), pygame.SRCALPHA)
        N = 72  # 36 dashes + 36 gaps
        drew = False
        for planet in self.planets:
            if not planet.discovered:
                continue
            entry = self._planet_known_ranges.get(planet.id)
            if not entry:
                continue
            max_range, rel = entry
            if max_range <= 0:
                continue
            r_px = int(max_range * self.camera.zoom)
            if r_px < 6:
                continue
            base = _REL_COLOR.get(rel, GRAY)
            color_a = (*base, 110)
            sx, sy = self.camera.world_to_screen(planet.x, planet.y)
            for i in range(0, N, 2):  # even indices = dashes
                a1 = 2 * math.pi * i / N
                a2 = 2 * math.pi * (i + 1) / N
                pygame.draw.line(surf, color_a,
                                 (int(sx + r_px * math.cos(a1)), int(sy + r_px * math.sin(a1))),
                                 (int(sx + r_px * math.cos(a2)), int(sy + r_px * math.sin(a2))), 1)
            drew = True
        if drew:
            self.screen.blit(surf, (0, 0))

    # ── update ───────────────────────────────────────────────────
    def _update(self, dt):
        self.space_map.update(dt)
        self.ui.update(dt)
        if self._hud_msg_timer > 0:
            self._hud_msg_timer -= dt

        all_ships = self.ships + self.enemy_ships
        for p in self.planets:
            p.update(dt, self.ships)
            if p.colonized:
                self._update_planet_defense(p, dt)
        for s in self.ships:
            s.update(dt, self.planets, self.highways, all_ships)
        self._update_enemies(dt, all_ships)
        for fleet in list(self.fleets.values()):
            fleet.update(dt, self.planets, self.highways,
                         self.ships + self.enemy_ships)
        if self.fleet_ui.visible and self.fleet_ui.fleet not in self.fleets.values():
            self.fleet_ui.close()
        self._update_discovered_planets()
        for s in self.ships:
            if s._destroyed:
                self._spawn_debris_from_ship(s)
        if self.ship_ui.visible and self.ship_ui.ship and self.ship_ui.ship._destroyed:
            self.ship_ui.close()
        self.ships = [s for s in self.ships if not s._destroyed]

        self._visible_enemies = self._compute_visible_enemies()
        self._visible_debris  = self._compute_visible_debris()
        self.debris_list = [d for d in self.debris_list if not d._collected]
        self._update_planet_known_ranges()

        mx, my = pygame.mouse.get_pos()
        in_planet_panel = self.ui.visible and self.ui.panel_rect.collidepoint(mx, my)
        in_ship_panel   = self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint(mx, my)
        in_colony_bar   = self.colony_bar.contains_point((mx, my), self.planets)
        in_fleet_panel  = self.fleet_ui.visible and self.fleet_ui.panel_rect.collidepoint(mx, my)
        in_fleet_bar    = self.fleet_bar.contains_point((mx, my))
        _any_ui = in_planet_panel or in_ship_panel or in_colony_bar or in_fleet_panel or in_fleet_bar

        # Ship hover (priority) — player ships first, then visible enemy ships
        self._hovered_ship = None
        if not _any_ui:
            self._hovered_ship = next(
                (s for s in self.ships + list(self._visible_enemies)
                 if not s.is_docked and s.fleet is None
                 and s.is_clicked(mx, my, self.camera)), None)

        # Planet hover (only if no ship hovered)
        self._hovered_planet = None
        if not self._hovered_ship and not _any_ui:
            self._hovered_planet = next(
                (p for p in self.planets if p.discovered and p.is_clicked(mx, my, self.camera)), None)

        self._hovered_debris = None
        if not self._hovered_ship and not self._hovered_planet and not _any_ui:
            mx2, my2 = pygame.mouse.get_pos()
            self._hovered_debris = next(
                (d for d in self._visible_debris if d.is_clicked(mx2, my2, self.camera)),
                None,
            )

    # ── draw ─────────────────────────────────────────────────────
    def _draw(self):
        self.space_map.draw(self.screen, self.camera)
        self._draw_highways()
        self._draw_detection_radii()
        for p in self.planets:
            p.draw(self.screen, self.camera, force=self._debug_fog_off)
        self._draw_planet_threat_circles()
        selected_planet = self.ui.planet if self.ui.visible else None
        if selected_planet and selected_planet is not self._hovered_planet:
            selected_planet.draw_selected(self.screen, self.camera)
        if self._hovered_planet:
            self._hovered_planet.draw_hover(self.screen, self.camera)
        for s in self.ships:
            if not s.is_docked:
                s.draw(self.screen, self.camera)
        _draw_enemies = (s for s in self.enemy_ships if not s._destroyed) \
                        if self._debug_fog_off else self._visible_enemies
        for s in _draw_enemies:
            s.draw(self.screen, self.camera)
        _draw_debris = self.debris_list if self._debug_fog_off else self._visible_debris
        for d in _draw_debris:
            d.draw(self.screen, self.camera, hovered=(d is self._hovered_debris))
        for fleet in self.fleets.values():
            fleet.draw(self.screen, self.camera)
        if self.ship_ui.visible and self.ship_ui.ship:
            self.ship_ui.ship.draw_selected(self.screen, self.camera)
        if self._hovered_ship:
            self._hovered_ship.draw_hover(self.screen, self.camera)
        # Range circle for combat ships (pending dispatch or selected in ShipUI)
        _pending_ship = self._pending_dispatch[0] if self._pending_dispatch else None
        _range_ship = _pending_ship or (self.ship_ui.ship if self.ship_ui.visible else None)
        if _range_ship:
            self._draw_navigate_range_circle(_range_ship)

        dispatch_modes = {}
        if self._pending_dispatch:
            _ds, _dm = self._pending_dispatch
            dispatch_modes[_ds] = _dm
        if self.ui._mission_mode:
            _mm_type, _mm_ship = self.ui._mission_mode
            dispatch_modes[_mm_ship] = _mm_type
        _open_fleet = self.fleet_ui.fleet if self.fleet_ui.visible else None
        self.ui.draw(self.screen, self.planets, self.highways, dispatch_modes=dispatch_modes,
                     open_fleet=_open_fleet)
        if self._hovered_planet:
            _is_nav = self._pending_dispatch and self._pending_dispatch[1] == "navigate"
            _hint_ship = self._pending_dispatch[0] if _is_nav else None
            if not _hint_ship and self.ship_ui.visible and self.ship_ui.ship:
                _s = self.ship_ui.ship
                _ms = SHIP_DEFS.get(_s.type, {}).get("missions", [])
                if "navigate" in _ms:
                    _hint_ship = _s
            self.ui.draw_mission_hover(self.screen, self._hovered_planet, self.camera, self.highways,
                                       navigate_ship=_hint_ship)
        elif self._hovered_debris and not self._hovered_planet:
            _debris_ship = (_pending_ship
                            or (self.ship_ui.ship if self.ship_ui.visible else None))
            if _debris_ship:
                self.ui.draw_debris_hover(self.screen, self._hovered_debris, self.camera,
                                          _debris_ship)
        elif self._pending_dispatch and self._pending_dispatch[1] == "navigate":
            mx, my = pygame.mouse.get_pos()
            wx, wy = self.camera.screen_to_world(mx, my)
            self.ui.draw_navigate_hover(self.screen, wx, wy, self.camera,
                                        self._pending_dispatch[0], planets=self.planets)
        self.ship_ui.draw(self.screen, dispatch_modes=dispatch_modes)
        if self._pending_fleet_dispatch:
            dispatch_modes[self._pending_fleet_dispatch] = "fleet_navigate"
        self.fleet_bar.draw(self.screen, self.fleets,
                            selected_fleet=self.fleet_ui.fleet if self.fleet_ui.visible else None)
        self.fleet_ui.draw(self.screen, dispatch_modes=dispatch_modes)
        self.colony_bar.draw(self.screen, self.planets,
                             selected_planet=self.ui.planet if self.ui.visible else None,
                             mission_mode=bool(self.ui._mission_mode))
        self._draw_mission_dash()
        self._draw_navigate_overlay()
        self._draw_collect_overlay()
        self._draw_fleet_navigate_overlay()
        self._draw_hud()
        self.minimap.draw(self.screen, self.planets, self.camera, fog_off=self._debug_fog_off)
        pygame.display.flip()

    def _draw_mission_dash(self):
        mx, my = pygame.mouse.get_pos()

        if self.ui._mission_mode and self._hovered_planet:
            mtype, ship = self.ui._mission_mode
            src_x = ship.home.x if ship.is_docked else ship.x
            src_y = ship.home.y if ship.is_docked else ship.y
            src = self.camera.world_to_screen(src_x, src_y)
            dst = self.camera.world_to_screen(self._hovered_planet.x, self._hovered_planet.y)
            ok = self.ui._mission_ok(mtype, ship, self._hovered_planet, self.highways)
            color = (180, 180, 180) if ok else (220, 70, 70)
            _draw_dashed_line(self.screen, color, src, dst)

        if self._pending_dispatch and self._pending_dispatch[1] == "navigate":
            ship = self._pending_dispatch[0]
            src_x = ship.home.x if ship.is_docked else ship.x
            src_y = ship.home.y if ship.is_docked else ship.y
            src = self.camera.world_to_screen(src_x, src_y)
            if self._hovered_planet:
                wx_dst, wy_dst = self._hovered_planet.x, self._hovered_planet.y
                dst = self.camera.world_to_screen(wx_dst, wy_dst)
            else:
                wx_dst, wy_dst = self.camera.screen_to_world(mx, my)
                dst = (mx, my)
            color = (180, 180, 180) if ship.can_navigate_to(wx_dst, wy_dst, self.planets) else (220, 70, 70)
            _draw_dashed_line(self.screen, color, src, dst)

    def _draw_navigate_range_circle(self, ship):
        """Draw the exact reachable navigate zone as a polygon.

        For each sampled direction the max reach d satisfies:
          d + dist(P, nearest_colony) = R  (R = fuel_remaining / fuel_rate)
        which for colony at relative (cx,cy) gives the closed form:
          d = (R^2 - dc^2) / (2*(R - cx*cos - cy*sin))
        Blocked directions pin to the ship position, naturally producing the
        sector/camembert cutoff seen when fuel is low or colonies are one-sided.
        """
        if ship.fuel_remaining < 1.0:
            return
        R = ship.fuel_remaining / ship.fuel_rate
        colonies = [
            (p.x - ship.x, p.y - ship.y, math.hypot(p.x - ship.x, p.y - ship.y))
            for p in self.planets if p.colonized
        ]
        if not colonies:
            return

        N = 90
        sx0, sy0 = self.camera.world_to_screen(ship.x, ship.y)
        pts = []
        for i in range(N):
            theta = 2 * math.pi * i / N
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            max_d = 0.0
            for cx, cy, dc in colonies:
                if dc >= R:
                    continue
                denom = 2.0 * (R - cx * cos_t - cy * sin_t)
                if denom < 1e-9:
                    continue
                d = (R * R - dc * dc) / denom
                if d > max_d:
                    max_d = d
            if max_d > 0:
                wx = ship.x + max_d * cos_t
                wy = ship.y + max_d * sin_t
                px, py = self.camera.world_to_screen(wx, wy)
                pts.append((int(px), int(py)))
            else:
                pts.append((int(sx0), int(sy0)))

        if len(pts) < 3:
            return
        color = GOLD if ship.pnr_advisory else (200, 120, 20)
        pygame.draw.polygon(self.screen, color, pts, 2)

    def _draw_navigate_overlay(self):
        if not (self._pending_dispatch and self._pending_dispatch[1] == "navigate"):
            return
        try:
            font = pygame.font.SysFont("consolas", 14)
        except Exception:
            font = pygame.font.Font(None, 16)
        msg = ">> Cliquez sur la carte pour définir la destination  |  ESC pour annuler <<"
        t = font.render(msg, True, ORANGE)
        x = SCREEN_W // 2 - t.get_width() // 2
        surface = pygame.Surface((t.get_width() + 20, t.get_height() + 8), pygame.SRCALPHA)
        surface.fill((10, 10, 30, 180))
        self.screen.blit(surface, (x - 10, 14))
        self.screen.blit(t, (x, 18))

    def _draw_collect_overlay(self):
        if not (self._pending_dispatch and self._pending_dispatch[1] == "recycle"):
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

    def _draw_detection_radii(self):
        """Gray semi-transparent circles showing detection range (SECTOR_SIZE) around player assets."""
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        r_px = int(DETECTION_RANGE * self.camera.zoom)
        if r_px < 2:
            return
        for p in self.planets:
            if p.colonized:
                sx, sy = self.camera.world_to_screen(p.x, p.y)
                pygame.draw.circle(surf, (110, 110, 110, 18), (sx, sy), r_px)
                pygame.draw.circle(surf, (140, 140, 140, 55), (sx, sy), r_px, 1)
        for s in self.ships:
            if not s.is_docked:
                s_r_px = int(s.detection_range * self.camera.zoom)
                if s_r_px < 2:
                    continue
                sx, sy = self.camera.world_to_screen(s.x, s.y)
                pygame.draw.circle(surf, (110, 110, 110, 18), (sx, sy), s_r_px)
                pygame.draw.circle(surf, (140, 140, 140, 55), (sx, sy), s_r_px, 1)
        self.screen.blit(surf, (0, 0))

    def _draw_highways(self):
        planet_by_id = {p.id: p for p in self.planets}
        for link in self.highways:
            ids = list(link)
            if len(ids) != 2: continue
            pa = planet_by_id.get(ids[0])
            pb = planet_by_id.get(ids[1])
            if not pa or not pb: continue
            ax, ay = self.camera.world_to_screen(pa.x, pa.y)
            bx, by = self.camera.world_to_screen(pb.x, pb.y)
            surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(surf, (*GOLD, 80), (ax, ay), (bx, by), 2)
            self.screen.blit(surf, (0, 0))

    def _draw_hud(self):
        try:
            font = pygame.font.SysFont("consolas", 12)
        except Exception:
            font = pygame.font.Font(None, 14)

        fps_txt = font.render(f"FPS: {self.clock.get_fps():.0f}", True, GRAY)
        self.screen.blit(fps_txt, (8, 8))

        zoom_txt = font.render(f"Zoom: {self.camera.zoom:.1f}x", True, GRAY)
        self.screen.blit(zoom_txt, (8, 22))

        if self._time_scale > 1.0:
            spd_txt = font.render(f"[DEBUG] x{int(self._time_scale)}", True, ORANGE)
            self.screen.blit(spd_txt, (8, 36))


        if self._hud_msg_timer > 0 and self._hud_msg:
            try:
                mf = pygame.font.SysFont("consolas", 14)
            except Exception:
                mf = pygame.font.Font(None, 16)
            mt = mf.render(self._hud_msg, True, (220, 80, 80))
            self.screen.blit(mt, (SCREEN_W // 2 - mt.get_width() // 2, 48))
