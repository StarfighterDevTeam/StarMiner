# debris.py
import pygame
import math
from constants import RESOURCE_NAMES, SCREEN_W, SCREEN_H


class Debris:
    _click_radius = 12   # screen px for hit-test

    def __init__(self, x, y, resources):
        self.x = float(x)
        self.y = float(y)
        self.resources = {r: float(v) for r, v in resources.items() if v > 0}
        self._collected = False

    def is_clicked(self, mx, my, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        return (mx - sx) ** 2 + (my - sy) ** 2 <= self._click_radius ** 2

    def draw(self, surface, camera, hovered=False):
        sx, sy = camera.world_to_screen(self.x, self.y)
        if sx < -20 or sx > SCREEN_W + 20 or sy < -20 or sy > SCREEN_H + 20:
            return
        # Pixel cluster
        offsets = [(-3, -3), (2, -2), (-1, 2), (3, 1), (0, -1)]
        for i, (dx, dy) in enumerate(offsets):
            color = (200, 175, 60) if i % 2 == 0 else (130, 130, 130)
            pygame.draw.rect(surface, color, (int(sx + dx), int(sy + dy), 3, 3))

        if hovered:
            pygame.draw.circle(surface, (60, 220, 220), (int(sx), int(sy)), 14, 1)

        if camera.zoom >= 0.4 and self.resources:
            try:
                f = pygame.font.SysFont("consolas", 9)
            except Exception:
                f = pygame.font.Font(None, 10)
            label = "  ".join(
                f"{r[:3].upper()}:{int(v)}" for r, v in self.resources.items()
            )
            t = f.render(label, True, (210, 195, 120))
            surface.blit(t, (int(sx) - t.get_width() // 2, int(sy) + 9))
