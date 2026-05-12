import pygame
import math
import os
from constants import *

_ship_sheets = {}

def _load_sprite_frames(path, num_frames, size):
    key = (path, num_frames, size)
    if key not in _ship_sheets:
        try:
            sheet = pygame.image.load(path).convert_alpha()
            frame_w = sheet.get_width() // num_frames
            frame_h = sheet.get_height()
            frames = []
            for i in range(num_frames):
                sub = sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h))
                sub = pygame.transform.smoothscale(sub, (size, size))
                frames.append(sub)
        except Exception:
            fallback = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.polygon(fallback, (180, 200, 255),
                                [(size//2, 0), (size, size), (size//2, size*3//4), (0, size)])
            frames = [fallback] * max(num_frames, 1)
        _ship_sheets[key] = frames
    return _ship_sheets[key]

SHIP_IMG_PATHS = {
    "Probe": "assets/2D/Probe1.png",
    "Miner": "assets/2D/Miner1.png",
}
SHIP_SPRITE_FRAMES = {
    "Probe": 3,
    "Miner": 3,
}
SHIP_DRAW_SIZE = 28
_ANIM_FRAME_DUR = 1 / 8   # 8 fps animation

MINE_RESOURCES = frozenset({"iron", "silver", "gold"})
PUMP_RESOURCES = frozenset({"oil", "deuterium"})

MISSION_IDLE     = "idle"
MISSION_TRAVEL   = "travel"
MISSION_EXPLORE  = "exploring"
MISSION_DISCOVER = "discovering"
MISSION_MINE     = "mining"
MISSION_RETURN   = "returning"
MISSION_PATROL   = "patrol"
MISSION_COMBAT   = "combat"


class Ship:
    _id_counters: dict = {}  # per-faction counters

    def __init__(self, ship_type, home_planet, faction="player"):
        self.faction = faction
        Ship._id_counters[faction] = Ship._id_counters.get(faction, 0) + 1
        self.id = Ship._id_counters[faction]
        self.type = ship_type
        self.home = home_planet
        defn = SHIP_DEFS[ship_type]
        self.speed = defn["speed"]
        self.capacity = defn["capacity"]
        self._effective_speed = defn["speed"]  # updated each frame with highway bonus

        self.x = float(home_planet.x)
        self.y = float(home_planet.y)
        self.angle = 0.0

        self.state = MISSION_IDLE
        self.target_planet = None
        self.cargo = {r: 0.0 for r in RESOURCE_NAMES}
        self._mine_timer = 0.0
        self._mine_duration = 8.0
        self._discover_timer = 0.0
        self._discover_duration = 10.0
        self._destroyed = False
        self.repeat = False

        # Faction display
        fdef = FACTION_DEFS.get(faction, FACTION_DEFS["player"])
        self.faction_name = fdef["name"]
        self.faction_relationship = fdef["relationship"]
        self.faction_color = RELATIONSHIP_COLORS[self.faction_relationship]

        # Combat attributes
        self.hp = defn.get("hp", -1)
        self.max_hp = defn.get("hp", -1)
        self.damage = defn.get("damage", 0)
        self.fire_range = defn.get("fire_range", 0)
        self.fire_rate = defn.get("fire_rate", 0)
        self._fire_cooldown = 0.0
        self._target_enemy = None
        self._shoot_flash = None      # (world_tx, world_ty, timer)

        # Patrol attributes
        self._patrol_dest = None      # (wx, wy) destination in world coords
        self._dock_planet = None      # colonized planet to dock at on arrival
        self._pre_combat_dest = None  # patrol dest saved before entering combat

        # Fuel attributes
        self.fuel_type      = defn.get("fuel_type", "oil")
        self.fuel_rate      = defn.get("fuel_rate", 0.005)
        self.fuel_capacity  = defn.get("fuel_capacity", None)  # None = no dedicated tank
        self.fuel_remaining = 0.0

        # Animation
        self._anim_timer = 0.0
        self._anim_frame = 0

    # ── fuel helpers ─────────────────────────────────────────────
    def fuel_cost(self, mtype, target):
        dist = math.hypot(self.home.x - target.x, self.home.y - target.y)
        return dist * self.fuel_rate * (2.0 if mtype in ("mine", "pump") else 1.0)

    def has_fuel_for(self, mtype, target):
        return self.home.resources.get(self.fuel_type, 0) >= self.fuel_cost(mtype, target)

    def fuel_cost_patrol(self, wx, wy):
        return math.hypot(self.x - wx, self.y - wy) * self.fuel_rate

    def _fuel_to_nearest_colony(self, wx, wy, planets):
        """Minimum fuel to reach any colonized planet from world position (wx, wy)."""
        best = float("inf")
        for p in planets:
            if p.colonized:
                cost = math.hypot(wx - p.x, wy - p.y) * self.fuel_rate
                if cost < best:
                    best = cost
        return best if best < float("inf") else 0.0

    def can_patrol_to(self, wx, wy, planets=None):
        """True if this ship can reach (wx,wy) and still return to a colonized planet."""
        fuel_leg = self.fuel_cost_patrol(wx, wy)
        if self.fuel_capacity is not None:
            fuel_return = self._fuel_to_nearest_colony(wx, wy, planets or [])
            return self.fuel_remaining >= fuel_leg + fuel_return
        else:
            available = self.home.resources.get(self.fuel_type, 0) + self.fuel_remaining
            return available >= fuel_leg

    def has_fuel_for_patrol(self, wx, wy):
        """Legacy check used by non-combat ships and enemy AI."""
        available = self.home.resources.get(self.fuel_type, 0) + self.fuel_remaining
        return available >= self.fuel_cost_patrol(wx, wy)

    def _load_fuel(self, amount):
        self.home.resources[self.fuel_type] -= amount
        self.fuel_remaining = amount

    def _refund_fuel(self):
        if self.fuel_remaining > 0:
            self.home.resources[self.fuel_type] = (
                self.home.resources.get(self.fuel_type, 0) + self.fuel_remaining)
        self.fuel_remaining = 0.0

    # ── missions ─────────────────────────────────────────────────
    def send_explore(self, target):
        if self.state != MISSION_IDLE: return False
        fuel = self.fuel_cost("explore", target)
        if self.home.resources.get(self.fuel_type, 0) < fuel: return False
        self._load_fuel(fuel)
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "explore"
        return True

    def send_mine(self, target):
        if self.state != MISSION_IDLE: return False
        if self.type != "Miner": return False
        fuel = self.fuel_cost("mine", target)
        if self.home.resources.get(self.fuel_type, 0) < fuel: return False
        self._load_fuel(fuel)
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "mine"
        return True

    def send_pump(self, target):
        if self.state != MISSION_IDLE: return False
        if self.type != "Tanker": return False
        fuel = self.fuel_cost("pump", target)
        if self.home.resources.get(self.fuel_type, 0) < fuel: return False
        self._load_fuel(fuel)
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "pump"
        return True

    def send_colonize(self, target):
        if self.state != MISSION_IDLE: return False
        if self.type != "Colonizer": return False
        fuel = self.fuel_cost("colonize", target)
        if self.home.resources.get(self.fuel_type, 0) < fuel: return False
        self._load_fuel(fuel)
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "colonize"
        return True

    def send_highway(self, target):
        if self.state != MISSION_IDLE: return False
        if self.type != "Constructor": return False
        fuel = self.fuel_cost("highway", target)
        if self.home.resources.get(self.fuel_type, 0) < fuel: return False
        self._load_fuel(fuel)
        self.target_planet = target
        self.state = MISSION_TRAVEL
        self._mission_type = "highway"
        return True

    def send_patrol(self, wx, wy, dock_planet=None, planets=None):
        if self.state not in (MISSION_IDLE, MISSION_PATROL, MISSION_COMBAT): return False
        fuel_leg = self.fuel_cost_patrol(wx, wy)
        if self.fuel_capacity is not None:
            # Combat ship: validate leg + return-to-nearest-colony budget from tank
            fuel_return = self._fuel_to_nearest_colony(wx, wy, planets) if planets else 0.0
            if self.fuel_remaining < fuel_leg + fuel_return:
                return False
            # No pre-deduction — _move_toward drains the tank continuously during travel
        else:
            # Non-combat / enemy: borrow from home planet as before
            available = self.home.resources.get(self.fuel_type, 0) + self.fuel_remaining
            if available < fuel_leg: return False
            net = fuel_leg - self.fuel_remaining
            self.home.resources[self.fuel_type] = self.home.resources.get(self.fuel_type, 0) - net
            self.fuel_remaining = fuel_leg
        self._patrol_dest = (wx, wy)
        self._dock_planet = dock_planet
        self._pre_combat_dest = None
        self._target_enemy = None
        self.state = MISSION_PATROL
        return True

    def cancel_mission(self):
        if self.state in (MISSION_TRAVEL, MISSION_MINE, MISSION_DISCOVER):
            self.state = MISSION_RETURN
            return True
        if self.state in (MISSION_PATROL, MISSION_COMBAT):
            self._patrol_dest = None
            self._pre_combat_dest = None
            self._target_enemy = None
            self.state = MISSION_IDLE
            return True
        return False

    def _find_enemy(self, all_ships):
        if not all_ships or self.fire_range <= 0:
            return None
        closest = None
        closest_dist = self.fire_range
        for s in all_ships:
            if s is self or s.faction == self.faction or s._destroyed or s.is_docked:
                continue
            dist = math.hypot(s.x - self.x, s.y - self.y)
            if dist <= self.fire_range and dist < closest_dist:
                closest = s
                closest_dist = dist
        return closest

    def take_damage(self, amount):
        if self.hp < 0:
            return
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            if self in self.home.ships:
                self.home.ships.remove(self)
            self._destroyed = True

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, planets, highways=None, all_ships=None):
        # Tick shoot flash regardless of state
        if self._shoot_flash:
            tx, ty, t = self._shoot_flash
            t -= dt
            self._shoot_flash = (tx, ty, t) if t > 0 else None

        if self.state == MISSION_IDLE:
            return

        if self.state == MISSION_TRAVEL:
            speed = self._travel_speed(highways)
            self._move_toward(self.target_planet.x, self.target_planet.y, dt, speed)
            dist = math.hypot(self.x - self.target_planet.x, self.y - self.target_planet.y)
            if dist < 40:
                self.x = self.target_planet.x
                self.y = self.target_planet.y
                if self._mission_type == "explore":
                    self.state = MISSION_DISCOVER
                    self._discover_timer = self._discover_duration
                elif self._mission_type in ("mine", "pump"):
                    self.state = MISSION_MINE
                    self._mine_timer = self._mine_duration
                elif self._mission_type == "colonize":
                    self.target_planet.colonize()
                    if self in self.home.ships:
                        self.home.ships.remove(self)
                    self._destroyed = True
                    return
                elif self._mission_type == "highway":
                    if highways is not None:
                        highways.add(frozenset({self.home.id, self.target_planet.id}))
                    if self in self.home.ships:
                        self.home.ships.remove(self)
                    self._destroyed = True
                    return

        elif self.state == MISSION_DISCOVER:
            self._discover_timer -= dt
            if self._discover_timer <= 0:
                self.target_planet.explored = True
                if self in self.home.ships:
                    self.home.ships.remove(self)
                self._destroyed = True
                return

        elif self.state == MISSION_MINE:
            self._mine_timer -= dt
            extractable = PUMP_RESOURCES if self._mission_type == "pump" else MINE_RESOURCES
            for res in self.target_planet.available_resources:
                if res not in extractable:
                    continue
                space = self.capacity - sum(self.cargo.values())
                amount = min(10 * dt, space)
                self.cargo[res] = self.cargo.get(res, 0) + amount
            if self._mine_timer <= 0 or sum(self.cargo.values()) >= self.capacity:
                self.state = MISSION_RETURN

        elif self.state == MISSION_RETURN:
            speed = self._travel_speed(highways)
            self._move_toward(self.home.x, self.home.y, dt, speed)
            dist = math.hypot(self.x - self.home.x, self.y - self.home.y)
            if dist < 40:
                self.x = self.home.x
                self.y = self.home.y
                self._refund_fuel()
                # Unload cargo
                for res, amt in self.cargo.items():
                    self.home.resources[res] = self.home.resources.get(res, 0) + amt
                self.cargo = {r: 0.0 for r in RESOURCE_NAMES}
                prev_target = self.target_planet
                prev_mtype  = getattr(self, "_mission_type", None)
                self.state = MISSION_IDLE
                self.target_planet = None
                if self.repeat and prev_mtype in ("mine", "pump") and prev_target:
                    if prev_mtype == "pump":
                        self.send_pump(prev_target)
                    else:
                        self.send_mine(prev_target)

        elif self.state == MISSION_PATROL:
            # Enter combat if enemy spotted
            if self.fire_range > 0 and all_ships:
                enemy = self._find_enemy(all_ships)
                if enemy:
                    self._pre_combat_dest = self._patrol_dest
                    self._target_enemy = enemy
                    self.state = MISSION_COMBAT
                    return

            wx, wy = self._patrol_dest
            self._move_toward(wx, wy, dt, self.speed)
            dist = math.hypot(self.x - wx, self.y - wy)
            if dist < 5:
                self.x = wx
                self.y = wy
                if self._dock_planet and self._dock_planet.colonized and self.faction == "player":
                    if self in self.home.ships:
                        self.home.ships.remove(self)
                    self.home = self._dock_planet
                    if self not in self.home.ships:
                        self.home.ships.append(self)
                    # Refuel combat ships from the dock planet's resources
                    if self.fuel_capacity is not None:
                        needed = self.fuel_capacity - self.fuel_remaining
                        available = self.home.resources.get(self.fuel_type, 0)
                        amount = min(needed, available)
                        self.home.resources[self.fuel_type] -= amount
                        self.fuel_remaining += amount
                if self.fuel_capacity is None:
                    self._refund_fuel()  # non-combat ships return unused fuel to home
                self._patrol_dest = None
                self._dock_planet = None
                self.state = MISSION_IDLE

        elif self.state == MISSION_COMBAT:
            self._fire_cooldown = max(0.0, self._fire_cooldown - dt)
            enemy = self._find_enemy(all_ships) if all_ships else None
            if not enemy:
                self._target_enemy = None
                if self._pre_combat_dest:
                    self._patrol_dest = self._pre_combat_dest
                    self._pre_combat_dest = None
                    self.state = MISSION_PATROL
                else:
                    self.state = MISSION_IDLE
                return
            self._target_enemy = enemy
            dx = enemy.x - self.x
            dy = enemy.y - self.y
            d = math.hypot(dx, dy)
            if d > 0:
                self.angle = math.atan2(dy, dx)
            if self._fire_cooldown <= 0 and self.damage > 0:
                enemy.take_damage(self.damage)
                self._shoot_flash = (enemy.x, enemy.y, 0.15)
                self._fire_cooldown = 1.0 / max(self.fire_rate, 0.001)

        # Sprite animation
        nframes = SHIP_SPRITE_FRAMES.get(self.type, 1)
        if nframes > 1:
            self._anim_timer += dt
            if self._anim_timer >= _ANIM_FRAME_DUR:
                self._anim_timer -= _ANIM_FRAME_DUR
                self._anim_frame = (self._anim_frame + 1) % nframes

    def _travel_speed(self, highways):
        if highways and self.target_planet:
            link = frozenset({self.home.id, self.target_planet.id})
            if link in highways:
                self._effective_speed = self.speed * 1.5
                return self._effective_speed
        self._effective_speed = self.speed
        return self._effective_speed

    def _move_toward(self, tx, ty, dt, speed=None):
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        self.angle = math.atan2(dy, dx)
        step = min((speed if speed is not None else self.speed) * dt, dist)
        self.x += (dx / dist) * step
        self.y += (dy / dist) * step
        self.fuel_remaining = max(0.0, self.fuel_remaining - step * self.fuel_rate)

    @property
    def is_docked(self):
        if self.state != MISSION_IDLE:
            return False
        return math.hypot(self.x - self.home.x, self.y - self.home.y) < 2

    # ── hit-testing ──────────────────────────────────────────────
    def is_clicked(self, mx, my, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        r = max(8, int(SHIP_DRAW_SIZE * camera.zoom)) // 2 + 8
        return (mx - sx) ** 2 + (my - sy) ** 2 <= r ** 2

    def draw_hover(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        r = max(8, int(SHIP_DRAW_SIZE * camera.zoom)) // 2 + 10
        pygame.draw.circle(surface, CYAN, (sx, sy), r, 2)
        if self.faction != "player":
            rel_label = RELATIONSHIP_LABELS.get(self.faction_relationship, self.faction_relationship)
            try:
                _rf = pygame.font.SysFont("consolas", 10)
            except Exception:
                _rf = pygame.font.Font(None, 12)
            _rt = _rf.render(rel_label, True, self.faction_color)
            surface.blit(_rt, (sx - _rt.get_width() // 2, sy - r - _rt.get_height() - 2))

    # ── draw ─────────────────────────────────────────────────────
    def draw(self, surface, camera):
        sx, sy = camera.world_to_screen(self.x, self.y)
        if sx < -50 or sx > SCREEN_W + 50 or sy < -50 or sy > SCREEN_H + 50:
            return
        draw_size = max(8, int(SHIP_DRAW_SIZE * camera.zoom))
        nframes = SHIP_SPRITE_FRAMES.get(self.type, 1)
        frames = _load_sprite_frames(SHIP_IMG_PATHS.get(self.type, ""), nframes, draw_size)
        img = frames[self._anim_frame % len(frames)]
        deg = -math.degrees(self.angle) - 90
        rotated = pygame.transform.rotate(img, deg)
        rect = rotated.get_rect(center=(sx, sy))
        surface.blit(rotated, rect)

        # State dot
        mission_type = getattr(self, "_mission_type", None)
        if self.faction != "player":
            dot_color = self.faction_color
        elif self.state == MISSION_TRAVEL and mission_type == "colonize":
            dot_color = GOLD
        elif self.state == MISSION_COMBAT:
            dot_color = RED
        elif self.state == MISSION_PATROL:
            dot_color = ORANGE
        else:
            dot_color = {
                MISSION_IDLE:     GRAY,
                MISSION_TRAVEL:   CYAN,
                MISSION_DISCOVER: GOLD,
                MISSION_MINE:     ORANGE,
                MISSION_RETURN:   GREEN,
                MISSION_EXPLORE:  CYAN,
            }.get(self.state, WHITE)
        pygame.draw.circle(surface, dot_color, (sx + draw_size // 2, sy - draw_size // 2), max(3, int(4 * camera.zoom)))

        # Non-player faction ring + permanent name label
        if self.faction != "player":
            pygame.draw.circle(surface, self.faction_color, (sx, sy),
                               max(8, draw_size // 2) + 3, 1)
            if camera.zoom >= 0.3:
                try:
                    _ff = pygame.font.SysFont("consolas", 9)
                except Exception:
                    _ff = pygame.font.Font(None, 10)
                _fl = _ff.render(self.faction_name, True, self.faction_color)
                surface.blit(_fl, (sx - _fl.get_width() // 2,
                                   sy + draw_size // 2 + 12))

        # HP bar for combat ships
        if self.hp >= 0 and self.max_hp > 0:
            hp_ratio = max(0.0, self.hp / self.max_hp)
            bar_w = max(20, draw_size)
            bar_h = 4
            bar_x = sx - bar_w // 2
            bar_y = sy + draw_size // 2 + 6
            pygame.draw.rect(surface, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
            fill_color = GREEN if hp_ratio > 0.5 else (ORANGE if hp_ratio > 0.25 else RED)
            fw = int(bar_w * hp_ratio)
            if fw > 0:
                pygame.draw.rect(surface, fill_color, (bar_x, bar_y, fw, bar_h))
            pygame.draw.rect(surface, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h), 1)

        # Laser flash on shoot
        if self._shoot_flash:
            tx, ty, t = self._shoot_flash
            fx, fy = camera.world_to_screen(tx, ty)
            ratio = min(1.0, t / 0.15)
            r = int(255 * ratio)
            pygame.draw.line(surface, (r, r // 4, r // 4), (sx, sy), (fx, fy), 2)

        # Travel line toward actual destination
        if self.state in (MISSION_TRAVEL, MISSION_MINE) and self.target_planet:
            tx, ty = camera.world_to_screen(self.target_planet.x, self.target_planet.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif self.state == MISSION_RETURN:
            tx, ty = camera.world_to_screen(self.home.x, self.home.y)
            pygame.draw.line(surface, (*CYAN, 60), (sx, sy), (tx, ty), 1)
        elif self.state == MISSION_PATROL and self._patrol_dest:
            tx, ty = camera.world_to_screen(self._patrol_dest[0], self._patrol_dest[1])
            line_color = (*self.faction_color, 60) if self.faction != "player" else (*ORANGE, 60)
            pygame.draw.line(surface, line_color, (sx, sy), (tx, ty), 1)

        # Fire range circle in combat state
        if self.state == MISSION_COMBAT and self.faction == "player":
            r_px = int(self.fire_range * camera.zoom)
            if 10 < r_px < 1200:
                ring_surf = pygame.Surface((r_px * 2 + 2, r_px * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(ring_surf, (220, 60, 60, 40), (r_px + 1, r_px + 1), r_px)
                pygame.draw.circle(ring_surf, (220, 60, 60, 80), (r_px + 1, r_px + 1), r_px, 1)
                surface.blit(ring_surf, (sx - r_px - 1, sy - r_px - 1))

        # ETA label while moving toward a destination
        if self.state in (MISSION_TRAVEL, MISSION_RETURN):
            dest_x = self.target_planet.x if self.state == MISSION_TRAVEL else self.home.x
            dest_y = self.target_planet.y if self.state == MISSION_TRAVEL else self.home.y
            dist = math.hypot(dest_x - self.x, dest_y - self.y)
            eta = dist / max(self._effective_speed, 1)
            label = f"{int(eta//60)}m {int(eta%60)}s" if eta >= 60 else f"{eta:.0f}s"
            try:
                font = pygame.font.SysFont("consolas", max(12, int(10 * camera.zoom)))
            except Exception:
                font = pygame.font.Font(None, max(11, int(12 * camera.zoom)))
            txt = font.render(label, True, CYAN)
            surface.blit(txt, (sx - txt.get_width() // 2,
                               sy - draw_size // 2 - txt.get_height() - 2))
