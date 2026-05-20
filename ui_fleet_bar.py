# ui_fleet_bar.py
import pygame
from constants import *
from ui_common import _font

BAR_H   = 44
BAR_Y   = SCREEN_H - BAR_H   # = 756
CARD_W  = 160
CARD_H  = 36
CARD_PAD = 6
START_X = 175   # right of minimap (minimap ends at x=170)


class FleetBar:
    def contains_point(self, pos):
        return pos[1] >= BAR_Y and pos[0] >= START_X

    def handle_event(self, event, fleets):
        """Returns ('select', fleet) | ('consume', None) | (None, None)."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None, None
        mx, my = pygame.mouse.get_pos()
        if my < BAR_Y or mx < START_X:
            return None, None
        x = START_X + CARD_PAD
        for fleet in fleets.values():
            card_rect = pygame.Rect(x, BAR_Y + (BAR_H - CARD_H) // 2, CARD_W, CARD_H)
            if card_rect.collidepoint((mx, my)):
                return "select", fleet
            x += CARD_W + CARD_PAD
        return "consume", None

    def draw(self, surface, fleets, selected_fleet=None):
        # Background band (right of minimap)
        bar_w = SCREEN_W - START_X
        band = pygame.Surface((bar_w, BAR_H), pygame.SRCALPHA)
        band.fill((10, 14, 30, 200))
        surface.blit(band, (START_X, BAR_Y))
        pygame.draw.line(surface, UI_BORDER, (START_X, BAR_Y), (SCREEN_W, BAR_Y), 1)

        if not fleets:
            t = _font(10).render("Aucune flotte", True, GRAY)
            surface.blit(t, (START_X + 12, BAR_Y + (BAR_H - t.get_height()) // 2))
            return

        mx, my = pygame.mouse.get_pos()
        STATE_COLORS = {
            "docked":    CYAN,
            "navigate":  ORANGE,
            "returning": GREEN,
            "combat":    RED,
        }
        STATE_LABELS = {
            "docked":    "En orbite",
            "navigate":  "En route",
            "returning": "Retour",
            "combat":    "Combat",
        }
        x = START_X + CARD_PAD
        for fleet in fleets.values():
            card_rect = pygame.Rect(x, BAR_Y + (BAR_H - CARD_H) // 2, CARD_W, CARD_H)
            hov = card_rect.collidepoint((mx, my))
            sel = fleet is selected_fleet

            bg = (20, 36, 68) if hov else (14, 20, 38)
            pygame.draw.rect(surface, bg, card_rect, border_radius=4)
            border_col = CYAN if sel else UI_BORDER
            pygame.draw.rect(surface, border_col, card_rect, 1, border_radius=4)

            dot_color = STATE_COLORS.get(fleet.state, WHITE)
            cy = card_rect.centery
            pygame.draw.circle(surface, dot_color, (card_rect.x + 10, cy), 4)

            name = fleet.name[:18] + ("…" if len(fleet.name) > 18 else "")
            nt = _font(10).render(name, True, WHITE if hov else UI_TEXT)
            surface.blit(nt, (card_rect.x + 20, card_rect.y + 6))

            sl  = STATE_LABELS.get(fleet.state, fleet.state)
            cnt = _font(9).render(f"{sl}  [{len(fleet.ships)}]", True, dot_color)
            surface.blit(cnt, (card_rect.x + 20, card_rect.y + 20))

            x += CARD_W + CARD_PAD
