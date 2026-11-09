# bot_report.py
# Progress Report Generator, File Saver and Keyboard Listener

import os
import json
import time
import datetime
import threading
import select
import sys
import bot_config
import bot_adb

REPORT_SAVE_FILE = "bot_last_report.json"
_REPORT_LOCK = threading.Lock()

def _create_fresh_session_stats():
    now_ts = time.time()
    now_dt = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
    return {
        "session_start_ts": now_ts,
        "session_start_str": now_dt,
        "operating_mode_str": "Not Selected",
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

def reset_session_progress_report(mode_label="Active Mode"):
    global SESSION_STATS
    with _REPORT_LOCK:
        SESSION_STATS = _create_fresh_session_stats()
        SESSION_STATS["operating_mode_str"] = mode_label
    _save_report_to_disk()

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
            "walls": 0
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
    _save_report_to_disk()

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
    _save_report_to_disk()

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
    _save_report_to_disk()

def _save_report_to_disk():
    try:
        with open(REPORT_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(SESSION_STATS, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def print_saved_progress_report():
    """Prints the previous session's report if it exists on disk, before starting a new run."""
    if not os.path.exists(REPORT_SAVE_FILE):
        return
    try:
        with open(REPORT_SAVE_FILE, "r", encoding="utf-8") as f:
            saved_stats = json.load(f)
        global SESSION_STATS
        old_stats = dict(SESSION_STATS)
        SESSION_STATS = saved_stats
        print_previous_progress_report(report_stage="PREVIOUS SESSION REPORT")
        SESSION_STATS = old_stats
    except Exception:
        pass

def _format_duration_hms(total_seconds):
    total_seconds = max(0, int(round(total_seconds)))
    hrs = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hrs:02d}h {mins:02d}m {secs:02d}s"

def _make_ascii_bar(value, max_val, width=22, fill_char="█", empty_char="░"):
    if max_val <= 0 or value <= 0: return empty_char * width
    filled = int(round((float(value) / float(max_val)) * width))
    filled = max(1, min(width, filled))
    return (fill_char * filled) + (empty_char * (width - filled))

def _make_segmented_pie_bar(segments, total_width=40):
    total_val = sum(val for _, val, _ in segments)
    if total_val <= 0: return "░" * total_width
    out, used_w = "", 0
    for idx, (label, val, color_code) in enumerate(segments):
        if val <= 0: continue
        w = int(round((float(val) / float(total_val)) * total_width))
        if idx == len(segments) - 1 or (used_w + w) > total_width:
            w = max(0, total_width - used_w)
        out += f"{color_code}{'█' * w}\033[0m"
        used_w += w
    if used_w < total_width: out += "░" * (total_width - used_w)
    return out

def print_previous_progress_report(report_stage="PAUSED / STOPPED"):
    with _REPORT_LOCK:
        now_ts = time.time()
        now_dt_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
        start_ts = SESSION_STATS.get("session_start_ts", now_ts)
        start_str = SESSION_STATS.get("session_start_str", "Unknown")

        total_elapsed = max(0.0, now_ts - start_ts)
        paused_so_far = SESSION_STATS.get("total_paused_sec", 0.0)
        if SESSION_STATS.get("current_pause_start_ts") is not None:
            paused_so_far += max(0.0, now_ts - SESSION_STATS["current_pause_start_ts"])
        active_elapsed = max(0.0, total_elapsed - paused_so_far)

        C_RST, C_BOLD, C_CYN, C_GRN, C_YLW, C_MAG, C_RED, C_BLU, C_WHT = "\033[0m", "\033[1m", "\033[96m", "\033[92m", "\033[93m", "\033[95m", "\033[91m", "\033[94m", "\033[97m"

        atk_ok = SESSION_STATS.get("attacks_success", 0)
        atk_fail = SESSION_STATS.get("attacks_failed", 0)
        atk_total = atk_ok + atk_fail
        atk_rate = (atk_ok / float(atk_total) * 100.0) if atk_total > 0 else 100.0
        fail_rate = 100.0 - atk_rate

        bld_up = SESSION_STATS.get("buildings_upgraded", 0)
        wall_up = SESSION_STATS.get("walls_upgraded", 0)
        total_up = bld_up + wall_up

        atk_cnt, atk_t_tot = SESSION_STATS.get("attack_time_count", 0), SESSION_STATS.get("attack_time_total", 0.0)
        avg_atk_s = (atk_t_tot / float(atk_cnt)) if atk_cnt > 0 else 0.0

        upg_cnt, upg_t_tot = SESSION_STATS.get("upgrade_time_count", 0), SESSION_STATS.get("upgrade_time_total", 0.0)
        avg_upg_s = (upg_t_tot / float(upg_cnt)) if upg_cnt > 0 else 0.0

        sw_cnt, sw_t_tot = SESSION_STATS.get("id_switch_time_count", 0), SESSION_STATS.get("id_switch_time_total", 0.0)
        avg_sw_s = (sw_t_tot / float(sw_cnt)) if sw_cnt > 0 else 0.0

        other_active_t = max(0.0, active_elapsed - (atk_t_tot + upg_t_tot + sw_t_tot))
        denom_active = max(1.0, active_elapsed)
        pct_atk = min(100.0, (atk_t_tot / denom_active) * 100.0)
        pct_upg = min(100.0, (upg_t_tot / denom_active) * 100.0)
        pct_sw = min(100.0, (sw_t_tot / denom_active) * 100.0)
        pct_oth = max(0.0, 100.0 - (pct_atk + pct_upg + pct_sw))

        print(f"\n{C_CYN}{C_BOLD}╔══════════════════════════════════════════════════════════════════════════════╗{C_RST}")
        print(f"{C_CYN}{C_BOLD}║                  📊  PROGRESS REPORT DASHBOARD (BOT v9) 📊                   ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Report Status    :{C_RST} {C_BOLD}{C_GRN}{report_stage:<57}{C_RST}{C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Bot Mode & Speed :{C_RST} {C_WHT}{SESSION_STATS.get('operating_mode_str', 'N/A')} (Speed: {bot_config.get_bot_speed_multiplier():.2f}x){C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Start Date & Time:{C_RST} {C_WHT}{start_str:<57}{C_RST}{C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}End/Pause Time   :{C_RST} {C_WHT}{now_dt_str:<57}{C_RST}{C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_YLW}Total Time Gap   :{C_RST} {C_BOLD}{C_CYN}{_format_duration_hms(total_elapsed)}{C_RST}  (Active: {C_GRN}{_format_duration_hms(active_elapsed)}{C_RST} | Paused: {C_MAG}{_format_duration_hms(paused_so_far)}{C_RST})")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║              ⏱️  AVERAGE TIME CATEGORY & SPEED ANALYTICS  ⏱️                 ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠═════════════════════════╦══════════════════════════╦═════════════════════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_GRN}⚔ Avg Attack Time     {C_RST} {C_CYN}║{C_RST} {C_YLW}🏰 Avg Upgrade Loop Time{C_RST} {C_CYN}║{C_RST} {C_MAG}🔄 Avg ID Switch Time {C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_BOLD}{avg_atk_s:>7.1f}s{C_RST} ({atk_cnt:>3} runs)   {C_CYN}║{C_RST} {C_BOLD}{avg_upg_s:>7.1f}s{C_RST} ({upg_cnt:>3} loops)   {C_CYN}║{C_RST} {C_BOLD}{avg_sw_s:>7.1f}s{C_RST} ({sw_cnt:>3} switches) {C_CYN}║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠═════════════════════════╩══════════════════════════╩═════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║              🏆  COMBINED GRAND TOTALS (ALL IDS SUMMARY)  🏆                 ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════╦═══════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_GRN}✔ Successful Attacks   :{C_RST} {C_BOLD}{atk_ok:>10}{C_RST} {C_CYN}║{C_RST} {C_RED}✖ Unsuccessful/Restart :{C_RST} {C_BOLD}{atk_fail:>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_CYN}🔄 Total IDs Switched  :{C_RST} {C_BOLD}{SESSION_STATS.get('id_switches',0):>10}{C_RST} {C_CYN}║{C_RST} {C_YLW}🏰 Buildings Upgraded  :{C_RST} {C_BOLD}{bld_up:>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_MAG}🧱 Walls Upgraded      :{C_RST} {C_BOLD}{wall_up:>10}{C_RST} {C_CYN}║{C_RST} {C_GRN}⚡ Combined Upgrades   :{C_RST} {C_BOLD}{total_up:>11}{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════╩═══════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║            🥧  PIE DISTRIBUTION CHARTS & VISUAL GRAPHS  🥧                   ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")

        time_pie_bar = _make_segmented_pie_bar([("Attack", atk_t_tot, C_GRN), ("Upgrade", upg_t_tot, C_YLW), ("ID Switch", sw_t_tot, C_MAG), ("Other", other_active_t, C_BLU)], total_width=44)
        print(f"{C_CYN}║{C_RST} {C_BOLD}Time Share Pie :{C_RST} [{time_pie_bar}]")
        print(f"{C_CYN}║{C_RST}   ├─ {C_GRN}█ Attack Time  : {pct_atk:5.1f}% ({_format_duration_hms(atk_t_tot)}){C_RST}   ├─ {C_YLW}█ Upgrade Time : {pct_upg:5.1f}% ({_format_duration_hms(upg_t_tot)}){C_RST}")
        print(f"{C_CYN}║{C_RST}   └─ {C_MAG}█ ID Switch    : {pct_sw:5.1f}% ({_format_duration_hms(sw_t_tot)}){C_RST}   └─ {C_BLU}█ Home/Checks  : {pct_oth:5.1f}% ({_format_duration_hms(other_active_t)}){C_RST}")

        print(f"{C_CYN}{C_BOLD}╠══════════════════════════════════════════════════════════════════════════════╣{C_RST}")
        print(f"{C_CYN}{C_BOLD}║          📋  PER-ID DETAILED BREAKDOWN (NAME, ATTACKS & UPGRADES)  📋        ║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════╦══════════════════════╦══════════╦════════╦════════╦═════════╦═════════╣{C_RST}")
        print(f"{C_CYN}║{C_RST} {C_BOLD}ID #{C_RST} {C_CYN}║{C_RST} {C_BOLD}Unique ID / Name    {C_RST} {C_CYN}║{C_RST} {C_BOLD}Role    {C_RST} {C_CYN}║{C_RST} {C_GRN}{C_BOLD}Atk OK{C_RST} {C_CYN}║{C_RST} {C_RED}{C_BOLD}Retry {C_RST} {C_CYN}║{C_RST} {C_YLW}{C_BOLD}Bld Up {C_RST} {C_CYN}║{C_RST} {C_MAG}{C_BOLD}Wall Up{C_RST} {C_CYN}║{C_RST}")
        print(f"{C_CYN}{C_BOLD}╠══════╬══════════════════════╬══════════╬════════╬════════╬═════════╬═════════╣{C_RST}")

        sorted_keys = sorted(SESSION_STATS["per_id"].keys(), key=lambda x: int(x))
        if not sorted_keys:
            print(f"{C_CYN}║{C_RST}  --  {C_CYN}║{C_RST} No ID activity yet   {C_CYN}║{C_RST}    --    {C_CYN}║{C_RST}      0 {C_CYN}║{C_RST}      0 {C_CYN}║{C_RST}       0 {C_CYN}║{C_RST}       0 {C_CYN}║{C_RST}")
        else:
            for k in sorted_keys:
                info = SESSION_STATS["per_id"][k]
                idx_str = f"#{info['id_index']}"
                uname = (info["name"] or f"ID #{info['id_index']}")[:20]
                print(f"{C_CYN}║{C_RST} {C_BOLD}{idx_str:<4}{C_RST} {C_CYN}║{C_RST} {C_WHT}{uname:<20}{C_RST} {C_CYN}║{C_RST} {info['role'][:8]:<8} {C_CYN}║{C_RST} {C_GRN}{info['attacks_ok']:>6}{C_RST} {C_CYN}║{C_RST} {C_RED}{info['attacks_fail']:>6}{C_RST} {C_CYN}║{C_RST} {C_YLW}{info['buildings']:>7}{C_RST} {C_CYN}║{C_RST} {C_MAG}{info['walls']:>7}{C_RST} {C_CYN}║{C_RST}")

        print(f"{C_CYN}{C_BOLD}╚══════════════════════════════════════════════════════════════════════════════╝{C_RST}\n")

# ==========================================
# KEYBOARD LISTENER ENGINE ('ZX' / 'QW')
# ==========================================
def _trigger_pause_state():
    with _REPORT_LOCK:
        SESSION_STATS["pause_count"] = SESSION_STATS.get("pause_count", 0) + 1
        SESSION_STATS["current_pause_start_ts"] = time.time()
    _save_report_to_disk()
    print("\n======================================================================")
    print(f"|| [BOT PAUSED BY 'ZX'] Bot wahin ruk gaya hai (Speed={bot_config.get_bot_speed_multiplier():.2f}x Safe)! ||")
    print("|| Dubara Home Page se Resume karne ke liye 'QW' type karein...      ||")
    print("======================================================================")
    print_previous_progress_report(report_stage="PAUSED BY 'ZX' (LIVE SNAPSHOT)")

def _trigger_resume_state():
    with _REPORT_LOCK:
        SESSION_STATS["resume_count"] = SESSION_STATS.get("resume_count", 0) + 1
        if SESSION_STATS.get("current_pause_start_ts") is not None:
            SESSION_STATS["total_paused_sec"] = SESSION_STATS.get("total_paused_sec", 0.0) + max(0.0, time.time() - SESSION_STATS["current_pause_start_ts"])
            SESSION_STATS["current_pause_start_ts"] = None
    _save_report_to_disk()
    bot_adb.LAST_HOME_CLEANUP_TIME = 0.0
    print("\n======================================================================")
    print(f"|| [BOT RESUMED BY 'QW'] Home Page se wapas start (Speed={bot_config.get_bot_speed_multiplier():.2f}x)! ||")
    print("======================================================================\n")

def _keyboard_listener_worker():
    try:
        import termios, tty
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
                    if not ch: time.sleep(0.1); continue
                    do_pause, do_resume = False, False
                    with bot_adb._PAUSE_LOCK:
                        bot_adb._PAUSE_STATE["buffer"] = (bot_adb._PAUSE_STATE["buffer"] + ch.lower())[-12:]
                        buf = bot_adb._PAUSE_STATE["buffer"]
                        if not bot_adb._PAUSE_STATE["paused"] and "zx" in buf:
                            bot_adb._PAUSE_STATE["paused"], bot_adb._PAUSE_STATE["buffer"], do_pause = True, "", True
                        elif bot_adb._PAUSE_STATE["paused"] and "qw" in buf:
                            bot_adb._PAUSE_STATE["paused"], bot_adb._PAUSE_STATE["resumed_just_now"], bot_adb._PAUSE_STATE["buffer"], do_resume = False, True, "", True
                    if do_pause: _trigger_pause_state()
                    elif do_resume: _trigger_resume_state()
            else:
                line = sys.stdin.readline()
                if not line: time.sleep(0.2); continue
                clean_line = line.strip().lower()
                do_pause, do_resume = False, False
                with bot_adb._PAUSE_LOCK:
                    if not bot_adb._PAUSE_STATE["paused"] and "zx" in clean_line:
                        bot_adb._PAUSE_STATE["paused"], do_pause = True, True
                    elif bot_adb._PAUSE_STATE["paused"] and "qw" in clean_line:
                        bot_adb._PAUSE_STATE["paused"], bot_adb._PAUSE_STATE["resumed_just_now"], do_resume = False, True, True
                if do_pause: _trigger_pause_state()
                elif do_resume: _trigger_resume_state()
    except Exception:
        pass
    finally:
        if use_cbreak:
            try: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except: pass

def start_pause_resume_listener():
    with bot_adb._PAUSE_LOCK:
        if bot_adb._PAUSE_STATE["listener_started"]: return
        bot_adb._PAUSE_STATE["listener_started"] = True
    threading.Thread(target=_keyboard_listener_worker, daemon=True).start()
