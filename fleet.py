# fleet.py
import math
import pygame
from constants import CYAN, SHIP_DEFS
from ui_common import _font


class Fleet:
    _id_counter = 0

    def __init__(self, home):
        Fleet._id_counter += 1
        self.id    = Fleet._id_counter
        self.name  = f"Flotte de {home.name}"
        self.home  = home
        self.ships : list = []
        self.state : str  = "docked"        # "docked"|"orbiting"|"navigate"|"returning"|"combat"
        self._pre_combat_state : str = "docked"
        self.x : float = float(home.x)
        self.y : float = float(home.y)
        self._nav_target = None             # (wx, wy) | None

    # ── membership ───────────────────────────────────────────────
    def add_ship(self, ship):
        if self.state != "docked":
            return False
        if ship.state != "idle":
            return False
        if ship.home is not self.home:
            return False
        if ship.fleet is not None:
            return False
        ship.fleet = self
        self.ships.append(ship)
        return True

    def remove_ship(self, ship):
        if self.state != "docked":
            return False
        if ship not in self.ships:
            return False
        ship.fleet = None
        ship.__dict__.pop("_fleet_nav_speed", None)
        self.ships.remove(ship)
        return True

    def dissolve(self, game_fleets):
        for s in list(self.ships):
            s.fleet = None
            s.__dict__.pop("_fleet_nav_speed", None)
        self.ships.clear()
        game_fleets.pop(self.home.id, None)

    # ── missions ─────────────────────────────────────────────────
    def send_navigate(self, wx, wy, planets=None):
        if self.state not in ("docked", "orbiting") or not self.ships:
            return False
        planets = planets or []
        for s in self.ships:
            if not s.pnr_advisory:
                fuel_leg    = s.fuel_cost_navigate(wx, wy)
                fuel_return = s._fuel_to_nearest_colony(wx, wy, planets)
                if s.fuel_remaining < fuel_leg + fuel_return:
                    return False
        for s in self.ships:
            s.send_navigate(wx, wy, planets=planets)
        self._nav_target = (wx, wy)
        self.state = "navigate"
        return True

    def send_return(self, planets=None):
        if self.state not in ("navigate", "docked", "orbiting") or not self.ships:
            return False
        planets = planets or []
        for s in self.ships:
            s.send_navigate(self.home.x, self.home.y,
                            dock_planet=self.home, planets=planets)
        self.state = "returning"
        return True

    def cancel(self):
        if self.state not in ("navigate", "returning", "combat"):
            return False
        # Handles fleet-specific _fleet_nav_speed cleanup that cancel_mission() doesn't know about
        for s in self.ships:
            if s.state == "navigate":
                s._navigate_dest    = None
                s._dock_planet      = None
                s._target_enemy     = None
                s.state             = "idle"
                s.__dict__.pop("_fleet_nav_speed", None)
        self.state       = "orbiting"
        self._nav_target = None
        return True

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, planets, highways, all_ships):
        # Cleanup destroyed members
        for s in list(self.ships):
            if s._destroyed:
                s.fleet = None
                s.__dict__.pop("_fleet_nav_speed", None)
                self.ships.remove(s)

        if not self.ships:
            self.state       = "docked"
            self._nav_target = None
            self.x           = float(self.home.x)
            self.y           = float(self.home.y)
            return

        # Update barycentre position
        self.x = sum(s.x for s in self.ships) / len(self.ships)
        self.y = sum(s.y for s in self.ships) / len(self.ships)

        fleet_speed = min(s.speed for s in self.ships)

        # Detect combat entry
        if self.state != "combat" and any(s.state == "combat" for s in self.ships):
            self._pre_combat_state = self.state
            self.state = "combat"

        if self.state == "combat":
            if not any(s.state == "combat" for s in self.ships):
                self.state = self._pre_combat_state
            return

        if self.state in ("navigate", "returning"):
            for s in self.ships:
                if s.state == "navigate":
                    s._fleet_nav_speed = fleet_speed

        if self.state in ("navigate", "returning", "orbiting"):
            if all(s.state == "idle" for s in self.ships):
                for s in self.ships:
                    s.__dict__.pop("_fleet_nav_speed", None)
                docked_p = next(
                    (p for p in planets
                     if p.colonized and math.hypot(self.x - p.x, self.y - p.y) < 80),
                    None
                )
                self.state       = "docked" if docked_p else "orbiting"
                self._nav_target = None

    # ── map interaction ───────────────────────────────────────────
    def is_clicked(self, mx, my, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        return math.hypot(mx - sx, my - sy) < 12

    def draw(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        sx, sy = int(sx), int(sy)
        r = 10
        pts = [(sx, sy - r), (sx + r, sy), (sx, sy + r), (sx - r, sy)]
        pygame.draw.polygon(surface, CYAN, pts, 2)
        label = _font(9).render(self.name, True, CYAN)
        surface.blit(label, (sx - label.get_width() // 2, sy - r - 12))
