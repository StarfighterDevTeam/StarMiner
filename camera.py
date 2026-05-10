import pygame
from constants import WORLD_W, WORLD_H, SCREEN_W, SCREEN_H, ZOOM_MIN, ZOOM_MAX, ZOOM_STEP, SCROLL_SPEED

class Camera:
    def __init__(self):
        self.x = WORLD_W // 2 - SCREEN_W // 2
        self.y = WORLD_H // 2 - SCREEN_H // 2
        self.zoom = 1.0
        self._drag_start = None
        self._cam_start = None

    # ── world → screen ──────────────────────────────────────────
    def world_to_screen(self, wx, wy):
        sx = (wx - self.x) * self.zoom
        sy = (wy - self.y) * self.zoom
        return int(sx), int(sy)

    def screen_to_world(self, sx, sy):
        wx = sx / self.zoom + self.x
        wy = sy / self.zoom + self.y
        return wx, wy

    def world_rect_to_screen(self, wx, wy, ww, wh):
        sx, sy = self.world_to_screen(wx, wy)
        return pygame.Rect(sx, sy, int(ww * self.zoom), int(wh * self.zoom))

    # ── scroll / zoom ────────────────────────────────────────────
    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            wbefore = self.screen_to_world(mx, my)
            self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom + event.y * ZOOM_STEP))
            wafter = self.screen_to_world(mx, my)
            self.x += wbefore[0] - wafter[0]
            self.y += wbefore[1] - wafter[1]
            self._clamp()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._drag_start = pygame.mouse.get_pos()
            self._cam_start = (self.x, self.y)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._drag_start = None
            return False

        if event.type == pygame.MOUSEMOTION and self._drag_start:
            dx = (event.pos[0] - self._drag_start[0]) / self.zoom
            dy = (event.pos[1] - self._drag_start[1]) / self.zoom
            self.x = self._cam_start[0] - dx
            self.y = self._cam_start[1] - dy
            self._clamp()
            return True

        return False

    def update(self, keys):
        spd = SCROLL_SPEED / self.zoom
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.x -= spd
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.x += spd
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.y -= spd
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.y += spd
        self._clamp()

    def _clamp(self):
        max_x = WORLD_W - SCREEN_W / self.zoom
        max_y = WORLD_H - SCREEN_H / self.zoom
        self.x = max(0, min(self.x, max_x))
        self.y = max(0, min(self.y, max_y))
