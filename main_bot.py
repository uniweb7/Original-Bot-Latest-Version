import os
import json
import time
import random
import traceback
import bot_tools
from bot_tools import (
    BotPausedResumeHomeException,
    ADVANCE_SPEED_TABLE,
    start_pause_resume_listener,
    check_pause_point,
    smart_sleep,
    human_sleep,
    set_bot_speed_multiplier,
    get_bot_speed_multiplier,
    check_wrong_buttons_a14,
    check_daily_reward_popup,
    check_and_handle_maintenance_break,
    run_zone2_home_periodic_checks,
    double_click_storage_bars,
    perform_home_cleanup_once,
    ensure_return_to_home_page_a14,
    check_resources_full_for_upgrade,
    zoom_out_village_a14,
    clean_ram_garbage,
    reset_session_progress_report,
    print_previous_progress_report,
    show_saved_previous_report_once_at_startup,
    save_current_progress_report,
    record_stat
)
from bot_upgrade import (
    run_a14_combined_upgrade_loop,
    run_a14_buildings_only_upgrade_loop,
    run_a14_special_upgrade_loop,
    run_full_smart_upgrade_sequence,
    run_custom_mode_upgrade_loop
)
from bot_attack import execute_attack
from bot_id_switch import (
    load_id_memory,
    save_id_memory,
    get_id_role_label,
    switch_to_target_id,
    sync_initial_id_to_report
)

CUSTOM_PRESET_FILE = "bot_custom_preset.json"

# ==========================================
# 1. CUSTOM MODE PRESET MANAGER & CONFIGURATOR
# ==========================================

def load_custom_preset():
    default_preset = {
        "combo_type": "1+2+3",
        "attacks_per_round": 5,
        "upgrade_order": "BUILDING_THEN_WALL",
        "include_specials": True,
        "check_storage": False,
        "stop_builders": 0,
        "rounds_per_id": 3
    }
    if not os.path.exists(CUSTOM_PRESET_FILE):
        return default_preset
    try:
        with open(CUSTOM_PRESET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                default_preset.update(data)
    except Exception:
        pass
    return default_preset

def save_custom_preset(preset_data):
    try:
        with open(CUSTOM_PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def configure_custom_mode_14():
    preset = load_custom_preset()
    print("\n==============================================================================")
    print(" ||         OPTION [14]: CREATE OPTIONS (MANUAL CUSTOM BUILDER)             ||")
    print("==============================================================================")
    print(" || Saved Custom Preset Summary:                                             ||")
    print(f" ||   * Combination      : {preset['combo_type']}                                              ||")
    print(f" ||   * Attacks / Round  : {preset['attacks_per_round']} Fast Attacks                                    ||")
    print(f" ||   * Upgrade Sequence : {preset['upgrade_order']}                             ||")
    print(f" ||   * Special Upgrades : {'Yes (Spell+Pet+Equip)' if preset.get('include_specials', True) else 'No'}                        ||")
    print(f" ||   * Storage Check    : {'Yes' if preset['check_storage'] else 'No (Direct Fast Upgrade)'}                               ||")
    print(f" ||   * Builder Target   : Stop at {preset['stop_builders']} Builder(s)                                ||")
    print(f" ||   * Attempts per ID  : {preset['rounds_per_id']} Round(s) before ID Switch                       ||")
    print("==============================================================================")

    use_saved = input("\n Kya pichhla Saved Custom Preset use karein? (y/n) [Default=y]: ").strip().lower()
    if use_saved in ["", "y", "yes"]:
        return preset

    print("\n [STEP 1] Select System Combination:")
    print("   [1] -> 1 + 3 : Fast Attack + ID Switching Only")
    print("   [2] -> 1 + 2 : Fast Attack + Fast Upgrading Only")
    print("   [3] -> 1 + 2 + 3 : Fast Attack + Fast Upgrading + ID Switching (Full Custom Sequence)")
    c_in = input(" Option type karein (1/2/3) [Default=3 (1+2+3)]: ").strip()
    if c_in == "1":
        preset["combo_type"] = "1+3"
    elif c_in == "2":
        preset["combo_type"] = "1+2"
    else:
        preset["combo_type"] = "1+2+3"

    raw_atk = input(f"\n [STEP 2] Har round me kitne Fast Attacks karne hain? (1 se 50) [Default={preset['attacks_per_round']}]: ").strip()
    if raw_atk.isdigit() and 1 <= int(raw_atk) <= 50:
        preset["attacks_per_round"] = int(raw_atk)

    if "2" in preset["combo_type"]:
        print("\n [STEP 3] Select Upgrade Category & Sequence Order:")
        print("   [1] -> Building Upgrade FIRST -> then Wall Upgrade")
        print("   [2] -> Wall Upgrade FIRST -> then Building Upgrade")
        print("   [3] -> Building Upgrade ONLY (No Wall)")
        print("   [4] -> Wall Upgrade ONLY (No Building)")
        u_in = input(" Option type karein (1/2/3/4) [Default=1]: ").strip()
        if u_in == "2":
            preset["upgrade_order"] = "WALL_THEN_BUILDING"
        elif u_in == "3":
            preset["upgrade_order"] = "BUILDING_ONLY"
        elif u_in == "4":
            preset["upgrade_order"] = "WALL_ONLY"
        else:
            preset["upgrade_order"] = "BUILDING_THEN_WALL"

        sp_in = input("\n [STEP 3B] Kya Spell + Pet + Equipment Upgrade bhi shamil karein? (y/n) [Default=y]: ").strip().lower()
        preset["include_specials"] = (sp_in in ["", "y", "yes"])

        st_in = input("\n [STEP 4] Upgrade se pehle Storage Box check karein ya Direct Upgrade? (d=Direct / c=Check) [Default=d]: ").strip().lower()
        preset["check_storage"] = (st_in == "c")

        b_in = input("\n [STEP 5] Builders kitne bachne par upgrade close karein? (0 = Zero Builders / 1 = One Builder) [Default=0]: ").strip()
        preset["stop_builders"] = 1 if b_in == "1" else 0

    if "3" in preset["combo_type"]:
        r_in = input(f"\n [STEP 6] Ek ID par (Attack + Upgrade) kitne Attempts/Rounds chalane ke baad ID Switch karein? (1 se 10) [Default=3]: ").strip()
        if r_in.isdigit() and 1 <= int(r_in) <= 10:
            preset["rounds_per_id"] = int(r_in)
        else:
            preset["rounds_per_id"] = 3

    save_custom_preset(preset)
    print(" [✔] Custom Option [14] Preset saved successfully!")
    return preset

# ==========================================
# 2. ADVANCE FEATURES & SPEED-UP MENU (A TO Y)
# ==========================================

def open_advance_features_menu():
    letter_to_speed = {letter: mult for letter, mult, _ in ADVANCE_SPEED_TABLE}

    while True:
        cur_spd = get_bot_speed_multiplier()
        print("\n======================================================================")
        print(" ||        ADVANCE FEATURES MENU - GAME SPEED-UP SYSTEM              ||")
        print("======================================================================")
        print(f" || Current Active Bot Speed : {cur_spd:.2f}x                               ||")
        print("----------------------------------------------------------------------")
        print(" || Select Game Speed-Up Option (A to Y):                          ||")
        for letter, mult, desc in ADVANCE_SPEED_TABLE:
            marker = " <-- [ACTIVE]" if abs(cur_spd - mult) < 0.005 else ""
            print(f" ||   [{letter}] -> {mult:.2f}x  ({desc}){marker}")
        print("----------------------------------------------------------------------")
        print(" ||   [R] -> View Current / Previous Progress Report               ||")
        print(" ||   [0] -> Back to Main Bot Operating Menu                       ||")
        print("======================================================================")

        raw_in = input("\n Speed Option type karein (A se Y tak, R report ke liye, ya 0 wapas jane ke liye) [Default=A]: ").strip().upper()
        if raw_in == "":
            set_bot_speed_multiplier(1.00)
            break
        if raw_in == "0":
            break
        if raw_in == "R":
            print_previous_progress_report(report_stage="MENU PREVIEW")
            continue
        if raw_in in letter_to_speed:
            chosen_mult = letter_to_speed[raw_in]
            set_bot_speed_multiplier(chosen_mult)
            print(f" [✔] Root-Level Game Speed-Up '{raw_in}' ({chosen_mult:.2f}x) successfully activate ho gaya hai!")
            break
        try:
            val = float(raw_in.replace("X", ""))
            if 1.0 <= val <= 2.25:
                set_bot_speed_multiplier(val)
                print(f" [✔] Custom Root-Level Game Speed-Up ({val:.2f}x) successfully activate ho gaya hai!")
                break
        except Exception:
            pass
        print(" [!] Galat input! Kripya A se Y ke beech ka letter (jaise A, B, C, D, E...) type karein.")

# ==========================================
# 3. OPERATING MODE CONFIGURATION MENU (MODES 1 TO 15)
# ==========================================

def select_bot_configuration():
    while True:
        cur_spd = get_bot_speed_multiplier()
        print("\n==============================================================================")
        print(" ||      CLASH OF CLANS AI BOT v9 - SAMSUNG GALAXY A14 ULTIMATE EDITION      ||")
        print("==============================================================================")
        print(f" || Active Game Speed Multiplier : {cur_spd:.2f}x {'(Standard Default)' if abs(cur_spd - 1.0) < 0.005 else '(Root Speed-Up Active!)'}")
        print("------------------------------------------------------------------------------")
        print(" || Select Bot Operating Mode (1 to 15):                                     ||")
        print(" || [1]  -> Fast Attack Only                 (सिर्फ फास्ट अटैक - Infinity)      ||")
        print(" || [2]  -> Combined Building & Wall Only    (बिल्डिंग + वॉल अपग्रेड - 1m Gap)  ||")
        print(" || [3]  -> Combined Special Upgrade Only    (Spells + Pets + Equipments)    ||")
        print(" || [4]  -> Tried All                        (Full Upgrade + 10 Attacks)     ||")
        print(" || [5]  -> ID Changement Only               (सिर्फ ID चेंज - हर 2 सेकंड में)    ||")
        print(" || [6]  -> ID Changement + Fast Attack      (हर ID पर 10 Min अटैक स्विच)      ||")
        print(" || [7]  -> ID Changement + Tried All        (Fully Botted System - Default) ||")
        print(" || [8]  -> Advance Features / Speed Control (Game Speed-Up: 1.00x to 2.25x) ||")
        print(" || [9]  -> Fast Mode 1                      (N Atk -> Bldg & Wall -> Switch)||")
        print(" || [10] -> Fast Mode 2                      (N Atk -> Upg till 0 Builders)  ||")
        print(" || [11] -> Smart Loot-First Turbo Mode      (Upg -> 5 Atk -> Upg -> Switch) ||")
        print(" || [12] -> 3-Wave Builder-Zero Dominator    (3x [4 Atk + Upg], Exit on 0)   ||")
        print(" || [13] -> Overnight Marathon Mode          (20 Min Continuous Loop per ID) ||")
        print(" || [14] -> Create Options (Custom Builder)  (1+3 / 1+2 / 5 Atk+Bld+Wall+3x) ||")
        print(" || [15] -> Direct Full Upg + 5 Atk + Full Upg (No Storage Check -> Switch)  ||")
        print("==============================================================================")
        print(" || Live Controls Inside Termux:                                             ||")
        print(" || Pause & Show Progress Report : Type 'ZX' (or 'zx') anytime               ||")
        print(" || Resume Bot (Same Speed/State): Type 'QW' (or 'qw') anytime               ||")
        print(" || Stop & Final Progress Report : Press Ctrl+C anytime                      ||")
        print("==============================================================================")

        choice = input("\n Apna Option type karein (1 se 15) [Default=7]: ").strip()
        if choice == "":
            choice = "7"

        if choice == "8":
            open_advance_features_menu()
            continue

        if choice in [str(i) for i in range(1, 16) if i != 8]:
            break
        print(" [!] Galat input! Kripya 1 se 15 ke beech ka number type karein.")

    custom_cfg = load_custom_preset()
    if choice == "14":
        custom_cfg = configure_custom_mode_14()

    mode_names = {
        "1": "MODE 1: FAST ATTACK ONLY (Infinity)",
        "2": "MODE 2: COMBINED BUILDING & WALL UPGRADE ONLY (1 Min Gap)",
        "3": "MODE 3: COMBINED SPECIAL UPGRADE ONLY (Spells + Pets + Equipments)",
        "4": "MODE 4: TRIED ALL (Full Upgrade + 10 Fast Attacks)",
        "5": "MODE 5: ID CHANGEMENT ONLY (2s Hold + Fast Dynamic Switch)",
        "6": "MODE 6: ID CHANGEMENT + FAST ATTACK (10 Min per ID)",
        "7": "MODE 7: ID CHANGEMENT + TRIED ALL (Fully Botted System)",
        "9": "MODE 9: FAST MODE 1 (Fast Attacks -> Direct Building & Wall Upgrade -> 1s Switch)",
        "10": "MODE 10: FAST MODE 2 (Fast Attacks -> Full Upgrade till 0 Builders -> 1s Switch)",
        "11": "MODE 11: SMART LOOT-FIRST TURBO (Upgrade -> 5 Attacks -> Upgrade -> Switch)",
        "12": "MODE 12: 3-WAVE BUILDER-ZERO DOMINATOR (3x [4 Atk + Upgrade], Exit on 0 Builders)",
        "13": "MODE 13: OVERNIGHT MARATHON MODE (20 Min Continuous Attack+Upgrade per ID)",
        "14": f"MODE 14: CUSTOM ({custom_cfg['combo_type']} | {custom_cfg['attacks_per_round']} Atk | {custom_cfg['upgrade_order']} | {custom_cfg['rounds_per_id']}x Rounds)",
        "15": "MODE 15: DIRECT FULL UPGRADE (Bld+Wall+Equip) -> 5 FAST ATTACKS -> DIRECT FULL UPGRADE -> ID SWITCH"
    }
    print(f"\n [✔] Selected Mode: [{choice}] -> {mode_names[choice]} | Speed: {get_bot_speed_multiplier():.2f}x")

    total_ids = 1
    start_id_index = 1
    fast_mode_attacks_per_id = 5

    needs_id_config = (choice in ["5", "6", "7", "9", "10", "11", "12", "13", "15"]) or (choice == "14" and "3" in custom_cfg["combo_type"])
    if needs_id_config:
        mem = load_id_memory()
        default_total = mem.get("total_ids", 10)
        if default_total < 1 or default_total > 100:
            default_total = 10

        while True:
            raw_total = input(f" Total IDs type karein (1 se 100 ke beech, First 4 = Main ID) [Default={default_total}]: ").strip()
            if raw_total == "":
                total_ids = default_total
                break
            if raw_total.isdigit() and 1 <= int(raw_total) <= 100:
                total_ids = int(raw_total)
                break
            print(" [!] Kripya 1 se 100 ke beech ka sahi number type karein.")

        if choice in ["9", "10"]:
            default_fm_atk = mem.get("mode8_attacks_per_id", 5)
            if not isinstance(default_fm_atk, int) or default_fm_atk < 1 or default_fm_atk > 50:
                default_fm_atk = 5
            while True:
                raw_atk = input(f" [MODE {choice}] Har ID par kitne Fast Attacks karne hain? (1 se 50) [Default={default_fm_atk}]: ").strip()
                if raw_atk == "":
                    fast_mode_attacks_per_id = default_fm_atk
                    break
                if raw_atk.isdigit() and 1 <= int(raw_atk) <= 50:
                    fast_mode_attacks_per_id = int(raw_atk)
                    break
                print(" [!] Kripya 1 se 50 ke beech ka sahi attack number type karein.")
            mem["mode8_attacks_per_id"] = fast_mode_attacks_per_id

        saved_idx = mem.get("current_id_index", 1)
        if 1 < saved_idx <= total_ids:
            ans = input(f" Pichhli baar Bot ID #{saved_idx} par tha. Kya ID #{saved_idx} se Resume karein? (y/n) [Default=n (Start from ID #1)]: ").strip().lower()
            if ans == "y":
                start_id_index = saved_idx

        mem["total_ids"] = total_ids
        mem["current_id_index"] = start_id_index
        save_id_memory(mem)
        print(f" [✔] ID Changement Configured: Total IDs = {total_ids} | Starting on ID #{start_id_index} [{get_id_role_label(start_id_index)}]")

    mode_summary_label = mode_names[choice] + (f" ({fast_mode_attacks_per_id} Atk/ID)" if choice in ["9", "10"] else "")
    reset_session_progress_report(mode_label=mode_summary_label)
    sync_initial_id_to_report(start_id_index)

    input("\n Bot Start karne ke liye [ENTER] key dabayein: ")
    return choice, total_ids, start_id_index, fast_mode_attacks_per_id, custom_cfg

# ==========================================
# 4. SHARED UPGRADE & ATTACK RUNNERS WITH RESUME MEMORY
# ==========================================

def run_combined_building_and_wall_upgrade(loop_label="COMBINED UPGRADE", include_specials=False, stop_at_builders=1):
    check_pause_point(allow_raise=True)
    print("\n----------------------------------------------------------------------")
    print(f" | [{loop_label}] Single Storage Check -> Building -> Wall Handoff |")
    print("----------------------------------------------------------------------")

    if perform_home_cleanup_once(max_age_sec=1.5):
        human_sleep(0.18, 0.04)

    img = bot_tools.get_screenshot()
    check_and_handle_maintenance_break(img)

    print(f"\n [{loop_label}] Checking Gold & Elixir Storage Boxes for Combined Upgrade...")
    if check_resources_full_for_upgrade(img):
        print(" [+] Storage Box is FULL! Starting Combined Upgrade in 0.20s...")
        human_sleep(0.20, 0.04)
        b_up, w_up, any_up = run_a14_combined_upgrade_loop(
            stop_at_builders=stop_at_builders,
            include_specials=include_specials
        )
    else:
        print(" [-] Storage Box is not full yet. Skipping Combined Upgrade...")
        b_up, w_up, any_up = False, False, False

    print(f" [{loop_label} RESULT] Building Upgraded: {b_up} | Wall Upgraded: {w_up} | Any Upgraded: {any_up}")
    return b_up, w_up, any_up

def run_n_fast_attacks_with_resume_memory(state_dict, target_attacks, phase_label="ATTACK SERIES"):
    consecutive_failed_attacks = 0

    while state_dict["attacks_done"] < target_attacks:
        check_pause_point(allow_raise=True)
        next_atk_num = state_dict["attacks_done"] + 1
        pre_attack_wait = random.uniform(0.20, 0.38)
        print(f"\n [{phase_label}] Attack #{next_atk_num} / {target_attacks} starting in {pre_attack_wait:.2f}s (Speed={get_bot_speed_multiplier():.2f}x)...")
        smart_sleep(pre_attack_wait, apply_speed=True)

        atk_ok = execute_attack(is_first_attack=(next_atk_num == 1))
        if atk_ok:
            consecutive_failed_attacks = 0
            state_dict["attacks_done"] += 1
            print(f" [✔] [{phase_label}] Completed Attack #{state_dict['attacks_done']} / {target_attacks}!")
        else:
            consecutive_failed_attacks += 1
            print(f" [!] [{phase_label}] Attack #{next_atk_num} unsuccessful (Consecutive Fails: {consecutive_failed_attacks}/2).")
            if consecutive_failed_attacks >= 2:
                print(" [SMART RECOVERY] 2 consecutive full attacks failed on this ID! Advancing to next phase...")
                ensure_return_to_home_page_a14()
                break

        if state_dict["attacks_done"] > 0 and (state_dict["attacks_done"] % 5 == 0) and (state_dict["attacks_done"] < target_attacks):
            print(f" [HEALTH CHECK] 5-Attack milestone ({state_dict['attacks_done']}/{target_attacks}) -> Checking Clan Chat, Daily Reward & Maintenance...")
            run_zone2_home_periodic_checks()

    run_zone2_home_periodic_checks()

# ==========================================
# 5. MASTER BOT EXECUTION LOOP
# ==========================================

def main_loop():
    # Display last saved session's progress report once at startup if available
    show_saved_previous_report_once_at_startup()

    bot_mode, total_ids, current_id, fast_mode_attacks_per_id, custom_cfg = select_bot_configuration()

    start_pause_resume_listener()

    # Home-Page-Only Symmetric 2-Finger Zoom-Out at startup
    zoom_out_village_a14(passes=2, reason="BOT STARTUP HOME PAGE ZOOM-OUT")

    if int(bot_mode) >= 9:
        print(f"\n[MODE {bot_mode} STARTUP] Waiting 1.0 second on ID #{current_id} before starting...")
        smart_sleep(1.0, apply_speed=True)
    else:
        startup_rest = random.uniform(0.8, 1.2)
        print(f"\n[STARTUP] Taking {startup_rest:.1f} seconds initial rest on Home Page (Speed={get_bot_speed_multiplier():.2f}x)...")
        smart_sleep(startup_rest, apply_speed=True)

    cycle_count = 1
    consecutive_loop_errors = 0

    runtime_state = {
        "current_id": current_id,
        "phase": "START_CYCLE",
        "attacks_done": 0,
        "custom_round_idx": 1,
        "id_timer_start": None,
        "id_elapsed_sec": 0.0,
        "loop2_any_upgraded": False
    }

    while True:
        try:
            check_pause_point(allow_raise=True)
            active_id = runtime_state["current_id"]
            id_role = get_id_role_label(active_id)
            cur_spd = get_bot_speed_multiplier()

            print("\n" + "=" * 74)
            if int(bot_mode) >= 5:
                print(f" MASTER CYCLE #{cycle_count} | MODE: [{bot_mode}] | SPEED: {cur_spd:.2f}x | ACTIVE ID: #{active_id}/{total_ids} [{id_role}]")
            else:
                print(f" MASTER CYCLE #{cycle_count} | MODE: [{bot_mode}] | SPEED: {cur_spd:.2f}x")
            print("=" * 74)

            run_zone2_home_periodic_checks()

            # ---------------------------------------------------------
            # MODE 1: FAST ATTACK ONLY (INFINITY)
            # ---------------------------------------------------------
            if bot_mode == "1":
                pre_wait = random.uniform(0.20, 0.38)
                print(f" [MODE 1] Starting Fast Attack in {pre_wait:.2f}s...")
                smart_sleep(pre_wait, apply_speed=True)
                execute_attack(is_first_attack=(cycle_count == 1))

            # ---------------------------------------------------------
            # MODE 2: COMBINED BUILDING & WALL UPGRADE ONLY (1M GAP)
            # ---------------------------------------------------------
            elif bot_mode == "2":
                run_combined_building_and_wall_upgrade("MODE 2 COMBINED UPGRADE", include_specials=False)
                print(" [MODE 2] Waiting 1 Minute (60s) before next Combined Upgrade resource check...")
                smart_sleep(60.0, apply_speed=False)

            # ---------------------------------------------------------
            # MODE 3: COMBINED SPECIAL UPGRADE ONLY (SPELLS + PETS + EQUIPMENTS)
            # ---------------------------------------------------------
            elif bot_mode == "3":
                print(" [MODE 3] Running Combined Special Upgrade (Spells + Pets + Equipments)...")
                run_a14_special_upgrade_loop(close_menu_on_exit=True)
                print(" [MODE 3] Waiting 1 Minute (60s) before next Special Upgrade check...")
                smart_sleep(60.0, apply_speed=False)

            # ---------------------------------------------------------
            # MODE 4: TRIED ALL (FULL UPGRADE + 10 FAST ATTACKS)
            # ---------------------------------------------------------
            elif bot_mode == "4":
                if runtime_state["phase"] == "START_CYCLE":
                    run_combined_building_and_wall_upgrade("MODE 4 FULL UPGRADE", include_specials=True)
                    runtime_state["phase"] = "ATTACK_10"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "ATTACK_10":
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=10,
                        phase_label="MODE 4 (10-ATTACK LOOP)"
                    )
                    runtime_state["phase"] = "START_CYCLE"
                    runtime_state["attacks_done"] = 0

            # ---------------------------------------------------------
            # MODE 5: ID CHANGEMENT ONLY (2S HOLD)
            # ---------------------------------------------------------
            elif bot_mode == "5":
                print(f" [MODE 5] Spending 2 Seconds on ID #{active_id}/{total_ids} [{id_role}]...")
                perform_home_cleanup_once(max_age_sec=1.0)
                smart_sleep(2.0, apply_speed=True)

                next_id = (active_id % total_ids) + 1
                print(f" [MODE 5] 2 Seconds complete! Switching from ID #{active_id} -> ID #{next_id}/{total_ids}...")
                switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id

            # ---------------------------------------------------------
            # MODE 6: ID CHANGEMENT + FAST ATTACK (10 MIN PER ID)
            # ---------------------------------------------------------
            elif bot_mode == "6":
                target_duration_sec = 600.0
                if runtime_state["id_timer_start"] is None:
                    runtime_state["id_timer_start"] = time.time()
                    runtime_state["attacks_done"] = 0
                    print(f" [MODE 6] Started 10-Minute Fast Attack Timer on ID #{active_id}/{total_ids} [{id_role}]!")

                while True:
                    check_pause_point(allow_raise=True)
                    elapsed_total = runtime_state["id_elapsed_sec"] + (time.time() - runtime_state["id_timer_start"])
                    remaining_sec = target_duration_sec - elapsed_total

                    if remaining_sec <= 0:
                        print(f"\n [10 MIN COMPLETE] Spent {elapsed_total/60.0:.1f} minutes ({runtime_state['attacks_done']} attacks) on ID #{active_id}!")
                        break

                    atk_no = runtime_state["attacks_done"] + 1
                    print(f"\n [MODE 6 | ID #{active_id}] Starting Fast Attack #{atk_no} (Time elapsed: {elapsed_total/60.0:.1f}m / 10.0m)...")
                    pre_wait = random.uniform(0.20, 0.38)
                    smart_sleep(pre_wait, apply_speed=True)

                    execute_attack(is_first_attack=(atk_no == 1))
                    runtime_state["attacks_done"] += 1

                next_id = (active_id % total_ids) + 1
                switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                runtime_state["id_timer_start"] = None
                runtime_state["id_elapsed_sec"] = 0.0
                runtime_state["attacks_done"] = 0

            # ---------------------------------------------------------
            # MODE 7: ID CHANGEMENT + TRIED ALL (FULLY BOTTED SYSTEM)
            # ---------------------------------------------------------
            elif bot_mode == "7":
                if runtime_state["phase"] == "START_CYCLE":
                    run_combined_building_and_wall_upgrade(f"ID #{active_id} - COMBINED UPGRADE LOOP #1", include_specials=True)
                    runtime_state["phase"] = "ATTACK_10"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "ATTACK_10":
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=10,
                        phase_label=f"ID #{active_id} - 10 FAST ATTACKS"
                    )
                    runtime_state["phase"] = "UPGRADE_LOOP_2"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "UPGRADE_LOOP_2":
                    _, _, any_up_2 = run_combined_building_and_wall_upgrade(f"ID #{active_id} - COMBINED UPGRADE LOOP #2", include_specials=True)
                    runtime_state["loop2_any_upgraded"] = any_up_2

                    if any_up_2:
                        print("\n [MODE 7 RULE] Combined Upgrade Loop #2 me upgrade safal raha! Attack rok kar seedha Next ID par switch kar rahe hain...")
                        runtime_state["phase"] = "SWITCH_ID"
                    else:
                        print("\n [i MODE 7 RULE] Combined Upgrade Loop #2 me koi upgrade nahi hua! Ab 5 Fast Attacks karenge phir ID switch karenge...")
                        runtime_state["phase"] = "ATTACK_5"
                        runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "ATTACK_5":
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=5,
                        phase_label=f"ID #{active_id} - 5 EXTRA FAST ATTACKS"
                    )
                    runtime_state["phase"] = "SWITCH_ID"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "SWITCH_ID":
                    next_id = (active_id % total_ids) + 1
                    switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["phase"] = "START_CYCLE"
                    runtime_state["attacks_done"] = 0
                    runtime_state["loop2_any_upgraded"] = False

            # ---------------------------------------------------------
            # MODE 9 & MODE 10: FAST MODE 1 (STOP AT 1) & FAST MODE 2 (STOP AT 0)
            # ---------------------------------------------------------
            elif bot_mode in ["9", "10"]:
                stop_b_target = 1 if bot_mode == "9" else 0
                inc_spec = (bot_mode == "10")

                if runtime_state["phase"] in ["START_CYCLE", "FAST_MODE_ATTACKS"]:
                    runtime_state["phase"] = "FAST_MODE_ATTACKS"
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=fast_mode_attacks_per_id,
                        phase_label=f"MODE {bot_mode} | ID #{active_id} ({fast_mode_attacks_per_id} FAST ATTACKS)"
                    )
                    runtime_state["phase"] = "FAST_MODE_UPGRADE"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "FAST_MODE_UPGRADE":
                    print(f"\n [MODE {bot_mode} DIRECT UPGRADE] {fast_mode_attacks_per_id} Attacks complete! Starting Direct Upgrade (Stop Builders <= {stop_b_target})...")
                    run_a14_combined_upgrade_loop(stop_at_builders=stop_b_target, include_specials=inc_spec)
                    runtime_state["phase"] = "FAST_MODE_SWITCH_ID"

                if runtime_state["phase"] == "FAST_MODE_SWITCH_ID":
                    print(f" [MODE {bot_mode}] Waiting 1.0 second after Upgrade before ID Switch...")
                    smart_sleep(1.0, apply_speed=True)

                    next_id = (active_id % total_ids) + 1
                    switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["phase"] = "START_CYCLE"
                    runtime_state["attacks_done"] = 0

                    print(f" [MODE {bot_mode}] Arrived on ID #{next_id}! Waiting 1.0 second before starting {fast_mode_attacks_per_id} Fast Attacks...")
                    smart_sleep(1.0, apply_speed=True)

            # ---------------------------------------------------------
            # MODE 11: SMART LOOT-FIRST TURBO (UPGRADE -> 5 ATK -> UPGRADE -> SWITCH)
            # ---------------------------------------------------------
            elif bot_mode == "11":
                if runtime_state["phase"] == "START_CYCLE":
                    run_full_smart_upgrade_sequence(stop_builders=1)
                    runtime_state["phase"] = "M11_ATTACKS"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "M11_ATTACKS":
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=5,
                        phase_label=f"MODE 11 | ID #{active_id} (5 TURBO ATTACKS)"
                    )
                    runtime_state["phase"] = "M11_UPGRADE_2"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "M11_UPGRADE_2":
                    run_full_smart_upgrade_sequence(stop_builders=1)
                    smart_sleep(1.0, apply_speed=True)
                    next_id = (active_id % total_ids) + 1
                    switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["phase"] = "START_CYCLE"
                    runtime_state["attacks_done"] = 0

            # ---------------------------------------------------------
            # MODE 12: 3-WAVE BUILDER-ZERO DOMINATOR (3x [4 ATK + UPG], EXIT ON 0)
            # ---------------------------------------------------------
            elif bot_mode == "12":
                while runtime_state["custom_round_idx"] <= 3:
                    w_no = runtime_state["custom_round_idx"]
                    if runtime_state["phase"] in ["START_CYCLE", "M12_ATTACKS"]:
                        runtime_state["phase"] = "M12_ATTACKS"
                        run_n_fast_attacks_with_resume_memory(
                            runtime_state,
                            target_attacks=4,
                            phase_label=f"MODE 12 | ID #{active_id} (Wave {w_no}/3 - 4 ATTACKS)"
                        )
                        runtime_state["phase"] = "M12_UPGRADE"
                        runtime_state["attacks_done"] = 0

                    if runtime_state["phase"] == "M12_UPGRADE":
                        rem_b = run_full_smart_upgrade_sequence(stop_builders=0)
                        if rem_b <= 0:
                            print(f" [✔] [MODE 12] 0 Builders left on Wave #{w_no}! Switching ID early...")
                            break
                        runtime_state["custom_round_idx"] += 1
                        runtime_state["phase"] = "START_CYCLE"

                smart_sleep(1.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                runtime_state["custom_round_idx"] = 1
                runtime_state["phase"] = "START_CYCLE"
                runtime_state["attacks_done"] = 0

            # ---------------------------------------------------------
            # MODE 13: OVERNIGHT MARATHON MODE (20 MIN CONTINUOUS PER ID)
            # ---------------------------------------------------------
            elif bot_mode == "13":
                if runtime_state["id_timer_start"] is None:
                    runtime_state["id_timer_start"] = time.time()
                    runtime_state["id_elapsed_sec"] = 0.0

                while True:
                    check_pause_point(allow_raise=True)
                    elapsed_m = runtime_state["id_elapsed_sec"] + (time.time() - runtime_state["id_timer_start"])
                    if elapsed_m >= 1200.0:
                        print(f"\n [20 MIN MARATHON COMPLETE] Switching from ID #{active_id}...")
                        break
                    runtime_state["attacks_done"] = 0
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=3,
                        phase_label=f"MODE 13 MARATHON | ID #{active_id} ({elapsed_m/60.0:.1f}m/20m)"
                    )
                    run_full_smart_upgrade_sequence(stop_builders=1)

                smart_sleep(1.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                runtime_state["id_timer_start"] = None
                runtime_state["id_elapsed_sec"] = 0.0
                runtime_state["attacks_done"] = 0

            # ---------------------------------------------------------
            # MODE 14: CREATE OPTIONS (MANUAL CUSTOM BUILDER)
            # ---------------------------------------------------------
            elif bot_mode == "14":
                combo = custom_cfg.get("combo_type", "1+2+3")
                atk_target = int(custom_cfg.get("attacks_per_round", 5))
                upg_order = custom_cfg.get("upgrade_order", "BUILDING_THEN_WALL")
                inc_spec = bool(custom_cfg.get("include_specials", True))
                chk_store = bool(custom_cfg.get("check_storage", False))
                stop_b = int(custom_cfg.get("stop_builders", 0))
                max_rounds = int(custom_cfg.get("rounds_per_id", 3)) if "3" in combo else 1

                while runtime_state["custom_round_idx"] <= max_rounds:
                    r_no = runtime_state["custom_round_idx"]
                    print(f"\n [CUSTOM MODE 14] ID #{active_id} | Attempt/Round #{r_no}/{max_rounds} | Combo={combo} | Order={upg_order}")

                    if runtime_state["phase"] in ["START_CYCLE", "CUSTOM_ATTACKS"]:
                        runtime_state["phase"] = "CUSTOM_ATTACKS"
                        run_n_fast_attacks_with_resume_memory(
                            runtime_state,
                            target_attacks=atk_target,
                            phase_label=f"CUSTOM MODE 14 | ID #{active_id} (Round {r_no}/{max_rounds} - {atk_target} ATTACKS)"
                        )
                        runtime_state["phase"] = "CUSTOM_UPGRADE"
                        runtime_state["attacks_done"] = 0

                    if runtime_state["phase"] == "CUSTOM_UPGRADE":
                        if "2" in combo:
                            do_upg = True
                            if chk_store:
                                perform_home_cleanup_once(max_age_sec=1.5)
                                do_upg = check_resources_full_for_upgrade()
                            if do_upg:
                                run_custom_mode_upgrade_loop(
                                    order_type=upg_order,
                                    stop_at_builders=stop_b,
                                    include_specials=inc_spec
                                )
                                if bot_tools.LAST_DETECTED_BUILDERS is not None and bot_tools.LAST_DETECTED_BUILDERS <= stop_b:
                                    print(f" [✔] [CUSTOM MODE 14] Builders reached {bot_tools.LAST_DETECTED_BUILDERS} (<= {stop_b}) on Round #{r_no}! Proceeding to ID Switch...")
                                    runtime_state["custom_round_idx"] = max_rounds + 1
                                    break
                        runtime_state["custom_round_idx"] += 1
                        runtime_state["phase"] = "START_CYCLE"

                if "3" in combo:
                    smart_sleep(1.0, apply_speed=True)
                    next_id = (active_id % total_ids) + 1
                    switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    smart_sleep(1.0, apply_speed=True)

                runtime_state["custom_round_idx"] = 1
                runtime_state["phase"] = "START_CYCLE"
                runtime_state["attacks_done"] = 0

            # ---------------------------------------------------------
            # MODE 15: DIRECT FULL UPGRADE -> 5 FAST ATTACKS -> DIRECT FULL UPGRADE -> ID SWITCH
            # (Bina Resource/Storage Check kiye 100% Accuracy ke sath Fast Full Upgrade!)
            # ---------------------------------------------------------
            elif bot_mode == "15":
                if runtime_state["phase"] in ["START_CYCLE", "M15_DIRECT_UPGRADE_1"]:
                    runtime_state["phase"] = "M15_DIRECT_UPGRADE_1"
                    print(f"\n [MODE 15 | STEP 1/4] ID #{active_id} Open hote hi Bina Resource Check kiye Direct Full Upgrade (Building + Wall + Equipment) start kar rahe hain...")
                    perform_home_cleanup_once(max_age_sec=1.5)
                    run_full_smart_upgrade_sequence(
                        do_bldg=True,
                        do_wall=True,
                        do_spell=True,
                        do_pet=True,
                        do_equip=True,
                        stop_builders=0
                    )
                    runtime_state["phase"] = "M15_FAST_ATTACKS_5"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "M15_FAST_ATTACKS_5":
                    print(f"\n [MODE 15 | STEP 2/4] First Full Upgrade complete! Ab turant 5 Fast Attacks start kar rahe hain...")
                    run_n_fast_attacks_with_resume_memory(
                        runtime_state,
                        target_attacks=5,
                        phase_label=f"MODE 15 | ID #{active_id} (5 FAST ATTACKS)"
                    )
                    runtime_state["phase"] = "M15_DIRECT_UPGRADE_2"
                    runtime_state["attacks_done"] = 0

                if runtime_state["phase"] == "M15_DIRECT_UPGRADE_2":
                    print(f"\n [MODE 15 | STEP 3/4] 5 Fast Attacks complete! Ab Bina Resource Check kiye 2nd Direct Full Upgrade (Building + Wall + Equipment) start kar rahe hain...")
                    perform_home_cleanup_once(max_age_sec=1.5)
                    run_full_smart_upgrade_sequence(
                        do_bldg=True,
                        do_wall=True,
                        do_spell=True,
                        do_pet=True,
                        do_equip=True,
                        stop_builders=0
                    )
                    runtime_state["phase"] = "M15_SWITCH_ID"

                if runtime_state["phase"] == "M15_SWITCH_ID":
                    print(f"\n [MODE 15 | STEP 4/4] 2nd Full Upgrade complete! Turant Next ID par switch kar rahe hain...")
                    smart_sleep(0.5, apply_speed=True)
                    next_id = (active_id % total_ids) + 1
                    switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["phase"] = "START_CYCLE"
                    runtime_state["attacks_done"] = 0
                    smart_sleep(0.5, apply_speed=True)

            save_current_progress_report()
            clean_ram_garbage()
            consecutive_loop_errors = 0

            print(f"\n[SUCCESS] Master Cycle #{cycle_count} Completed! (Speed={get_bot_speed_multiplier():.2f}x)")
            cycle_count += 1
            smart_sleep(random.uniform(0.40, 0.70), apply_speed=True)

        except BotPausedResumeHomeException as resume_sig:
            print(f"\n[RESUME HANDLER] {resume_sig} (Speed={get_bot_speed_multiplier():.2f}x Preserved)")
            if bot_mode in ["6", "13"] and runtime_state["id_timer_start"] is not None:
                runtime_state["id_elapsed_sec"] += max(0.0, time.time() - runtime_state["id_timer_start"])
                runtime_state["id_timer_start"] = time.time()

            ensure_return_to_home_page_a14()
            zoom_out_village_a14(passes=2, reason="RESUME HOME ZOOM-OUT")
            human_sleep(0.6, 0.10)
            print(f" [RESUMED ON HOME PAGE] Continuing ID #{runtime_state['current_id']} | Phase: {runtime_state['phase']} | Attacks Done: {runtime_state['attacks_done']} | Speed: {get_bot_speed_multiplier():.2f}x")
            continue

        except KeyboardInterrupt:
            print("\n[!] Bot ko manually roka gaya (Ctrl+C). Saving & Generating Final Previous Progress Report...")
            save_current_progress_report()
            print_previous_progress_report(report_stage="STOPPED / COMPLETED (FINAL SESSION REPORT)")
            break

        except Exception as e:
            consecutive_loop_errors += 1
            record_stat("stuck_recoveries", 1)
            print("\n==================================================")
            print(f"[! CRITICAL ERROR #{consecutive_loop_errors} !] Main Loop me error aayi:")
            print(f"-> Reason: {str(e)}")
            traceback.print_exc()
            print("==================================================")
            print("Recovering in 2.5 seconds...")
            time.sleep(2.5)
            ensure_return_to_home_page_a14()
            zoom_out_village_a14(passes=2, reason="ERROR RECOVERY ZOOM-OUT")

            if consecutive_loop_errors >= 5 and int(bot_mode) >= 5 and total_ids > 1:
                next_id = (runtime_state["current_id"] % total_ids) + 1
                print(f" [NIGHT WATCHDOG] 5 consecutive errors on ID #{runtime_state['current_id']}! Switching to ID #{next_id}...")
                switch_to_target_id(next_id, total_ids, current_id_index=runtime_state["current_id"])
                runtime_state["current_id"] = next_id
                runtime_state["phase"] = "START_CYCLE"
                runtime_state["attacks_done"] = 0
                runtime_state["custom_round_idx"] = 1
                consecutive_loop_errors = 0

if __name__ == "__main__":
    main_loop()
