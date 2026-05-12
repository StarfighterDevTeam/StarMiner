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
    one_way_mission = mtype in MISSION_ONE_WAY
    if mtype == "mine":
        mdur = getattr(ship, "_mine_duration", 8.0)
    elif mtype == "explore":
        mdur = getattr(ship, "_discover_duration", 10.0)
    else:
        mdur = 0.0
    t = ship.target_planet
    spd = max(getattr(ship, "_effective_speed", ship.speed), 1)
    d_there  = math.hypot(ship.home.x - t.x, ship.home.y - t.y) / spd
    d_back   = 0.0 if one_way_mission else d_there
    total    = d_there + mdur + d_back
    if ship.state == MISSION_TRAVEL:
        rem = math.hypot(ship.x - t.x, ship.y - t.y) / spd + mdur + d_back
    elif ship.state == MISSION_DISCOVER:
        rem = getattr(ship, "_discover_timer", 0.0)
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
        self._patrol_request = None  # combat ship requesting patrol mode
        self._message = ""
        self._msg_timer = 0.0
        self._build_scroll = 0
        self._ship_scroll  = 0
        self._fleet_scroll = 0
        self._planet_tabs: dict = {}  # planet.id → last active tab
        self._sb_drag = None          # scrollbar drag state
        self._sb_info: dict = {}      # scrollbar geometry per tab (set during draw)

    def open(self, planet):
        self.planet = planet
        self.visible = True
        self._tab = self._planet_tabs.get(planet.id, "buildings")
        self._mission_mode = None
        self._build_scroll = 0
        self._ship_scroll  = 0
        self._fleet_scroll = 0

    def close(self):
        self.visible = False
        self.planet = None
        self._mission_mode = None
        self._sb_drag = None

    @property
    def panel_rect(self):
        top = 50
        return pygame.Rect(int(SCREEN_W) - self.PANEL_W - 10, top,
                           self.PANEL_W, int(SCREEN_H) - top - 10)

    def show_message(self, msg):
        self._message = msg
        self._msg_timer = 3.0

    def switch_tab(self, tab):
        self._tab = tab
        if self.planet:
            self._planet_tabs[self.planet.id] = tab

    def _sb_update_drag(self, mouse_y):
        d = self._sb_drag
        delta = mouse_y - d["start_mouse_y"]
        scroll_range_px = d["track_h"] - d["handle_h"]
        if scroll_range_px > 0:
            new_scroll = d["start_scroll"] + round(delta * d["max_scroll"] / scroll_range_px)
            setattr(self, d["scroll_attr"], max(0, min(new_scroll, d["max_scroll"])))

    def _draw_scrollbar(self, surface, tab_key, scroll_attr,
                        sb_x, track_y, track_h, total_h, visible_h, scroll_offset, max_scroll):
        track_h = max(0, track_h)
        if track_h == 0:
            self._sb_info.pop(tab_key, None)
            return
        if total_h > visible_h:
            pygame.draw.rect(surface, (20, 25, 45), (sb_x, track_y, 7, track_h), border_radius=3)
            handle_h = max(18, int(track_h * visible_h / max(total_h, 1)))
            handle_y = track_y + int((track_h - handle_h) * scroll_offset / max(total_h - visible_h, 1))
            handle_rect = pygame.Rect(sb_x, handle_y, 7, handle_h)
            is_hot = (handle_rect.collidepoint(pygame.mouse.get_pos()) or
                      (self._sb_drag and self._sb_drag.get("scroll_attr") == scroll_attr))
            pygame.draw.rect(surface, (120, 160, 230) if is_hot else (70, 110, 180),
                             handle_rect, border_radius=3)
            self._sb_info[tab_key] = {
                "handle_rect": handle_rect,
                "scroll_attr": scroll_attr,
                "max_scroll": max_scroll,
                "track_h": track_h,
                "handle_h": handle_h,
                "sb_x": sb_x,
                "track_y": track_y,
            }
        else:
            pygame.draw.rect(surface, (25, 32, 55), (sb_x, track_y, 7, track_h), border_radius=3)
            self._sb_info.pop(tab_key, None)

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

        # Scrollbar drag: intercept motion/release before any other handler
        if self._sb_drag:
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._sb_drag = None
                return True
            if event.type == pygame.MOUSEMOTION:
                self._sb_update_drag(my)
                return True

        # Mission mode: next click on a planet selects target
        if self._mission_mode:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.panel_rect.collidepoint(pos):
                    self._mission_mode = None
                    # fall through: let button handlers process the click
                else:
                    return False   # let game handle planet click for mission

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(pos):
                self.close()
                return False
            sb_info = self._sb_info.get(self._tab)
            if sb_info and sb_info["handle_rect"].collidepoint(pos):
                self._sb_drag = {
                    "scroll_attr":   sb_info["scroll_attr"],
                    "start_mouse_y": my,
                    "start_scroll":  getattr(self, sb_info["scroll_attr"]),
                    "max_scroll":    sb_info["max_scroll"],
                    "track_h":       sb_info["track_h"],
                    "handle_h":      sb_info["handle_h"],
                }
                return True
            if sb_info:
                track_rect = pygame.Rect(sb_info["sb_x"], sb_info["track_y"],
                                         7, sb_info["track_h"])
                if track_rect.collidepoint(pos):
                    scroll_range = sb_info["track_h"] - sb_info["handle_h"]
                    if scroll_range > 0:
                        rel = my - sb_info["track_y"] - sb_info["handle_h"] / 2
                        frac = max(0.0, min(1.0, rel / scroll_range))
                        new_val = round(frac * sb_info["max_scroll"])
                        setattr(self, sb_info["scroll_attr"], new_val)
                    return True

        # Tab buttons
        for tb in self._tab_btns:
            if tb.is_clicked(pos, event):
                self._tab = tb.text.lower()
                if self.planet:
                    self._planet_tabs[self.planet.id] = self._tab
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
            elif self._tab == "ships":
                self._ship_scroll = max(0, self._ship_scroll - event.y)
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

        elif tag.startswith("patrol:"):
            sid = int(tag[7:])
            ship = next((s for s in p.ships if s.id == sid), None)
            if ship:
                self._patrol_request = ship
                self.show_message("Cliquez sur la carte pour définir la destination")

        elif tag.startswith(("explore:", "mine:", "pump:", "colonize:", "highway:")):
            mtype, sid = tag.split(":")
            ship = next((s for s in p.ships if s.id == int(sid)), None)
            if ship:
                if self._mission_mode and self._mission_mode == (mtype, ship):
                    self._mission_mode = None
                    self.show_message("Mission annulée")
                else:
                    self._mission_mode = (mtype, ship)
                    verb = {"explore": "explorer", "mine": "miner", "pump": "pomper",
                            "colonize": "coloniser", "highway": "relier en autoroute"}.get(mtype, mtype)
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
        if mtype in ("mine", "pump"):
            if target_planet is ship.home:
                self.show_message("Même planète — choisissez une autre")
                return
            if not target_planet.explored:
                self.show_message(f"Explorez d'abord {target_planet.name}")
                return
        if mtype == "mine":
            from ship import MINE_RESOURCES
            if not any(r in MINE_RESOURCES for r in target_planet.available_resources):
                self.show_message(f"{target_planet.name} n'a pas de ressources solides")
                return
        if mtype == "pump":
            from ship import PUMP_RESOURCES
            if not any(r in PUMP_RESOURCES for r in target_planet.available_resources):
                self.show_message(f"{target_planet.name} n'a pas de ressources fluides")
                return
        if mtype == "colonize":
            if not target_planet.explored:
                self.show_message(f"Explorez d'abord {target_planet.name}")
                return
            if not target_planet.habitable:
                self.show_message(f"{target_planet.name} n'est pas habitable")
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
        elif mtype == "pump":
            ok = ship.send_pump(target_planet)
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
    def draw(self, surface, planets, highways=None, patrol_mode_ship=None):
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
        if p.explored:
            hab_label = "Habitable" if p.habitable else "Non habitable"
            hab_color = GREEN if p.habitable else RED
            ht = _font(10).render(hab_label, True, hab_color)
            surface.blit(ht, (pr.x + pr.w - ht.get_width() - 12, y + 2))
        y += 18


        # ── Resources ────────────────────────────────────────────
        pygame.draw.line(surface, UI_BORDER, (pr.x + 8, y), (pr.x + pr.w - 8, y))
        y += 6
        res_font = _font(11)
        col_w = (pr.w - 20) // 3
        prod = {}
        if p.colonized:
            for b in p.buildings:
                for r, rate in b.produces.items():
                    prod[r] = prod.get(r, 0) + rate
        res_items = [(r, v) for r, v in p.resources.items() if v > 0 or r in p.available_resources]
        for i, (res, val) in enumerate(res_items):
            col = i % 3
            row = i // 3
            rx = pr.x + 10 + col * col_w
            ry = y + row * 16
            color = RESOURCE_COLORS.get(res, WHITE)
            if p.colonized:
                cap = p.storage_cap_for(res)
                near_cap = val >= cap * 0.95
                rate = prod.get(res, 0)
                prod_str = f" (+{rate:.0f}/s)" if rate > 0 else ""
                label = f"{res[:3].upper()}:{int(val)}/{int(cap)}{prod_str}"
                t = res_font.render(label, True, RED if near_cap else color)
            else:
                label = res[:RESOURCE_MAX_CHAR].upper()
                t = res_font.render(label, True, color)
            surface.blit(t, (rx, ry))
        rows = (len(res_items) + 2) // 3
        y += max(rows * 16 + 4, 20)

        if p.colonized:
            # ── Tabs ─────────────────────────────────────────────────
            tabs = ["Buildings", "Ships", "Fleet"]
            tab_w = pr.w // len(tabs)
            for i, tab in enumerate(tabs):
                active = self._tab == tab.lower()
                color = UI_BTN_HOV if active else UI_BTN
                tr = pygame.Rect(pr.x + i * tab_w, y, tab_w, 24)
                pygame.draw.rect(surface, color, tr)
                pygame.draw.rect(surface, UI_BORDER, tr, 1)
                tf = _font(11)
                tt = tf.render(f"{tab} (F{i+1})", True, WHITE)
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
                self._draw_fleet(surface, pr, content_y, p, patrol_mode_ship)

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
            if p.explored == False:
                surface.blit(hf.render("Cette planète n'est pas explorée.", True, hc), (pr.x + 12, y + 10))
                surface.blit(hf.render("Explorez-la avec une Probe.", True, hc), (pr.x + 12, y + 26))
            elif p.habitable and p.colonized == False:
                surface.blit(hf.render("Cette planète n'est pas colonisée.", True, hc), (pr.x + 12, y + 10))
                surface.blit(hf.render("Envoyez un Colonisateur depuis votre flotte", True, hc), (pr.x + 12, y + 26))
                surface.blit(hf.render("pour prendre possession de cette planète.", True, hc), (pr.x + 12, y + 42))
            elif p.habitable == False:
                surface.blit(hf.render("Cette planète n'est pas habitable", True, hc), (pr.x + 12, y + 10))
                surface.blit(hf.render("mais elle peut être minée.", True, hc), (pr.x + 12, y + 26))
                surface.blit(hf.render("Envoyer un Miner pour extraire ses ressources.", True, hc), (pr.x + 12, y + 42))
            
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

    def _mission_ok(self, mtype, ship, planet, highways=None):
        from ship import MINE_RESOURCES, PUMP_RESOURCES
        has_highway = (highways is not None and
                       frozenset({ship.home.id, planet.id}) in highways)
        if planet is ship.home:
            return False
        if mtype == "explore":
            if planet.explored: return False
        elif mtype == "mine":
            if not planet.explored: return False
            if not any(r in MINE_RESOURCES for r in planet.available_resources): return False
        elif mtype == "pump":
            if not planet.explored: return False
            if not any(r in PUMP_RESOURCES for r in planet.available_resources): return False
        elif mtype == "colonize":
            if not (planet.explored and planet.habitable and not planet.colonized): return False
        elif mtype == "highway":
            if not planet.colonized or has_highway: return False
        return ship.has_fuel_for(mtype, planet)

    def draw_mission_hover(self, surface, planet, camera, highways=None, patrol_ship=None):
        if self._mission_mode:
            mtype, ship = self._mission_mode
        elif patrol_ship:
            mtype, ship = "patrol", patrol_ship
        else:
            return

        dist_to   = math.hypot(ship.x - planet.x, ship.y - planet.y)
        dist_back = math.hypot(planet.x - ship.home.x, planet.y - ship.home.y)

        # Highway bonus applies if a link already exists (not relevant for patrol)
        has_highway = (mtype != "patrol" and highways is not None and
                       frozenset({ship.home.id, planet.id}) in highways)
        speed_mult = 1.5 if has_highway else 1.0
        travel_to   = dist_to   / max(ship.speed * speed_mult, 1)
        travel_back = dist_back / max(ship.speed * speed_mult, 1)

        if mtype == "explore":
            mission_dur = getattr(ship, "_discover_duration", 10.0)
        elif mtype in ("mine", "pump"):
            mission_dur = getattr(ship, "_mine_duration", 8.0)
        else:
            mission_dur = 0.0

        from ship import MINE_RESOURCES, PUMP_RESOURCES
        one_way = mtype in MISSION_ONE_WAY or mtype == "patrol"
        total = travel_to + mission_dur + (0 if one_way else travel_back)

        lines = []
        # Check for blocking conditions first (show error instead of ETA)
        error = None
        if planet is ship.home and not (mtype == "patrol" and not ship.is_docked):
            error = ("Même planète", RED)
        elif mtype == "explore" and planet.explored:
            error = (f"{planet.name} déjà explorée", ORANGE)
        elif mtype == "mine" and not planet.explored:
            error = ("Planète non explorée", RED)
        elif mtype == "mine" and not any(r in MINE_RESOURCES for r in planet.available_resources):
            error = ("Pas de ressources solides (iron/silver/gold)", ORANGE)
        elif mtype == "pump" and not planet.explored:
            error = ("Planète non explorée", RED)
        elif mtype == "pump" and not any(r in PUMP_RESOURCES for r in planet.available_resources):
            error = ("Pas de ressources fluides (oil/deuterium)", ORANGE)

        elif mtype == "colonize" and not planet.explored:
            error = ("Planète non explorée", RED)
        elif mtype == "colonize" and not planet.habitable:
            error = ("Planète non habitable", RED)
        elif mtype == "colonize" and planet.colonized:
            error = ("Déjà colonisée", ORANGE)
        elif mtype == "highway" and not planet.colonized:
            error = ("Planète non colonisée", RED)
        elif mtype == "highway" and has_highway:
            error = ("Autoroute déjà existante", ORANGE)

        # Fuel check — patrol draws from current position and may reuse existing fuel
        if mtype == "patrol":
            fuel = ship.fuel_cost_patrol(planet.x, planet.y)
            if ship.fuel_capacity is not None:
                fuel_return = ship._fuel_to_nearest_colony(planet.x, planet.y, [])
                fuel_ok = ship.fuel_remaining >= fuel + fuel_return
                fuel_line = (f"Réservoir : {fuel:.0f} requis / {ship.fuel_remaining:.0f} {ship.fuel_type}",
                             GREEN if fuel_ok else RED)
            else:
                fuel_avail = ship.home.resources.get(ship.fuel_type, 0) + ship.fuel_remaining
                fuel_ok = fuel_avail >= fuel
                fuel_line = (f"Carburant : {fuel:.0f} {ship.fuel_type}", GREEN if fuel_ok else RED)
        else:
            fuel = ship.fuel_cost(mtype, planet)
            fuel_avail = ship.home.resources.get(ship.fuel_type, 0)
            fuel_ok = fuel_avail >= fuel
            fuel_line = (f"Carburant : {fuel:.0f} {ship.fuel_type}", GREEN if fuel_ok else RED)
        if error is None and not fuel_ok:
            error = (f"{ship.fuel_type.capitalize()} insuffisant"
                     f" ({fuel:.0f} requis)", RED)

        # Habitability hint appended to valid targets when relevant
        hab_hint = None
        if error is None and planet.explored and not planet.habitable and mtype not in ("colonize", "patrol"):
            hab_hint = ("Non colonisable (inhabitable)", (100, 80, 60))

        if error:
            lines.append(error)
        elif mtype == "highway":
            lines.append((f"Aller   : {_fmt_time(travel_to)}", UI_TEXT))
            lines.append((f"Total   : {_fmt_time(total)}", CYAN))
            lines.append(("→ +50% vitesse sur ce trajet", GOLD))
            lines.append(fuel_line)
        else:
            if has_highway:
                lines.append(("★ Autoroute active (+50%)", GOLD))
            lines.append((f"Aller   : {_fmt_time(travel_to)}", UI_TEXT))
            if mtype == "explore":
                lines.append((f"Découv. : {_fmt_time(mission_dur)}", GOLD))
            elif mtype == "mine":
                lines.append((f"Extract.: {_fmt_time(mission_dur)}", ORANGE))
            elif mtype == "pump":
                lines.append((f"Pompage : {_fmt_time(mission_dur)}", CYAN))
            if not one_way:
                lines.append((f"Retour  : {_fmt_time(travel_back)}", UI_TEXT))
            lines.append((f"Total   : {_fmt_time(total)}", CYAN))
            lines.append(fuel_line)
            if hab_hint:
                lines.append(hab_hint)

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

    def draw_patrol_hover(self, surface, wx, wy, camera, ship, planets=None):
        dist = math.hypot(ship.x - wx, ship.y - wy)
        travel_to = dist / max(ship.speed, 1)
        fuel_leg = ship.fuel_cost_patrol(wx, wy)

        if ship.fuel_capacity is not None:
            fuel_return = ship._fuel_to_nearest_colony(wx, wy, planets or [])
            fuel_needed = fuel_leg + fuel_return
            fuel_ok = ship.fuel_remaining >= fuel_needed
            fuel_label = (f"Réservoir : {fuel_needed:.0f} requis / "
                          f"{ship.fuel_remaining:.0f} {ship.fuel_type}")
        else:
            fuel_avail = ship.home.resources.get(ship.fuel_type, 0) + ship.fuel_remaining
            fuel_ok = fuel_avail >= fuel_leg
            fuel_label = f"Carburant : {fuel_leg:.0f} {ship.fuel_type}"

        lines = []
        if not fuel_ok:
            lines.append((f"{ship.fuel_type.capitalize()} insuffisant", RED))
        else:
            lines.append((f"Aller   : {_fmt_time(travel_to)}", UI_TEXT))
            lines.append((f"Total   : {_fmt_time(travel_to)}", CYAN))
        lines.append((fuel_label, GREEN if fuel_ok else RED))

        f = _font(11)
        line_h = 15
        pad = 8
        w = max(f.size(txt)[0] for txt, _ in lines) + pad * 2
        h = len(lines) * line_h + pad

        sx, sy = camera.world_to_screen(wx, wy)
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

        self._draw_scrollbar(surface, "buildings", "_build_scroll",
                             pr.x + pr.w - 6 - SB_W, y, visible_h,
                             total_h, visible_h, scroll_offset, max_scroll)

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

        # Fixed header (does not scroll)
        lf = _font(11)
        lc = GOLD if sy_level >= LEVEL_MAX else CYAN
        lt = lf.render(f"Chantier Naval  Niv.{sy_level}  |  Temps construction: -{int((1-factor)*100)}%", True, lc)
        surface.blit(lt, (pr.x + 10, y + 2))
        y += 16  # scrollable area starts here

        row_h = 52
        SB_W = 7
        content_w = pr.w - 12 - SB_W - 2
        right = pr.x + 6 + content_w
        all_types = list(SHIP_DEFS.items())
        total_h = len(all_types) * row_h
        visible_h = pr.y + pr.h - 202 - 14 - y

        max_scroll = max(0, (total_h - visible_h) // row_h + 1)
        self._ship_scroll = max(0, min(self._ship_scroll, max_scroll))
        scroll_offset = self._ship_scroll * row_h

        ry = y + 2 - scroll_offset
        mouse_pos = pygame.mouse.get_pos()

        for stype, defn in all_types:
            if ry + row_h < y or ry > y + visible_h:
                ry += row_h
                continue

            req_lvl = defn.get("shipyard_level", 1)
            unlocked = sy_level >= req_lvl

            bg_color = (20, 28, 42) if unlocked else (18, 18, 26)
            pygame.draw.rect(surface, bg_color,  (pr.x + 6, ry + 2, content_w, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, UI_BORDER, (pr.x + 6, ry + 2, content_w, row_h - 4), 1, border_radius=4)

            name_color = CYAN if unlocked else (50, 60, 80)
            nt = f.render(stype, True, name_color)
            surface.blit(nt, (pr.x + 12, ry + 5))

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
                btn = Button((right - 76, ry + 15, 72, 22),
                             "Construire", enabled=can, tooltip=f"ship:{stype}")
                btn.handle_mouse(mouse_pos); btn.draw(surface)
                self._buttons.append(btn)
                t = _font(9).render(_fmt_time(actual_time), True, (80, 100, 130))
                surface.blit(t, (right - 76 + (72 - t.get_width()) // 2, ry + 39))
            else:
                lock_t = sf.render(f"[Chantier Niv.{req_lvl}]", True, (55, 60, 75))
                surface.blit(lock_t, (right - lock_t.get_width() - 4, ry + 20))

            ry += row_h

        self._draw_scrollbar(surface, "ships", "_ship_scroll",
                             pr.x + pr.w - 6 - SB_W, y, visible_h,
                             total_h, visible_h, scroll_offset, max_scroll)

    def _draw_fleet(self, surface, pr, y, p, patrol_mode_ship=None):
        f = _font(12)
        sf = _font(10)
        if not p.ships:
            t = f.render("Aucun vaisseau assigné", True, GRAY)
            surface.blit(t, (pr.x + 20, y + 10))
            return

        row_h = 70
        SB_W = 7
        content_w = pr.w - 12 - SB_W - 2
        right = pr.x + 6 + content_w
        total_h = len(p.ships) * row_h
        visible_h = pr.y + pr.h - 202 - 14 - y

        max_scroll = max(0, (total_h - visible_h) // row_h + 1)
        self._fleet_scroll = max(0, min(self._fleet_scroll, max_scroll))
        scroll_offset = self._fleet_scroll * row_h
        ry = y - scroll_offset + 4

        _MISSION_LABELS = {"explore": "Explorer", "mine": "Extraire", "pump": "Pomper",
                           "colonize": "Coloniser", "patrol": "Patrouille",
                           "highway": "Route"}
        mouse_pos = pygame.mouse.get_pos()

        for ship in p.ships:
            if ry + row_h < y or ry > y + visible_h:
                ry += row_h
                continue

            here = ship.is_docked
            bg_color  = (14, 30, 18) if here else (20, 25, 40)
            brd_color = (50, 160, 80) if here else UI_BORDER
            pygame.draw.rect(surface, bg_color,  (pr.x + 6, ry + 2, content_w, row_h - 4), border_radius=4)
            pygame.draw.rect(surface, brd_color, (pr.x + 6, ry + 2, content_w, row_h - 4), 1, border_radius=4)

            # Line 1 – name + dock badge
            nt = f.render(f"{ship.type} #{ship.id}", True, CYAN)
            surface.blit(nt, (pr.x + 12, ry + 6))
            if here:
                badge = sf.render("ANCRÉ", True, (80, 220, 120))
                surface.blit(badge, (right - badge.get_width() - 4, ry + 8))

            # Line 2 – status
            if here:
                st_txt = "Idle – ancré"
                st_col = (80, 220, 120)
            elif ship.state == "idle":
                st_txt = "Idle – hors base"
                st_col = ORANGE
            elif ship.state == "patrol":
                dp = getattr(ship, "_dock_planet", None)
                st_txt = f"Patrouille → {dp.name}" if dp and dp is not p else "Patrouille"
                st_col = ORANGE
            elif ship.state == "combat":
                st_txt = "Combat"
                st_col = RED
            else:
                st_txt, st_col = {
                    "travel":     ("En transit",   CYAN),
                    "discovering":("Découverte",   GOLD),
                    "mining":     ("Extraction",   ORANGE),
                    "returning":  ("Retour base",  GREEN),
                    "exploring":  ("Exploration",  CYAN),
                }.get(ship.state, (ship.state, WHITE))
            surface.blit(sf.render(st_txt, True, st_col), (pr.x + 12, ry + 22))

            if ship.state == "idle":
                missions = SHIP_DEFS[ship.type]["missions"]
                n = len(missions)
                bx = right - n * 76 - (n - 1) * 6 - 4
                for mi, mtype in enumerate(missions):
                    is_active = (patrol_mode_ship is ship) if mtype == "patrol" else (self._mission_mode == (mtype, ship))
                    enabled = not (mtype == "patrol"
                                   and ship.fuel_capacity is not None
                                   and ship.fuel_remaining < 1.0)
                    btn = Button((bx + mi * 82, ry + 10, 76, 20),
                                 _MISSION_LABELS.get(mtype, mtype.capitalize()),
                                 tooltip=f"{mtype}:{ship.id}", active=is_active, enabled=enabled)
                    btn.handle_mouse(mouse_pos); btn.draw(surface)
                    self._buttons.append(btn)
            elif ship.state in ("patrol", "combat"):
                patrol_btn = Button((right - 164, ry + 10, 76, 20),
                                    "Patrouille", tooltip=f"patrol:{ship.id}",
                                    active=patrol_mode_ship is ship)
                patrol_btn.handle_mouse(mouse_pos); patrol_btn.draw(surface)
                self._buttons.append(patrol_btn)
                btn = Button((right - 84, ry + 10, 80, 20),
                             "Annuler", tooltip=f"cancel_mission:{ship.id}")
                btn.handle_mouse(mouse_pos); btn.draw(surface)
                self._buttons.append(btn)
            elif ship.state in ("travel", "discovering", "mining"):
                _one_way = getattr(ship, "_mission_type", None) in MISSION_ONE_WAY
                if _one_way:
                    if ship.state == "travel" and ship.target_planet:
                        _d_home   = math.hypot(ship.x - ship.home.x, ship.y - ship.home.y)
                        _d_target = math.hypot(ship.x - ship.target_planet.x, ship.y - ship.target_planet.y)
                        _can_cancel = _d_home < _d_target
                    else:
                        _can_cancel = False  # already at destination, past PNR (Point of No Return)
                else:
                    _can_cancel = True
                btn = Button((right - 84, ry + 10, 80, 20),
                             "Annuler", tooltip=f"cancel_mission:{ship.id}", enabled=_can_cancel)
                btn.handle_mouse(mouse_pos); btn.draw(surface)
                self._buttons.append(btn)

            if ship.type == "Miner":
                rbtn = Button((right - 164, ry + 37, 76, 15),
                              "Repeat", active=ship.repeat, tooltip=f"toggle_repeat:{ship.id}")
                rbtn.handle_mouse(mouse_pos); rbtn.draw(surface)
                self._buttons.append(rbtn)

            cargo_total = sum(ship.cargo.values())
            if cargo_total > 0:
                cargo_str = "  ".join(f"{int(v)} {r[:RESOURCE_MAX_CHAR]}" for r, v in ship.cargo.items() if v > 0)
                surface.blit(sf.render(f"Cargo: {cargo_str}", True, GOLD), (pr.x + 12, ry + 36))

            if ship.fuel_capacity is not None:
                ratio = max(0.0, min(1.0, ship.fuel_remaining / ship.fuel_capacity))
                fc = RED if ratio < 0.1 else (ORANGE if ratio < 0.25 else CYAN)
                tank_lbl = f"Réservoir : {ship.fuel_remaining:.0f} / {ship.fuel_capacity} {ship.fuel_type}"
                surface.blit(_font(9).render(tank_lbl, True, fc), (pr.x + 12, ry + 36))
                bar_x, bar_y = pr.x + 12, ry + 47
                bar_w, bar_h = content_w - 6, 4
                pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
                fw = int(bar_w * ratio)
                if fw > 0:
                    pygame.draw.rect(surface, fc, (bar_x, bar_y, fw, bar_h), border_radius=2)
                pygame.draw.rect(surface, (40, 55, 80), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

            eta_data = _mission_eta(ship)
            if eta_data:
                rem, total = eta_data
                progress = max(0.0, min(1.0, 1.0 - rem / total))
                state_color = {"travel": CYAN, "discovering": GOLD,
                               "mining": ORANGE, "returning": GREEN}.get(ship.state, CYAN)
                surface.blit(_font(9).render(f"ETA: {_fmt_time(rem)}", True, state_color),
                             (pr.x + 12, ry + 52))
                bar_x, bar_y, bar_w, bar_h = pr.x + 12, ry + 63, content_w - 6, 4
                pygame.draw.rect(surface, (22, 28, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
                fw = int(bar_w * progress)
                if fw > 0:
                    pygame.draw.rect(surface, state_color, (bar_x, bar_y, fw, bar_h), border_radius=2)
                pygame.draw.rect(surface, (40, 55, 80), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

            ry += row_h

        self._draw_scrollbar(surface, "fleet", "_fleet_scroll",
                             pr.x + pr.w - 6 - SB_W, y - 4, visible_h,
                             total_h, visible_h, scroll_offset, max_scroll)

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
        h += 26  # cancel/repeat row (always reserved)
        if s.fire_range > 0:
            h += 26  # patrol row (always reserved for combat ships)

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
        return pygame.Rect(10, int(SCREEN_H) - h - 56, self.PANEL_W, h)

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
            MISSION_DISCOVER: "En découverte",
            MISSION_MINE:     "En extraction",
            MISSION_RETURN:   "Retour",
            MISSION_PATROL:   "En patrouille",
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

        # Cancel + Repeat row (space always reserved)
        has_cancel = s.state in (MISSION_TRAVEL, MISSION_DISCOVER, MISSION_MINE)
        has_repeat = s.type in ("Miner", "Tanker")
        if has_cancel:
            _one_way = getattr(s, "_mission_type", None) in MISSION_ONE_WAY
            if _one_way:
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

        # Patrol row for combat ships (space always reserved)
        if s.fire_range > 0:
            has_patrol_cancel = s.state in (MISSION_PATROL, MISSION_COMBAT)
            bx = pr.x + 10# if has_patrol_cancel else pr.x + pr.w // 2 - 55
            bw = 140# if has_patrol_cancel else 110
            patrol_btn = Button((bx, y + 2, bw, 20), "Patrouille", tooltip="patrol_request")
            patrol_btn.handle_mouse(pygame.mouse.get_pos())
            patrol_btn.draw(surface)
            self._buttons.append(patrol_btn)
            if has_patrol_cancel:
                cancel_btn = Button((pr.x + pr.w - 150, y + 2, 140, 20),
                                    "Annuler patrouille", tooltip="cancel_mission")
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

            # HP text + combat stats
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

        # Fuel tank gauge for combat ships (dedicated tank)
        if s.fuel_capacity is not None:
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
        elif s.fuel_remaining > 0:
            fav = s.home.resources.get(s.fuel_type, 0)
            low = s.fuel_remaining < 10 or s.fuel_remaining < fav * 0.15
            fc = ORANGE if low else CYAN
            moving = s.state in (MISSION_TRAVEL, MISSION_RETURN, MISSION_PATROL)
            _mtype = getattr(s, "_mission_type", None)
            _past_pnr = (
                _mtype in MISSION_ONE_WAY
                and s.state == MISSION_TRAVEL
                and s.target_planet is not None
                and math.hypot(s.x - s.home.x, s.y - s.home.y)
                    >= math.hypot(s.x - s.target_planet.x, s.y - s.target_planet.y)
            )
            label = ("En transit (Point of No Return reached)" if _past_pnr
                     else "En transit" if moving
                     else "Réservé    ")
            rem_t = _font(10).render(f"{label} : {s.fuel_remaining:.0f} {s.fuel_type}", True, fc)
            surface.blit(rem_t, (pr.x + 12, y))
