import pygame
from constants import *
from camera import Camera
from space_map import SpaceMap
from planet import generate_planets
from ui import PlanetUI, ShipUI, ColonyBar

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
        self.ship_ui = ShipUI()
        self.colony_bar = ColonyBar()
        self._hovered_planet = None
        self._hovered_ship = None
        self._time_scale = 1.0
        self._running = True

        # Center camera on home planet at initial zoom
        self.camera.zoom = ZOOM_INIT
        home = self.planets[0]
        self.camera.x = home.x - SCREEN_W / (2 * self.camera.zoom)
        self.camera.y = home.y - SCREEN_H / (2 * self.camera.zoom)

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

            # ESC: cancel mission mode first, then close UIs, then quit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.ui._mission_mode:
                    self.ui._mission_mode = None
                    self.ui.show_message("Mission annulée")
                elif self.ship_ui.visible:
                    self.ship_ui.close()
                elif self.ui.visible:
                    self.ui.close()
                else:
                    self._running = False
                return

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

            # Ship UI events (intercepts clicks on its panel)
            if self.ship_ui.handle_event(event):
                continue

            # Planet UI events
            if self.ui.handle_event(event, self.planets, self.ships):
                continue

            # Mission target selection: only left-click picks a planet
            if self.ui._mission_mode:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for p in self.planets:
                        if p.is_clicked(mx, my, self.camera) and p is not self.ui.planet:
                            self.ui.dispatch_mission(p, self.highways)
                            break
                else:
                    self.camera.handle_event(event)
                continue

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
                    (p for p in self.planets if p.is_clicked(mx, my, self.camera)), None)
                if clicked_planet:
                    if self.ui.visible and self.ui.planet is clicked_planet:
                        self.ui.close()
                    else:
                        self.ui.open(clicked_planet)
                        self.ship_ui.close()

        keys = pygame.key.get_pressed()
        self.camera.update(keys)
        self._time_scale = 10.0 if keys[pygame.K_KP_PLUS] else 1.0

    # ── update ───────────────────────────────────────────────────
    def _update(self, dt):
        self.space_map.update(dt)
        self.ui.update(dt)
        for p in self.planets:
            p.update(dt, self.ships)
        for s in self.ships:
            s.update(dt, self.planets, self.highways)
        self.ships = [s for s in self.ships if not s._destroyed]

        mx, my = pygame.mouse.get_pos()
        in_planet_panel = self.ui.visible and self.ui.panel_rect.collidepoint(mx, my)
        in_ship_panel   = self.ship_ui.visible and self.ship_ui.panel_rect.collidepoint(mx, my)
        in_colony_bar   = self.colony_bar.contains_point((mx, my), self.planets)

        # Ship hover (priority)
        self._hovered_ship = None
        if not in_planet_panel and not in_ship_panel and not in_colony_bar:
            self._hovered_ship = next(
                (s for s in self.ships
                 if not s.is_docked and s.is_clicked(mx, my, self.camera)), None)

        # Planet hover (only if no ship hovered)
        self._hovered_planet = None
        if not self._hovered_ship and not in_planet_panel and not in_ship_panel and not in_colony_bar:
            self._hovered_planet = next(
                (p for p in self.planets if p.is_clicked(mx, my, self.camera)), None)

    # ── draw ─────────────────────────────────────────────────────
    def _draw(self):
        self.space_map.draw(self.screen, self.camera)
        self._draw_highways()
        for p in self.planets:
            p.draw(self.screen, self.camera)
        selected_planet = self.ui.planet if self.ui.visible else None
        if selected_planet and selected_planet is not self._hovered_planet:
            selected_planet.draw_selected(self.screen, self.camera)
        if self._hovered_planet:
            self._hovered_planet.draw_hover(self.screen, self.camera)
        for s in self.ships:
            s.draw(self.screen, self.camera)
        if self._hovered_ship:
            self._hovered_ship.draw_hover(self.screen, self.camera)
        self.ui.draw(self.screen, self.planets, self.highways)
        if self._hovered_planet:
            self.ui.draw_mission_hover(self.screen, self._hovered_planet, self.camera, self.highways)
        self.ship_ui.draw(self.screen)
        self.colony_bar.draw(self.screen, self.planets,
                             selected_planet=self.ui.planet if self.ui.visible else None,
                             mission_mode=bool(self.ui._mission_mode))
        self._draw_hud()
        pygame.display.flip()

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

        home = self.planets[0]
        cap = home.storage_cap
        x = 8
        y = SCREEN_H - 20
        for res in RESOURCE_NAMES:
            val = home.resources.get(res, 0)
            color = RESOURCE_COLORS.get(res, WHITE)
            near_cap = val >= cap * 0.95
            t = font.render(f"{res[:3].upper()}:{int(val)}/{int(cap)}", True, RED if near_cap else color)
            self.screen.blit(t, (x, y))
            x += t.get_width() + 12

        hint = "WASD/Arrows:scroll  |  Scroll:zoom  |  RMB drag:pan  |  Click:select  |  ESC:fermer"
        ht = font.render(hint, True, (60, 70, 90))
        self.screen.blit(ht, (SCREEN_W - ht.get_width() - 8, SCREEN_H - 20))
