import time
from constants import BUILDING_DEFS

class Building:
    def __init__(self, name):
        self.name = name
        defn = BUILDING_DEFS[name]
        self.produces = defn["produces"].copy()
        self.category = defn["category"]
        self.build_time = defn["time"]
        self.done = True           # already constructed
        self._timer = 0.0

    def update(self, dt, resources):
        if not self.done:
            return
        for res, rate in self.produces.items():
            resources[res] = resources.get(res, 0) + rate * dt

    # ── ship queue (for Shipyard) ────────────────────────────────
    # Shipyard uses planet.ship_queue list, not this class directly.
