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

# Storage
STORAGE_BASE           = 5000  # base cap per resource on any colonized planet
STORAGE_PER_SILO_LEVEL = 2500  # cap added per Silo level

# Planet types → which resources they carry
PLANET_RESOURCES = {
    "rocky":     ["iron", "gold", "silver"],
    "gas":       ["deuterium", "oil"],
    "asteroid":  ["iron", "silver", "gold"],
}

# Buildings
BUILDING_DEFS = {
    "Iron Mine":       {"cost": {"iron": 50},               "time": 10, "produces": {"iron": 2},       "requires": [], "category": "mine"},
    "Gold Mine":       {"cost": {"iron": 80, "gold": 30},   "time": 20, "produces": {"gold": 1},       "requires": [], "category": "mine"},
    "Silver Mine":     {"cost": {"iron": 60},               "time": 15, "produces": {"silver": 1.5},   "requires": [], "category": "mine"},
    "Oil Rig":         {"cost": {"iron": 100},              "time": 25, "produces": {"oil": 1},         "requires": [], "category": "mine"},
    "Deuterium Plant": {"cost": {"iron": 120, "silver": 40},"time": 30, "produces": {"deuterium": 0.8},"requires": [], "category": "mine"},
    "Silo":            {"cost": {"iron": 120, "gold": 30},  "time": 25, "produces": {},                "requires": [], "category": "storage"},
    "Shipyard":        {"cost": {"iron": 200, "gold": 50},  "time": 45, "produces": {},                "requires": [], "category": "factory"},
}

BUILDING_PLANET_TYPES = {
    "Iron Mine":       ["rocky", "asteroid"],
    "Gold Mine":       ["rocky", "asteroid"],
    "Silver Mine":     ["rocky", "asteroid"],
    "Oil Rig":         ["gas"],
    "Deuterium Plant": ["gas"],
    "Shipyard":        ["rocky", "gas", "asteroid"],
    "Silo":            ["rocky", "gas", "asteroid"],
}

# Ships — shipyard_level = niveau minimal du chantier naval requis
SHIP_DEFS = {
    "Probe":      {"cost": {"iron": 50,  "gold": 10},                        "time": 15, "speed": 180, "capacity": 0,    "missions": ["explore"],   "shipyard_level": 1},
    "Miner":      {"cost": {"iron": 120, "gold": 20,  "oil": 10},            "time": 30, "speed": 100, "capacity": 200,  "missions": ["mine"],      "shipyard_level": 1},
    "Colonizer":  {"cost": {"iron": 300, "gold": 80,  "silver": 50},         "time": 60, "speed": 80,  "capacity": 0,    "missions": ["colonize"],  "shipyard_level": 1},
    "Scout":      {"cost": {"iron": 80,  "gold": 40},                        "time": 20, "speed": 300, "capacity": 0,    "missions": ["explore"],   "shipyard_level": 3},
    "Freighter":  {"cost": {"iron": 250, "gold": 60,  "oil": 30},            "time": 60, "speed": 60,  "capacity": 800,  "missions": ["mine"],      "shipyard_level": 5},
    "Constructor":{"cost": {"iron": 400, "gold": 100, "silver": 80},         "time": 90, "speed": 70,  "capacity": 0,    "missions": ["highway"],   "shipyard_level": 1},
    }

# Starting resources for player's first planet
START_RESOURCES = {"iron": 5000, "gold": 1000, "silver": 800, "oil": 50, "deuterium": 30}
