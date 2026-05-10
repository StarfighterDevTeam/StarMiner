from constants import BUILDING_DEFS, LEVEL_MAX

class Building:
    def __init__(self, name, level=1):
        self.name = name
        self.level = level
        defn = BUILDING_DEFS[name]
        self.category = defn["category"]
        self._base_produces = defn["produces"].copy()
        self._base_cost = defn["cost"].copy()
        self._base_time = defn["time"]
        self._refresh_produces()

    def _refresh_produces(self):
        self.produces = {r: v * self.level for r, v in self._base_produces.items()}

    def level_up(self):
        if self.level < LEVEL_MAX:
            self.level += 1
            self._refresh_produces()

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
        return 0.9 ** (self.level - 1)   # −10 % per level above 1

    # ── update ───────────────────────────────────────────────────
    def update(self, dt, resources):
        for res, rate in self.produces.items():
            resources[res] = resources.get(res, 0) + rate * dt
