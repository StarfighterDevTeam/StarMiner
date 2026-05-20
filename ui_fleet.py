# ui_fleet.py
import pygame
from constants import *
from ui_common import _font, Button


class FleetUI:
    PANEL_W = 300

    def __init__(self):
        self.fleet    = None
        self.visible  = False
        self._buttons : list = []
        self._add_mode  = False
        self._renaming  = False
        self._name_buf  = ""

    def open(self, fleet):
        self.fleet      = fleet
        self.visible    = True
        self._add_mode  = False
        self._renaming  = False
        self._name_buf  = fleet.name

    def close(self):
        self.visible   = False
        self.fleet     = None
        self._add_mode = False
        self._renaming = False

    # ── helpers ──────────────────────────────────────────────────
    def _get_addable(self, fleet):
        return [s for s in fleet.home.ships
                if s.state == "idle"
                and s.fleet is None
                and "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])]

    def _compute_panel_h(self, fleet):
        h = 10 + 20 + 14 + 8   # pad + name + home/state + sep
        h += max(1, len(fleet.ships)) * 20 + 8  # member rows
        if self._add_mode and fleet.state == "docked":
            h += 24 + max(1, len(self._get_addable(fleet))) * 18
        h += 24 + 28            # Ajouter btn + mission buttons
        if fleet.state == "orbiting":
            h += 28             # Retour base button
        return h

    @property
    def panel_rect(self):
        h = getattr(self, "_panel_h", 280)
        return pygame.Rect(10, 200, self.PANEL_W, h)

    # ── events ───────────────────────────────────────────────────
    def handle_event(self, event):
        if not self.visible or not self.fleet:
            return False
        pos   = pygame.mouse.get_pos()
        fleet = self.fleet

        # Inline rename mode
        if self._renaming:
            if event.type == pygame.TEXTINPUT:
                self._name_buf += event.text
                return True
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    fleet.name     = self._name_buf.strip() or fleet.name
                    self._renaming = False
                elif event.key == pygame.K_BACKSPACE:
                    self._name_buf = self._name_buf[:-1]
                elif event.key == pygame.K_ESCAPE:
                    self._renaming = False
                    self._name_buf = fleet.name
                return True

        for btn in self._buttons:
            if btn.is_clicked(pos, event):
                tip = btn.tooltip
                if tip == "fleet_navigate_request":
                    return "fleet_navigate_requested"
                if tip == "fleet_cancel":
                    fleet.cancel()
                    return True
                if tip == "fleet_return":
                    return "fleet_return_requested"
                if tip == "fleet_dissolve":
                    return "fleet_dissolve"
                if tip == "fleet_add_toggle":
                    self._add_mode = not self._add_mode
                    return True
                if tip == "fleet_rename":
                    self._renaming = True
                    self._name_buf = fleet.name
                    return True
                if tip.startswith("fleet_remove:"):
                    sid = int(tip.split(":")[1])
                    s = next((s for s in fleet.ships if s.id == sid), None)
                    if s:
                        fleet.remove_ship(s)
                    return True
                if tip.startswith("fleet_add_ship:"):
                    sid = int(tip.split(":")[1])
                    s = next((s for s in fleet.home.ships if s.id == sid), None)
                    if s:
                        fleet.add_ship(s)
                    return True
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(pos):
                self.close()
                return False
        return self.panel_rect.collidepoint(pos)

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, dispatch_modes=None):
        if not self.visible or not self.fleet:
            return
        fleet = self.fleet
        self._panel_h = self._compute_panel_h(fleet)
        pr  = self.panel_rect
        self._buttons.clear()
        mx, my = pygame.mouse.get_pos()

        panel = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        panel.fill((10, 14, 30, 225))
        pygame.draw.rect(panel, CYAN, (0, 0, pr.w, pr.h), 2, border_radius=8)
        surface.blit(panel, pr.topleft)

        y = pr.y + 10

        # ── Name (editable) ───────────────────────────────────────
        disp_name  = (self._name_buf + "|") if self._renaming else fleet.name
        name_color = GOLD if self._renaming else CYAN
        nt = _font(13).render(disp_name, True, name_color)
        surface.blit(nt, (pr.x + 12, y))
        # Invisible click zone over the name label → triggers rename
        rename_btn = Button(pygame.Rect(pr.x + 12, y, nt.get_width(), nt.get_height()),
                            "", tooltip="fleet_rename", enabled=not self._renaming)
        rename_btn.handle_mouse((mx, my))
        self._buttons.append(rename_btn)
        y += 20

        STATE_LABELS = {
            "docked":    ("À quai",      CYAN),
            "orbiting":  ("En orbite",   CYAN),
            "navigate":  ("En route",    ORANGE),
            "returning": ("Retour base", GREEN),
            "combat":    ("Au combat",   RED),
        }
        slabel, scolor = STATE_LABELS.get(fleet.state, (fleet.state, WHITE))
        info_t = _font(10).render(f"{slabel}  —  Base : {fleet.home.name}", True, scolor)
        surface.blit(info_t, (pr.x + 12, y))
        y += 14

        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8

        # ── Member list ───────────────────────────────────────────
        can_modify = (fleet.state == "docked")
        sf = _font(10)

        if not fleet.ships:
            surface.blit(sf.render("Aucun membre", True, GRAY), (pr.x + 14, y))
            y += 20
        else:
            STATE_SHORT = {
                "idle": "Ancré", "navigate": "En route", "combat": "Combat",
                "travel": "Transit", "returning": "Retour",
                "discovering": "Exploration", "mining": "Extraction",
            }
            STATE_FALLBACK = {
                "navigate": "En route", "returning": "Retour base",
                "combat": "Au combat",  "orbiting":  "En orbite",
            }
            for s in fleet.ships:
                if s.state == "idle" and fleet.state != "docked":
                    st_str = STATE_FALLBACK.get(fleet.state, fleet.state)
                else:
                    st_str = STATE_SHORT.get(s.state, s.state)
                prefix_t = sf.render(f"{s.type} #{s.id}  ", True, UI_TEXT)
                lvl_t    = sf.render(f"Niv.{s._upgrade_level}", True, GOLD)
                suffix_t = sf.render(f"  —  {st_str}", True, UI_TEXT)
                surface.blit(prefix_t, (pr.x + 14, y))
                surface.blit(lvl_t,    (pr.x + 14 + prefix_t.get_width(), y))
                surface.blit(suffix_t, (pr.x + 14 + prefix_t.get_width() + lvl_t.get_width(), y))
                if can_modify:
                    rem = Button((pr.x + pr.w - 62, y - 1, 50, 16),
                                 "Retirer", tooltip=f"fleet_remove:{s.id}")
                    rem.handle_mouse((mx, my)); rem.draw(surface)
                    self._buttons.append(rem)
                y += 20

        # ── Add-ship sub-list ─────────────────────────────────────
        if self._add_mode and can_modify:
            addable = self._get_addable(fleet)
            pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
            y += 4
            surface.blit(sf.render("Disponibles :", True, GOLD), (pr.x + 14, y))
            y += 18
            if not addable:
                surface.blit(sf.render("Aucun vaisseau disponible", True, GRAY),
                             (pr.x + 14, y))
                y += 18
            for s in addable:
                prefix_t = sf.render(f"  {s.type} #{s.id}  ", True, GREEN)
                lvl_t    = sf.render(f"Niv.{s._upgrade_level}", True, GOLD)
                surface.blit(prefix_t, (pr.x + 14, y))
                surface.blit(lvl_t,    (pr.x + 14 + prefix_t.get_width(), y))
                add_s = Button((pr.x + pr.w - 62, y - 1, 50, 16),
                               "Ajouter", tooltip=f"fleet_add_ship:{s.id}")
                add_s.handle_mouse((mx, my)); add_s.draw(surface)
                self._buttons.append(add_s)
                y += 18

        # ── Ajouter/Fermer toggle ─────────────────────────────────
        if can_modify:
            lbl = "▲ Fermer" if self._add_mode else "+ Ajouter"
            add_toggle = Button((pr.x + 12, y + 2, 110, 18), lbl,
                                tooltip="fleet_add_toggle")
            add_toggle.handle_mouse((mx, my)); add_toggle.draw(surface)
            self._buttons.append(add_toggle)
        y += 24

        # ── Mission buttons ───────────────────────────────────────
        if fleet.state in ("docked", "orbiting"):
            nav_active = (dispatch_modes or {}).get(fleet) == "fleet_navigate"
            nav_btn = Button((pr.x + 12, y + 2, 120, 22), "Naviguer",
                             tooltip="fleet_navigate_request",
                             enabled=bool(fleet.ships), active=nav_active)
            nav_btn.handle_mouse((mx, my)); nav_btn.draw(surface)
            self._buttons.append(nav_btn)
        else:
            cancel_btn = Button((pr.x + 12, y + 2, 120, 22), "Annuler",
                                tooltip="fleet_cancel")
            cancel_btn.handle_mouse((mx, my)); cancel_btn.draw(surface)
            self._buttons.append(cancel_btn)

        
        if fleet.state == "docked":
            dissolve_btn = Button((pr.x + pr.w - 132, y + 2, 120, 22), "Dissoudre",
                                tooltip="fleet_dissolve")
            dissolve_btn.handle_mouse((mx, my)); dissolve_btn.draw(surface)
            self._buttons.append(dissolve_btn)

        if fleet.state == "orbiting":
            ret_btn = Button((pr.x + 12, y + 30, 120, 22), "Retour base",
                             tooltip="fleet_return", enabled=bool(fleet.ships))
            ret_btn.handle_mouse((mx, my)); ret_btn.draw(surface)
            self._buttons.append(ret_btn)
