import pygame

# World
WORLD_W = 24000
WORLD_H = 24000
SECTOR_SIZE = 800          # pixels per sector cell
PLANET_MIN_DIST = 1000     # min distance between planets
PLANET_MAX_DIST = 2000     # max distance between planets
NUM_PLANETS = 30
HABITABLE_RATIO = 0.25     # fraction of non-home planets that can be colonized

# Window
SCREEN_W = 1280
SCREEN_H = 800
FPS = 60

# Scroll
SCROLL_SPEED = 15
ZOOM_MIN = 0.1
ZOOM_MAX = 2.0
ZOOM_STEP = 0.1
ZOOM_INIT = 0.8

# Stars background
NUM_STARS_LAYER1 = 600     # slow parallax
NUM_STARS_LAYER2 = 300     # fast parallax
NUM_NEBULAE = 12
NUM_SHOOTING_STARS = 3

# Colors
BLACK       = (0, 0, 0)
WHITE       = (255, 255, 255)
GRAY        = (120, 120, 120)
DARK_GRAY   = (40, 40, 50)
GRID_COLOR  = (25, 35, 55)
SECTOR_LABEL= (40, 60, 90)

UI_BG       = (10, 14, 30, 220)
UI_BORDER   = (60, 100, 160)
UI_TITLE    = (180, 220, 255)
UI_TEXT     = (200, 210, 230)
UI_BTN      = (30, 60, 120)
UI_BTN_HOV  = (50, 100, 180)
UI_BTN_TXT  = (220, 235, 255)
UI_DISABLED = (50, 55, 65)

ORANGE      = (255, 160, 40)
GREEN       = (80, 220, 120)
RED         = (220, 70, 70)
CYAN        = (60, 200, 220)
GOLD        = (255, 210, 60)

# Resources
RESOURCE_NAMES  = ["iron", "gold", "silver", "oil", "deuterium"]
RESOURCE_COLORS = {
    "iron":      (160, 140, 130),
    "gold":      (255, 210, 60),
    "silver":    (200, 210, 220),
    "oil":       (80, 80, 100),
    "deuterium": (60, 160, 255),
}
RESOURCE_MAX_CHAR = 10
QUEUE_MAX  = 10         # max items per production queue
LEVEL_MAX  = 10         # max building level

# Storage — solids (iron/silver/gold) vs fluids (oil/deuterium)
SOLID_RESOURCES        = frozenset({"iron", "silver", "gold"})
FLUID_RESOURCES        = frozenset({"oil", "deuterium"})

STORAGE_BASE           = 5000  # base solid cap per colonized planet
STORAGE_PER_SILO_LEVEL = 2500  # solid cap added per Silo level

FLUID_BASE             = 2000  # base fluid cap per colonized planet
STORAGE_PER_TANK_LEVEL = 1500  # fluid cap added per Fuel Tank level

# Planet types → fallback resource lists (actual lists are generated procedurally)
PLANET_RESOURCES = {
    "rocky":     ["iron", "oil", "silver"],
    "gas":       ["oil", "deuterium"],
    "asteroid":  ["iron", "oil", "silver"],
}

# Buildings
BUILDING_DEFS = {
    "Iron Mine":       {"cost": {"iron": 50},               "time": 10, "produces": {"iron": 2},        "requires": [], "category": "mine"},
    "Gold Mine":       {"cost": {"iron": 80, "gold": 30},   "time": 20, "produces": {"gold": 1},        "requires": [], "category": "mine"},
    "Silver Mine":     {"cost": {"iron": 60},               "time": 15, "produces": {"silver": 1.5},    "requires": [], "category": "mine"},
    "Oil Pump":        {"cost": {"iron": 80, "gold": 20},   "time": 20, "produces": {"oil": 0.6},       "requires": [], "category": "mine"},
    "Oil Rig":         {"cost": {"iron": 100},              "time": 25, "produces": {"oil": 1},          "requires": [], "category": "mine"},
    "Deuterium Pump":  {"cost": {"iron": 100, "silver": 40},"time": 25, "produces": {"deuterium": 0.5}, "requires": [], "category": "mine"},
    "Deuterium Plant": {"cost": {"iron": 120, "silver": 40},"time": 30, "produces": {"deuterium": 0.8}, "requires": [], "category": "mine"},
    "Silo":            {"cost": {"iron": 120, "gold": 30},  "time": 25, "produces": {},                 "requires": [], "category": "storage"},
    "Fuel Tank":       {"cost": {"iron": 100, "silver": 40},"time": 30, "produces": {},                 "requires": [], "category": "storage"},
    "Shipyard":        {"cost": {"iron": 200, "gold": 50},  "time": 45, "produces": {},                 "requires": [], "category": "factory"},
}

BUILDING_PLANET_TYPES = {
    "Iron Mine":       ["rocky", "asteroid"],
    "Gold Mine":       ["rocky", "asteroid"],
    "Silver Mine":     ["rocky", "asteroid"],
    "Oil Pump":        ["rocky", "asteroid"],
    "Oil Rig":         ["gas"],
    "Deuterium Pump":  ["rocky", "asteroid"],
    "Deuterium Plant": ["gas"],
    "Silo":            ["rocky", "gas", "asteroid"],
    "Fuel Tank":       ["rocky", "gas", "asteroid"],
    "Shipyard":        ["rocky", "gas", "asteroid"],
}

# Ships — shipyard_level = niveau minimal du chantier naval requis
# fuel_type: ressource consommée en vol  |  fuel_rate: unités/px parcouru
SHIP_DEFS = {
    "Probe":      {"cost": {"iron": 50,  "gold": 10},                        "time": 15, "speed": 180, "capacity": 0,    "missions": ["explore"],   "shipyard_level": 1, "fuel_type": "oil",       "fuel_rate": 0.003},
    "Miner":      {"cost": {"iron": 120, "gold": 20,  "oil": 10},            "time": 30, "speed": 100, "capacity": 200,  "missions": ["mine"],      "shipyard_level": 1, "fuel_type": "oil",       "fuel_rate": 0.005},
    "Colonizer":  {"cost": {"iron": 300, "gold": 80,  "silver": 50},         "time": 60, "speed": 80,  "capacity": 0,    "missions": ["colonize"],  "shipyard_level": 1, "fuel_type": "oil",       "fuel_rate": 0.006},
    "Scout":      {"cost": {"iron": 80,  "gold": 40},                        "time": 20, "speed": 300, "capacity": 0,    "missions": ["explore"],   "shipyard_level": 3, "fuel_type": "deuterium", "fuel_rate": 0.002},
    "Tanker":     {"cost": {"iron": 200, "gold": 50},                        "time": 55, "speed": 80,  "capacity": 600,  "missions": ["pump"],      "shipyard_level": 2, "fuel_type": "oil",       "fuel_rate": 0.007},
    "Freighter":  {"cost": {"iron": 250, "gold": 60,  "oil": 30},            "time": 60, "speed": 60,  "capacity": 800,  "missions": ["mine"],      "shipyard_level": 5, "fuel_type": "oil",       "fuel_rate": 0.008},
    "Constructor":{"cost": {"iron": 400, "gold": 100, "silver": 80},         "time": 90,  "speed": 70,  "capacity": 0, "missions": ["highway"],   "shipyard_level": 1, "fuel_type": "oil",       "fuel_rate": 0.005},
    "Fighter":    {"cost": {"iron": 150, "gold": 60},                         "time": 40,  "speed": 120, "capacity": 0, "missions": ["patrol"],    "shipyard_level": 1,
                   "hp": 60,  "damage": 15, "fire_range": 350, "fire_rate": 1.2, "fuel_type": "oil",       "fuel_rate": 0.004},
    "Destroyer":  {"cost": {"iron": 350, "gold": 120, "silver": 60},          "time": 80,  "speed": 100, "capacity": 0, "missions": ["patrol"],    "shipyard_level": 2,
                   "hp": 200, "damage": 35, "fire_range": 450, "fire_rate": 0.6, "fuel_type": "oil",       "fuel_rate": 0.006},
    "Battleship": {"cost": {"iron": 800, "gold": 300, "silver": 150, "oil": 50}, "time": 180, "speed": 80, "capacity": 0, "missions": ["patrol"],  "shipyard_level": 3,
                   "hp": 600, "damage": 80, "fire_range": 550, "fire_rate": 0.3, "fuel_type": "deuterium", "fuel_rate": 0.004},
    }

# Mission types that are one-way (ship does not return to home after completing)
MISSION_ONE_WAY = frozenset({"explore", "colonize", "highway"})

# Starting resources for player's first planet
START_RESOURCES = {"iron": 5000, "gold": 1000, "silver": 800, "oil": 50, "deuterium": 30}
