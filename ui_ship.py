import pygame
import math
from constants import *
from ui_common import _font, Button


class ShipUI:
    PANEL_W = 330
    PANEL_H = 310

    def __init__(self):
        self.ship = None
        self.visible = False
        self._buttons: list[Button] = []

    def open(self, ship):
        self.ship = ship
        self.visible = True

    def close(self):
        self.visible = False
        self.ship = None

    def _compute_panel_h(self, s):
        from ship import MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE, MISSION_RETURN
        h = 10 + 20 + 16 + 8 + 18 + 15 + 15  # pad + title + home + sep + status + depart + dest

        if s.state in (MISSION_TRAVEL, MISSION_RETURN):
            h += 15 + 12  # ETA + progress bar
        if s.state == MISSION_DISCOVER:
            h += 15 + 12  # discover timer + bar
        if s.state == MISSION_MINE:
            h += 15       # mine timer
        h += 26  # cancel/repeat row (always reserved)
        _can_navigate = s.fire_range > 0 or "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
        if _can_navigate:
            h += 26  # navigate row

        if s.capacity > 0:
            h += 8   # separator before cargo
            h += 14  # cargo total line
            cargo_total = sum(s.cargo.values())
            if cargo_total > 0:
                n = sum(1 for v in s.cargo.values() if v > 0)
                h += ((n - 1) // 3 + 1) * 13
            else:
                h += 13  # "(vide)"
            h += 10  # separator after cargo

        # Combat stats section
        if s.fire_range > 0:
            h += 8 + 14 + 12 + 14  # sep + HP bar row + hp text + combat stats

        h += 8   # separator before stats
        h += 13  # speed stat
        h += 13  # fuel stat
        if s.fuel_remaining > 0:
            h += 13  # fuel remaining (in flight)
        h += 8   # bottom pad
        return h

    @property
    def panel_rect(self):
        h = getattr(self, '_panel_h', self.PANEL_H)
        return pygame.Rect(int(SCREEN_W) - self.PANEL_W - 10, 50, self.PANEL_W, h)

    def handle_event(self, event):
        if not self.visible:
            return False
        pos = pygame.mouse.get_pos()
        for btn in self._buttons:
            if btn.is_clicked(pos, event):
                if btn.tooltip == "cancel_mission" and self.ship:
                    self.ship.cancel_mission()
                elif btn.tooltip == "toggle_repeat" and self.ship:
                    self.ship.repeat = not self.ship.repeat
                elif btn.tooltip == "patrol_request" and self.ship:
                    return "patrol_requested"
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(pos):
                self.close()
                return False
        return self.panel_rect.collidepoint(pos)

    def draw(self, surface):
        if not self.visible or not self.ship:
            return
        s = self.ship
        self._panel_h = self._compute_panel_h(s)
        pr = self.panel_rect
        self._buttons.clear()

        # Background
        panel = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        panel.fill((10, 14, 30, 225))
        pygame.draw.rect(panel, CYAN, (0, 0, pr.w, pr.h), 2, border_radius=8)
        surface.blit(panel, pr.topleft)

        y = pr.y + 10

        # ── Title ────────────────────────────────────────────────
        title_f = _font(15)
        title_t = title_f.render(f"{s.type}  #{s.id}", True, CYAN)
        surface.blit(title_t, (pr.x + 12, y))
        ulvl_t = _font(11).render(f"Niv.{s._upgrade_level}", True, GOLD)
        surface.blit(ulvl_t, (pr.x + 12 + title_t.get_width() + 8, y + 3))
        y += 20

        sub_f = _font(11)
        base_t = sub_f.render(f"Base : {s.home.name}", True, GRAY)
        surface.blit(base_t, (pr.x + 12, y))
        y += 16

        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8

        # ── Mission status ────────────────────────────────────────
        from ship import (MISSION_IDLE, MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE,
                          MISSION_RETURN, MISSION_PATROL, MISSION_COMBAT)
        STATE_LABELS = {
            MISSION_IDLE:     "En attente",
            MISSION_TRAVEL:   "En transit",
            MISSION_DISCOVER: "En exploration",
            MISSION_MINE:     "En extraction",
            MISSION_RETURN:   "Retour",
            MISSION_PATROL:   "En navigation",
            MISSION_COMBAT:   "Au combat",
        }
        STATE_COLORS = {
            MISSION_IDLE:     GRAY,
            MISSION_TRAVEL:   CYAN,
            MISSION_DISCOVER: GOLD,
            MISSION_MINE:     ORANGE,
            MISSION_RETURN:   GREEN,
            MISSION_PATROL:   ORANGE,
            MISSION_COMBAT:   RED,
        }
        sf = _font(12)
        state_label = STATE_LABELS.get(s.state, s.state)
        state_color = STATE_COLORS.get(s.state, WHITE)

        mission_type = getattr(s, "_mission_type", None)
        if s.state == MISSION_TRAVEL and mission_type:
            labels = {"explore": "exploration", "mine": "extraction", "colonize": "colonisation", "highway": "autoroute"}
            state_label += f"  ({labels.get(mission_type, mission_type)})"
        if s.state == MISSION_TRAVEL and mission_type == "colonize":
            state_color = GOLD
        st = sf.render(f"Statut : {state_label}", True, state_color)
        surface.blit(st, (pr.x + 12, y))
        y += 18

        # ── Route ────────────────────────────────────────────────
        df = _font(11)
        dep_t = df.render(f"Départ      :  {s.home.name}", True, UI_TEXT)
        surface.blit(dep_t, (pr.x + 12, y))
        y += 15

        if s.state in (MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE) and s.target_planet:
            dest_name = s.target_planet.name
        elif s.state == MISSION_RETURN:
            dest_name = s.home.name
        elif s.state == MISSION_PATROL and s._patrol_dest:
            if s._dock_planet:
                dest_name = s._dock_planet.name
            else:
                wx, wy = s._patrol_dest
                dest_name = f"({int(wx)}, {int(wy)})"
        elif s.state == MISSION_COMBAT:
            dest_name = "Zone de combat"
        else:
            dest_name = "—"
        dest_t = df.render(f"Destination :  {dest_name}", True, UI_TEXT)
        surface.blit(dest_t, (pr.x + 12, y))
        y += 15

        # ETA
        _spd = max(getattr(s, "_effective_speed", s.speed), 1)
        if s.state == MISSION_TRAVEL and s.target_planet:
            dist = math.hypot(s.target_planet.x - s.x, s.target_planet.y - s.y)
            eta = dist / _spd
        elif s.state == MISSION_RETURN:
            dist = math.hypot(s.home.x - s.x, s.home.y - s.y)
            eta = dist / _spd
        else:
            eta = None

        if eta is not None:
            eta_str = f"{int(eta//60)}m {int(eta%60)}s" if eta >= 60 else f"{eta:.0f}s"
            eta_t = df.render(f"ETA         :  {eta_str}", True, CYAN)
            surface.blit(eta_t, (pr.x + 12, y))
            y += 15

            # Mini progress bar (distance covered)
            if s.state == MISSION_TRAVEL and s.target_planet:
                total_dist = math.hypot(s.target_planet.x - s.home.x,
                                        s.target_planet.y - s.home.y)
            elif s.state == MISSION_RETURN:
                total_dist = math.hypot(s.home.x - s.target_planet.x if s.target_planet
                                        else s.home.x - s.x,
                                        s.home.y - s.target_planet.y if s.target_planet
                                        else s.home.y - s.y)
            else:
                total_dist = 1
            progress = max(0.0, min(1.0, 1.0 - dist / max(total_dist, 1)))
            bar_x, bar_y = pr.x + 12, y
            bar_w, bar_h = pr.w - 24, 7
            pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            fw = int(bar_w * progress)
            if fw > 0:
                pygame.draw.rect(surface, CYAN, (bar_x, bar_y, fw, bar_h), border_radius=3)
                highlight = tuple(min(255, c + 60) for c in CYAN)
                pygame.draw.rect(surface, highlight, (bar_x, bar_y, fw, 2), border_radius=3)
            pygame.draw.rect(surface, (50, 65, 100), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)
            y += 12

        # Discovery timer
        if s.state == MISSION_DISCOVER:
            remaining = max(0, getattr(s, "_discover_timer", 0))
            total = max(1, getattr(s, "_discover_duration", 1))
            dt_t = df.render(f"Exploration  :  {remaining:.0f}s restantes", True, GOLD)
            surface.blit(dt_t, (pr.x + 12, y))
            y += 15
            progress = max(0.0, min(1.0, 1.0 - remaining / total))
            bar_x, bar_y = pr.x + 12, y
            bar_w, bar_h = pr.w - 24, 7
            pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            fw = int(bar_w * progress)
            if fw > 0:
                pygame.draw.rect(surface, GOLD, (bar_x, bar_y, fw, bar_h), border_radius=3)
                highlight = tuple(min(255, c + 60) for c in GOLD)
                pygame.draw.rect(surface, highlight, (bar_x, bar_y, fw, 2), border_radius=3)
            pygame.draw.rect(surface, (50, 65, 100), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)
            y += 12

        # Mining timer
        if s.state == MISSION_MINE:
            remaining = max(0, getattr(s, "_mine_timer", 0))
            mt = df.render(f"Extraction  :  {remaining:.0f}s restantes", True, ORANGE)
            surface.blit(mt, (pr.x + 12, y))
            y += 15

        # Cancel + Repeat row (space always reserved)
        has_cancel = s.state in (MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE)
        has_repeat = s.type in ("Miner", "Tanker")
        if has_cancel:
            _one_way = getattr(s, "_mission_type", None) in MISSION_ONE_WAY
            _free_nav = "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
            if _one_way and not _free_nav:
                if s.state == MISSION_TRAVEL and s.target_planet:
                    _d_home   = math.hypot(s.x - s.home.x, s.y - s.home.y)
                    _d_target = math.hypot(s.x - s.target_planet.x, s.y - s.target_planet.y)
                    _can_cancel = _d_home < _d_target
                else:
                    _can_cancel = False  # already at destination, past PNR
            else:
                _can_cancel = True
            cancel_btn = Button((pr.x + pr.w // 2 - 70, y + 2, 140, 20),
                                "Annuler mission", tooltip="cancel_mission",
                                enabled=_can_cancel)
            cancel_btn.handle_mouse(pygame.mouse.get_pos())
            cancel_btn.draw(surface)
            self._buttons.append(cancel_btn)
        if has_repeat:
            repeat_btn = Button((pr.x + pr.w - 88, y + 2, 76, 20),
                                "Repeat", active=s.repeat, tooltip="toggle_repeat")
            repeat_btn.handle_mouse(pygame.mouse.get_pos())
            repeat_btn.draw(surface)
            self._buttons.append(repeat_btn)
        y += 26  # always advance

        # Navigate row for combat ships and ships with "navigate" mission
        _can_navigate = s.fire_range > 0 or "navigate" in SHIP_DEFS.get(s.type, {}).get("missions", [])
        if _can_navigate:
            has_nav_cancel = s.state in (MISSION_PATROL, MISSION_COMBAT)
            bx = pr.x + 10
            bw = 140
            nav_btn = Button((bx, y + 2, bw, 20), "Naviguer", tooltip="patrol_request")
            nav_btn.handle_mouse(pygame.mouse.get_pos())
            nav_btn.draw(surface)
            self._buttons.append(nav_btn)
            if has_nav_cancel:
                cancel_btn = Button((pr.x + pr.w - 150, y + 2, 140, 20),
                                    "Annuler navigation", tooltip="cancel_mission")
                cancel_btn.handle_mouse(pygame.mouse.get_pos())
                cancel_btn.draw(surface)
                self._buttons.append(cancel_btn)
            y += 26  # always advance

        # ── Cargo ────────────────────────────────────────────────
        if s.capacity > 0:
            pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
            y += 8
            cargo_total = sum(s.cargo.values())
            cf = _font(11)
            cap_color = ORANGE if cargo_total >= s.capacity else UI_TEXT
            cap_t = cf.render(f"Cargaison   :  {int(cargo_total)} / {s.capacity}", True, cap_color)
            surface.blit(cap_t, (pr.x + 12, y))
            y += 14

            if cargo_total > 0:
                items = [(r, v) for r, v in s.cargo.items() if v > 0]
                col_w = (pr.w - 24) // min(len(items), 3)
                for i, (res, amt) in enumerate(items):
                    color = RESOURCE_COLORS.get(res, WHITE)
                    rt = _font(10).render(f"{res[:3].upper()}: {int(amt)}", True, color)
                    surface.blit(rt, (pr.x + 14 + (i % 3) * col_w, y + (i // 3) * 13))
                y += ((len(items) - 1) // 3 + 1) * 13
            else:
                et = cf.render("  (vide)", True, (55, 65, 85))
                surface.blit(et, (pr.x + 12, y))
                y += 13

            pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y + 2), (pr.x + pr.w - 8, y + 2))
            y += 10

        # ── Combat section ────────────────────────────────────────
        if s.fire_range > 0:
            pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
            y += 8

            # HP bar
            hp_ratio = max(0.0, s.hp / max(s.max_hp, 1)) if s.hp >= 0 else 1.0
            bar_w = pr.w - 100
            bar_h = 10
            bar_x = pr.x + 12
            pygame.draw.rect(surface, (40, 40, 40), (bar_x, y, bar_w, bar_h), border_radius=3)
            fill_color = GREEN if hp_ratio > 0.5 else (ORANGE if hp_ratio > 0.25 else RED)
            fw = int(bar_w * hp_ratio)
            if fw > 0:
                pygame.draw.rect(surface, fill_color, (bar_x, y, fw, bar_h), border_radius=3)
            pygame.draw.rect(surface, (80, 80, 80), (bar_x, y, bar_w, bar_h), 1, border_radius=3)
            hp_t = _font(10).render(f"PV: {max(0, s.hp)}/{s.max_hp}", True, fill_color)
            surface.blit(hp_t, (bar_x + bar_w + 6, y))
            y += 12

            # Combat stats
            cf = _font(10)
            rof_str = f"{s.fire_rate:.1f}" if s.fire_rate < 10 else f"{s.fire_rate:.0f}"
            stats = f"ATK:{s.damage}  Portée:{s.fire_range}  ROF:{rof_str}/s"
            surface.blit(cf.render(stats, True, (160, 100, 100)), (pr.x + 12, y))
            y += 14

            if s.state == MISSION_COMBAT and s._target_enemy:
                tgt_t = _font(10).render(f"Cible: #{s._target_enemy.id}", True, RED)
                surface.blit(tgt_t, (pr.x + 12, y))
                y += 14

        # ── Stats ────────────────────────────────────────────────
        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8
        stats_str = f"Vitesse : {s.speed} px/s"
        speed_t = _font(10).render(stats_str, True, (80, 95, 120))
        surface.blit(speed_t, (pr.x + 12, y))
        y += 13
        fuel_rate_str = f"Carburant : {s.fuel_rate * 1000:.1f} {s.fuel_type}/1000u"
        fuel_rate_t = _font(10).render(fuel_rate_str, True, (80, 95, 120))
        surface.blit(fuel_rate_t, (pr.x + 12, y))
        y += 13

        # Fuel tank gauge
        ratio = max(0.0, min(1.0, s.fuel_remaining / s.fuel_capacity))
        low = ratio < 0.25
        fc = RED if ratio < 0.1 else (ORANGE if low else CYAN)
        tank_label = f"Réservoir : {s.fuel_remaining:.0f} / {s.fuel_capacity} {s.fuel_type}"
        surface.blit(_font(10).render(tank_label, True, fc), (pr.x + 12, y))
        y += 13
        bar_x, bar_y = pr.x + 12, y
        bar_w, bar_h = pr.w - 24, 6
        pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fw = int(bar_w * ratio)
        if fw > 0:
            pygame.draw.rect(surface, fc, (bar_x, bar_y, fw, bar_h), border_radius=3)
        pygame.draw.rect(surface, (50, 65, 100), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)
        y += 10
