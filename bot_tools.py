import sys
import os
import io
import gc
import time
import json
import datetime
import subprocess
import random
import re
import threading
import select

# Single-thread Tesseract lock to prevent CPU contention & phone heating/lag
os.environ["OMP_THREAD_LIMIT"] = "1"

from PIL import Image, ImageOps
import pytesseract

class RestartLoopException(Exception):
    """Raised when bot detects Home Page or Wrong Button during Attack."""
    pass

class BotPausedResumeHomeException(Exception):
    """Raised when bot is paused via 'ZX' and resumed via 'QW' to restart cleanly from Home Page."""
    pass

# ==========================================
# 0A. ROOT-LEVEL GAME SPEED-UP ENGINE (1.00x TO 2.25x)
# ==========================================
BOT_SPEED_MULTIPLIER = 1.0

SPEED_PRESETS = {
    "A": 1.00, "B": 1.10, "C": 1.15, "D": 1.20, "E": 1.25,
    "F": 1.30, "G": 1.35, "H": 1.40, "I": 1.45, "J": 1.50,
    "K": 1.55, "L": 1.60, "M": 1.65, "N": 1.70, "O": 1.75,
    "P": 1.80, "Q": 1.85, "R": 1.90, "S": 1.95, "T": 2.00,
    "U": 2.05, "V": 2.10, "W": 2.15, "X": 2.20, "Y": 2.25
}

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
    """Sets the global bot speed multiplier (1.00x standard up to 2.25x max). Persists across ZX/QW."""
    global BOT_SPEED_MULTIPLIER
    val = max(1.0, min(2.25, float(mult)))
    BOT_SPEED_MULTIPLIER = round(val, 2)
    print(f" [SPEED ENGINE] Root-Level Bot Speed Multiplier set to: {BOT_SPEED_MULTIPLIER:.2f}x")
    return BOT_SPEED_MULTIPLIER

def get_bot_speed_multiplier():
    return BOT_SPEED_MULTIPLIER

def scale_time_by_speed(seconds, min_floor=0.08):
    """
    Scales wait/delay durations inversely by BOT_SPEED_MULTIPLIER at root level,
    while enforcing a mandatory safe hardware floor (0.08s default) so that even at 2.0x-2.25x
    no button click or game transition ever fails!
    """
    raw = float(seconds)
    if raw <= 0.0:
        return 0.0
    if BOT_SPEED_MULTIPLIER <= 1.0:
        return max(min_floor, raw)
    scaled = raw / BOT_SPEED_MULTIPLIER
    return max(min_floor, scaled)

# ==========================================
# 0B. PERSISTENT PREVIOUS PROGRESS REPORT, AVERAGE TIMERS & PIE CHART ENGINE
# ==========================================
REPORT_SAVE_FILE = "bot_last_report.json"
_REPORT_LOCK = threading.Lock()

def _create_fresh_session_stats():
    now_ts = time.time()
    now_dt = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
    return {
        "session_start_ts": now_ts,
        "session_start_str": now_dt,
        "session_end_ts": now_ts,
        "session_end_str": now_dt,
        "operating_mode_str": "Not Selected",
        "speed_multiplier": BOT_SPEED_MULTIPLIER,
        "pause_count": 0,
        "resume_count": 0,
        "total_paused_sec": 0.0,
        "current_pause_start_ts": None,
        "active_id_index": 1,
        "active_id_name": "ID #1",
        "id_switches": 0,
        "attacks_success": 0,
        "attacks_failed": 0,
        "buildings_upgraded": 0,
        "walls_upgraded": 0,
        "spells_upgraded": 0,
        "pets_upgraded": 0,
        "equipments_upgraded": 0,
        "goblin_popups_cut": 0,
        "wrong_buttons_cut": 0,
        "clan_chat_closed": 0,
        "daily_rewards_claimed": 0,
        "welcome_chief_closed": 0,
        "maintenance_breaks": 0,
        "connection_lost_reloads": 0,
        "stuck_recoveries": 0,
        "zoom_outs_done": 0,
        "attack_time_total": 0.0,
        "attack_time_count": 0,
        "upgrade_time_total": 0.0,
        "upgrade_time_count": 0,
        "id_switch_time_total": 0.0,
        "id_switch_time_count": 0,
        "per_id": {}
    }

SESSION_STATS = _create_fresh_session_stats()

def _save_report_to_disk_unlocked():
    """Saves the current session stats to disk so they persist across restarts."""
    try:
        SESSION_STATS["session_end_ts"] = time.time()
        SESSION_STATS["session_end_str"] = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
        SESSION_STATS["speed_multiplier"] = BOT_SPEED_MULTIPLIER
        with open(REPORT_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(SESSION_STATS, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def save_current_progress_report():
    with _REPORT_LOCK:
        _save_report_to_disk_unlocked()

def show_saved_previous_report_once_at_startup():
    """
    If a previous session report exists on disk (e.g. from yesterday or last run),
    displays it ONCE when the bot script is launched.
    """
    if not os.path.exists(REPORT_SAVE_FILE):
        return False
    try:
        with open(REPORT_SAVE_FILE, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        if not isinstance(saved_data, dict):
            return False
        print("\n==============================================================================")
        print("||       📂 LAST SAVED SESSION PROGRESS REPORT (FROM PREVIOUS RUN) 📂       ||")
        print("==============================================================================")
        print_previous_progress_report(
            report_stage="LAST SAVED SESSION (PREVIOUS RUN)",
            stats_override=saved_data
        )
        return True
    except Exception:
        return False

def reset_session_progress_report(mode_label="Active Mode"):
    """
    Clears the old saved report as soon as the new bot session starts,
    and initializes fresh tracking for the current session.
    """
    global SESSION_STATS
    with _REPORT_LOCK:
        SESSION_STATS = _create_fresh_session_stats()
        SESSION_STATS["operating_mode_str"] = mode_label
        SESSION_STATS["speed_multiplier"] = BOT_SPEED_MULTIPLIER
        _save_report_to_disk_unlocked()

def _ensure_id_entry_unlocked(id_idx, id_name=None):
    key = str(id_idx)
    if key not in SESSION_STATS["per_id"]:
        role = "MAIN ID" if int(id_idx) <= 4 else "SECONDARY ID"
        SESSION_STATS["per_id"][key] = {
            "id_index": int(id_idx),
            "name": id_name if id_name else f"ID #{id_idx}",
            "role": role,
            "visits": 1,
            "attacks_ok": 0,
            "attacks_fail": 0,
            "buildings": 0,
            "walls": 0,
            "specials": 0
        }
    elif id_name and id_name != f"ID #{id_idx}":
        SESSION_STATS["per_id"][key]["name"] = id_name
    return SESSION_STATS["per_id"][key]

def set_report_active_id(id_idx, id_name=None, is_switch=False):
    with _REPORT_LOCK:
        SESSION_STATS["active_id_index"] = int(id_idx)
        if id_name:
            SESSION_STATS["active_id_name"] = str(id_name)
        entry = _ensure_id_entry_unlocked(id_idx, id_name)
        if is_switch:
            SESSION_STATS["id_switches"] += 1
            entry["visits"] += 1
        _save_report_to_disk_unlocked()

def record_stat(event_key, amount=1, id_idx=None):
    with _REPORT_LOCK:
        target_id = id_idx if id_idx is not None else SESSION_STATS["active_id_index"]
        entry = _ensure_id_entry_unlocked(target_id)
        if event_key in SESSION_STATS:
            SESSION_STATS[event_key] += amount
        if event_key == "attacks_success":
            entry["attacks_ok"] += amount
        elif event_key == "attacks_failed":
            entry["attacks_fail"] += amount
        elif event_key == "buildings_upgraded":
            entry["buildings"] += amount
        elif event_key == "walls_upgraded":
            entry["walls"] += amount
        elif event_key in ["spells_upgraded", "pets_upgraded", "equipments_upgraded"]:
            entry["specials"] = entry.get("specials", 0) + amount
        _save_report_to_disk_unlocked()

def record_duration(category, duration_sec):
    dur = max(0.0, float(duration_sec))
    with _REPORT_LOCK:
        if category == "attack":
            SESSION_STATS["attack_time_total"] += dur
            SESSION_STATS["attack_time_count"] += 1
        elif category == "upgrade":
            SESSION_STATS["upgrade_time_total"] += dur
            SESSION_STATS["upgrade_time_count"] += 1
        elif category == "id_switch":
            SESSION_STATS["id_switch_time_total"] += dur
            SESSION_STATS["id_switch_time_count"] += 1
        _save_report_to_disk_unlocked()

def _format_duration_hms(total_seconds):
    total_seconds = max(0, int(round(total_seconds)))
    hrs = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hrs:02d}h {mins:02d}m {secs:02d}s"

def _make_ascii_bar(value, max_val, width=22, fill_char="█", empty_char="░"):
    if max_val <= 0 or value <= 0:
        return empty_char * width
    filled = int(round((float(value) / float(max_val)) * width))
    filled = max(1, min(width, filled))
    return (fill_char * filled) + (empty_char * (width - filled))

def _make_segmented_pie_bar(segments, total_width=40):
    total_val = sum(val for _, val, _ in segments)
    if total_val <= 0:
        return "░" * total_width
    out = ""
    used_w = 0
    for idx, (label, val, color_code) in enumerate(segments):
        if val <= 0:
            continue
        w = int(round((float(val) / float(total_val)) * total_width))
        if idx == len(segments) - 1 or (used_w + w) > total_width:
            w = max(0, total_width - used_w)
        out += f"{color_code}{'█' * w}\033[0m"
        used_w += w
    if used_w < total_width:
        out += "░" * (total_width - used_w)
    return out

def print_previous_progress_report(report_stage="PAUSED / STOPPED", stats_override=None):
    with _REPORT_LOCK:
        target_stats = stats_override if isinstance(stats_override, dict) else SESSION_STATS
        is_saved_snapshot = (stats_override is not None)

        if is_saved_snapshot:
            now_ts = float(target_stats.get("session_end_ts", time.time()))
            now_dt_str = str(target_stats.get("session_end_str", "Unknown"))
            spd_disp = float(target_stats.get("speed_multiplier", BOT_SPEED_MULTIPLIER))
        else:
            now_ts = time.time()
            now_dt_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
            spd_disp = BOT_SPEED_MULTIPLIER
            _save_report_to_disk_unlocked()

        start_ts = float(target_stats.get("session_start_ts", now_ts))
        start_str = str(target_stats.get("session_start_str", "Unknown"))

        total_elapsed = max(0.0, now_ts - start_ts)
        paused_so_far = float(target_stats.get("total_paused_sec", 0.0))
        if (not is_saved_snapshot) and target_stats.get("current_pause_start_ts") is not None:
            paused_so_far += max(0.0, now_ts - float(target_stats["current_pause_start_ts"]))
        active_elapsed = max(0.0, total_elapsed - paused_so_far)

        C_RST = "\033[0m"
        C_BOLD = "\033[1m"
        C_CYN = "\033[96m"
        C_GRN = "\033[92m"
        C_YLW = "\033[93m"
        C_MAG = "\033[95m"
        C_RED = "\033[91m"
        C_BLU = "\033[94m"
        C_WHT = "\033[97m"

        atk_ok = int(target_stats.get("attacks_success", 0))
        atk_fail = int(target_stats.get("attacks_failed", 0))
        atk_total = atk_ok + atk_fail
        atk_rate = (atk_ok / float(atk_total) * 100.0) if atk_total > 0 else 100.0
        fail_rate = 100.0 - atk_rate

        bld_up = int(target_stats.get("buildings_upgraded", 0))
        wall_up = int(target_stats.get("walls_upgraded", 0))
        sp_up = int(target_stats.get("spells_upgraded", 0))
        pet_up = int(target_stats.get("pets_upgraded", 0))
        eq_up = int(target_stats.get("equipments_upgraded", 0))
        spec_up = sp_up + pet_up + eq_up
        total_up = bld_up + wall_up + spec_up

        atk_cnt = int(target_stats.get("attack_time_count", 0))
        atk_t_tot = float(target_stats.get("attack_time_total", 0.0))
        avg_atk_s = (atk_t_tot / float(atk_cnt)) if atk_cnt > 0 else 0.0

        upg_cnt = int(target_stats.get("upgrade_time_count", 0))
        upg_t_tot = float(target_stats.get("upgrade_time_total", 0.0))
        avg_upg_s = (upg_t_tot / float(upg_cnt)) if upg_cnt > 0 else 0.0

        sw_cnt = int(target_stats.get("id_switch_time_count", 0))
        sw_t_tot = float(target_stats.get("id_switch_time_total", 0.0))
        avg_sw_s = (sw_t_tot / float(sw_cnt)) if sw_cnt > 0 else 0.0

        other_active_t = max(0.0, active_elapsed - (atk_t_tot + upg_t_tot + sw_t_tot))
        denom_active = max(1.0, active_elapsed)
        pct_atk = min(100.0, (atk_t_tot / denom_active) * 100.0)
        pct_upg = min(100.0, (upg_t_tot / denom_active) * 100.0)
        pct_sw = min(100.0, (sw_t_tot / denom_active) * 100.0)
        pct_oth = max(0.0, 100.0 - (pct_atk + pct_upg + pct_sw))

        print(f"\n{C_CYN}{C_BOLD}╔══════════════════════════════════════════════════════════════════════════════╗{C_RST}")
        print(f"{C_CYN}{C_BOLD}║                  📊  PREVIOUS PROGRESS REPORT (BOT v9)  📊                   ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Report Status    :{C_RST} {C_BOLD}{C_GRN}{report_stage:<57}{C_RST}{C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Bot Mode & Speed :{C_RST} {C_WHT}{target_stats.get('operating_mode_str', 'N/A')} (Speed: {spd_disp:.2f}x){C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Start Date & Time:{C_RST} {C_WHT}{start_str:<57}{C_RST}{C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}End/Pause Time   :{C_RST} {C_WHT}{now_dt_str:<57}{C_RST}{C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Total Time Gap   :{C_RST} {C_BOLD}{C_CYN}{_format_duration_hms(total_elapsed)}{C_RST}  (Active: {C_GRN}{_format_duration_hms(active_elapsed)}{C_RST} | Paused: {C_MAG}{_format_duration_hms(paused_so_far)}{C_RST})")
        print(f"{C_CYN}║{C_RST} {C_YLW}Pause/Resume Cnt :{C_RST} Paused: {C_MAG}{target_stats.get('pause_count', 0)}x{C_RST} | Resumed: {C_GRN}{target_stats.get('resume_count', 0)}x{C_RST} | Wi-Fi Reloads: {C_CYN}{target_stats.get('connection_lost_reloads', 0)}x{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║              ⏱️  AVERAGE TIME CATEGORY & SPEED ANALYTICS  ⏱️                 ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠═════════════════════════╦══════════════════════════╦═════════════════════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_GRN}⚔ Avg Attack Time     {C_RST} {C_CYN}║{C_RST} {C_YLW}🏰 Avg Upgrade Loop Time{C_RST} {C_CYN}║{C_RST} {C_MAG}🔄 Avg ID Switch Time {C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_BOLD}{avg_atk_s:>7.1f}s{C_RST} ({atk_cnt:>3} runs)   {C_CYN}║{C_RST} {C_BOLD}{avg_upg_s:>7.1f}s{C_RST} ({upg_cnt:>3} loops)   {C_CYN}║{C_RST} {C_BOLD}{avg_sw_s:>7.1f}s{C_RST} ({sw_cnt:>3} switches) {C_CYN}║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠═════════════════════════╩══════════════════════════╩═════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║              🏆  COMBINED GRAND TOTALS (ALL IDS SUMMARY)  🏆                 ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════╦═══════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_GRN}✔ Successful Attacks   :{C_RST} {C_BOLD}{atk_ok:>10}{C_RST} {C_CYN}║{C_RST} {C_RED}✖ Unsuccessful/Restart :{C_RST} {C_BOLD}{atk_fail:>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_CYN}🔄 Total IDs Switched  :{C_RST} {C_BOLD}{target_stats.get('id_switches', 0):>10}{C_RST} {C_CYN}║{C_RST} {C_YLW}🏰 Buildings Upgraded  :{C_RST} {C_BOLD}{bld_up:>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_MAG}🧱 Walls Upgraded      :{C_RST} {C_BOLD}{wall_up:>10}{C_RST} {C_CYN}║{C_RST} {C_GRN}⚡ Combined Upgrades   :{C_RST} {C_BOLD}{total_up:>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_CYN}🧪 Spells/Pets/Equips  :{C_RST} {C_BOLD}{f'{sp_up}/{pet_up}/{eq_up}':>10}{C_RST} {C_CYN}║{C_RST} {C_RED}👺 Goblin Popups Cut   :{C_RST} {C_BOLD}{target_stats.get('goblin_popups_cut', 0):>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}✂ Wrong Buttons Cut    :{C_RST} {C_BOLD}{target_stats.get('wrong_buttons_cut', 0):>10}{C_RST} {C_CYN}║{C_RST} {C_BLU}💬 Clan Chat Closed    :{C_RST} {C_BOLD}{target_stats.get('clan_chat_closed', 0):>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_GRN}🎁 Daily Rewards Claim :{C_RST} {C_BOLD}{target_stats.get('daily_rewards_claimed', 0):>10}{C_RST} {C_CYN}║{C_RST} {C_MAG}👋 Welcome Chief Cut   :{C_RST} {C_BOLD}{target_stats.get('welcome_chief_closed', 0):>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_RED}🛠 Stuck/Loop Recoveries:{C_RST} {C_BOLD}{target_stats.get('stuck_recoveries', 0):>10}{C_RST} {C_CYN}║{C_RST} {C_YLW}⏳ Maintenance Breaks  :{C_RST} {C_BOLD}{target_stats.get('maintenance_breaks', 0):>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════╩═══════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║            🥧  PIE DISTRIBUTION CHARTS & VISUAL GRAPHS  🥧                   ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")

        time_pie_bar = _make_segmented_pie_bar([
            ("Attack", atk_t_tot, C_GRN),
            ("Upgrade", upg_t_tot, C_YLW),
            ("ID Switch", sw_t_tot, C_MAG),
            ("Other", other_active_t, C_BLU)
        ], total_width=44)
        print(f"{C_CYN}║{C_RST} {C_BOLD}Time Share Pie :{C_RST} [{time_pie_bar}]")
        print(f"{C_CYN}║{C_RST}   ├─ {C_GRN}█ Attack Time  : {pct_atk:5.1f}% ({_format_duration_hms(atk_t_tot)}){C_RST}   ├─ {C_YLW}█ Upgrade Time : {pct_upg:5.1f}% ({_format_duration_hms(upg_t_tot)}){C_RST}")
        print(f"{C_CYN}║{C_RST}   └─ {C_MAG}█ ID Switch    : {pct_sw:5.1f}% ({_format_duration_hms(sw_t_tot)}){C_RST}   └─ {C_BLU}█ Home/Checks  : {pct_oth:5.1f}% ({_format_duration_hms(other_active_t)}){C_RST}")

        atk_pie_bar = _make_segmented_pie_bar([
            ("Success", atk_ok, C_GRN),
            ("Restart/Fail", atk_fail, C_RED)
        ], total_width=44)
        print(f"{C_CYN}║{C_RST} {C_BOLD}Attack Pie     :{C_RST} [{atk_pie_bar}]")
        print(f"{C_CYN}║{C_RST}   ├─ {C_GRN}█ Success Ratio: {atk_rate:5.1f}% ({atk_ok} OK){C_RST}         └─ {C_RED}█ Retry/Fail   : {fail_rate:5.1f}% ({atk_fail} Retry){C_RST}")

        up_max = max(1, bld_up, wall_up)
        bld_bar = _make_ascii_bar(bld_up, up_max, width=26)
        wal_bar = _make_ascii_bar(wall_up, up_max, width=26)
        print(f"{C_CYN}║{C_RST} Building Upgrd : [{C_YLW}{bld_bar}{C_RST}] {C_BOLD}{bld_up:>5}{C_RST} Buildings")
        print(f"{C_CYN}║{C_RST} Wall Upgrades  : [{C_MAG}{wal_bar}{C_RST}] {C_BOLD}{wall_up:>5}{C_RST} Walls")

        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║          📋  PER-ID DETAILED BREAKDOWN (NAME, ATTACKS & UPGRADES)  📋        ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════╦══════════════════════╦══════════╦════════╦════════╦═════════╦═════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_BOLD}ID #{C_RST} {C_CYN}║{C_RST} {C_BOLD}Unique ID / Name    {C_RST} {C_CYN}║{C_RST} {C_BOLD}Role    {C_RST} {C_CYN}║{C_RST} {C_GRN}{C_BOLD}Atk OK{C_RST} {C_CYN}║{C_RST} {C_RED}{C_BOLD}Retry {C_RST} {C_CYN}║{C_RST} {C_YLW}{C_BOLD}Bld Up {C_RST} {C_CYN}║{C_RST} {C_MAG}{C_BOLD}Wall Up{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════╬══════════════════════╬══════════╬════════╬════════╬═════════╬═════════╣{C_RST}")

        per_id_map = target_stats.get("per_id", {})
        sorted_keys = sorted(per_id_map.keys(), key=lambda x: int(x))
        if not sorted_keys:
            print(f"{C_CYN}║{C_RST}  --  {C_CYN}║{C_RST} No ID activity yet   {C_CYN}║{C_RST}    --    {C_CYN}║{C_RST}      0 {C_CYN}║{C_RST}      0 {C_CYN}║{C_RST}       0 {C_CYN}║{C_RST}       0 {C_CYN}║{C_RST}")
        else:
            max_id_atk = max([1] + [int(per_id_map[k].get("attacks_ok", 0)) for k in sorted_keys])
            for k in sorted_keys:
                info = per_id_map[k]
                idx_str = f"#{info['id_index']}"
                uname = (info.get("name") or f"ID #{info['id_index']}")[:20]
                role_s = "MAIN" if int(info["id_index"]) <= 4 else "SECOND"
                a_ok = int(info.get("attacks_ok", 0))
                a_fl = int(info.get("attacks_fail", 0))
                b_u = int(info.get("buildings", 0))
                w_u = int(info.get("walls", 0))
                print(f"{C_CYN}║{C_RST} {C_BOLD}{idx_str:<4}{C_RST} {C_CYN}║{C_RST} {C_WHT}{uname:<20}{C_RST} {C_CYN}║{C_RST} {role_s:<8} {C_CYN}║{C_RST} {C_GRN}{a_ok:>6}{C_RST} {C_CYN}║{C_RST} {C_RED}{a_fl:>6}{C_RST} {C_CYN}║{C_RST} {C_YLW}{b_u:>7}{C_RST} {C_CYN}║{C_RST} {C_MAG}{w_u:>7}{C_RST} {C_CYN}║{C_RST}")

            print(f"{C_CYN}{C_BOLD}╠══════╩══════════════════════╩══════════╩════════╩════════╩═════════╩═════════╣{C_RST}")
            print(f"{C_CYN}{C_BOLD}║                        📊  PER-ID ATTACK GRAPH  📊                           ║{C_RST}")
            for k in sorted_keys:
                info = per_id_map[k]
                uname = (info.get("name") or f"ID #{info['id_index']}")[:14]
                bar_s = _make_ascii_bar(int(info.get("attacks_ok", 0)), max_id_atk, width=18)
                print(f"{C_CYN}║{C_RST} ID #{info['id_index']:<2} ({uname:<14}) [{C_GRN}{bar_s}{C_RST}] {C_BOLD}{info.get('attacks_ok', 0)}{C_RST} Atk | {C_YLW}{info.get('buildings', 0)}B{C_RST}/{C_MAG}{info.get('walls', 0)}W{C_RST}")

        print(f"{C_CYN}{C_BOLD}╚══════════════════════════════════════════════════════════════════════════════╝{C_RST}\n")

# ==========================================
# 0C. LIVE PAUSE ('ZX') & RESUME ('QW') ENGINE
# ==========================================
_PAUSE_STATE = {
    "paused": False,
    "resumed_just_now": False,
    "buffer": "",
    "listener_started": False
}
_PAUSE_LOCK = threading.Lock()

def _trigger_pause_state():
    with _REPORT_LOCK:
        SESSION_STATS["pause_count"] += 1
        SESSION_STATS["current_pause_start_ts"] = time.time()
        _save_report_to_disk_unlocked()
    print("\n======================================================================")
    print(f"|| [BOT PAUSED BY 'ZX'] Bot wahin ruk gaya hai (Speed={BOT_SPEED_MULTIPLIER:.2f}x Safe)! ||")
    print("|| Dubara Home Page se Resume karne ke liye 'QW' type karein...      ||")
    print("======================================================================")
    print_previous_progress_report(report_stage="PAUSED BY 'ZX' (LIVE SNAPSHOT)")

def _trigger_resume_state():
    global LAST_HOME_CLEANUP_TIME
    with _REPORT_LOCK:
        SESSION_STATS["resume_count"] += 1
        if SESSION_STATS["current_pause_start_ts"] is not None:
            SESSION_STATS["total_paused_sec"] += max(0.0, time.time() - SESSION_STATS["current_pause_start_ts"])
            SESSION_STATS["current_pause_start_ts"] = None
        _save_report_to_disk_unlocked()
    LAST_HOME_CLEANUP_TIME = 0.0
    print("\n======================================================================")
    print(f"|| [BOT RESUMED BY 'QW'] Home Page se wapas start (Speed={BOT_SPEED_MULTIPLIER:.2f}x)! ||")
    print("======================================================================\n")

def _keyboard_listener_worker():
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        use_cbreak = True
    except Exception:
        use_cbreak = False

    try:
        while True:
            if use_cbreak:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.15)
                if rlist:
                    ch = sys.stdin.read(1)
                    if not ch:
                        time.sleep(0.1)
                        continue
                    do_pause = False
                    do_resume = False
                    with _PAUSE_LOCK:
                        _PAUSE_STATE["buffer"] = (_PAUSE_STATE["buffer"] + ch.lower())[-12:]
                        buf = _PAUSE_STATE["buffer"]
                        if not _PAUSE_STATE["paused"] and "zx" in buf:
                            _PAUSE_STATE["paused"] = True
                            _PAUSE_STATE["buffer"] = ""
                            do_pause = True
                        elif _PAUSE_STATE["paused"] and "qw" in buf:
                            _PAUSE_STATE["paused"] = False
                            _PAUSE_STATE["resumed_just_now"] = True
                            _PAUSE_STATE["buffer"] = ""
                            do_resume = True
                    if do_pause:
                        _trigger_pause_state()
                    elif do_resume:
                        _trigger_resume_state()
            else:
                line = sys.stdin.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                clean_line = line.strip().lower()
                do_pause = False
                do_resume = False
                with _PAUSE_LOCK:
                    if not _PAUSE_STATE["paused"] and "zx" in clean_line:
                        _PAUSE_STATE["paused"] = True
                        do_pause = True
                    elif _PAUSE_STATE["paused"] and "qw" in clean_line:
                        _PAUSE_STATE["paused"] = False
                        _PAUSE_STATE["resumed_just_now"] = True
                        do_resume = True
                if do_pause:
                    _trigger_pause_state()
                elif do_resume:
                    _trigger_resume_state()
    except Exception:
        pass
    finally:
        if use_cbreak:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

def start_pause_resume_listener():
    with _PAUSE_LOCK:
        if _PAUSE_STATE["listener_started"]:
            return
        _PAUSE_STATE["listener_started"] = True
    # Keep Android screen awake while bot is running so device never auto-sleeps!
    try:
        subprocess.run(["adb", "shell", "svc", "power", "stayon", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
    except Exception:
        pass
    t = threading.Thread(target=_keyboard_listener_worker, daemon=True)
    t.start()

def check_pause_point(allow_raise=True):
    was_paused = False
    while True:
        with _PAUSE_LOCK:
            is_paused = _PAUSE_STATE["paused"]
            resumed_flag = _PAUSE_STATE["resumed_just_now"]
        if is_paused:
            was_paused = True
            time.sleep(0.20)
            continue
        if was_paused or resumed_flag:
            with _PAUSE_LOCK:
                _PAUSE_STATE["resumed_just_now"] = False
            if allow_raise:
                raise BotPausedResumeHomeException("Resumed via QW -> Resetting to Home Page")
        break

def smart_sleep(seconds, apply_speed=True, min_floor=0.08):
    raw_sec = max(0.0, float(seconds))
    if raw_sec <= 0.0:
        check_pause_point(allow_raise=True)
        return
    dur = scale_time_by_speed(raw_sec, min_floor=min_floor) if apply_speed else raw_sec
    end_time = time.time() + dur
    while time.time() < end_time:
        check_pause_point(allow_raise=True)
        rem = end_time - time.time()
        if rem <= 0:
            break
        time.sleep(min(0.18, rem))
        check_pause_point(allow_raise=True)

# ==========================================
# 1. WRONG BUTTON, CLAN CHAT, WELCOME CHIEF, DAILY REWARD, MAINTENANCE & CONNECTION LOST COORDS
# ==========================================
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
MAINTENANCE_REST_SEC = 600.0

CONNECTION_LOST_OUTER_BOX = (751, 684, 1733, 1017)
CONNECTION_LOST_TEXT_BOX_LEFT = (773, 690, 1059, 767)
CONNECTION_LOST_TEXT_BOX_WIDE = (773, 690, 1773, 767)
TRY_AGAIN_BTN_BOX = (1053, 934, 1460, 1022)
TRY_AGAIN_CLICK_COORD = (1256, 978)

CONNECTION_OCR_INTERVAL_SEC = 300.0   # 5 Minutes periodic OCR check
CONNECTION_RETRY_GAP_SEC = 300.0      # 5 Minutes gap between reload attempts
CONNECTION_MAX_ATTEMPTS = 5           # 5 reload attempts
CONNECTION_MAX_OUTAGE_SEC = 3600.0    # 1 Hour (60 Minutes) maximum recovery window before auto-sleep & exit

HOME_PAGE_CHECK_COORDS = [(2050, 285), (2050, 250)]

GOLD_STORAGE_BAR = (2170, 63)
ELIXIR_STORAGE_BAR = (2166, 128)
GOLD_STORAGE_CHECK_BOX = (2015, 43, 2081, 78)
ELIXIR_STORAGE_CHECK_BOX = (2003, 116, 2103, 151)

WALL_GOLD_STORAGE_CHECK_BOX = (1947, 44, 2015, 76)
WALL_ELIXIR_STORAGE_CHECK_BOX = (1947, 115, 2015, 149)

# ==========================================
# 2. UPGRADE SYSTEM COORDINATES (SAMSUNG GALAXY A14 - V8 + V9 EXTENSIONS)
# ==========================================
ENABLE_CONDITION_2 = True

UPGRADE_A14 = {
    "BUILD_CLICK": (2233, 948),
    "BUILDER_CHECK_BOX": (1754, 1008, 1847, 1038),
    "UPGRADE_LIST_BOX": (1820, 545, 2312, 926),
    "UPGRADE_LIST_BOX_INITIAL": (1820, 545, 2312, 926),
    "UPGRADE_LIST_BOX_EXPANDED": (1818, 95, 2311, 925),
    "CLOSE_MENU": (2322, 45),

    # Filter Select Process (V9)
    "FILTER_ENTER_BTN": (1788, 43),
    "FILTER_SELECT_BTN": (1145, 715),
    "FILTER_BACK_BTN": (2021, 51),

    "C1_CLICK_1": (1780, 46),
    "C1_CLICK_2": (1392, 707),
    "C1_CLICK_3": (2048, 54),
    "SCROLL_START": (2050, 863),
    "SCROLL_END": (2050, 542),
    "C1_CONFIRM_CLICK": (1582, 930),
    "C1_WRONG_BTN": (1589, 339),
    "C1_REOPEN_LIST": (2050, 56),

    "WALL_STEP_A1_CLICK": (439, 851),
    "WALL_NAME_CHECK_BOX": (1018, 45, 1400, 108),
    "WALL_REOPEN_LIST_CLICK": (2062, 54),
    "WALL_CONFIRM_CLICK": (1595, 942),

    # Special Upgrade Tabs (Spells, Pets, Equipments)
    "SPELL_CHECK_BOX": (1915, 1007, 2007, 1046),
    "SPELL_TAB_CLICK": (1961, 1026),
    "PET_CHECK_BOX": (2085, 1006, 2195, 1042),
    "PET_TAB_CLICK": (2183, 1023),
    "EQUIPMENT_TAB_CLICK": (2121, 1011),

    # Goblin Builder Popup Coords
    "GOBLIN_PAGE_BOX": (1134, 193, 2009, 735),
    "GOBLIN_CHIEF_BOX": (1420, 203, 1714, 282),
    "GOBLIN_LETTER_BOX": (1154, 330, 1980, 493),
    "GOBLIN_RED_X_BOX": (1927, 209, 1996, 266),
    "GOBLIN_RED_X_CLICK": (1961, 237),

    "C2_STEP_1": (960, 845),
    "C2_STEP_2": (1580, 930),
    "C2_RED_X": (1590, 326),
    "C2_RED_X_NEXT": (2065, 51),
    "C2_RED_X_ALT_1": (1162, 841),
    "C2_RED_X_ALT_2": (1587, 928),
    "C2_NO_RED_ALT_1": (1172, 835),
    "C2_NO_RED_ALT_2": (1586, 927),
    "C2_FOUR_CLICK": (2080, 50)
}

CARD_GEOMETRY = {
    "CARD_X1": 1820,
    "CARD_X2": 2312,
    "CARD_HEIGHT": 81,
    "NAME_X1": 1823,
    "NAME_X2": 2124,
    "NAME_DY1": 5,
    "NAME_DY2": 41,
    "TIME_X1": 2241,
    "TIME_X2": 2310,
    "TIME_DY1": 2,
    "TIME_DY2": 35,
    "COST_X1": 2108,
    "COST_X2": 2252,
    "COST_DY1": 33,
    "COST_DY2": 78
}

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

# ==========================================
# 3. FAST ATTACK COORDINATES (A14 - V8 + V9 DYNAMIC SCANNER)
# ==========================================
FAST_ATTACK = {
    "BATTLE_BTN": (182, 961),
    "FIND_MATCH_BTN": (364, 808),
    "ATTACK_BTN": (1980, 972),

    "ARMY_CARD_SCAN_BOX": (355, 884, 2213, 1071),

    "SPELL_SELECT": (1527, 983),
    "SPELL_DEPLOY_LIST": [
        (378, 469), (594, 350), (566, 569), (691, 461),
        (864, 278), (812, 760), (928, 569), (915, 444),
        (1170, 580), (1070, 250), (892, 815)
    ],

    "ARMY_1_SELECT": (470, 988),
    "ARMY_1_DEPLOY_LIST": [
        (325, 525), (225, 510), (303, 473), (292, 592),
        (222, 516), (453, 363), (337, 611), (256, 512),
        (375, 524)
    ],
    "ARMY_DEPLOY_LIST": [
        (325, 525), (225, 510), (303, 473), (292, 592),
        (222, 516), (453, 363), (337, 611), (256, 512),
        (375, 524)
    ],

    "ARMY_2_SELECT": (590, 985),
    "ARMY_2_DEPLOY_LIST": [
        (243, 522), (318, 527), (355, 465)
    ],

    "SIEGE_SELECT": (770, 977),
    "SIEGE_DEPLOY_LIST": [
        (325, 525), (225, 510), (303, 473), (292, 592)
    ],
    "HERO_1_SELECT": (925, 1005),
    "HERO_2_SELECT": (1073, 987),
    "HERO_3_SELECT": (1218, 990),
    "HERO_4_SELECT": (1350, 978),

    "SURRENDER_BTN": (181, 800),
    "OKAY_BTN": (1419, 701),
    "RETURN_HOME_BTN": (1222, 918)
}

# ==========================================
# 3B. SUPERCELL ID SWITCH SYSTEM COORDINATES (100% RESTORED ORIGINAL BOT v8)
# ==========================================
ID_SWITCH_A14 = {
    "PROFILE_BTN": (142, 122),
    "SETTINGS_BTN": (1755, 92),
    "SWITCH_ICON_BTN": (1507, 207),
    "CLOSE_SWITCH_PANEL_BTN": (135, 80),

    "LIST_BOX_CORNERS": (135, 150, 2370, 1040),
    "SUPERCELL_LOGO_BOX": (335, 502, 710, 518),
    "SUPERCELL_LOGO_OCR_BOX": (325, 465, 725, 550),
    "DIVIDER_X": 1118,

    "FIRST_CARD_BOX": (1158, 209, 2376, 434),
    "PROFILE_ICON_BOX": (1187, 237, 1340, 386),
    "UNIQUE_ID_BOX": (1350, 236, 1940, 292),
    "ID_NAME_BOX": (1190, 300, 1429, 353),
    "TOWN_HALL_BOX": (1348, 360, 1662, 396),
    "LEAGUE_BOX": (2162, 265, 2335, 368),

    "CARD_HEIGHT": 225,
    "CARD_STEP_Y": 242,
    "UNIQUE_ID_REL_Y1": 27,
    "UNIQUE_ID_REL_Y2": 83,
    "ID_NAME_REL_Y1": 91,
    "ID_NAME_REL_Y2": 144,
    "TH_REL_Y1": 151,
    "TH_REL_Y2": 187,

    "ID_1_CLICK": (1763, 321),
    "ID_2_CLICK": (1763, 563),
    "ID_3_CLICK": (1763, 800),
    "ID_4_CLICK": (1763, 1044),
    "ID_SLOTS": [
        (1763, 321),
        (1763, 563),
        (1763, 800),
        (1763, 1044)
    ],

    # Restored 100% Original Bot v8 Scroll & Timing Coordinates
    "SCROLL_START": (1763, 1030),
    "SCROLL_END": (1763, 215),
    "SCROLL_DURATION_MS": 1050,

    "ID_INITIAL_WAIT_SEC": 3.5,
    "ID_POLL_INTERVAL_SEC": 1.0,
    "ID_LOAD_WAIT_SEC": 30.0
}

# ==========================================
# 4. PERSISTENT ADB SHELL, SCREENSHOT, 1-HOUR DEVICE WATCHDOG & HOME ZOOM-OUT
# ==========================================
_ADB_SHELL_PROC = None
_ADB_LOCK = threading.Lock()
_MONKEY_SCRIPT_READY = False

_SCREENSHOT_CACHE = {
    "img": None,
    "timestamp": 0.0
}
LAST_HOME_CLEANUP_TIME = 0.0
LAST_DETECTED_BUILDERS = None
LAST_BUILDER_CHECK_TIME = 0.0
LAST_GOBLIN_DETECTED = False
_LAST_CONN_LOST_OCR_TIME = 0.0
_IN_CONN_LOST_HANDLER = False

def reset_goblin_detected_flag():
    global LAST_GOBLIN_DETECTED
    LAST_GOBLIN_DETECTED = False

def was_goblin_detected():
    return bool(LAST_GOBLIN_DETECTED)

def _invalidate_screen_cache():
    _SCREENSHOT_CACHE["img"] = None
    _SCREENSHOT_CACHE["timestamp"] = 0.0

def reset_persistent_adb_shell():
    global _ADB_SHELL_PROC
    with _ADB_LOCK:
        if _ADB_SHELL_PROC is not None:
            try:
                _ADB_SHELL_PROC.stdin.close()
            except Exception:
                pass
            try:
                _ADB_SHELL_PROC.terminate()
            except Exception:
                pass
            _ADB_SHELL_PROC = None

def _shutdown_bot_into_sleep_mode(reason="1-Hour Connection/Device Outage Limit Reached"):
    """
    Puts the device screen to sleep (keyevent 223) ONLY after a genuine 1-hour (60-minute) outage,
    saves and prints the final Previous Progress Report, and terminates the bot cleanly!
    """
    print("\n==============================================================================")
    print(f"|| [AUTO-SLEEP & SHUTDOWN] {reason}")
    print("|| Device ko Sleep Mode me bhej kar Bot ko safely band kiya ja raha hai...  ||")
    print("==============================================================================")
    try:
        subprocess.run(["adb", "shell", "svc", "power", "stayon", "false"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        subprocess.run(["adb", "shell", "input", "keyevent", "223"], timeout=4)
    except Exception:
        pass
    try:
        print_previous_progress_report(report_stage=f"AUTO-SHUTDOWN ({reason})")
    except Exception:
        pass
    os._exit(0)

def _exec_adb_shell_cmd(cmd_str):
    global _ADB_SHELL_PROC
    _invalidate_screen_cache()
    with _ADB_LOCK:
        try:
            if _ADB_SHELL_PROC is None or _ADB_SHELL_PROC.poll() is not None:
                _ADB_SHELL_PROC = subprocess.Popen(
                    ["adb", "shell"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )
            _ADB_SHELL_PROC.stdin.write(cmd_str + "\n")
            _ADB_SHELL_PROC.stdin.flush()
            return
        except Exception:
            _ADB_SHELL_PROC = None
    try:
        subprocess.run(["adb", "shell", cmd_str], timeout=5)
    except Exception:
        pass

def zoom_out_village_a14(passes=2, reason="HOME PAGE VIEW"):
    """
    HOME-PAGE-ONLY SYMMETRIC 2-FINGER PINCH-IN ZOOM-OUT:
    Uses center-symmetric 2-finger PinchZoom around screen center (1200, 540).
    """
    global _MONKEY_SCRIPT_READY
    check_pause_point(allow_raise=True)
    _invalidate_screen_cache()
    print(f" [HOME ZOOM-OUT] Executing Symmetric 2-Finger Pinch-In ({passes}x) on Home Page [{reason}]...")

    try:
        if not _MONKEY_SCRIPT_READY:
            mks_content = (
                "type= raw events\n"
                "count= 1\n"
                "speed= 1.0\n"
                "start data >>\n"
                "PinchZoom(400,200,1100,500,2000,880,1300,580,18)\n"
                "UserWait(120)\n"
                "PinchZoom(400,200,1100,500,2000,880,1300,580,18)\n"
            )
            setup_cmd = f"cat << 'EOM' > /data/local/tmp/coc_pinch_out.mks\n{mks_content}EOM\n"
            subprocess.run(["adb", "shell", setup_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            _MONKEY_SCRIPT_READY = True

        subprocess.run(
            ["adb", "shell", "monkey -f /data/local/tmp/coc_pinch_out.mks 1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
    except Exception:
        _MONKEY_SCRIPT_READY = False

    human_sleep(0.20, 0.03)
    tap(*GOLD_STORAGE_BAR, delay_range=(0.04, 0.07), jitter=2)
    record_stat("zoom_outs_done", 1)
    _invalidate_screen_cache()

def human_sleep(base_sec, variance=0.04, apply_speed=True, min_floor=0.08):
    check_pause_point(allow_raise=True)
    raw_t = max(0.02, float(base_sec) + random.uniform(-variance, variance))
    smart_sleep(raw_t, apply_speed=apply_speed, min_floor=min_floor)

def tap(x, y, delay_range=(0.03, 0.07), jitter=2, check_pause=True, apply_speed=True):
    if check_pause:
        check_pause_point(allow_raise=True)
    jx = int(x) + random.randint(-jitter, jitter)
    jy = int(y) + random.randint(-jitter, jitter)
    _exec_adb_shell_cmd(f"input tap {jx} {jy}")
    if delay_range and delay_range[1] > 0:
        wait_t = random.uniform(*delay_range)
        if apply_speed:
            wait_t = scale_time_by_speed(wait_t, min_floor=0.025)
        if check_pause:
            smart_sleep(wait_t, apply_speed=False)
        else:
            time.sleep(wait_t)

def fast_serial_taps(coord_list, rounds=1, jitter=2):
    check_pause_point(allow_raise=True)
    cmds = []
    for _ in range(rounds):
        for (x, y) in coord_list:
            jx = int(x) + random.randint(-jitter, jitter)
            jy = int(y) + random.randint(-jitter, jitter)
            cmds.append(f"input tap {jx} {jy}")
    if cmds:
        _exec_adb_shell_cmd("; ".join(cmds))

def batch_tap_sequence(coord_list, inter_delay=0.04, jitter=2):
    check_pause_point(allow_raise=True)
    cmds = []
    scaled_gap = scale_time_by_speed(inter_delay, min_floor=0.025) if inter_delay > 0 else 0.0
    for idx, (x, y) in enumerate(coord_list):
        jx = int(x) + random.randint(-jitter, jitter)
        jy = int(y) + random.randint(-jitter, jitter)
        cmds.append(f"input tap {jx} {jy}")
        if scaled_gap >= 0.08 and idx < len(coord_list) - 1:
            cmds.append(f"sleep {scaled_gap:.2f}")
    if cmds:
        _exec_adb_shell_cmd("; ".join(cmds))
    if 0 < scaled_gap < 0.08:
        smart_sleep(0.04, apply_speed=False)

def swipe(x1, y1, x2, y2, duration=350, post_sleep=0.38, apply_speed=True):
    check_pause_point(allow_raise=True)
    sx1 = int(x1) + random.randint(-3, 3)
    sy1 = int(y1) + random.randint(-3, 3)
    sx2 = int(x2) + random.randint(-3, 3)
    sy2 = int(y2) + random.randint(-3, 3)
    if apply_speed:
        scaled_dur = int(max(220, scale_time_by_speed(duration, min_floor=220) + random.randint(-15, 20)))
    else:
        scaled_dur = int(max(220, duration + random.randint(-15, 20)))
    _exec_adb_shell_cmd(f"input swipe {sx1} {sy1} {sx2} {sy2} {scaled_dur}")
    human_sleep(post_sleep, 0.04, apply_speed=apply_speed, min_floor=0.12)

def _capture_raw_screenshot_once():
    """Attempts to capture a single screenshot via RAM pipe or fallback file. Returns PIL Image or None."""
    try:
        proc = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=6
        )
        if proc.returncode == 0 and proc.stdout and len(proc.stdout) > 1024:
            bio = io.BytesIO(proc.stdout)
            loaded_img = Image.open(bio)
            loaded_img.load()
            img = loaded_img.convert("RGB")
            bio.close()
            return img
    except Exception:
        pass

    try:
        if os.path.exists("screen.png"):
            os.remove("screen.png")
        subprocess.run("adb exec-out screencap -p > screen.png", shell=True, timeout=6)
        if os.path.exists("screen.png") and os.path.getsize("screen.png") > 1024:
            return Image.open("screen.png").convert("RGB")
    except Exception:
        pass
    return None

def get_screenshot(check_pause=True, force_fresh=False):
    """
    In-Memory RAM Screenshot with:
      1. 0.24s micro-cache.
      2. Automatic 1-Hour Device/ADB Disconnect Recovery Loop.
      3. Safe 5-Minute Periodic 'Connection lost / Try again' Check (Never false-triggers sleep!).
    """
    global _LAST_CONN_LOST_OCR_TIME, _IN_CONN_LOST_HANDLER
    if check_pause:
        check_pause_point(allow_raise=True)

    now = time.time()
    if (not force_fresh) and (_SCREENSHOT_CACHE["img"] is not None) and ((now - _SCREENSHOT_CACHE["timestamp"]) <= 0.24):
        return _SCREENSHOT_CACHE["img"]

    img = _capture_raw_screenshot_once()

    if img is None:
        outage_start = time.time()
        attempt_no = 1
        while img is None:
            elapsed_outage = time.time() - outage_start
            if elapsed_outage >= CONNECTION_MAX_OUTAGE_SEC:
                _shutdown_bot_into_sleep_mode("Device/ADB Unresponsive for 1 Full Hour (60 Mins)")
            print(f" [!] [DEVICE/ADB ERROR #{attempt_no}] Screenshot failed ({elapsed_outage/60.0:.1f}m / 60.0m)! Waking screen & retrying in 15s...")
            reset_persistent_adb_shell()
            try:
                subprocess.run(["adb", "reconnect"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["adb", "shell", "input", "keyevent", "224"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                subprocess.run(["adb", "shell", "svc", "power", "stayon", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            except Exception:
                pass
            time.sleep(15.0)
            img = _capture_raw_screenshot_once()
            attempt_no += 1

    _SCREENSHOT_CACHE["img"] = img
    _SCREENSHOT_CACHE["timestamp"] = time.time()

    if (not _IN_CONN_LOST_HANDLER) and ((time.time() - _LAST_CONN_LOST_OCR_TIME) >= CONNECTION_OCR_INTERVAL_SEC):
        _LAST_CONN_LOST_OCR_TIME = time.time()
        if check_and_handle_connection_lost_a14(img, force_ocr=False):
            img = _capture_raw_screenshot_once() or img
            _SCREENSHOT_CACHE["img"] = img
            _SCREENSHOT_CACHE["timestamp"] = time.time()

    return img

def clean_ram_garbage():
    _invalidate_screen_cache()
    reset_persistent_adb_shell()
    gc.collect()

# ==========================================
# 5. CONNECTION LOST / TRY AGAIN AUTO-RELOAD (FIXED FALSE-POSITIVE SLEEP BUG!)
# ==========================================

def _has_connection_lost_dark_box_pixels(img):
    """
    Strict Pixel Pre-Check for the 'Connection lost' dark charcoal dialog box
    at (751, 684) to (1733, 1017).
    NEVER triggers if Home Page Green '+' or Upgrade Menu Red 'X' is visible!
    """
    if is_on_home_page_a14(img):
        return False
    if is_red_x_box_at(img, *UPGRADE_A14["CLOSE_MENU"], radius=14):
        return False

    w, h = img.size
    px_map = img.load()
    ox1, oy1, ox2, oy2 = CONNECTION_LOST_OUTER_BOX

    dark_slate_px = 0
    total_bg_px = 0
    for sy in range(max(0, oy1 + 25), min(h, oy2 - 25), 14):
        for sx in range(max(0, ox1 + 35), min(w, ox2 - 35), 28):
            r, g, b = px_map[sx, sy]
            total_bg_px += 1
            if (26 <= r <= 64) and (28 <= g <= 66) and (30 <= b <= 70) and (max(r, g, b) - min(r, g, b) <= 12):
                dark_slate_px += 1

    if total_bg_px == 0 or (dark_slate_px / float(total_bg_px)) < 0.65:
        return False

    tx1, ty1, tx2, ty2 = CONNECTION_LOST_TEXT_BOX_LEFT
    header_white_px = 0
    for sy in range(max(0, ty1), min(h, ty2), 3):
        for sx in range(max(0, tx1), min(w, tx2), 4):
            r, g, b = px_map[sx, sy]
            if r > 200 and g > 200 and b > 200 and (max(r, g, b) - min(r, g, b) <= 22):
                header_white_px += 1

    bx1, by1, bx2, by2 = TRY_AGAIN_BTN_BOX
    btn_white_px = 0
    for sy in range(max(0, by1), min(h, by2), 3):
        for sx in range(max(0, bx1), min(w, bx2), 4):
            r, g, b = px_map[sx, sy]
            if r > 200 and g > 200 and b > 200 and (max(r, g, b) - min(r, g, b) <= 22):
                btn_white_px += 1

    return header_white_px >= 12 and btn_white_px >= 10

def _ocr_white_text_on_dark_box(img, box_coords):
    w, h = img.size
    x1, y1, x2, y2 = box_coords
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if (x2 - x1) < 15 or (y2 - y1) < 12:
        return ""

    crop = img.crop((x1, y1, x2, y2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    uw, uh = upscaled.size
    src = upscaled.load()

    bw = Image.new("L", (uw, uh), 255)
    dst = bw.load()
    ink_px = 0
    for py in range(uh):
        for px in range(uw):
            r, g, b = src[px, py]
            if r > 170 and g > 170 and b > 170 and (max(r, g, b) - min(r, g, b) <= 32):
                dst[px, py] = 0
                ink_px += 1

    if ink_px < 12:
        return ""
    padded = ImageOps.expand(bw, border=12, fill=255)
    return pytesseract.image_to_string(padded, config="--oem 3 --psm 6").strip()

def is_connection_lost_popup_visible_a14(img, force_ocr=False):
    """
    STRICT CONNECTION LOST VERIFIER:
    Always requires the dark charcoal dialog box pixels to be present FIRST so it NEVER
    falsely triggers on normal gameplay screens!
    """
    has_pixels = _has_connection_lost_dark_box_pixels(img)
    if not has_pixels:
        return False, ""

    header_txt = _ocr_white_text_on_dark_box(img, CONNECTION_LOST_TEXT_BOX_LEFT)
    if not header_txt:
        header_txt = _ocr_white_text_on_dark_box(img, CONNECTION_LOST_TEXT_BOX_WIDE)
    btn_txt = _ocr_white_text_on_dark_box(img, TRY_AGAIN_BTN_BOX)

    combined_clean = re.sub(r"[^a-zA-Z\s]", " ", f"{header_txt} {btn_txt}").lower()
    combined_clean = re.sub(r"\s+", " ", combined_clean).strip()

    strict_phrases = ["connection lost", "conection lost", "try again", "connection", "conection", "lost connection"]
    if any(phrase in combined_clean for phrase in strict_phrases):
        return True, f"Header='{header_txt}' | Button='{btn_txt}'"

    return False, ""

def check_and_handle_connection_lost_a14(img=None, force_ocr=False):
    global _IN_CONN_LOST_HANDLER, _LAST_CONN_LOST_OCR_TIME
    if _IN_CONN_LOST_HANDLER:
        return False

    _IN_CONN_LOST_HANDLER = True
    try:
        if img is None:
            img = _capture_raw_screenshot_once()
            if img is None:
                return False

        is_lost, ocr_info = is_connection_lost_popup_visible_a14(img, force_ocr=force_ocr)
        _LAST_CONN_LOST_OCR_TIME = time.time()
        if not is_lost:
            return False

        outage_start_t = time.time()
        attempt = 1

        while True:
            elapsed_total = time.time() - outage_start_t
            print("\n==============================================================================")
            print(f"|| [📡 CONNECTION LOST DETECTED] {ocr_info}")
            print(f"|| [RELOAD ATTEMPT #{attempt}/{CONNECTION_MAX_ATTEMPTS}] Clicking 'Try again' (1256, 978)... (Outage: {elapsed_total/60.0:.1f}m / 60.0m)")
            print("==============================================================================")

            record_stat("connection_lost_reloads", 1)
            tap(*TRY_AGAIN_CLICK_COORD, delay_range=(0.18, 0.30), jitter=4, check_pause=False, apply_speed=False)

            smart_sleep(10.0, apply_speed=False)

            chk_img = _capture_raw_screenshot_once()
            if chk_img is not None:
                still_lost, _ = is_connection_lost_popup_visible_a14(chk_img, force_ocr=False)
                if not still_lost:
                    smart_sleep(5.0, apply_speed=False)
                    chk_img2 = _capture_raw_screenshot_once()
                    if chk_img2 is not None:
                        still_lost2, _ = is_connection_lost_popup_visible_a14(chk_img2, force_ocr=False)
                        if not still_lost2:
                            print(f" [✔] [WIFI RECONNECTED] Game reloaded successfully on Attempt #{attempt}!")
                            _LAST_CONN_LOST_OCR_TIME = time.time()
                            return True

            elapsed_total = time.time() - outage_start_t
            if elapsed_total >= CONNECTION_MAX_OUTAGE_SEC:
                _shutdown_bot_into_sleep_mode(
                    f"Wi-Fi / Server Connection Lost for 1 Full Hour ({attempt} Reload Attempts Failed)"
                )

            rem_window = max(30.0, min(CONNECTION_RETRY_GAP_SEC, CONNECTION_MAX_OUTAGE_SEC - elapsed_total))
            print(f" [⏳ WIFI RECOVERY WAIT] Connection still down after Attempt #{attempt}. Waiting {rem_window/60.0:.1f} minutes before next Try Again click...")
            wait_end = time.time() + rem_window
            recovered_during_wait = False

            while time.time() < wait_end:
                smart_sleep(min(30.0, max(1.0, wait_end - time.time())), apply_speed=False)
                probe_img = _capture_raw_screenshot_once()
                if probe_img is not None:
                    lost_now, _ = is_connection_lost_popup_visible_a14(probe_img, force_ocr=False)
                    if not lost_now and is_on_home_page_a14(probe_img):
                        print(" [✔] [WIFI RECOVERED] Home Page detected during recovery wait!")
                        recovered_during_wait = True
                        break

            if recovered_during_wait:
                _LAST_CONN_LOST_OCR_TIME = time.time()
                return True

            attempt += 1
            fresh_img = _capture_raw_screenshot_once()
            if fresh_img is not None:
                _, ocr_info = is_connection_lost_popup_visible_a14(fresh_img, force_ocr=False)
                if not ocr_info:
                    ocr_info = "Connection still offline / retrying reload"
    finally:
        _IN_CONN_LOST_HANDLER = False

# ==========================================
# 6. STRICT POPUP, GOBLIN BUILDER & SCREEN SCANNERS
# ==========================================
def is_red_x_box_at(img, cx, cy, radius=10):
    w, h = img.size
    px_map = img.load()
    red_count = 0
    white_count = 0
    for dy in range(-radius, radius + 1, 2):
        for dx in range(-radius, radius + 1, 2):
            px = min(max(0, cx + dx), w - 1)
            py = min(max(0, cy + dy), h - 1)
            r, g, b = px_map[px, py]
            if r > 182 and g < 72 and b < 72 and (r > g + 115):
                red_count += 1
            elif r > 215 and g > 215 and b > 215 and (max(r, g, b) - min(r, g, b) <= 25):
                white_count += 1
    return red_count >= 7 and white_count >= 2

def find_red_x_in_box_a14(img, box_coords):
    """
    Scans an entire rectangular box (x1, y1, x2, y2) for a Red 'X' close button.
    Returns (True, click_x, click_y) if found, else (False, center_x, center_y).
    """
    w, h = img.size
    px_map = img.load()
    x1, y1, x2, y2 = box_coords
    x1, x2 = max(0, min(x1, x2)), min(w - 1, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h - 1, max(y1, y2))

    red_xs = []
    red_ys = []
    white_count = 0

    for sy in range(y1, y2 + 1, 2):
        for sx in range(x1, x2 + 1, 2):
            r, g, b = px_map[sx, sy]
            if r > 178 and g < 78 and b < 78 and (r > g + 105):
                red_xs.append(sx)
                red_ys.append(sy)
            elif r > 210 and g > 210 and b > 210 and (max(r, g, b) - min(r, g, b) <= 28):
                white_count += 1

    if len(red_xs) >= 14 and white_count >= 3:
        cx = sum(red_xs) // len(red_xs)
        cy = sum(red_ys) // len(red_ys)
        return True, cx, cy

    return False, (x1 + x2) // 2, (y1 + y2) // 2

def _ocr_dual_polarity_box(img, box_coords):
    """
    Runs both White-Text OCR and Dark-Text OCR on a given box so text is 100% read
    whether it is white text on a dark header or dark text on a light parchment dialog!
    """
    w, h = img.size
    x1, y1, x2, y2 = box_coords
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if (x2 - x1) < 12 or (y2 - y1) < 10:
        return ""

    crop = img.crop((x1, y1, x2, y2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    uw, uh = upscaled.size
    src = upscaled.load()

    # Pass 1: White/Bright Text Filter (e.g. "Chief!", "All Builders Busy", "Hire")
    bw_white = Image.new("L", (uw, uh), 255)
    dst_w = bw_white.load()
    ink_w = 0

    # Pass 2: Dark Text Filter (e.g. dark letters inside Goblin parchment box)
    bw_dark = Image.new("L", (uw, uh), 255)
    dst_d = bw_dark.load()
    ink_d = 0

    for py in range(uh):
        for px in range(uw):
            r, g, b = src[px, py]
            if r > 185 and g > 185 and b > 185 and (max(r, g, b) - min(r, g, b) <= 38):
                dst_w[px, py] = 0
                ink_w += 1
            if r < 105 and g < 105 and b < 105 and (max(r, g, b) - min(r, g, b) <= 40):
                dst_d[px, py] = 0
                ink_d += 1

    out_texts = []
    if ink_w >= 10:
        pad_w = ImageOps.expand(bw_white, border=12, fill=255)
        t_w = pytesseract.image_to_string(pad_w, config="--oem 3 --psm 6").strip()
        if t_w:
            out_texts.append(t_w)
    if ink_d >= 10:
        pad_d = ImageOps.expand(bw_dark, border=12, fill=255)
        t_d = pytesseract.image_to_string(pad_d, config="--oem 3 --psm 6").strip()
        if t_d:
            out_texts.append(t_d)

    return " ".join(out_texts).strip().lower()

def check_goblin_builder_popup_a14(img=None):
    """
    100% RELIABLE GOBLIN BUILDER DETECTOR & CUTTER:
      1. Scans the entire GOBLIN_RED_X_BOX (1927, 209, 1996, 266) + wider popup close area (1910, 195, 2012, 280).
      2. Runs Dual-Polarity (White + Dark text) LANCZOS 2x OCR on:
         - GOBLIN_CHIEF_BOX (1420, 203, 1714, 282)
         - GOBLIN_LETTER_BOX (1154, 330, 1980, 493)
      3. If called right after an upgrade confirm click and the popup is still animating (0.22s),
         automatically re-checks once so Goblin Builder is NEVER missed!
      4. Sets LAST_GOBLIN_DETECTED = True whenever Goblin Builder is detected.
    """
    global LAST_GOBLIN_DETECTED

    for pass_idx in range(2):
        if pass_idx == 0 and img is not None:
            cur_img = img
        else:
            cur_img = get_screenshot(force_fresh=True)

        # 1. Check Red 'X' inside Goblin Red X Box (1927, 209, 1996, 266) and slightly padded box
        rx_found, click_rx, click_ry = find_red_x_in_box_a14(cur_img, (1915, 198, 2008, 276))
        if not rx_found:
            rx_default, ry_default = UPGRADE_A14["GOBLIN_RED_X_CLICK"]
            if is_red_x_box_at(cur_img, rx_default, ry_default, radius=14):
                rx_found = True
                click_rx, click_ry = rx_default, ry_default

        # 2. Check Dual-Polarity OCR on Goblin Chief Box & Goblin Letter Box
        chief_txt = _ocr_dual_polarity_box(cur_img, UPGRADE_A14["GOBLIN_CHIEF_BOX"])
        letter_txt = _ocr_dual_polarity_box(cur_img, UPGRADE_A14["GOBLIN_LETTER_BOX"])
        combined_txt = re.sub(r"[^a-z0-9\s]", " ", f"{chief_txt} {letter_txt}").lower()

        goblin_keywords = [
            "chief", "goblin", "busy", "builder", "builders", "gems",
            "extra", "hire", "work", "assist", "available", "all builders"
        ]
        matched_ocr = any(kw in combined_txt for kw in goblin_keywords)

        # 3. Also check if a centered Goblin / Gem dialog with Red 'X' at (1589, 339) or (1685, 215) has Goblin text
        alt_rx_found, alt_x, alt_y = find_red_x_in_box_a14(cur_img, (1555, 185, 1900, 365))
        if alt_rx_found and not matched_ocr:
            center_txt = _ocr_dual_polarity_box(cur_img, (820, 200, 1650, 520))
            if any(kw in center_txt for kw in ["goblin", "chief", "busy", "hire"]):
                matched_ocr = True
                combined_txt = center_txt

        if rx_found or matched_ocr:
            LAST_GOBLIN_DETECTED = True
            target_x, target_y = (click_rx, click_ry) if rx_found else UPGRADE_A14["GOBLIN_RED_X_CLICK"]
            print(f" [!] [GOBLIN BUILDER DETECTED] OCR='{combined_txt[:45].strip()}' | RedX={rx_found} -> Cutting at ({target_x}, {target_y})...")
            tap(target_x, target_y, delay_range=(0.18, 0.28), jitter=3)
            human_sleep(0.38, 0.05)

            # Verify popup is gone; if an alternate Red X is still visible, cut it too
            chk_after = get_screenshot(force_fresh=True)
            still_rx, sx2, sy2 = find_red_x_in_box_a14(chk_after, (1915, 198, 2008, 276))
            if still_rx:
                tap(sx2, sy2, delay_range=(0.15, 0.25), jitter=2)
                human_sleep(0.30, 0.04)
            elif alt_rx_found and is_red_x_box_at(chk_after, alt_x, alt_y, radius=12):
                tap(alt_x, alt_y, delay_range=(0.15, 0.25), jitter=2)
                human_sleep(0.30, 0.04)

            record_stat("goblin_popups_cut", 1)
            return True

        # Wait 0.22s once in case the Goblin popup was mid-animation after clicking Confirm
        if pass_idx == 0:
            human_sleep(0.22, 0.03)

    return False

def is_on_home_page_a14(img=None):
    """Checks (2050, 285) and (2050, 250) for the green box with a white '+' sign."""
    if img is None:
        img = get_screenshot()
    w, h = img.size
    px_map = img.load()
    for (cx, cy) in HOME_PAGE_CHECK_COORDS:
        green_pixels = 0
        white_pixels = 0
        for dy in range(-12, 13, 2):
            for dx in range(-12, 13, 2):
                px = min(max(0, cx + dx), w - 1)
                py = min(max(0, cy + dy), h - 1)
                r, g, b = px_map[px, py]
                if g > 135 and g > r + 25 and g > b + 25:
                    green_pixels += 1
                elif r > 210 and g > 210 and b > 210:
                    white_pixels += 1
        if green_pixels >= 6 and white_pixels >= 1:
            return True
    return False

def check_clan_chat_drawer_a14(img=None, use_build_fallback=False):
    if img is None:
        img = get_screenshot()
    w, h = img.size
    px_map = img.load()
    cx1, cy1, cx2, cy2 = CLAN_CHAT_DRAWER_BOX

    orange_px = 0
    total_px = 0
    for sy in range(max(0, cy1 + 2), min(h, cy2 - 2), 2):
        for sx in range(max(0, cx1 + 3), min(w, cx2 - 3), 3):
            r, g, b = px_map[sx, sy]
            total_px += 1
            if r > 195 and (105 <= g <= 205) and b < 75 and (r > g + 25):
                orange_px += 1

    is_drawer_open = (total_px > 0 and (orange_px / float(total_px)) >= 0.58)
    if not is_drawer_open and not use_build_fallback:
        return False

    if is_drawer_open:
        print(" [!] [CLAN CHAT DRAWER] Open Clan Chat detected at (792,423..863,457)! Clicking (827, 440) to close...")
        tap(*CLAN_CHAT_CLICK_COORD, delay_range=(0.12, 0.20), jitter=3)
        human_sleep(0.25, 0.04)
        record_stat("clan_chat_closed", 1)
        chk = get_screenshot(force_fresh=True)
        px2 = chk.load()
        rem_orange = sum(
            1 for sy in range(max(0, cy1 + 2), min(h, cy2 - 2), 3)
            for sx in range(max(0, cx1 + 3), min(w, cx2 - 3), 4)
            if px2[sx, sy][0] > 195 and (105 <= px2[sx, sy][1] <= 205) and px2[sx, sy][2] < 75
        )
        if rem_orange <= 6 and not use_build_fallback:
            return True

    if use_build_fallback or is_drawer_open:
        print(" [SAFE IN-GAME RESET] Clicking Build (2233, 948) -> Close (2322, 45) to clear Clan Chat / Center Modal...")
        tap(*UPGRADE_A14["BUILD_CLICK"], delay_range=(0.18, 0.28), jitter=3)
        human_sleep(0.38, 0.05)
        tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
        human_sleep(0.32, 0.05)
        record_stat("clan_chat_closed", 1)
        return True

    return False

def check_welcome_back_chief_a14(img=None):
    if img is None:
        img = get_screenshot()
    w, h = img.size
    px_map = img.load()

    rx1, ry1, rx2, ry2 = WELCOME_CHIEF_RED_BANNER_BOX
    red_px = 0
    r_total = 0
    for sy in range(max(0, ry1 + 2), min(h, ry2 - 2), 3):
        for sx in range(max(0, rx1 + 4), min(w, rx2 - 4), 5):
            r, g, b = px_map[sx, sy]
            r_total += 1
            if r > 165 and g < 75 and b < 75 and (r > g + 95):
                red_px += 1

    if r_total == 0 or (red_px / float(r_total)) < 0.60:
        return False

    gx1, gy1, gx2, gy2 = WELCOME_CHIEF_GREEN_BTN_BOX
    green_px = 0
    g_total = 0
    for sy in range(max(0, gy1 + 1), min(h, gy2 - 1), 2):
        for sx in range(max(0, gx1 + 4), min(w, gx2 - 4), 4):
            r, g, b = px_map[sx, sy]
            g_total += 1
            if g > 130 and g > (r + 25) and g > (b + 25):
                green_px += 1

    if g_total == 0 or (green_px / float(g_total)) < 0.55:
        return False

    print(" [!] [WELCOME BACK CHIEF] Red Banner + Green Button verified! Clicking (1227, 932)...")
    tap(*WELCOME_CHIEF_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3)
    human_sleep(0.35, 0.05)
    record_stat("welcome_chief_closed", 
