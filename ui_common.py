import pygame
from constants import *

_BTN_ACTIVE     = (160, 90, 10)
_BTN_ACTIVE_HOV = (200, 120, 20)
_BTN_ACTIVE_TXT = (255, 210, 120)
_BTN_ACTIVE_BRD = (255, 160, 40)


def _font(size):
    try:
        return pygame.font.SysFont("consolas", size)
    except Exception:
        return pygame.font.Font(None, size + 4)


def _fmt_time(secs):
    s = int(secs)
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


class Button:
    def __init__(self, rect, text, enabled=True, tooltip="", active=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.enabled = enabled
        self.tooltip = tooltip
        self.active = active
        self._hovered = False

    def draw(self, surface):
        if self.active:
            color = _BTN_ACTIVE_HOV if self._hovered else _BTN_ACTIVE
            border = _BTN_ACTIVE_BRD
            txt_color = _BTN_ACTIVE_TXT
            label = ">> " + self.text
        elif self._hovered and self.enabled:
            color, border, txt_color, label = UI_BTN_HOV, UI_BORDER, UI_BTN_TXT, self.text
        elif self.enabled:
            color, border, txt_color, label = UI_BTN, UI_BORDER, UI_BTN_TXT, self.text
        else:
            color, border, txt_color, label = UI_DISABLED, UI_BORDER, GRAY, self.text

        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=4)
        txt = _font(11).render(label, True, txt_color)
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def handle_mouse(self, pos):
        self._hovered = self.rect.collidepoint(pos)
        return self._hovered

    def is_clicked(self, pos, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(pos) and self.enabled)
