import pygame
import math
from constants import *

def _font(size):
    try:
        return pygame.font.SysFont("consolas", size)
    except Exception:
        return pygame.font.Font(None, size + 4)

def _fmt_time(secs):
    s = int(secs)
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"

def _mission_eta(ship):
    """Returns (remaining_secs, total_secs) for the full mission, or None."""
    import math
    from ship import MISSION_IDLE, MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE, MISSION_RETURN
    if ship.state == MISSION_IDLE or ship.target_planet is None:
        return None
    mtype = getattr(ship, "_mission_type", None)
    if mtype == "mine":
        mdur = getattr(ship, "_mine_duration", 8.0)
    elif mtype == "explore":
        mdur = getattr(ship, "_discover_duration", 10.0)
    else:
        mdur = 0.0
    t = ship.target_planet
    spd = max(getattr(ship, "_effective_speed", ship.speed), 1)
    d_there  = math.hypot(ship.home.x - t.x, ship.home.y - t.y) / spd
    d_back   = d_there  # symmetric
    total    = d_there + mdur + d_back
    if ship.state == MISSION_TRAVEL:
        rem = math.hypot(ship.x - t.x, ship.y - t.y) / spd + mdur + d_back
    elif ship.state == MISSION_DISCOVER:
        rem = getattr(ship, "_discover_timer", 0.0) + d_back
    elif ship.state == MISSION_MINE:
        rem = getattr(ship, "_mine_timer", 0.0) + d_back
    elif ship.state == MISSION_RETURN:
        rem = math.hypot(ship.x - ship.home.x, ship.y - ship.home.y) / spd
    else:
        return None
    return (max(0.0, rem), max(total, 0.001))

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
    PANEL_H = 620

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
        top = 50
        return pygame.Rect(int(SCREEN_W) - self.PANEL_W - 10, top,
                           self.PANEL_W, int(SCREEN_H) - top - 10)

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

        elif tag == "cancel_build_one":
            p.cancel_build()
            self.show_message("Production annulée (remboursée)")
        elif tag == "cancel_build_all":
            p.cancel_all_builds()
            self.show_message("Toutes les productions annulées")
        elif tag == "cancel_ship_one":
            p.cancel_ship()
            self.show_message("Construction annulée (remboursée)")
        elif tag == "cancel_ship_all":
            p.cancel_all_ships()
            self.show_message("Toutes les constructions annulées")

        elif tag.startswith("upgrade:"):
            bname = tag[8:]
            ok = p.start_upgrade(bname)
            b = p.get_building(bname)
            lvl = b.level if b else "?"
            self.show_message(f"Upgrade {bname} → Niv.{lvl + 1 if b else '?'}..." if ok else "Upgrade impossible")

        elif tag.startswith("cancel_mission:"):
            sid = int(tag.split(":")[1])
            ship = next((s for s in p.ships if s.id == sid), None)
            if ship and ship.cancel_mission():
                self.show_message("Mission annulée")

        elif tag.startswith("toggle_repeat:"):
            sid = int(tag.split(":")[1])
            ship = next((s for s in p.ships if s.id == sid), None)
            if ship:
                ship.repeat = not ship.repeat
                self.show_message(f"Repeat {'activé' if ship.repeat else 'désactivé'}")

        elif tag.startswith("explore:") or tag.startswith("mine:") or tag.startswith("colonize:") or tag.startswith("highway:"):
            mtype, sid = tag.split(":")
            ship = next((s for s in p.ships if s.id == int(sid)), None)
            if ship:
                if self._mission_mode and self._mission_mode == (mtype, ship):
                    self._mission_mode = None
                    self.show_message("Mission annulée")
                else:
                    self._mission_mode = (mtype, ship)
                    verb = {"explore": "explorer", "mine": "miner", "colonize": "coloniser", "highway": "relier en autoroute"}.get(mtype, mtype)
                    self.show_message(f"Cliquez sur une planète à {verb}")

    def dispatch_mission(self, target_planet, highways=None):
        if not self._mission_mode:
            return
        mtype, ship = self._mission_mode

        # Validate — keep mission mode active so the player can pick another planet
        if mtype == "explore":
            if target_planet is ship.home:
                self.show_message("Même planète — choisissez une autre")
                return
            if target_planet.explored:
                self.show_message(f"{target_planet.name} est déjà explorée")
                return
        if mtype == "mine":
            if target_planet is ship.home:
                self.show_message("Même planète — choisissez une autre")
                return
            if not target_planet.colonized:
                self.show_message(f"{target_planet.name} n'est pas colonisée")
                return
            if not target_planet.explored:
                self.show_message(f"Explorez d'abord {target_planet.name}")
                return
        if mtype == "colonize":
            if not target_planet.explored:
                self.show_message(f"Explorez d'abord {target_planet.name}")
                return
            if target_planet.colonized:
                self.show_message(f"{target_planet.name} est déjà colonisée")
                return
        if mtype == "highway":
            if not target_planet.colonized:
                self.show_message(f"{target_planet.name} n'est pas colonisée")
                return
            if target_planet is ship.home:
                self.show_message("Choisissez une autre planète")
                return
            if highways is not None and frozenset({ship.home.id, target_planet.id}) in highways:
                self.show_message(f"Autoroute déjà existante vers {target_planet.name}")
                return

        self._mission_mode = None
        if mtype == "explore":
            ok = ship.send_explore(target_planet)
        elif mtype == "mine":
            ok = ship.send_mine(target_planet)
        elif mtype == "highway":
            ok = ship.send_highway(target_planet)
        else:
            ok = ship.send_colonize(target_planet)
        if mtype == "colonize" and ok:
            self.show_message(f"Coloniseur en route → {target_planet.name} (aller simple)")
        elif mtype == "highway" and ok:
            self.show_message(f"Constructeur en route → {target_planet.name} (aller simple)")
        else:
            self.show_message(f"Mission {mtype} → {target_planet.name}" if ok else "Mission échouée")

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, planets, highways=None):
        if not self.visible or not self.planet:
            return
        p = self.planet
        pr = self.panel_rect
        self._highways = highways

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


        # ── Resources ────────────────────────────────────────────
        pygame.draw.line(surface, UI_BORDER, (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 6
        res_font = _font(11)
        col_w = (pr.w - 20) // 3
        cap = p.storage_cap if p.colonized else None
        res_items = [(r, v) for r, v in p.resources.items() if v > 0 or r in p.available_resources]
        for i, (res, val) in enumerate(res_items):
            col = i % 3
            row = i // 3
            rx = pr.x + 10 + col * col_w
            ry = y + row * 16
            color = RESOURCE_COLORS.get(res, WHITE)
            if p.colonized:
                near_cap = cap and val >= cap * 0.95
                label = f"{res[:3].upper()}:{int(val)}/{int(cap)}"
                t = res_font.render(label, True, RED if near_cap else color)
            else:
                label = res[:RESOURCE_MAX_CHAR].upper()
                t = res_font.render(label, True, color)
            surface.blit(t, (rx, ry))
        rows = (len(res_items) + 2) // 3
        y += max(rows * 16 + 4, 20)

        if p.colonized:
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
            _QUEUE_SEC_H = 202
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

        else:
            # ── Uncolonized hint ──────────────────────────────────────
            hf = _font(11)
            hc = (70, 80, 100)
            surface.blit(hf.render("Cette planète n'est pas colonisée.", True, hc), (pr.x + 12, y + 10))
            if p.explored:
                surface.blit(hf.render("Envoyez un Colonisateur depuis votre flotte", True, hc), (pr.x + 12, y + 26))
                surface.blit(hf.render("pour prendre possession de cette planète.", True, hc), (pr.x + 12, y + 42))
            else:
                surface.blit(hf.render("Explorez-la avec une Probe, puis envoyez", True, hc), (pr.x + 12, y + 26))
                surface.blit(hf.render("un Colonisateur depuis votre flotte.", True, hc), (pr.x + 12, y + 42))

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

    def draw_mission_hover(self, surface, planet, camera, highways=None):
        if not self._mission_mode:
            return
        mtype, ship = self._mission_mode

        dist_to   = math.hypot(ship.x - planet.x, ship.y - planet.y)
        dist_back = math.hypot(planet.x - ship.home.x, planet.y - ship.home.y)

        # Highway bonus applies if a link already exists
        has_highway = (highways is not None and
                       frozenset({ship.home.id, planet.id}) in highways)
        speed_mult = 1.5 if has_highway else 1.0
        travel_to   = dist_to   / max(ship.speed * speed_mult, 1)
        travel_back = dist_back / max(ship.speed * speed_mult, 1)

        if mtype == "explore":
            mission_dur = getattr(ship, "_discover_duration", 10.0)
        elif mtype == "mine":
            mission_dur = getattr(ship, "_mine_duration", 8.0)
        else:
            mission_dur = 0.0

        one_way = mtype in ("colonize", "highway")
        total = travel_to + mission_dur + (0 if one_way else travel_back)

        lines = []
        # Check for blocking conditions first (show error instead of ETA)
        error = None
        if planet is ship.home:
            error = ("Même planète", RED)
        elif mtype == "explore" and planet.explored:
            error = (f"{planet.name} déjà explorée", ORANGE)
        elif mtype == "mine" and not planet.colonized:
            error = ("Planète non colonisée", RED)
        elif mtype == "mine" and not planet.explored:
            error = ("Planète non explorée", RED)
        elif mtype == "highway" and not planet.colonized:
            error = ("Planète non colonisée", RED)
        elif mtype == "highway" and has_highway:
            error = ("Autoroute déjà existante", ORANGE)

        if error:
            lines.append(error)
        elif mtype == "highway":
            lines.append((f"Aller   : {_fmt_time(travel_to)}", UI_TEXT))
            lines.append((f"Total   : {_fmt_time(total)}", CYAN))
            lines.append(("→ +50% vitesse sur ce trajet", GOLD))
        else:
            if has_highway:
                lines.append(("★ Autoroute active (+50%)", GOLD))
            lines.append((f"Aller   : {_fmt_time(travel_to)}", UI_TEXT))
            if mtype == "explore":
                lines.append((f"Découv. : {_fmt_time(mission_dur)}", GOLD))
            elif mtype == "mine":
                lines.append((f"Extract.: {_fmt_time(mission_dur)}", ORANGE))
            if not one_way:
                lines.append((f"Retour  : {_fmt_time(travel_back)}", UI_TEXT))
            lines.append((f"Total   : {_fmt_time(total)}", CYAN))

        f = _font(11)
        line_h = 15
        pad = 8
        w = max(f.size(txt)[0] for txt, _ in lines) + pad * 2
        h = len(lines) * line_h + pad

        sx, sy = camera.world_to_screen(planet.x, planet.y)
        tx = int(sx) + 18
        ty = int(sy) - h // 2
        tx = min(tx, int(SCREEN_W) - w - 4)
        ty = max(ty, 4)
        ty = min(ty, int(SCREEN_H) - h - 4)

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((8, 12, 28, 210))
        pygame.draw.rect(panel, ORANGE, (0, 0, w, h), 1, border_radius=4)
        surface.blit(panel, (tx, ty))
        for i, (txt, color) in enumerate(lines):
            surface.blit(f.render(txt, True, color), (tx + pad, ty + pad // 2 + i * line_h))

    def _draw_buildings(self, surface, pr, y, p):
        f = _font(12)
        sf = _font(10)
        mouse_pos = pygame.mouse.get_pos()

        # Collect only buildings available for this planet type
        visible = [(bname, defn) for bname, defn in BUILDING_DEFS.items()
                   if p.type in BUILDING_PLANET_TYPES.get(bname, [])]

        row_h = 46
        SB_W = 7                          # scrollbar width
        content_w = pr.w - 12 - SB_W - 2 # row width (leaves room for scrollbar)
        total_h = len(visible) * row_h
        visible_h = pr.y + pr.h - 202 - 14 - y   # mirrors content_h in draw()

        # Clamp scroll so last row is always reachable
        max_scroll = max(0, (total_h - visible_h) // row_h + 1)
        self._build_scroll = max(0, min(self._build_scroll, max_scroll))

        scroll_offset = self._build_scroll * row_h
        ry = y - scroll_offset

        for bname, defn in visible:
            if ry + row_h < y or ry > y + visible_h:
                ry += row_h
                continue

            b = p.get_building(bname)
            is_built = b is not None
            in_build_queue   = any(not e.get("upgrade") and e["name"] == bname for e in p.build_queue)
            in_upgrade_queue = any(e.get("upgrade")     and e["name"] == bname for e in p.build_queue)

            bg_color = (18, 38, 18) if is_built else (18, 18, 32)
            pygame.draw.rect(surface, bg_color,
                             (pr.x + 6, ry + 2, content_w, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, UI_BORDER,
                             (pr.x + 6, ry + 2, content_w, row_h - 4), 1, border_radius=4)

            # Name + level badge
            name_color = GREEN if is_built else (UI_TEXT if p.colonized else GRAY)
            nt = f.render(bname, True, name_color)
            surface.blit(nt, (pr.x + 12, ry + 4))
            if is_built:
                lvl_color = GOLD if b.level >= LEVEL_MAX else CYAN
                lt = _font(10).render(f"Niv.{b.level}", True, lvl_color)
                surface.blit(lt, (pr.x + 12 + nt.get_width() + 6, ry + 6))

            # Cost line
            if is_built and b.level < LEVEL_MAX:
                cost_dict = b.upgrade_cost()
                cost_str = "  ".join(f"{amt}{r[:3]}" for r, amt in cost_dict.items())
                label = f"Upg: {cost_str}"
            else:
                cost_str = "  ".join(f"{amt}{r[:3]}" for r, amt in defn["cost"].items())
                label = f"Cout: {cost_str}"
            ct = sf.render(label, True, GRAY)
            surface.blit(ct, (pr.x + 12, ry + 20))

            # Production / storage line
            produces = b.produces if is_built else defn.get("produces", {})
            prod_color = GREEN if is_built else (60, 130, 70)
            if produces:
                prod_str = "+" + "  +".join(f"{v:.1f}/s {k[:3]}" for k, v in produces.items())
                surface.blit(sf.render(prod_str, True, prod_color), (pr.x + 12, ry + 32))
            elif defn.get("category") == "storage":
                lvl = b.level if is_built else 0
                bonus = (lvl or 1) * STORAGE_PER_SILO_LEVEL
                if is_built:
                    cap_total = STORAGE_BASE + lvl * STORAGE_PER_SILO_LEVEL
                    storage_str = f"Stockage: {cap_total}/res  (+{bonus})"
                else:
                    storage_str = f"+{STORAGE_PER_SILO_LEVEL}/res par niveau"
                surface.blit(sf.render(storage_str, True, CYAN if is_built else (40, 100, 130)),
                             (pr.x + 12, ry + 32))

            # Right-side button / status
            btn_x = pr.x + 6 + content_w - 78
            if p.colonized:
                if not is_built and not in_build_queue:
                    can, _ = p.can_build(bname)
                    btn = Button((btn_x, ry + 6, 74, 18), "Construire",
                                 enabled=can, tooltip=f"build:{bname}")
                    btn.handle_mouse(mouse_pos); btn.draw(surface)
                    self._buttons.append(btn)
                    t = _font(9).render(_fmt_time(defn["time"]), True, (80, 100, 130))
                    surface.blit(t, (btn_x + (74 - t.get_width()) // 2, ry + 27))
                elif in_build_queue:
                    surface.blit(sf.render("En constr.", True, ORANGE), (btn_x + 2, ry + 10))
                elif is_built and b.level < LEVEL_MAX and not in_upgrade_queue:
                    can, _ = p.can_upgrade(bname)
                    btn = Button((btn_x, ry + 6, 74, 18), f"Upg.Niv.{b.level+1}",
                                 enabled=can, tooltip=f"upgrade:{bname}")
                    btn.handle_mouse(mouse_pos); btn.draw(surface)
                    self._buttons.append(btn)
                    t = _font(9).render(_fmt_time(b.upgrade_time()), True, (80, 100, 130))
                    surface.blit(t, (btn_x + (74 - t.get_width()) // 2, ry + 27))
                elif in_upgrade_queue:
                    surface.blit(sf.render("Upg. cours", True, ORANGE), (btn_x + 2, ry + 10))
                elif is_built and b.level >= LEVEL_MAX:
                    surface.blit(sf.render("MAX", True, GOLD), (btn_x + 24, ry + 10))

            ry += row_h

        # ── Scrollbar ────────────────────────────────────────────
        if total_h > visible_h:
            sb_x = pr.x + pr.w - 6 - SB_W
            sb_track_h = max(0, visible_h)
            pygame.draw.rect(surface, (20, 25, 45),
                             (sb_x, y, SB_W, sb_track_h), border_radius=3)
            handle_h = max(18, int(sb_track_h * visible_h / max(total_h, 1)))
            handle_y = y + int((sb_track_h - handle_h) * scroll_offset / max(total_h - visible_h, 1))
            pygame.draw.rect(surface, (70, 110, 180),
                             (sb_x, handle_y, SB_W, handle_h), border_radius=3)
        elif total_h > 0:
            # All items visible — subtle full bar
            sb_x = pr.x + pr.w - 6 - SB_W
            pygame.draw.rect(surface, (25, 32, 55),
                             (sb_x, y, SB_W, max(0, visible_h)), border_radius=3)

    def _draw_ships_tab(self, surface, pr, y, p):
        f = _font(12)
        sf = _font(10)
        if not p.colonized:
            surface.blit(f.render("Colonisez la planète d'abord", True, GRAY), (pr.x + 20, y + 10))
            return
        if not p.has_shipyard:
            surface.blit(f.render("Construisez un Chantier Naval d'abord", True, GRAY), (pr.x + 20, y + 10))
            return

        sy_level = p.shipyard_level
        sy = p.get_building("Shipyard")
        factor = sy.ship_time_factor() if sy else 1.0

        # Shipyard level header
        lf = _font(11)
        lc = GOLD if sy_level >= LEVEL_MAX else CYAN
        lt = lf.render(f"Chantier Naval  Niv.{sy_level}  |  Temps construction: -{int((1-factor)*100)}%", True, lc)
        surface.blit(lt, (pr.x + 10, y + 2))
        y += 16

        row_h = 52
        ry = y + 2
        mouse_pos = pygame.mouse.get_pos()
        for stype, defn in SHIP_DEFS.items():
            req_lvl = defn.get("shipyard_level", 1)
            unlocked = sy_level >= req_lvl

            bg_color = (20, 28, 42) if unlocked else (18, 18, 26)
            pygame.draw.rect(surface, bg_color, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, UI_BORDER, (pr.x + 6, ry + 2, pr.w - 12, row_h - 4), 1, border_radius=4)

            name_color = CYAN if unlocked else (50, 60, 80)
            nt = f.render(stype, True, name_color)
            surface.blit(nt, (pr.x + 12, ry + 5))

            # Lock / level requirement badge
            req_t = sf.render(f"Niv.{req_lvl}", True, GOLD if unlocked else GRAY)
            surface.blit(req_t, (pr.x + 12 + nt.get_width() + 6, ry + 7))

            cost_str = "  ".join(f"{amt}{r[:3]}" for r, amt in defn["cost"].items())
            actual_time = int(defn["time"] * factor)
            cap_str = f"  Cap:{defn['capacity']}" if defn['capacity'] > 0 else ""
            info = f"{cost_str}  |  Vit:{defn['speed']}{cap_str}"
            ct = sf.render(info, True, GRAY if unlocked else (40, 45, 55))
            surface.blit(ct, (pr.x + 12, ry + 22))

            missions_str = " / ".join(defn["missions"])
            mt = sf.render(f"Missions: {missions_str}", True, UI_TEXT if unlocked else (40, 45, 55))
            surface.blit(mt, (pr.x + 12, ry + 36))

            if unlocked:
                can, _ = p.can_build_ship(stype)
                btn = Button((pr.x + pr.w - 82, ry + 15, 72, 22),
                             "Construire", enabled=can, tooltip=f"ship:{stype}")
                btn.handle_mouse(mouse_pos); btn.draw(surface)
                self._buttons.append(btn)
                t = _font(9).render(_fmt_time(actual_time), True, (80, 100, 130))
                surface.blit(t, (pr.x + pr.w - 82 + (72 - t.get_width()) // 2, ry + 39))
            else:
                lock_t = sf.render(f"[Chantier Niv.{req_lvl}]", True, (55, 60, 75))
                surface.blit(lock_t, (pr.x + pr.w - 100, ry + 20))

            ry += row_h

    def _draw_fleet(self, surface, pr, y, p):
        f = _font(12)
        sf = _font(10)
        docked = p.ships
        if not docked:
            t = f.render("No ships docked here", True, GRAY)
            surface.blit(t, (pr.x + 20, y + 10))
            return

        row_h = 70
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
                "idle": GRAY, "travel": CYAN, "discovering": GOLD,
                "mining": ORANGE, "returning": GREEN, "exploring": CYAN
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
            elif ship.state in ("travel", "discovering", "mining"):
                btn = Button((pr.x + pr.w - 90, ry + 16, 80, 20),
                             "Annuler", tooltip=f"cancel_mission:{ship.id}")
                btn.handle_mouse(pygame.mouse.get_pos())
                btn.draw(surface)
                self._buttons.append(btn)

            if ship.type == "Miner":
                rbtn = Button((pr.x + pr.w - 170, ry + 37, 76, 15),
                              "Repeat", active=ship.repeat,
                              tooltip=f"toggle_repeat:{ship.id}")
                rbtn.handle_mouse(pygame.mouse.get_pos())
                rbtn.draw(surface)
                self._buttons.append(rbtn)

            cargo_total = sum(ship.cargo.values())
            if cargo_total > 0:
                cargo_str = "  ".join(f"{int(v)} {r[:RESOURCE_MAX_CHAR]}" for r, v in ship.cargo.items() if v > 0)
                ct = sf.render(f"Cargo: {cargo_str}", True, GOLD)
                surface.blit(ct, (pr.x + 12, ry + 36))

            eta_data = _mission_eta(ship)
            if eta_data:
                rem, total = eta_data
                progress = max(0.0, min(1.0, 1.0 - rem / total))
                state_color = {"travel": CYAN, "discovering": GOLD,
                               "mining": ORANGE, "returning": GREEN}.get(ship.state, CYAN)
                # ETA text
                eta_t = _font(9).render(f"ETA: {_fmt_time(rem)}", True, state_color)
                surface.blit(eta_t, (pr.x + 12, ry + 52))
                # Compact progress bar
                bar_x, bar_y, bar_w, bar_h = pr.x + 12, ry + 63, pr.w - 30, 4
                pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
                fw = int(bar_w * progress)
                if fw > 0:
                    pygame.draw.rect(surface, state_color, (bar_x, bar_y, fw, bar_h), border_radius=2)
                pygame.draw.rect(surface, (40, 55, 80), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

            ry += row_h

    # ── Queue section (bottom of panel) ──────────────────────────
    def _draw_queue_section(self, surface, pr, y, p):
        self._draw_single_queue(surface, pr, y,
                                p.build_queue, "BUILD QUEUE", ORANGE, is_ship=False)
        self._draw_single_queue(surface, pr, y + 94 + 6,
                                p.ship_queue, "SHIP QUEUE", CYAN, is_ship=True)

    def _draw_single_queue(self, surface, pr, y, queue, label, color, is_ship):
        from constants import QUEUE_MAX
        BLOCK_H = 94

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
        if is_ship:
            name = entry["ship_type"]
        elif entry.get("upgrade"):
            name = f"Upgrade {entry['name']} -> Niv.{entry['to_level']}"
        else:
            name = entry["name"]
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
                if is_ship:
                    chips.append(e["ship_type"])
                elif e.get("upgrade"):
                    chips.append(f"Upg.{e['name'].split()[0]}->Niv.{e['to_level']}")
                else:
                    chips.append(e["name"])
            remainder = len(queue) - 1 - len(chips)
            line = "  ›  ".join(chips)
            if remainder > 0:
                line += f"  +{remainder} more"
            qt = qf.render(line, True, (95, 110, 140))
            surface.blit(qt, (pr.x + 10, y + 48))

        # ── Cancel buttons ────────────────────────────────────────
        tag_one = "cancel_ship_one" if is_ship else "cancel_build_one"
        tag_all = "cancel_ship_all" if is_ship else "cancel_build_all"
        mouse_pos = pygame.mouse.get_pos()
        btn_y = y + 72
        btn_one = Button((pr.x + 10,      btn_y, 100, 16), "Annuler",
                         enabled=len(queue) > 0, tooltip=tag_one)
        btn_all = Button((pr.x + 116,     btn_y, 100, 16), "Annuler tout",
                         enabled=len(queue) > 0, tooltip=tag_all)
        for btn in (btn_one, btn_all):
            btn.handle_mouse(mouse_pos)
            btn.draw(surface)
            self._buttons.append(btn)


# ══════════════════════════════════════════════════════════════════
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
        if s.state in (MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE) or s.type == "Miner":
            h += 26       # cancel + repeat row

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

        h += 8   # separator before stats
        h += 13  # stats line
        h += 8   # bottom pad
        return h

    @property
    def panel_rect(self):
        h = getattr(self, '_panel_h', self.PANEL_H)
        return pygame.Rect(10, int(SCREEN_H) - h - 36, self.PANEL_W, h)

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
        y += 20

        sub_f = _font(11)
        base_t = sub_f.render(f"Base : {s.home.name}", True, GRAY)
        surface.blit(base_t, (pr.x + 12, y))
        y += 16

        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8

        # ── Mission status ────────────────────────────────────────
        from ship import MISSION_IDLE, MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE, MISSION_RETURN
        STATE_LABELS = {
            MISSION_IDLE:     "En attente",
            MISSION_TRAVEL:   "En transit",
            MISSION_DISCOVER: "En découverte",
            MISSION_MINE:     "En extraction",
            MISSION_RETURN:   "Retour",
        }
        STATE_COLORS = {
            MISSION_IDLE:     GRAY,
            MISSION_TRAVEL:   CYAN,
            MISSION_DISCOVER: GOLD,
            MISSION_MINE:     ORANGE,
            MISSION_RETURN:   GREEN,
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
            dt_t = df.render(f"Découverte  :  {remaining:.0f}s restantes", True, GOLD)
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

        # Cancel + Repeat sur la même ligne
        has_cancel = s.state in (MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE)
        has_repeat = s.type == "Miner"
        if has_cancel or has_repeat:
            if has_cancel:
                cancel_btn = Button((pr.x + pr.w // 2 - 70, y + 2, 140, 20),
                                    "Annuler mission", tooltip="cancel_mission")
                cancel_btn.handle_mouse(pygame.mouse.get_pos())
                cancel_btn.draw(surface)
                self._buttons.append(cancel_btn)
            if has_repeat:
                repeat_btn = Button((pr.x + pr.w - 88, y + 2, 76, 20),
                                    "Repeat", active=s.repeat, tooltip="toggle_repeat")
                repeat_btn.handle_mouse(pygame.mouse.get_pos())
                repeat_btn.draw(surface)
                self._buttons.append(repeat_btn)
            y += 26

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

        # ── Stats ────────────────────────────────────────────────
        pygame.draw.line(surface, (40, 80, 120), (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 8
        stats_str = f"Vitesse : {s.speed} px/s"
        speed_t = _font(10).render(stats_str, True, (80, 95, 120))
        surface.blit(speed_t, (pr.x + 12, y))
