# bot_config.py
# Global Configuration & Speed Settings for Clash of Clans AI Bot (Samsung Galaxy A14)

import time

BOT_SPEED_MULTIPLIER = 1.0

SPEED_PRESETS = {
    "A": 1.00, "B": 1.10, "C": 1.15, "D": 1.20, "E": 1.25,
    "F": 1.30, "G": 1.35, "H": 1.40, "I": 1.45, "J": 1.50,
    "K": 1.55, "L": 1.60, "M": 1.65, "N": 1.70, "O": 1.75,
    "P": 1.80, "Q": 1.85, "R": 1.90, "S": 1.95, "T": 2.00,
    "U": 2.05, "V": 2.10, "W": 2.15, "X": 2.20, "Y": 2.25
}

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
