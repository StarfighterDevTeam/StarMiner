from constants import BUILDING_DEFS, LEVEL_MAX

class Building:
    def __init__(self, name, level=1):
        self.name = name
        self.level = level
        defn = BUILDING_DEFS[name]
        self.category = defn.get("category", "")
        self._base_produces = defn.get("produces", {}).copy()
        self._base_cost = defn["cost"].copy()
        self._base_time = defn["time"]
        # Defense-only state
        if self.category == "defense":
            self.units_hp: list[float] = []
            self._fire_timers: list[float] = []
            self._no_combat_timer: float = 0.0
        self._refresh_produces()

    def _refresh_produces(self):
        self.produces = {r: v * self.level for r, v in self._base_produces.items()}

    @property
    def _upgrade_mult(self) -> float:
        return 1.0 + (self.level - 1) * 0.15

    @property
    def count(self) -> int:
        return len(self.units_hp) if self.category == "defense" else 1

    # ── defense stat helpers ─────────────────────────────────────
    def unit_hp(self) -> float:
        return BUILDING_DEFS[self.name]["hp"] * self._upgrade_mult

    def unit_damage(self) -> float:
        return BUILDING_DEFS[self.name]["damage"] * self._upgrade_mult

    def unit_range(self) -> float:
        return BUILDING_DEFS[self.name]["fire_range"] * self._upgrade_mult

    def unit_rate(self) -> float:
        return BUILDING_DEFS[self.name]["fire_rate"] * self._upgrade_mult

    def add_unit(self):
        if self.category != "defense":
            return
        self.units_hp.append(self.unit_hp())
        self._fire_timers.append(0.0)

    def take_damage(self, dmg: float) -> float:
        """Absorb damage sequentially across units. Returns leftover damage."""
        while dmg > 0 and self.units_hp:
            if self.units_hp[0] > dmg:
                self.units_hp[0] -= dmg
                return 0.0
            dmg -= self.units_hp[0]
            self.units_hp.pop(0)
            self._fire_timers.pop(0)
        return dmg

    def full_recover(self):
        if self.category == "defense":
            max_hp = self.unit_hp()
            self.units_hp = [max_hp] * len(self.units_hp)

    def level_up(self):
        if self.level < LEVEL_MAX:
            self.level += 1
            self._refresh_produces()
            if self.category == "defense":
                self.full_recover()

    # ── upgrade pricing ──────────────────────────────────────────
    def upgrade_cost(self):
        """Cost to go from current level to level+1. Doubles each level: base * 2^level."""
        return {r: int(amt * (2 ** self.level)) for r, amt in self._base_cost.items()}

    def upgrade_time(self):
        """Build time for the next upgrade. ×1.5 each level: base * 1.5^level."""
        return self._base_time * (1.5 ** self.level)

    # ── shipyard bonus ───────────────────────────────────────────
    def ship_time_factor(self):
        """Multiplier applied to ship build times (only relevant for Shipyard)."""
        return 0.9 ** (self.level - 1)

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, resources):
        for res, rate in self.produces.items():
            resources[res] = resources.get(res, 0) + rate * dt
