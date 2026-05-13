import pygame
from constants import *
from ui_common import _font


class ColonyBar:
    """Collapsible quick-access sidebar listing all colonized planets."""
    TAB_W    = 14
    BAR_W    = 152
    ROW_H    = 24
    HEADER_H = 24
    TOP_Y    = 40   # below FPS / zoom HUD lines

    def __init__(self):
        self._expanded      = True
        self._last_click_t  = 0
        self._last_click_id = None

    # ── geometry ─────────────────────────────────────────────────
    @staticmethod
    def _colonies(planets):
        return [p for p in planets if p.colonized]

    def _bar_rect(self, n):
        h = self.HEADER_H + n * self.ROW_H + 4
        return pygame.Rect(self.TAB_W, self.TOP_Y, self.BAR_W, h)

    @property
    def _tab_rect(self):
        return pygame.Rect(0, self.TOP_Y, self.TAB_W, 30)

    def contains_point(self, pos, planets):
        if self._tab_rect.collidepoint(pos):
            return True
        if not self._expanded:
            return False
        return self._bar_rect(len(self._colonies(planets))).collidepoint(pos)

    # ── events ───────────────────────────────────────────────────
    def handle_event(self, event, planets, mission_mode_active=False):
        """
        Returns ('toggle'|'select'|'center'|'consume', planet|None).
        'select'  → open planet UI
        'center'  → open planet UI AND center camera
        'consume' → click was inside bar but didn't hit a row
        """
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None, None
        pos = pygame.mouse.get_pos()

        if self._tab_rect.collidepoint(pos):
            self._expanded = not self._expanded
            return 'toggle', None

        if not self._expanded or mission_mode_active:
            return None, None

        cols = self._colonies(planets)
        br = self._bar_rect(len(cols))
        if not br.collidepoint(pos):
            return None, None

        ry = self.TOP_Y + self.HEADER_H
        for p in cols:
            if pygame.Rect(br.x, ry, br.w, self.ROW_H).collidepoint(pos):
                now = pygame.time.get_ticks()
                double = (self._last_click_id == p.id
                          and now - self._last_click_t < 400)
                self._last_click_t  = now
                self._last_click_id = p.id
                return ('center' if double else 'select'), p
            ry += self.ROW_H

        return 'consume', None

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, planets, selected_planet=None, mission_mode=False):
        cols = self._colonies(planets)
        mx, my = pygame.mouse.get_pos()
        tab = self._tab_rect

        # ── Tab button (always visible) ───────────────────────────
        hov_tab = tab.collidepoint((mx, my))
        pygame.draw.rect(surface, UI_BTN_HOV if hov_tab else UI_BTN, tab, border_radius=3)
        pygame.draw.rect(surface, UI_BORDER, tab, 1, border_radius=3)
        arrow = "◀" if self._expanded else "▶"
        at = _font(9).render(arrow, True, UI_BTN_TXT)
        surface.blit(at, at.get_rect(center=tab.center))

        if not self._expanded:
            return

        br = self._bar_rect(len(cols))

        # ── Panel background ──────────────────────────────────────
        alpha = 170 if mission_mode else 225
        panel = pygame.Surface((br.w, br.h), pygame.SRCALPHA)
        panel.fill((10, 14, 30, alpha))
        pygame.draw.rect(panel, UI_BORDER, (0, 0, br.w, br.h), 1, border_radius=6)
        surface.blit(panel, br.topleft)

        # ── Header ───────────────────────────────────────────────
        title_color = GRAY if mission_mode else UI_TITLE
        ht = _font(11).render(f"Colonies  [{len(cols)}]", True, title_color)
        surface.blit(ht, (br.x + 8, br.y + 5))
        pygame.draw.line(surface, UI_BORDER,
                         (br.x + 4,      br.y + self.HEADER_H - 2),
                         (br.x + br.w - 4, br.y + self.HEADER_H - 2))

        # ── Planet rows ───────────────────────────────────────────
        ry = br.y + self.HEADER_H
        nf = _font(11)
        for p in cols:
            row      = pygame.Rect(br.x, ry, br.w, self.ROW_H)
            hov      = row.collidepoint((mx, my)) and not mission_mode
            selected = (selected_planet is p)

            if selected:
                bg = (24, 48, 88)
            elif hov:
                bg = (20, 36, 68)
            else:
                bg = (14, 20, 38)
            pygame.draw.rect(surface, bg, (row.x + 1, row.y, row.w - 1, row.h))

            if selected:
                pygame.draw.rect(surface, CYAN, (row.x, row.y, 3, row.h))

            # Activity dot
            has_queue = bool(p.build_queue or p.ship_queue)
            if p.is_home:
                dot_color = GOLD
            elif has_queue:
                dot_color = ORANGE
            else:
                dot_color = GREEN
            cy = ry + self.ROW_H // 2
            pygame.draw.circle(surface, dot_color if not mission_mode else GRAY,
                               (br.x + 10, cy), 4)

            # Planet name
            if mission_mode:
                name_color = GRAY
            elif p.is_home:
                name_color = GOLD
            elif hov or selected:
                name_color = WHITE
            else:
                name_color = UI_TEXT
            nt = nf.render(p.name, True, name_color)
            surface.blit(nt, (br.x + 20, ry + (self.ROW_H - nt.get_height()) // 2))

            # Near-cap warning "!"
            if p.colonized and not mission_mode:
                near_cap = any(v >= p.storage_cap_for(res) * 0.95
                               for res, v in p.resources.items())
                if near_cap:
                    wt = _font(9).render("!", True, RED)
                    surface.blit(wt, (br.x + br.w - wt.get_width() - 5,
                                      cy - wt.get_height() // 2))

            ry += self.ROW_H
