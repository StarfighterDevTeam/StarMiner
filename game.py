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
        self.minimap = MiniMap()
        self._hovered_planet = None
        self._hovered_ship = None
        self._time_scale = 1.0
        self._running = True
        self._patrol_mode_ship = None

        # Center camera on home planet at initial zoom
        self.camera.zoom = ZOOM_INIT
        home = self.planets[0]
        self.camera.x = home.x - SCREEN_W / (2 * self.camera.zoom)
        self.camera.y = home.y - SCREEN_H / (2 * self.camera.zoom)

        # Enemy ships
        self.enemy_ships = []
        self._spawn_initial_enemies()
        self._visible_enemies = set()
        self._hud_msg = ""
        self._hud_msg_timer = 0.0
        self.debris_list: list = []
        self._visible_debris: set = set()
        self._collect_mode_ship = None
        self._hovered_debris = None
        self._spawn_initial_debris()

    # ── enemy management ─────────────────────────────────────────
    def _spawn_initial_enemies(self):
        rng = random.Random(42)
        home = self.planets[0]

        _ENEMY_SHIPS = [
            {"faction": "krell",   "type": "Fighter"},
            {"faction": "krell",   "type": "Destroyer"},
            {"faction": "vexari",  "type": "Fighter"},
            {"faction": "nexus",   "type": "Fighter"},
            {"faction": "neutral", "type": "Fighter"},
        ]

        n = len(_ENEMY_SHIPS)
        sectors = list(range(n))
        rng.shuffle(sectors)
        sector_size = 2 * math.pi / n

        class _FakePlanet:
            def __init__(self_, x, y, name, pid):
                self_.x = x; self_.y = y; self_.name = name
                self_.ships = []; self_.resources = {}; self_.id = pid

        for i, entry in enumerate(_ENEMY_SHIPS):
            faction = entry["faction"]
            relationship = FACTION_DEFS[faction]["relationship"]

            # Distance zone: neutrals closer to home, enemies farther
            if relationship == "neutral":
                r = rng.uniform(3000, 5000)
            else:
                r = rng.uniform(8000, 11000)

            # Evenly spread angular sectors, shuffled for randomness
            base_angle = sectors[i] * sector_size
            angle = base_angle + rng.uniform(-math.pi / 9, math.pi / 9)  # ±20° jitter

            wx = max(500, min(WORLD_W - 500, home.x + r * math.cos(angle)))
            wy = max(500, min(WORLD_H - 500, home.y + r * math.sin(angle)))

            fname = FACTION_DEFS[faction]["name"]
            fp = _FakePlanet(wx, wy, fname, -(i + 1))
            s = Ship(entry["type"], fp, faction=faction)
            s.x = float(wx)
            s.y = float(wy)
            if s.fuel_capacity is not None:
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
            if s.state == "idle":
                if s.fuel_capacity is not None:
                    s.fuel_remaining = s.fuel_capacity  # enemies magically refuel when idle
                wx = random.randint(500, WORLD_W - 500)
                wy = random.randint(500, WORLD_H - 500)
                s.send_patrol(wx, wy)

        for s in self.enemy_ships:
            if s._destroyed:
                self._spawn_debris_from_ship(s)
        self.enemy_ships = [s for s in self.enemy_ships if not s._destroyed]

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
                if self._patrol_mode_ship:
                    self._patrol_mode_ship = None
                elif self._collect_mode_ship:
                    self._collect_mode_ship = None
                elif self.ui._mission_mode:
                    self.ui._mission_mode = None
                    self.ui.show_message("Mission annulée")
                elif self.ship_ui.visible:
                    self.ship_ui.close()
                elif self.ui.visible:
                    self.ui.close()
                else:
                    self._running = False
                return

            # F1/F2/F3: switch planet UI tab
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3):
                if self.ui.visible:
                    self.ui.switch_tab(("buildings", "ships", "fleet")[event.key - pygame.K_F1])
                continue

            # F5 debug: complete all production on selected planet
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F5:
                if self.ui.visible and self.ui.planet:
                    self.ui.planet.debug_complete_all(self.ships)
                    self.ui.show_message("[DEBUG] Toutes les productions terminées")
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

            # Minimap: intercept mouse events before patrol/mission modes
            if self.minimap.handle_event(event, self.camera):
                continue

            # Patrol mode: click map to send combat ship to a destination
            # (checked before ShipUI so an outside click doesn't auto-close the panel)
            if self._patrol_mode_ship:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    on_ui = ((self.ui.visible and self.ui.panel_rect.collidepoint((mx, my))) or
                             (self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint((mx, my))) or
                             self.colony_bar.contains_point((mx, my), self.planets))
                    if not on_ui:
                        wx, wy = self.camera.screen_to_world(mx, my)
                        ship = self._patrol_mode_ship
                        self._patrol_mode_ship = None
                        # Auto-dispatch: explore if hovering unexplored planet
                        if (self._hovered_planet and not self._hovered_planet.explored
                                and "explore" in SHIP_DEFS.get(ship.type, {}).get("missions", [])):
                            ok = ship.send_explore(self._hovered_planet)
                        # Auto-dispatch: collect if hovering debris with cargo capacity
                        elif self._hovered_debris and ship.capacity > 0:
                            ok = ship.send_collect(self._hovered_debris)
                        else:
                            dock_planet = next(
                                (p for p in self.planets
                                 if p.colonized
                                 and (wx - p.x) ** 2 + (wy - p.y) ** 2 < (p.size + 10) ** 2),
                                None)
                            if dock_planet:
                                wx, wy = dock_planet.x, dock_planet.y
                            ok = ship.send_patrol(wx, wy, dock_planet=dock_planet,
                                                  planets=self.planets)
                        if not ok:
                            self._patrol_mode_ship = ship
                            self._hud_msg = f"Carburant insuffisant ({ship.fuel_type})"
                            self._hud_msg_timer = 3.0
                        continue
                else:
                    self.camera.handle_event(event)
                continue

            # Collect mode: next click on visible debris dispatches ship
            if self._collect_mode_ship:
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
                            ship = self._collect_mode_ship
                            self._collect_mode_ship = None
                            ok = ship.send_collect(clicked_debris)
                            if not ok:
                                self._hud_msg = "Carburant insuffisant pour collecter"
                                self._hud_msg_timer = 3.0
                        continue
                else:
                    self.camera.handle_event(event)
                continue

            # Ship UI events (intercepts clicks on its panel)
            ship_ev = self.ship_ui.handle_event(event)
            if ship_ev == "patrol_requested":
                self._patrol_mode_ship = self.ship_ui.ship
                continue
            if ship_ev:
                continue

            # Planet UI events
            if self.ui.handle_event(event, self.planets, self.ships):
                # Promote patrol request immediately so the patrol block
                # can protect subsequent events within the same frame.
                if self.ui._patrol_request:
                    self._patrol_mode_ship = self.ui._patrol_request
                    self.ui._patrol_request = None
                if self.ui._collect_request:
                    self._collect_mode_ship = self.ui._collect_request
                    self.ui._collect_request = None
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

            # Right-click shortcut: navigate or explore with selected ship
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
                    and self.ship_ui.visible and self.ship_ui.ship):
                _s = self.ship_ui.ship
                _on_ui = (
                    (self.ui.visible and self.ui.panel_rect.collidepoint((mx, my))) or
                    self.ship_ui.panel_rect.collidepoint((mx, my)) or
                    self.colony_bar.contains_point((mx, my), self.planets)
                )
                if not _on_ui:
                    _ms = SHIP_DEFS.get(_s.type, {}).get("missions", [])
                    wx, wy = self.camera.screen_to_world(mx, my)
                    ok = True
                    if "navigate" in _ms or "patrol" in _ms:
                        # Auto-detect explore/collect, otherwise navigate
                        if (self._hovered_planet and not self._hovered_planet.explored
                                and "explore" in _ms):
                            ok = _s.send_explore(self._hovered_planet)
                        elif self._hovered_debris and _s.capacity > 0:
                            ok = _s.send_collect(self._hovered_debris)
                        else:
                            dock_planet = next(
                                (p for p in self.planets
                                 if p.colonized
                                 and (wx - p.x) ** 2 + (wy - p.y) ** 2 < (p.size + 10) ** 2),
                                None)
                            if dock_planet:
                                wx, wy = dock_planet.x, dock_planet.y
                            ok = _s.send_patrol(wx, wy, dock_planet=dock_planet,
                                                planets=self.planets)
                    elif "explore" in _ms and self._hovered_planet and not self._hovered_planet.explored:
                        ok = _s.send_explore(self._hovered_planet)
                    else:
                        ok = True  # nothing to do, let camera handle drag
                        _on_ui = True  # fall through to camera
                    if not _on_ui:
                        if not ok:
                            self._hud_msg = f"Carburant insuffisant ({_s.fuel_type})"
                            self._hud_msg_timer = 3.0
                        continue  # swallow the right-click, no camera drag

            # Camera (zoom, pan)
            self.camera.handle_event(event)

            # Left click: ships take priority over planets
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_ship = next(
                    (s for s in self.ships
                     if not s.is_docked and s.is_clicked(mx, my, self.camera)), None)
                if clicked_ship:
                    if self.ship_ui.visible and self.ship_ui.ship is clicked_ship:
                        self.ship_ui.close()
                    else:
                        self.ship_ui.open(clicked_ship)
                        self.ui.close()
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

    # ── update ───────────────────────────────────────────────────
    def _update(self, dt):
        self.space_map.update(dt)
        self.ui.update(dt)
        if self._hud_msg_timer > 0:
            self._hud_msg_timer -= dt

        all_ships = self.ships + self.enemy_ships
        for p in self.planets:
            p.update(dt, self.ships)
        for s in self.ships:
            s.update(dt, self.planets, self.highways, all_ships)
        self._update_enemies(dt, all_ships)
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

        mx, my = pygame.mouse.get_pos()
        in_planet_panel = self.ui.visible and self.ui.panel_rect.collidepoint(mx, my)
        in_ship_panel   = self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint(mx, my)
        in_colony_bar   = self.colony_bar.contains_point((mx, my), self.planets)

        # Ship hover (priority) — player ships first, then visible enemy ships
        self._hovered_ship = None
        if not in_planet_panel and not in_ship_panel and not in_colony_bar:
            self._hovered_ship = next(
                (s for s in self.ships + list(self._visible_enemies)
                 if not s.is_docked and s.is_clicked(mx, my, self.camera)), None)

        # Planet hover (only if no ship hovered)
        self._hovered_planet = None
        if not self._hovered_ship and not in_planet_panel and not in_ship_panel and not in_colony_bar:
            self._hovered_planet = next(
                (p for p in self.planets if p.discovered and p.is_clicked(mx, my, self.camera)), None)

        self._hovered_debris = None
        if (not self._hovered_ship and not self._hovered_planet
                and not in_planet_panel and not in_ship_panel and not in_colony_bar):
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
            p.draw(self.screen, self.camera)
        selected_planet = self.ui.planet if self.ui.visible else None
        if selected_planet and selected_planet is not self._hovered_planet:
            selected_planet.draw_selected(self.screen, self.camera)
        if self._hovered_planet:
            self._hovered_planet.draw_hover(self.screen, self.camera)
        for s in self.ships:
            if not s.is_docked:
                s.draw(self.screen, self.camera)
        for s in self._visible_enemies:
            s.draw(self.screen, self.camera)
        for d in self._visible_debris:
            d.draw(self.screen, self.camera, hovered=(d is self._hovered_debris))
        if self.ship_ui.visible and self.ship_ui.ship:
            self.ship_ui.ship.draw_selected(self.screen, self.camera)
        if self._hovered_ship:
            self._hovered_ship.draw_hover(self.screen, self.camera)
        # Range circle for combat ships (patrol mode or selected in ShipUI)
        _range_ship = self._patrol_mode_ship or (
            self.ship_ui.ship if self.ship_ui.visible else None)
        if _range_ship and _range_ship.fuel_capacity is not None:
            self._draw_patrol_range_circle(_range_ship)

        self.ui.draw(self.screen, self.planets, self.highways,
                     patrol_mode_ship=self._patrol_mode_ship)
        if self._hovered_planet:
            _hint_ship = self._patrol_mode_ship
            if not _hint_ship and self.ship_ui.visible and self.ship_ui.ship:
                _s = self.ship_ui.ship
                _ms = SHIP_DEFS.get(_s.type, {}).get("missions", [])
                if "navigate" in _ms or "patrol" in _ms:
                    _hint_ship = _s
            self.ui.draw_mission_hover(self.screen, self._hovered_planet, self.camera, self.highways,
                                       patrol_ship=_hint_ship)
        elif self._hovered_debris and not self._hovered_planet:
            _debris_ship = (self._patrol_mode_ship
                            or (self.ship_ui.ship if self.ship_ui.visible else None))
            if _debris_ship:
                self.ui.draw_debris_hover(self.screen, self._hovered_debris, self.camera,
                                          _debris_ship)
        elif self._patrol_mode_ship:
            mx, my = pygame.mouse.get_pos()
            wx, wy = self.camera.screen_to_world(mx, my)
            self.ui.draw_patrol_hover(self.screen, wx, wy, self.camera,
                                      self._patrol_mode_ship, planets=self.planets)
        self.ship_ui.draw(self.screen)
        self.colony_bar.draw(self.screen, self.planets,
                             selected_planet=self.ui.planet if self.ui.visible else None,
                             mission_mode=bool(self.ui._mission_mode))
        self._draw_mission_dash()
        self._draw_patrol_overlay()
        self._draw_collect_overlay()
        self._draw_hud()
        self.minimap.draw(self.screen, self.planets, self.camera)
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

        if self._patrol_mode_ship:
            ship = self._patrol_mode_ship
            src_x = ship.home.x if ship.is_docked else ship.x
            src_y = ship.home.y if ship.is_docked else ship.y
            src = self.camera.world_to_screen(src_x, src_y)
            if self._hovered_planet:
                wx_dst, wy_dst = self._hovered_planet.x, self._hovered_planet.y
                dst = self.camera.world_to_screen(wx_dst, wy_dst)
            else:
                wx_dst, wy_dst = self.camera.screen_to_world(mx, my)
                dst = (mx, my)
            color = (180, 180, 180) if ship.can_patrol_to(wx_dst, wy_dst, self.planets) else (220, 70, 70)
            _draw_dashed_line(self.screen, color, src, dst)

    def _draw_patrol_range_circle(self, ship):
        """Draw the exact reachable patrol zone as a polygon.

        For each sampled direction the max reach d satisfies:
          d + dist(P, nearest_colony) = R  (R = fuel_remaining / fuel_rate)
        which for colony at relative (cx,cy) gives the closed form:
          d = (R^2 - dc^2) / (2*(R - cx*cos - cy*sin))
        Blocked directions pin to the ship position, naturally producing the
        sector/camembert cutoff seen when fuel is low or colonies are one-sided.
        """
        if ship.fuel_capacity is None or ship.fuel_remaining < 1.0:
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

    def _draw_patrol_overlay(self):
        if not self._patrol_mode_ship:
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
        if not self._collect_mode_ship:
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
