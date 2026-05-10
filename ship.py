import pygame
import math
import os
from constants import *

_ship_images = {}

def _load_ship_img(path, size):
    key = (path, size)
    if key not in _ship_images:
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (size, size))
        except Exception:
            img = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.polygon(img, (180, 200, 255),
                                [(size//2, 0), (size, size), (size//2, size*3//4), (0, size)])
        _ship_images[key] = img
    return _ship_images[key]

SHIP_IMG_PATHS = {
    "Probe": "assets/2D/Probe1.png",
    "Miner": "assets/2D/Miner1.png",
}
SHIP_DRAW_SIZE = 28

MISSION_IDLE    = "idle"
MISSION_TRAVEL  = "travel"
MISSION_EXPLORE = "exploring"
MISSION_MINE    = "mining"
MISSION_RETURN  = "returning"


class Ship:
    _id_counter = 0

    def __init__(self, ship_type, home_planet):
        Ship._id_counter += 1
        self.id = Ship._id_counter
        self.type = ship_type
        self.home = home_planet
        defn = SHIP_DEFS[ship_type]
        self.speed = defn["speed"]
        self.capacity = defn["capacity"]

        self.x = float(home_planet.x)
        self.y = float(home_planet.y)
        self.angle = 0.0

        self.state = MISSION_IDLE
        self.target_planet = None
        self.cargo = {r: 0.0 for r in RESOURCE_NAMES}
        self._mine_timer = 0.0
        self._mine_duration = 8.0   # seconds to mine at destination

    # ── missions ─────────────────────────────────────────────────
    def send_explore(self, target):
        if self.state != MISSION_IDLE: return False
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "explore"
        return True

    def send_mine(self, target):
        if self.state != MISSION_IDLE: return False
        if self.type != "Miner": return False
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "mine"
        return True

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, planets):
        if self.state == MISSION_IDLE:
            return

        if self.state == MISSION_TRAVEL:
            self._move_toward(self.target_planet.x, self.target_planet.y, dt)
            dist = math.hypot(self.x - self.target_planet.x, self.y - self.target_planet.y)
            if dist < 40:
                self.x = self.target_planet.x
                self.y = self.target_planet.y
                if self._mission_type == "explore":
                    self.target_planet.explored = True
                    self.state = MISSION_RETURN
                elif self._mission_type == "mine":
                    self.state = MISSION_MINE
                    self._mine_timer = self._mine_duration

        elif self.state == MISSION_MINE:
            self._mine_timer -= dt
            # Load resources from target
            for res in self.target_planet.available_resources:
                space = self.capacity - sum(self.cargo.values())
                amount = min(10 * dt, space)
                self.cargo[res] = self.cargo.get(res, 0) + amount
            if self._mine_timer <= 0 or sum(self.cargo.values()) >= self.capacity:
                self.state = MISSION_RETURN

        elif self.state == MISSION_RETURN:
            self._move_toward(self.home.x, self.home.y, dt)
            dist = math.hypot(self.x - self.home.x, self.y - self.home.y)
            if dist < 40:
                self.x = self.home.x
                self.y = self.home.y
                # Unload cargo
                for res, amt in self.cargo.items():
                    self.home.resources[res] = self.home.resources.get(res, 0) + amt
                self.cargo = {r: 0.0 for r in RESOURCE_NAMES}
                self.state = MISSION_IDLE
                self.target_planet = None

    def _move_toward(self, tx, ty, dt):
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        self.angle = math.atan2(dy, dx)
        step = min(self.speed * dt, dist)
        self.x += (dx / dist) * step
        self.y += (dy / dist) * step

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        if sx < -50 or sx > SCREEN_W + 50 or sy < -50 or sy > SCREEN_H + 50:
            return
        draw_size = max(8, int(SHIP_DRAW_SIZE * camera.zoom))
        img = _load_ship_img(SHIP_IMG_PATHS.get(self.type, ""), draw_size)
        deg = -math.degrees(self.angle) - 90
        rotated = pygame.transform.rotate(img, deg)
        rect = rotated.get_rect(center=(sx, sy))
        surface.blit(rotated, rect)

        # State dot
        dot_color = {
            MISSION_IDLE:    GRAY,
            MISSION_TRAVEL:  CYAN,
            MISSION_MINE:    ORANGE,
            MISSION_RETURN:  GREEN,
            MISSION_EXPLORE: CYAN,
        }.get(self.state, WHITE)
        pygame.draw.circle(surface, dot_color, (sx + draw_size // 2, sy - draw_size // 2), max(3, int(4 * camera.zoom)))

        # Travel line toward actual destination
        if self.state in (MISSION_TRAVEL, MISSION_MINE) and self.target_planet:
            tx, ty = camera.world_to_screen(self.target_planet.x, self.target_planet.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif self.state == MISSION_RETURN:
            tx, ty = camera.world_to_screen(self.home.x, self.home.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)

        # ETA label while moving toward a destination
        if self.state in (MISSION_TRAVEL, MISSION_RETURN):
            dest_x = self.target_planet.x if self.state == MISSION_TRAVEL else self.home.x
            dest_y = self.target_planet.y if self.state == MISSION_TRAVEL else self.home.y
            dist = math.hypot(dest_x - self.x, dest_y - self.y)
            eta = dist / self.speed
            label = f"{int(eta//60)}m {int(eta%60)}s" if eta >= 60 else f"{eta:.0f}s"
            try:
                font = pygame.font.SysFont("consolas", max(9, int(10 * camera.zoom)))
            except Exception:
                font = pygame.font.Font(None, max(11, int(12 * camera.zoom)))
            txt = font.render(label, True, CYAN)
            surface.blit(txt, (sx - txt.get_width() // 2,
                               sy - draw_size // 2 - txt.get_height() - 2))
