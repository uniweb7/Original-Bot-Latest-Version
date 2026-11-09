# bot_config.py
# Global Configuration & Speed Settings for Clash of Clans AI Bot (Samsung Galaxy A14)

import time

BOT_SPEED_MULTIPLIER = 1.0

# Fixed Variable Name: ADVANCE_SPEED_TABLE (Required by main_bot.py)
ADVANCE_SPEED_TABLE = [
    ("A", 1.00, "Standard Speed (Default - 100% As Coded)"),
    ("B", 1.10, "1.10x Fast Speed"),
    ("C", 1.15, "1.15x Fast Speed"),
    ("D", 1.20, "1.20x Fast Speed"),
    ("E", 1.25, "1.25x Fast Speed"),
    ("F", 1.30, "1.30x Fast Speed"),
    ("G", 1.35, "1.35x Fast Speed"),
    ("H", 1.40, "1.40x Fast Speed"),
    ("I", 1.45, "1.45x Fast Speed"),
    ("J", 1.50, "1.50x Turbo Speed"),
    ("K", 1.55, "1.55x Turbo Speed"),
    ("L", 1.60, "1.60x Turbo Speed"),
    ("M", 1.65, "1.65x Turbo Speed"),
    ("N", 1.70, "1.70x Turbo Speed"),
    ("O", 1.75, "1.75x Turbo Speed"),
    ("P", 1.80, "1.80x Ultra Speed"),
    ("Q", 1.85, "1.85x Ultra Speed"),
    ("R", 1.90, "1.90x Ultra Speed"),
    ("S", 1.95, "1.95x Ultra Speed"),
    ("T", 2.00, "2.00x Ultra Speed"),
    ("U", 2.05, "2.05x Extreme Speed"),
    ("V", 2.10, "2.10x Extreme Speed"),
    ("W", 2.15, "2.15x Extreme Speed"),
    ("X", 2.20, "2.20x Extreme Speed"),
    ("Y", 2.25, "2.25x Maximum Speed Limit")
]

def set_bot_speed_multiplier(mult):
    global BOT_SPEED_MULTIPLIER
    val = max(1.0, min(2.25, float(mult)))
    BOT_SPEED_MULTIPLIER = round(val, 2)
    print(f" [SPEED ENGINE] Root-Level Bot Speed Multiplier set to: {BOT_SPEED_MULTIPLIER:.2f}x")
    return BOT_SPEED_MULTIPLIER

def get_bot_speed_multiplier():
    return BOT_SPEED_MULTIPLIER

def scale_time_by_speed(seconds, min_floor=0.08):
    """Scales wait/delay durations inversely by BOT_SPEED_MULTIPLIER at root level."""
    raw = float(seconds)
    if raw <= 0.0:
        return 0.0
    if BOT_SPEED_MULTIPLIER <= 1.0:
        return max(min_floor, raw)
    scaled = raw / BOT_SPEED_MULTIPLIER
    return max(min_floor, scaled)

# ---------------------------------------------------------
# GLOBAL TIMERS & WATCHDOG SETTINGS
# ---------------------------------------------------------
CONNECTION_OCR_INTERVAL_SEC = 300.0   # 5 Minutes periodic OCR check
CONNECTION_RETRY_GAP_SEC = 300.0      # 5 Minutes gap between reload attempts
CONNECTION_MAX_ATTEMPTS = 5           # 5 reload attempts
CONNECTION_MAX_OUTAGE_SEC = 3600.0    # 1 Hour (60 Minutes) maximum recovery window
MAINTENANCE_REST_SEC = 600.0          # 10 Minutes rest for Maintenance Break
BATTLE_TIMER_DURATION_SEC = 45.0      # Max 45 seconds for attack deployment
