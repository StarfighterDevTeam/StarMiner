import pygame
from constants import (
    WORLD_W, WORLD_H, SCREEN_W, SCREEN_H,
    GREEN, GRAY, FACTION_DEFS, RELATIONSHIP_COLORS,
)

_W      = 160
_H      = 160
_MARGIN = 10
_X      = _MARGIN
_Y      = SCREEN_H - _H - _MARGIN
_DOT_R  = 3
_BG     = (8, 12, 25, 200)
_BORDER = (60, 100, 160)
_VP_FILL   = (180, 200, 255, 40)
_VP_BORDER = (180, 200, 255)
_OTHER_DOT = (55, 65, 90)   # dim color for discovered non-player planets


class MiniMap:
    def __init__(self):
        self.rect = pygame.Rect(_X, _Y, _W, _H)
        self._dragging = False

    # ── coordinate helpers ────────────────────────────────────────

    def _to_mini(self, wx, wy):
        return (
            int(_X + wx / WORLD_W * _W),
            int(_Y + wy / WORLD_H * _H),
        )

    def _to_world(self, sx, sy):
        return (
            (sx - _X) / _W * WORLD_W,
            (sy - _Y) / _H * WORLD_H,
        )

    # ── planet color ──────────────────────────────────────────────

    @staticmethod
    def _dot_color(planet):
        if planet.is_home or planet.colonized:
            return GREEN
        faction = getattr(planet, "faction", None)
        if faction:
            rel = FACTION_DEFS.get(faction, {}).get("relationship")
            if rel:
                return RELATIONSHIP_COLORS.get(rel, GRAY)
        return _OTHER_DOT

    # ── events ────────────────────────────────────────────────────

    def handle_event(self, event, camera):
        """Returns True if the event was consumed by the minimap."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._dragging = True
                self._center_camera(event.pos, camera)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self._dragging:
                self._center_camera(event.pos, camera)
                return True

        return False

    def _center_camera(self, screen_pos, camera):
        wx, wy = self._to_world(*screen_pos)
        camera.x = wx - SCREEN_W / (2 * camera.zoom)
        camera.y = wy - SCREEN_H / (2 * camera.zoom)
        camera._clamp()

    # ── draw ──────────────────────────────────────────────────────

    def draw(self, surface, planets, camera, fog_off=False):
        # Background
        bg = pygame.Surface((_W, _H), pygame.SRCALPHA)
        bg.fill(_BG)
        surface.blit(bg, (_X, _Y))
        pygame.draw.rect(surface, _BORDER, self.rect, 1)

        # Planet dots (fog_off → all, otherwise discovered only), clipped to minimap bounds
        for p in planets:
            if not p.discovered and not fog_off:
                continue
            mx, my = self._to_mini(p.x, p.y)
            if _X <= mx <= _X + _W and _Y <= my <= _Y + _H:
                pygame.draw.circle(surface, self._dot_color(p), (mx, my), _DOT_R)

        # Viewport rectangle
        vx = _X + camera.x / WORLD_W * _W
        vy = _Y + camera.y / WORLD_H * _H
        vw = max(1.0, SCREEN_W / camera.zoom / WORLD_W * _W)
        vh = max(1.0, SCREEN_H / camera.zoom / WORLD_H * _H)

        # Clamp to minimap bounds
        vx2 = min(vx + vw, float(_X + _W))
        vy2 = min(vy + vh, float(_Y + _H))
        vx  = max(vx, float(_X))
        vy  = max(vy, float(_Y))
        vw  = vx2 - vx
        vh  = vy2 - vy

        if vw > 0 and vh > 0:
            fill = pygame.Surface((int(vw) + 1, int(vh) + 1), pygame.SRCALPHA)
            fill.fill(_VP_FILL)
            surface.blit(fill, (int(vx), int(vy)))
            pygame.draw.rect(surface, _VP_BORDER,
                             (int(vx), int(vy), int(vw), int(vh)), 1)
