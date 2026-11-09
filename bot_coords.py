# bot_coords.py
# Centralized Geometry & Coordinates for Clash of Clans AI Bot (Samsung Galaxy A14)

# ---------------------------------------------------------
# 1. HOME PAGE, POPUPS & ERROR BOXES
# ---------------------------------------------------------
HOME_PAGE_CHECK_COORDS = [(2050, 285), (2050, 250)]

WRONG_BUTTON_CUT_COORDS = [
    ("Profile Section", 1917, 87),
    ("League Page", 2149, 84),
    ("Clan War", 192, 981),
    ("Season Reward", 2290, 83),
    ("Events", 1820, 76),
    ("News Letter", 2283, 89),
    ("News", 2284, 73),
    ("Tournament Hub", 1831, 73),
    ("Magic Items", 1720, 164),
    ("Shop", 2282, 79)
]

CLAN_CHAT_DRAWER_BOX = (792, 423, 863, 457)
CLAN_CHAT_CLICK_COORD = (827, 440)

WELCOME_CHIEF_RED_BANNER_BOX = (1549, 103, 1844, 164)
WELCOME_CHIEF_GREEN_BTN_BOX = (1142, 924, 1312, 940)
WELCOME_CHIEF_CLICK_COORD = (1227, 932)

DAILY_REWARD_OUTER_BOX = (458, 113, 1921, 930)
DAILY_REWARD_CLOSE_BTN = (1858, 153)
DAILY_REWARD_GREEN_BOXES = [
    (540, 467, 753, 490),
    (839, 467, 1042, 487),
    (1131, 468, 1332, 488),
    (537, 782, 744, 805),
    (844, 786, 1033, 804),
    (1136, 791, 1346, 812),
    (1435, 782, 1731, 813)
]

MAINTENANCE_BREAK_BOX = (979, 16, 1442, 63)
MAINTENANCE_CLICK_COORD = (1210, 39)

# Connection Lost Coords based on Sketch & Screenshots
CONNECTION_LOST_OUTER_BOX = (751, 684, 1733, 1017)
CONNECTION_LOST_TEXT_BOX_LEFT = (773, 690, 1059, 767)
CONNECTION_LOST_TEXT_BOX_WIDE = (773, 690, 1773, 767)
TRY_AGAIN_BTN_BOX = (1053, 934, 1460, 1022)
TRY_AGAIN_CLICK_COORD = (1256, 978)

GOLD_STORAGE_BAR = (2170, 63)
ELIXIR_STORAGE_BAR = (2166, 128)
GOLD_STORAGE_CHECK_BOX = (2015, 43, 2081, 78)
ELIXIR_STORAGE_CHECK_BOX = (2003, 116, 2103, 151)

# ---------------------------------------------------------
# 2. SMART UPGRADE SYSTEM (BUILDING, WALL, SPELL, PET, EQUIP)
# ---------------------------------------------------------
UPGRADE_A14 = {
    "BUILD_CLICK": (2233, 948),
    "BUILDER_CHECK_BOX": (1754, 1008, 1847, 1038),
    "CLOSE_MENU": (2322, 45),
    "C1_REOPEN_LIST": (2050, 56),
    "WALL_REOPEN_LIST_CLICK": (2062, 54),
    
    # Filter Select Process
    "FILTER_ENTER_BTN": (1788, 43),
    "FILTER_SELECT_BTN": (1145, 715),
    "FILTER_BACK_BTN": (2021, 51),
    
    # Upgrade List OCR Boxes (Initial & Expanded after scroll)
    "UPGRADE_LIST_BOX_INITIAL": (1820, 545, 2312, 926),
    "UPGRADE_LIST_BOX_EXPANDED": (1818, 95, 2311, 925),
    
    "SCROLL_START": (2050, 863),
    "SCROLL_END": (2050, 542),
    "C1_CONFIRM_CLICK": (1582, 930),
    "C1_WRONG_BTN": (1589, 339),
    "WALL_STEP_A1_CLICK": (439, 851),
    "WALL_CONFIRM_CLICK": (1595, 942),

    # Extra Upgrade Tabs (Spells, Pets, Equipments)
    "SPELL_CHECK_BOX": (1915, 1007, 2007, 1046),
    "SPELL_TAB_CLICK": (1961, 1026),
    "PET_CHECK_BOX": (2037, 1006, 2329, 1040),
    "PET_TAB_CLICK": (2183, 1023),
    "EQUIPMENT_TAB_CLICK": (2121, 1011),

    # Goblin Builder Exception Coords
    "GOBLIN_PAGE_BOX": (1134, 193, 2009, 735),
    "GOBLIN_CHIEF_BOX": (1420, 203, 1714, 282),
    "GOBLIN_LETTER_BOX": (1154, 330, 1980, 493),
    "GOBLIN_RED_X_BOX": (1927, 209, 1996, 266),
    "GOBLIN_RED_X_CLICK": (1961, 237)
}

CARD_GEOMETRY = {
    "CARD_HEIGHT": 81,
    "NAME_X1": 1823,
    "NAME_X2": 2124,
    "NAME_DY1": 5,
    "NAME_DY2": 41,
    "COST_X1": 2108,
    "COST_X2": 2252,
    "COST_DY1": 33,
    "COST_DY2": 78
}

KNOWN_BUILDINGS = [
    "eagle artillery", "scattershot", "inferno tower", "x-bow", "xbow",
    "monolith", "spell tower", "firespitter", "ricochet cannon", "multi-archer tower",
    "multi-gear tower", "air defense", "wizard tower", "hidden tesla", "tesla",
    "bomb tower", "mortar", "archer tower", "cannon", "air sweeper", "builder's hut",
    "builder hut", "clan castle", "laboratory", "spell factory", "dark spell factory",
    "barracks", "dark barracks", "workshop", "pet house", "blacksmith", "hero hall",
    "army camp", "gold storage", "elixir storage", "dark elixir storage",
    "gold mine", "elixir collector", "dark elixir drill", "helper hut", "revenge tower",
    "giant bomb", "air bomb", "seeking air mine", "skeleton trap", "tornado trap",
    "spring trap", "bomb", "giga bomb"
]

CONDITION_1_EXCLUDED = [
    "town hall", "townhall",
    "barbarian", "king",
    "dragon duke", "duke",
    "minion prince", "prince",
    "crafting", "station",
    "royal", "champion",
    "archer queen", "queen",
    "grand warden", "warden",
    "wall"
]

# ---------------------------------------------------------
# 3. SMART ATTACK SYSTEM (DYNAMIC ARMY DEPLOY)
# ---------------------------------------------------------
FAST_ATTACK = {
    "BATTLE_BTN": (182, 961),
    "FIND_MATCH_BTN": (364, 808),
    "ATTACK_BTN": (1980, 972),
    "SURRENDER_BTN": (181, 800),
    "OKAY_BTN": (1419, 701),
    "RETURN_HOME_BTN": (1222, 918),

    # Dynamic Army Card Scanner Box (Replaces static Siege/Hero coords)
    "ARMY_CARD_SCAN_BOX": (355, 884, 2213, 1071),
    
    # Base click coordinates (colorful cards are mapped here dynamically)
    "SPELL_DEPLOY_LIST": [
        (378, 469), (594, 350), (566, 569), (691, 461),
        (864, 278), (812, 760), (928, 569), (915, 444),
        (1170, 580), (1070, 250), (892, 815)
    ],
    "ARMY_DEPLOY_LIST": [
        (325, 525), (225, 510), (303, 473), (292, 592),
        (222, 516), (453, 363), (337, 611), (256, 512),
        (375, 524)
    ]
}

# ---------------------------------------------------------
# 4. SUPERCELL ID SWITCH SYSTEM
# ---------------------------------------------------------
ID_SWITCH_A14 = {
    "PROFILE_BTN": (142, 122),
    "SETTINGS_BTN": (1755, 92),
    "SWITCH_ICON_BTN": (1507, 207),
    "CLOSE_SWITCH_PANEL_BTN": (135, 80),

    "LIST_BOX_CORNERS": (135, 150, 2370, 1040),
    "SUPERCELL_LOGO_BOX": (335, 502, 710, 518),
    "SUPERCELL_LOGO_OCR_BOX": (325, 465, 725, 550),
    "DIVIDER_X": 1118,
    
    "UNIQUE_ID_BOX": (1350, 236, 1940, 292),
    "TOWN_HALL_BOX": (1348, 360, 1662, 396),
    "CARD_HEIGHT": 225,
    "UNIQUE_ID_REL_Y1": 27,
    "UNIQUE_ID_REL_Y2": 83,
    "TH_REL_Y1": 151,
    "TH_REL_Y2": 187,

    "ID_SLOTS": [
        (1763, 321),
        (1763, 563),
        (1763, 800),
        (1763, 1044)
    ],
    
    # 1050ms slow exact zero-inertia scroll
    "SCROLL_START": (1763, 1030),
    "SCROLL_END": (1763, 215),
    "SCROLL_DURATION_MS": 1050,

    "ID_INITIAL_WAIT_SEC": 3.5,
    "ID_POLL_INTERVAL_SEC": 1.0
}
