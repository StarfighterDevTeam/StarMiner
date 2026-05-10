import pygame
import random
import math
from constants import *

class ShootingStar:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.x = random.uniform(0, WORLD_W)
        self.y = random.uniform(0, WORLD_H)
        angle = random.uniform(math.pi * 0.1, math.pi * 0.4)
        speed = random.uniform(600, 1400)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.length = random.randint(80, 220)
        self.life = 1.0
        self.decay = random.uniform(0.4, 0.9)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= self.decay * dt
        if self.life <= 0:
            self._reset()

    def draw(self, surface, camera):
        if self.life <= 0:
            return
        alpha = int(self.life * 255)
        sx, sy = camera.world_to_screen(self.x, self.y)
        ex = sx - int(self.length * self.vx / max(abs(self.vx), 1) * camera.zoom * 0.06)
        ey = sy - int(self.length * self.vy / max(abs(self.vy), 1) * camera.zoom * 0.06)
        color = (min(255, 200 + alpha // 5), min(255, 200 + alpha // 5), 255, alpha)
        try:
            pygame.draw.line(surface, color[:3], (sx, sy), (ex, ey), max(1, int(camera.zoom)))
        except Exception:
            pass


class SpaceMap:
    def __init__(self):
        self._rng = random.Random(42)
        self._gen_stars()
        self._gen_nebulae()
        self.shooting_stars = [ShootingStar() for _ in range(NUM_SHOOTING_STARS)]
        # Pre-render static background
        self._bg_surface = None
        self._bg_zoom = None

    # ── generation ───────────────────────────────────────────────
    def _gen_stars(self):
        r = self._rng
        self.stars1 = [(r.randint(0, WORLD_W), r.randint(0, WORLD_H),
                        r.randint(1, 2), r.randint(150, 255)) for _ in range(NUM_STARS_LAYER1)]
        self.stars2 = [(r.randint(0, WORLD_W), r.randint(0, WORLD_H),
                        1, r.randint(80, 160)) for _ in range(NUM_STARS_LAYER2)]

    def _gen_nebulae(self):
        r = self._rng
        palettes = [
            (80, 20, 120), (20, 60, 130), (130, 40, 20),
            (20, 100, 80), (100, 80, 20), (40, 20, 100),
        ]
        self.nebulae = []
        for _ in range(NUM_NEBULAE):
            cx = r.randint(400, WORLD_W - 400)
            cy = r.randint(400, WORLD_H - 400)
            rx = r.randint(200, 600)
            ry = r.randint(150, 450)
            color = r.choice(palettes)
            alpha = r.randint(18, 45)
            self.nebulae.append((cx, cy, rx, ry, color, alpha))

    # ── update ───────────────────────────────────────────────────
    def update(self, dt):
        for s in self.shooting_stars:
            s.update(dt)

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, camera):
        surface.fill(BLACK)
        self._draw_nebulae(surface, camera)
        self._draw_stars(surface, camera)
        self._draw_grid(surface, camera)
        for s in self.shooting_stars:
            s.draw(surface, camera)

    def _draw_nebulae(self, surface, camera):
        for (cx, cy, rx, ry, color, alpha) in self.nebulae:
            scx, scy = camera.world_to_screen(cx, cy)
            srx = int(rx * camera.zoom)
            sry = int(ry * camera.zoom)
            if scx + srx < 0 or scx - srx > SCREEN_W: continue
            if scy + sry < 0 or scy - sry > SCREEN_H: continue
            # Draw layered ellipses for glow effect
            for layer in range(5):
                t = 1 - layer / 5
                a = int(alpha * t * 0.6)
                lrx = int(srx * (1 + layer * 0.3))
                lry = int(sry * (1 + layer * 0.3))
                neb_surf = pygame.Surface((lrx * 2, lry * 2), pygame.SRCALPHA)
                pygame.draw.ellipse(neb_surf, (*color, a), (0, 0, lrx * 2, lry * 2))
                surface.blit(neb_surf, (scx - lrx, scy - lry))

    def _draw_stars(self, surface, camera):
        # Layer 1 (parallax 0.95)
        for (wx, wy, r, brightness) in self.stars1:
            px = (wx - camera.x * 0.95) * camera.zoom
            py = (wy - camera.y * 0.95) * camera.zoom
            if -4 < px < SCREEN_W + 4 and -4 < py < SCREEN_H + 4:
                c = (brightness, brightness, brightness)
                sr = max(1, int(r * camera.zoom * 0.7))
                pygame.draw.circle(surface, c, (int(px), int(py)), sr)

        # Layer 2 (parallax 0.85 – more distant)
        for (wx, wy, r, brightness) in self.stars2:
            px = (wx - camera.x * 0.85) * camera.zoom
            py = (wy - camera.y * 0.85) * camera.zoom
            if -2 < px < SCREEN_W + 2 and -2 < py < SCREEN_H + 2:
                c = (brightness, brightness, min(255, brightness + 30))
                pygame.draw.circle(surface, c, (int(px), int(py)), 1)

    def _draw_grid(self, surface, camera):
        # Visible world rect
        x0 = int(camera.x // SECTOR_SIZE) * SECTOR_SIZE
        y0 = int(camera.y // SECTOR_SIZE) * SECTOR_SIZE
        x1 = camera.x + SCREEN_W / camera.zoom + SECTOR_SIZE
        y1 = camera.y + SCREEN_H / camera.zoom + SECTOR_SIZE

        try:
            font = pygame.font.SysFont("consolas", max(9, int(11 * camera.zoom)), bold=False)
        except Exception:
            font = pygame.font.Font(None, max(10, int(14 * camera.zoom)))

        x = x0
        while x <= x1:
            sx, _ = camera.world_to_screen(x, 0)
            pygame.draw.line(surface, GRID_COLOR, (sx, 0), (sx, SCREEN_H))
            x += SECTOR_SIZE

        y = y0
        while y <= y1:
            _, sy = camera.world_to_screen(0, y)
            pygame.draw.line(surface, GRID_COLOR, (0, sy), (SCREEN_W, sy))
            y += SECTOR_SIZE

        # Sector labels
        if camera.zoom >= 0.4:
            x = x0
            while x <= x1:
                y = y0
                while y <= y1:
                    col = int(x // SECTOR_SIZE)
                    row = int(y // SECTOR_SIZE)
                    label = f"{chr(65 + row % 26)}{col}"
                    sx, sy = camera.world_to_screen(x + 6, y + 4)
                    txt = font.render(label, True, SECTOR_LABEL)
                    surface.blit(txt, (sx, sy))
                    y += SECTOR_SIZE
                x += SECTOR_SIZE
