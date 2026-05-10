import pygame
from constants import *
from camera import Camera
from space_map import SpaceMap
from planet import generate_planets
from ui import PlanetUI

class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.space_map = SpaceMap()
        self.planets = generate_planets(NUM_PLANETS)
        self.ships = []
        self.ui = PlanetUI()
        self._hovered_planet = None
        self._running = True

        # Center camera on home planet
        home = self.planets[0]
        self.camera.x = home.x - SCREEN_W / 2
        self.camera.y = home.y - SCREEN_H / 2

    # ── main loop ────────────────────────────────────────────────
    def run(self):
        while self._running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.1)   # cap delta time
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
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.ui.visible:
                    self.ui.close()
                else:
                    self._running = False
                return

            # Let UI handle first
            if self.ui.handle_event(event, self.planets, self.ships):
                continue

            # Mission target selection
            if self.ui._mission_mode:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for p in self.planets:
                        if p.is_clicked(mx, my, self.camera) and p is not self.ui.planet:
                            self.ui.dispatch_mission(p)
                            break
                continue

            # Camera
            self.camera.handle_event(event)

            # Planet click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for p in self.planets:
                    if p.is_clicked(mx, my, self.camera):
                        if self.ui.visible and self.ui.planet is p:
                            self.ui.close()
                        else:
                            self.ui.open(p)
                        break

        keys = pygame.key.get_pressed()
        self.camera.update(keys)

    # ── update ───────────────────────────────────────────────────
    def _update(self, dt):
        self.space_map.update(dt)
        self.ui.update(dt)
        for p in self.planets:
            p.update(dt, self.ships)
        for s in self.ships:
            s.update(dt, self.planets)
        # Hover detection
        mx, my = pygame.mouse.get_pos()
        self._hovered_planet = None
        if not self.ui.visible or not self.ui.panel_rect.collidepoint(mx, my):
            for p in self.planets:
                if p.is_clicked(mx, my, self.camera):
                    self._hovered_planet = p
                    break

    # ── draw ─────────────────────────────────────────────────────
    def _draw(self):
        self.space_map.draw(self.screen, self.camera)
        for p in self.planets:
            p.draw(self.screen, self.camera)
        if self._hovered_planet:
            self._hovered_planet.draw_hover(self.screen, self.camera)
        for s in self.ships:
            s.draw(self.screen, self.camera)
        self.ui.draw(self.screen, self.planets)
        self._draw_hud()
        pygame.display.flip()

    def _draw_hud(self):
        try:
            font = pygame.font.SysFont("consolas", 12)
        except Exception:
            font = pygame.font.Font(None, 14)

        # FPS
        fps_txt = font.render(f"FPS: {self.clock.get_fps():.0f}", True, GRAY)
        self.screen.blit(fps_txt, (8, 8))

        # Zoom
        zoom_txt = font.render(f"Zoom: {self.camera.zoom:.1f}x", True, GRAY)
        self.screen.blit(zoom_txt, (8, 22))

        # Home resources mini-bar
        home = self.planets[0]
        res_font = font
        x = 8
        y = SCREEN_H - 20
        for res in RESOURCE_NAMES:
            val = home.resources.get(res, 0)
            color = RESOURCE_COLORS.get(res, WHITE)
            t = res_font.render(f"{res[:3].upper()}:{int(val)}", True, color)
            self.screen.blit(t, (x, y))
            x += t.get_width() + 12

        # Controls hint
        hints = ["WASD/Arrows:scroll  |  Scroll:zoom  |  RMB drag:pan  |  Click planet:open  |  ESC:close"]
        ht = font.render(hints[0], True, (60, 70, 90))
        self.screen.blit(ht, (SCREEN_W // 2 - ht.get_width() // 2, SCREEN_H - 18))
