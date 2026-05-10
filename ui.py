import pygame
import math
from constants import *

def _font(size):
    try:
        return pygame.font.SysFont("consolas", size)
    except Exception:
        return pygame.font.Font(None, size + 4)

_BTN_ACTIVE     = (160, 90, 10)
_BTN_ACTIVE_HOV = (200, 120, 20)
_BTN_ACTIVE_TXT = (255, 210, 120)
_BTN_ACTIVE_BRD = (255, 160, 40)

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


class PlanetUI:
    PANEL_W = 400
    PANEL_H = 560

    def __init__(self):
        self.planet = None
        self.visible = False
        self._tab = "buildings"   # "buildings" | "ships" | "fleet"
        self._buttons: list[Button] = []
        self._tab_btns: list[Button] = []
        self._mission_mode = None   # ("explore"|"mine", ship)
        self._message = ""
        self._msg_timer = 0.0
        self._build_scroll = 0
        self._fleet_scroll = 0

    def open(self, planet):
        self.planet = planet
        self.visible = True
        self._tab = "buildings"
        self._mission_mode = None
        self._build_scroll = 0
        self._fleet_scroll = 0

    def close(self):
        self.visible = False
        self.planet = None
        self._mission_mode = None

    @property
    def panel_rect(self):
        x = SCREEN_W - self.PANEL_W - 10
        y = SCREEN_H // 2 - self.PANEL_H // 2
        return pygame.Rect(x, y, self.PANEL_W, self.PANEL_H)

    def show_message(self, msg):
        self._message = msg
        self._msg_timer = 3.0

    # ── update ───────────────────────────────────────────────────
    def update(self, dt):
        if self._msg_timer > 0:
            self._msg_timer -= dt

    # ── events ───────────────────────────────────────────────────
    def handle_event(self, event, planets, all_ships):
        if not self.visible:
            return False
        mx, my = pygame.mouse.get_pos()
        pos = (mx, my)

        # Mission mode: next click on a planet selects target
        if self._mission_mode:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Check if click is inside panel → cancel
                if self.panel_rect.collidepoint(pos):
                    self._mission_mode = None
                    return True
                return False   # let game handle planet click for mission

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(pos):
                self.close()
                return False

        # Tab buttons
        for tb in self._tab_btns:
            if tb.is_clicked(pos, event):
                self._tab = tb.text.lower()
                return True

        # Action buttons
        for btn in self._buttons:
            if btn.is_clicked(pos, event):
                self._on_button(btn, planets, all_ships)
                return True

        # Scroll
        if event.type == pygame.MOUSEWHEEL and self.panel_rect.collidepoint(pos):
            if self._tab == "buildings":
                self._build_scroll = max(0, self._build_scroll - event.y)
            elif self._tab == "fleet":
                self._fleet_scroll = max(0, self._fleet_scroll - event.y)
            return True

        return self.panel_rect.collidepoint(pos)

    def _on_button(self, btn, planets, all_ships):
        p = self.planet
        tag = btn.tooltip   # we reuse tooltip as action tag

        if tag.startswith("build:"):
            bname = tag[6:]
            ok = p.start_build(bname)
            self.show_message(f"Building {bname}..." if ok else "Cannot build")

        elif tag.startswith("ship:"):
            stype = tag[5:]
            ok = p.start_ship(stype)
            self.show_message(f"Building {stype}..." if ok else "Cannot build ship")

        elif tag.startswith("colonize"):
            p.colonize()
            self.show_message(f"{p.name} colonized!")

        elif tag.startswith("explore:") or tag.startswith("mine:"):
            mtype, sid = tag.split(":")
            ship = next((s for s in p.ships if s.id == int(sid)), None)
            if ship:
                if self._mission_mode and self._mission_mode == (mtype, ship):
                    self._mission_mode = None          # toggle: annuler
                    self.show_message("Mission annulée")
                else:
                    self._mission_mode = (mtype, ship)
                    self.show_message(f"Cliquez sur une planète pour {mtype}")

    def dispatch_mission(self, target_planet):
        if not self._mission_mode:
            return
        mtype, ship = self._mission_mode

        # Validate — keep mission mode active so the player can pick another planet
        if mtype == "explore" and target_planet.explored:
            self.show_message(f"{target_planet.name} est déjà explorée")
            return
        if mtype == "mine" and not target_planet.explored:
            self.show_message(f"Explorez d'abord {target_planet.name}")
            return

        self._mission_mode = None
        if mtype == "explore":
            ok = ship.send_explore(target_planet)
        else:
            ok = ship.send_mine(target_planet)
        self.show_message(f"Mission {mtype} → {target_planet.name}" if ok else "Mission échouée")

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, planets):
        if not self.visible or not self.planet:
            return
        p = self.planet
        pr = self.panel_rect

        # Background panel
        panel = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        panel.fill((10, 14, 30, 225))
        pygame.draw.rect(panel, UI_BORDER, (0, 0, pr.w, pr.h), 2, border_radius=8)
        surface.blit(panel, pr.topleft)

        y = pr.y + 10
        self._tab_btns.clear()
        self._buttons.clear()

        # ── Title ────────────────────────────────────────────────
        title_font = _font(17)
        txt = title_font.render(p.name, True, UI_TITLE)
        surface.blit(txt, (pr.x + 12, y))
        y += 22

        sub_font = _font(11)
        type_label = {"rocky": "Rocky Planet", "gas": "Gas Giant", "asteroid": "Asteroid Field"}[p.type]
        status = "HOME" if p.is_home else ("Colonized" if p.colonized else ("Explored" if p.explored else "Unknown"))
        sub = sub_font.render(f"{type_label}  |  {status}", True, GRAY)
        surface.blit(sub, (pr.x + 12, y))
        y += 18

        # Colonize button
        if not p.colonized and p.explored:
            btn = Button((pr.x + pr.w - 120, pr.y + 10, 108, 24), "Colonize", tooltip="colonize")
            btn.draw(surface)
            self._buttons.append(btn)

        # ── Resources ────────────────────────────────────────────
        pygame.draw.line(surface, UI_BORDER, (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 6
        res_font = _font(11)
        col_w = (pr.w - 20) // 4
        res_items = [(r, v) for r, v in p.resources.items() if v > 0 or r in p.available_resources]
        for i, (res, val) in enumerate(res_items):
            col = i % 3
            row = i // 3
            rx = pr.x + 10 + col * col_w
            ry = y + row * 16
            color = RESOURCE_COLORS.get(res, WHITE)
            label = f"{res[:RESOURCE_MAX_CHAR].upper()}: {int(val)}" # shorten resources names to X characters max
            t = res_font.render(label, True, color)
            surface.blit(t, (rx, ry))
        rows = (len(res_items) + 2) // 3
        y += max(rows * 16 + 4, 20)

        # Production rates
        prod = {}
        for b in p.buildings:
            for r, rate in b.produces.items():
                prod[r] = prod.get(r, 0) + rate
        if prod:
            prod_font = _font(10)
            parts = [f"+{rate:.1f}/s {res[:RESOURCE_MAX_CHAR]}" for res, rate in prod.items()]
            pt = prod_font.render("  ".join(parts), True, GREEN)
            surface.blit(pt, (pr.x + 10, y))
            y += 14
        y += 4

        # ── Tabs ─────────────────────────────────────────────────
        tabs = ["Buildings", "Ships", "Fleet"]
        tab_w = pr.w // len(tabs)
        for i, tab in enumerate(tabs):
            active = self._tab == tab.lower()
            color = UI_BTN_HOV if active else UI_BTN
            tr = pygame.Rect(pr.x + i * tab_w, y, tab_w, 24)
            pygame.draw.rect(surface, color, tr)
            pygame.draw.rect(surface, UI_BORDER, tr, 1)
            tf = _font(12)
            tt = tf.render(tab, True, WHITE)
            surface.blit(tt, tt.get_rect(center=tr.center))
            tb = Button(tr, tab.lower(), tooltip="")
            tb._hovered = False
            self._tab_btns.append(tb)
        y += 26

        # ── Tab content ──────────────────────────────────────────
        content_y = y
        _QUEUE_SEC_H = 154   # height reserved at bottom for both queues
        content_h = pr.y + pr.h - _QUEUE_SEC_H - 14 - y
        clip = pygame.Rect(pr.x, content_y, pr.w, max(0, content_h))
        surface.set_clip(clip)

        if self._tab == "buildings":
            self._draw_buildings(surface, pr, content_y, p)
        elif self._tab == "ships":
            self._draw_ships_tab(surface, pr, content_y, p)
        elif self._tab == "fleet":
            self._draw_fleet(surface, pr, content_y, p)

        surface.set_clip(None)

        # ── Production queues ─────────────────────────────────────
        queue_y = pr.y + pr.h - _QUEUE_SEC_H - 2
        pygame.draw.line(surface, UI_BORDER,
                         (pr.x + 8, queue_y - 5), (pr.x + pr.w - 8, queue_y - 5))
        self._draw_queue_section(surface, pr, queue_y, p)

        # ── Message ──────────────────────────────────────────────
        if self._msg_timer > 0 and self._message:
            alpha = min(255, int(self._msg_timer * 120))
            mf = _font(12)
            mt = mf.render(self._message, True, GOLD)
            mx2 = pr.x + pr.w // 2 - mt.get_width() // 2
            surface.blit(mt, (mx2, pr.y - 28))

        # Mission mode overlay
        if self._mission_mode:
            mf = _font(13)
            mt = mf.render(">> Click a planet to set mission target <<", True, ORANGE)
            surface.blit(mt, (SCREEN_W // 2 - mt.get_width() // 2, 20))

    def _draw_buildings(self, surface, pr, y, p):
        f = _font(12)
        sf = _font(10)
        built = p.building_names()
        items = list(BUILDING_DEFS.items())
        row_h = 46
        scroll_offset = self._build_scroll * row_h
        ry = y - scroll_offset

        for bname, defn in items:
            if ry + row_h < y or ry > y + 400:
                ry += row_h
                continue
            # Is this building available for this planet type?
            available = p.type in BUILDING_PLANET_TYPES.get(bname, [])
            if not available:
                ry += row_h
                continue

            is_built = bname in built
            in_queue = any(e["name"] == bname for e in p.build_queue)

            bg_color = (20, 40, 20) if is_built else (20, 20, 35)
            pygame.draw.rect(surface, bg_color, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, UI_BORDER, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), 1, border_radius=4)

            name_color = GREEN if is_built else (UI_TEXT if p.colonized else GRAY)
            nt = f.render(bname, True, name_color)
            surface.blit(nt, (pr.x + 12, ry + 6))

            # Cost
            cost_str = "  ".join(f"{amt}{r[:RESOURCE_MAX_CHAR]}" for r, amt in defn["cost"].items())
            ct = sf.render(cost_str, True, GRAY)
            surface.blit(ct, (pr.x + 12, ry + 22))

            # Produces
            if defn["produces"]:
                prod_str = "+" + "  +".join(f"{v:.1f}/s {k[:RESOURCE_MAX_CHAR]}" for k, v in defn["produces"].items())
                pt = sf.render(prod_str, True, GREEN)
                surface.blit(pt, (pr.x + 12, ry + 33))

            # Button
            if p.colonized and not is_built and not in_queue:
                can, _ = p.can_build(bname)
                btn = Button((pr.x + pr.w - 82, ry + 10, 72, 22),
                             "Build", enabled=can, tooltip=f"build:{bname}")
                btn.handle_mouse(pygame.mouse.get_pos())
                btn.draw(surface)
                self._buttons.append(btn)
            elif in_queue:
                qt = sf.render("In queue", True, ORANGE)
                surface.blit(qt, (pr.x + pr.w - 80, ry + 14))

            ry += row_h

    def _draw_ships_tab(self, surface, pr, y, p):
        f = _font(12)
        sf = _font(10)
        if not p.colonized:
            t = f.render("Colonize planet first", True, GRAY)
            surface.blit(t, (pr.x + 20, y + 10))
            return
        if not p.has_shipyard:
            t = f.render("Build a Shipyard first", True, GRAY)
            surface.blit(t, (pr.x + 20, y + 10))
            return

        row_h = 50
        ry = y + 4
        for stype, defn in SHIP_DEFS.items():
            bg_color = (20, 25, 40)
            pygame.draw.rect(surface, bg_color, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, UI_BORDER, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), 1, border_radius=4)

            nt = f.render(stype, True, CYAN)
            surface.blit(nt, (pr.x + 12, ry + 6))

            cost_str = "  ".join(f"{amt}{r[:RESOURCE_MAX_CHAR]}" for r, amt in defn["cost"].items())
            ct = sf.render(f"Cost: {cost_str}  |  {defn['time']}s  |  SPD:{defn['speed']}", True, GRAY)
            surface.blit(ct, (pr.x + 12, ry + 22))

            missions_str = " / ".join(defn["missions"])
            mt = sf.render(f"Missions: {missions_str}", True, UI_TEXT)
            surface.blit(mt, (pr.x + 12, ry + 34))

            can, _ = p.can_build_ship(stype)
            btn = Button((pr.x + pr.w - 82, ry + 14, 72, 22),
                         "Build", enabled=can, tooltip=f"ship:{stype}")
            btn.handle_mouse(pygame.mouse.get_pos())
            btn.draw(surface)
            self._buttons.append(btn)
            ry += row_h

    def _draw_fleet(self, surface, pr, y, p):
        f = _font(12)
        sf = _font(10)
        docked = p.ships
        if not docked:
            t = f.render("No ships docked here", True, GRAY)
            surface.blit(t, (pr.x + 20, y + 10))
            return

        row_h = 56
        scroll_offset = self._fleet_scroll * row_h
        ry = y - scroll_offset + 4

        for ship in docked:
            if ry + row_h < y or ry > y + 400:
                ry += row_h
                continue

            bg_color = (20, 25, 40)
            pygame.draw.rect(surface, bg_color, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, UI_BORDER, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), 1, border_radius=4)

            nt = f.render(f"{ship.type} #{ship.id}", True, CYAN)
            surface.blit(nt, (pr.x + 12, ry + 6))

            state_color = {
                "idle": GRAY, "travel": CYAN, "mining": ORANGE,
                "returning": GREEN, "exploring": CYAN
            }.get(ship.state, WHITE)
            st = sf.render(f"State: {ship.state}", True, state_color)
            surface.blit(st, (pr.x + 12, ry + 22))

            if ship.state == "idle":
                missions = SHIP_DEFS[ship.type]["missions"]
                bx = pr.x + pr.w - 170
                for mi, mtype in enumerate(missions):
                    is_active = self._mission_mode == (mtype, ship)
                    btn = Button((bx + mi * 82, ry + 10, 76, 20),
                                 mtype.capitalize(), enabled=True,
                                 tooltip=f"{mtype}:{ship.id}", active=is_active)
                    btn.handle_mouse(pygame.mouse.get_pos())
                    btn.draw(surface)
                    self._buttons.append(btn)

            cargo_total = sum(ship.cargo.values())
            if cargo_total > 0:
                cargo_str = "  ".join(f"{int(v)} {r[:RESOURCE_MAX_CHAR]}" for r, v in ship.cargo.items() if v > 0)
                ct = sf.render(f"Cargo: {cargo_str}", True, GOLD)
                surface.blit(ct, (pr.x + 12, ry + 36))

            ry += row_h

    # ── Queue section (bottom of panel) ──────────────────────────
    def _draw_queue_section(self, surface, pr, y, p):
        self._draw_single_queue(surface, pr, y,
                                p.build_queue, "BUILD QUEUE", ORANGE, is_ship=False)
        self._draw_single_queue(surface, pr, y + 72 + 6,
                                p.ship_queue, "SHIP QUEUE", CYAN, is_ship=True)

    def _draw_single_queue(self, surface, pr, y, queue, label, color, is_ship):
        from constants import QUEUE_MAX
        BLOCK_H = 72

        # Background block
        pygame.draw.rect(surface, (12, 18, 36),
                         (pr.x + 6, y, pr.w - 12, BLOCK_H - 2), border_radius=4)
        pygame.draw.rect(surface, (40, 55, 85),
                         (pr.x + 6, y, pr.w - 12, BLOCK_H - 2), 1, border_radius=4)

        qlen = len(queue)
        lf = _font(10)

        # Label (left) + count badge (right)
        lt = lf.render(label, True, color)
        surface.blit(lt, (pr.x + 10, y + 4))

        cnt_color = RED if qlen >= QUEUE_MAX else (GRAY if qlen == 0 else WHITE)
        cnt_t = lf.render(f"[{qlen}/{QUEUE_MAX}]", True, cnt_color)
        surface.blit(cnt_t, (pr.x + pr.w - cnt_t.get_width() - 10, y + 4))

        if not queue:
            sf = _font(9)
            empty_t = sf.render("(empty)", True, (55, 65, 85))
            surface.blit(empty_t, (pr.x + 10, y + 22))
            return

        # ── Current item ──────────────────────────────────────────
        entry = queue[0]
        name       = entry["ship_type"] if is_ship else entry["name"]
        time_left  = entry["time_left"]
        time_total = entry.get("time_total", max(time_left, 1))
        progress   = max(0.0, min(1.0, 1.0 - time_left / max(time_total, 0.001)))
        pct        = int(progress * 100)

        # Item name
        nf = _font(11)
        nt = nf.render(name, True, WHITE)
        surface.blit(nt, (pr.x + 10, y + 18))

        # Time + %
        sf = _font(9)
        tt = sf.render(f"{time_left:.0f}s  {pct}%", True, GRAY)
        surface.blit(tt, (pr.x + pr.w - tt.get_width() - 10, y + 20))

        # Progress bar
        bar_x = pr.x + 10
        bar_y = y + 33
        bar_w = pr.w - 20
        bar_h = 9
        pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            pygame.draw.rect(surface, color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
            # Bright highlight strip at top of filled bar
            highlight = tuple(min(255, c + 60) for c in color)
            pygame.draw.rect(surface, highlight, (bar_x, bar_y, fill_w, 2), border_radius=3)
        pygame.draw.rect(surface, (50, 65, 100), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)

        # ── Queue list (items 1+) ─────────────────────────────────
        if len(queue) > 1:
            qf = _font(9)
            chips = []
            max_show = 4
            for e in queue[1: max_show + 1]:
                chips.append(e["ship_type"] if is_ship else e["name"])
            remainder = len(queue) - 1 - len(chips)
            line = "  ›  ".join(chips)
            if remainder > 0:
                line += f"  +{remainder} more"
            qt = qf.render(line, True, (95, 110, 140))
            surface.blit(qt, (pr.x + 10, y + 48))


# ══════════════════════════════════════════════════════════════════
class ShipUI:
    PANEL_W = 330
    PANEL_H = 280

    def __init__(self):
        self.ship = None
        self.visible = False

    def open(self, ship):
        self.ship = ship
        self.visible = True

    def close(self):
        self.visible = False
        self.ship = None

    @property
    def panel_rect(self):
        return pygame.Rect(10, SCREEN_H - self.PANEL_H - 36, self.PANEL_W, self.PANEL_H)

    def handle_event(self, event):
        if not self.visible:
            return False
        pos = pygame.mouse.get_pos()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(pos):
                self.close()
                return False
        return self.panel_rect.collidepoint(pos)

    def draw(self, surface):
        if not self.visible or not self.ship:
            return
        s = self.ship
        pr = self.panel_rect

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
        y += 20

        sub_f = _font(11)
        base_t = sub_f.render(f"Base : {s.home.name}", True, GRAY)
        surface.blit(base_t, (pr.x + 12, y))
        y += 16

        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8

        # ── Mission status ────────────────────────────────────────
        from ship import MISSION_IDLE, MISSION_TRAVEL, MISSION_MINE, MISSION_RETURN
        STATE_LABELS = {
            MISSION_IDLE:   "En attente",
            MISSION_TRAVEL: "En transit",
            MISSION_MINE:   "En extraction",
            MISSION_RETURN: "Retour",
        }
        STATE_COLORS = {
            MISSION_IDLE:   GRAY,
            MISSION_TRAVEL: CYAN,
            MISSION_MINE:   ORANGE,
            MISSION_RETURN: GREEN,
        }
        sf = _font(12)
        state_label = STATE_LABELS.get(s.state, s.state)
        state_color = STATE_COLORS.get(s.state, WHITE)

        mission_type = getattr(s, "_mission_type", None)
        if s.state == MISSION_TRAVEL and mission_type:
            state_label += f"  ({mission_type})"
        st = sf.render(f"Statut : {state_label}", True, state_color)
        surface.blit(st, (pr.x + 12, y))
        y += 18

        # ── Route ────────────────────────────────────────────────
        df = _font(11)
        dep_t = df.render(f"Départ      :  {s.home.name}", True, UI_TEXT)
        surface.blit(dep_t, (pr.x + 12, y))
        y += 15

        if s.state in (MISSION_TRAVEL, MISSION_MINE) and s.target_planet:
            dest_name = s.target_planet.name
        elif s.state == MISSION_RETURN:
            dest_name = s.home.name
        else:
            dest_name = "—"
        dest_t = df.render(f"Destination :  {dest_name}", True, UI_TEXT)
        surface.blit(dest_t, (pr.x + 12, y))
        y += 15

        # ETA
        if s.state == MISSION_TRAVEL and s.target_planet:
            dist = math.hypot(s.target_planet.x - s.x, s.target_planet.y - s.y)
            eta = dist / s.speed
        elif s.state == MISSION_RETURN:
            dist = math.hypot(s.home.x - s.x, s.home.y - s.y)
            eta = dist / s.speed
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

        # Mining timer
        if s.state == MISSION_MINE:
            remaining = max(0, getattr(s, "_mine_timer", 0))
            mt = df.render(f"Extraction  :  {remaining:.0f}s restantes", True, ORANGE)
            surface.blit(mt, (pr.x + 12, y))
            y += 15

        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8

        # ── Cargo ────────────────────────────────────────────────
        cargo_total = sum(s.cargo.values())
        cf = _font(11)
        cap_color = ORANGE if cargo_total >= s.capacity > 0 else UI_TEXT
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

        # ── Stats ────────────────────────────────────────────────
        speed_t = _font(10).render(
            f"Vitesse : {s.speed} px/s   Capacité : {s.capacity}",
            True, (80, 95, 120))
        surface.blit(speed_t, (pr.x + 12, y))
