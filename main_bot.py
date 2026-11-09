# main_bot.py
# Entry Point for Clash of Clans AI Bot v9 (Samsung Galaxy A14 Edition)
# (100% Original V8 Main Loop + V9 Custom Mode & Progress Report Integrations)

import os
import json
import time
import random
import traceback

import bot_config
from bot_config import ADVANCE_SPEED_TABLE
import bot_adb
from bot_adb import BotPausedResumeHomeException
import bot_popups
import bot_report
import bot_id_switch
import bot_attack
import bot_modes
import bot_upgrade_buildings
import bot_upgrade_special

# ==========================================
# 1. CUSTOM MODE (V9) CONFIGURATOR & UI
# ==========================================
def configure_custom_mode_14():
    """Builds and saves the Custom Mode Preset (Mode 14)."""
    preset = {
        "combo_type": "1+2+3",
        "attacks_per_round": 5,
        "upgrade_order": "BUILDING_THEN_WALL",
        "check_storage": False,
        "stop_builders": 0,
        "rounds_per_id": 3
    }
    if os.path.exists(bot_config.CUSTOM_PRESET_FILE):
        try:
            with open(bot_config.CUSTOM_PRESET_FILE, "r") as f:
                preset.update(json.load(f))
        except: pass

    print("\n==============================================================================")
    print(" ||         OPTION [14]: CREATE OPTIONS (MANUAL CUSTOM BUILDER)             ||")
    print("==============================================================================")
    print(" || Saved Custom Preset Summary:                                             ||")
    print(f" ||   * Combination      : {preset['combo_type']}                                              ||")
    print(f" ||   * Attacks / Round  : {preset['attacks_per_round']} Fast Attacks                                    ||")
    print(f" ||   * Upgrade Sequence : {preset['upgrade_order']}                             ||")
    print(f" ||   * Storage Check    : {'Yes' if preset['check_storage'] else 'No (Direct Fast Upgrade)'}                               ||")
    print(f" ||   * Builder Target   : Stop at {preset['stop_builders']} Builder(s)                                ||")
    print(f" ||   * Attempts per ID  : {preset['rounds_per_id']} Round(s) before ID Switch                       ||")
    print("==============================================================================")

    if input("\n Kya pichhla Saved Custom Preset use karein? (y/n) [Default=y]: ").strip().lower() in ["", "y", "yes"]:
        return preset

    print("\n [STEP 1] Select System Combination:")
    print("   [1] -> 1 + 3 : Fast Attack + ID Switching Only")
    print("   [2] -> 1 + 2 : Fast Attack + Fast Upgrading Only")
    print("   [3] -> 1 + 2 + 3 : Fast Attack + Fast Upgrading + ID Switching (Full Custom Sequence)")
    c_in = input(" Option type karein (1/2/3) [Default=3]: ").strip()
    preset["combo_type"] = "1+3" if c_in == "1" else ("1+2" if c_in == "2" else "1+2+3")

    raw_atk = input(f"\n [STEP 2] Har round me kitne Fast Attacks karne hain? (1-50) [Default={preset['attacks_per_round']}]: ").strip()
    if raw_atk.isdigit(): preset["attacks_per_round"] = int(raw_atk)

    if "2" in preset["combo_type"]:
        print("\n [STEP 3] Select Upgrade Category & Sequence Order:")
        print("   [1] -> Building Upgrade FIRST -> then Wall Upgrade")
        print("   [2] -> Wall Upgrade FIRST -> then Building Upgrade")
        print("   [3] -> Building Upgrade ONLY (No Wall)")
        print("   [4] -> Wall Upgrade ONLY (No Building)")
        u_in = input(" Option type karein (1/2/3/4) [Default=1]: ").strip()
        preset["upgrade_order"] = {"2":"WALL_THEN_BUILDING", "3":"BUILDING_ONLY", "4":"WALL_ONLY"}.get(u_in, "BUILDING_THEN_WALL")
        
        preset["check_storage"] = (input("\n [STEP 4] Storage Check karein ya Direct Upgrade? (d=Direct / c=Check) [Default=d]: ").strip().lower() == "c")
        preset["stop_builders"] = 1 if input("\n [STEP 5] Builders kitne bachne par upgrade close karein? (0/1) [Default=0]: ").strip() == "1" else 0

    if "3" in preset["combo_type"]:
        r_in = input(f"\n [STEP 6] Ek ID par (Attack+Upgrade) kitne Attempts/Rounds chalane ke baad ID Switch karein? (1-10) [Default=3]: ").strip()
        preset["rounds_per_id"] = int(r_in) if r_in.isdigit() else 3

    try:
        with open(bot_config.CUSTOM_PRESET_FILE, "w") as f:
            json.dump(preset, f, indent=2)
    except: pass
    return preset

# ==========================================
# 2. ADVANCE SPEED FEATURES MENU (A-Y)
# ==========================================
def open_advance_features_menu():
    letter_to_spd = {l: m for l, m, _ in ADVANCE_SPEED_TABLE}
    while True:
        cur_spd = bot_config.get_bot_speed_multiplier()
        print("\n======================================================================")
        print(" ||        ADVANCE FEATURES MENU - GAME SPEED-UP SYSTEM              ||")
        print("======================================================================")
        print(f" || Current Active Bot Speed : {cur_spd:.2f}x                               ||")
        for l, m, desc in ADVANCE_SPEED_TABLE:
            print(f" ||   [{l}] -> {m:.2f}x  ({desc}) {'<-- [ACTIVE]' if abs(cur_spd-m)<0.005 else ''}")
        print(" ||   [R] -> View Current / Previous Progress Report               ||")
        print(" ||   [0] -> Back to Main Bot Operating Menu                       ||")
        print("======================================================================")

        raw = input("\n Speed Option type karein (A-Y), R (Report), ya 0 wapas jane ke liye [Default=A]: ").strip().upper()
        if not raw or raw == "0": break
        if raw == "R":
            bot_report.print_previous_progress_report(report_stage="MENU PREVIEW")
            continue
        if raw in letter_to_spd:
            bot_config.set_bot_speed_multiplier(letter_to_spd[raw])
            break
        print(" [!] Galat input! Kripya A se Y ke beech chunein.")

# ==========================================
# 3. MAIN UI BOT CONFIGURATION
# ==========================================
def select_bot_configuration():
    while True:
        cur_spd = bot_config.get_bot_speed_multiplier()
        print("\n==============================================================================")
        print(" ||      CLASH OF CLANS AI BOT v9 - SAMSUNG GALAXY A14 ULTIMATE EDITION      ||")
        print("==============================================================================")
        print(f" || Active Speed : {cur_spd:.2f}x {'(Default)' if abs(cur_spd - 1.0) < 0.005 else '(Root Speed-Up Active!)'}")
        print("------------------------------------------------------------------------------")
        print(" || Select Bot Operating Mode (1 to 14):                                     ||")
        print(" || [1] -> Fast Attack Only                  (सिर्फ फास्ट अटैक - Infinity)      ||")
        print(" || [2] -> Combined Building & Wall Only     (बिल्डिंग + वॉल अपग्रेड - 1m Gap)  ||")
        print(" || [3] -> Combined Special Upgrade Only     (Spells + Pets + Equipments)    ||")
        print(" || [4] -> Tried All                         (Smart Upgrade + 10 Attacks)    ||")
        print(" || [5] -> ID Changement Only                (सिर्फ ID चेंज - हर 2 सेकंड में)    ||")
        print(" || [6] -> ID Changement + Fast Attack       (हर ID पर 10 Min अटैक स्विच)      ||")
        print(" || [7] -> ID Changement + Tried All         (Fully Botted System - Default) ||")
        print(" || [8] -> Game Speed Control                (Speed-Up: 1.00x to 2.25x)      ||")
        print(" || [9] -> Fast Mode 1                       (5 Atk -> Bldg & Wall -> Switch)||")
        print(" || [10]-> Fast Mode 2                       (5 Atk -> Upg till 0 Builders)  ||")
        print(" || [11]-> Smart Loot-First Turbo Mode [M1]  (Upg -> 5 Atk -> Upg -> Switch) ||")
        print(" || [12]-> 3-Wave Builder-Zero Dominator[M2] (3x [4 Atk + Upg], Exit on 0)   ||")
        print(" || [13]-> Overnight Marathon Mode [M7]      (20 Min Continues Loop per ID)  ||")
        print(" || [14]-> Create Options (Custom Builder)   (1+3 / 1+2 / 5 Atk+Bld+Wall+3x) ||")
        print("==============================================================================")
        print(" || Controls: 'ZX' = Pause/Live Report | 'QW' = Resume | Ctrl+C = Stop       ||")
        print("==============================================================================")

        choice = input("\n Apna Option type karein (1-14) [Default=7]: ").strip()
        if not choice: choice = "7"
        if choice == "8":
            open_advance_features_menu()
            continue
        if choice in [str(i) for i in range(1, 15)]:
            break
        print(" [!] Galat input! 1 se 14 ke beech number type karein.")

    custom_cfg = configure_custom_mode_14() if choice == "14" else {}
    mode_names = {
        "1": "MODE 1: FAST ATTACK ONLY (Infinity)", "2": "MODE 2: BUILDING & WALL UPGRADE (1 Min Gap)",
        "3": "MODE 3: SPECIAL UPGRADE ONLY", "4": "MODE 4: TRIED ALL (Combined Upgrade + 10 Attacks)",
        "5": "MODE 5: ID CHANGEMENT ONLY", "6": "MODE 6: ID CHANGE + FAST ATTACK",
        "7": "MODE 7: FULLY BOTTED SYSTEM", "9": "MODE 9: FAST MODE 1",
        "10": "MODE 10: FAST MODE 2", "11": "MODE 11: SMART LOOT-FIRST TURBO",
        "12": "MODE 12: 3-WAVE BUILDER-ZERO DOMINATOR", "13": "MODE 13: 20-MIN MARATHON",
        "14": f"MODE 14: CUSTOM ({custom_cfg.get('combo_type')} | {custom_cfg.get('rounds_per_id',1)}x Rounds)"
    }
    print(f"\n [✔] Selected Mode: [{choice}] -> {mode_names[choice]} | Speed: {cur_spd:.2f}x")

    total_ids, start_id = 1, 1
    needs_id = (int(choice) >= 5 and int(choice) != 8) or (choice == "14" and "3" in custom_cfg.get("combo_type", ""))
    
    if needs_id:
        mem = bot_id_switch.load_id_memory()
        default_tot = mem.get("total_ids", 10)
        raw_tot = input(f" Total IDs type karein (1-100, First 4 = Main ID) [Default={default_tot}]: ").strip()
        total_ids = int(raw_tot) if raw_tot.isdigit() else default_tot

        saved_idx = mem.get("current_id_index", 1)
        if 1 < saved_idx <= total_ids:
            if input(f" Pichhli baar Bot ID #{saved_idx} par tha. Resume karein? (y/n) [Default=n]: ").strip().lower() == "y":
                start_id = saved_idx

        mem["total_ids"], mem["current_id_index"] = total_ids, start_id
        bot_id_switch.save_id_memory(mem)
        print(f" [✔] ID Configured: Total IDs = {total_ids} | Start = ID #{start_id}")

    bot_report.reset_session_progress_report(mode_label=mode_names[choice])
    bot_id_switch.sync_initial_id_to_report(start_id)

    input("\n Bot Start karne ke liye [ENTER] key dabayein: ")
    return choice, total_ids, start_id, custom_cfg

# ==========================================
# 4. THE MASTER LOOP (100% Original Logic Core)
# ==========================================
def main_loop():
    # 1. Print Yesterday's / Previous Progress Report before starting!
    bot_report.print_saved_progress_report()
    
    bot_mode, total_ids, current_id, custom_cfg = select_bot_configuration()
    
    # 2. Start Background Keyboard Listener ('ZX' / 'QW')
    bot_report.start_pause_resume_listener()

    # 3. Initial Zoom-Out to secure the base view
    bot_adb.zoom_out_village_a14(passes=2, reason="BOT STARTUP HOME PAGE ZOOM-OUT")

    if int(bot_mode) >= 9:
        print(f"\n[STARTUP] Waiting 1.0s on ID #{current_id} before starting Mode {bot_mode}...")
        bot_adb.smart_sleep(1.0, apply_speed=True)
    else:
        bot_adb.smart_sleep(random.uniform(0.8, 1.2), apply_speed=True)

    cycle_count = 1
    consecutive_errors = 0
    runtime_state = {"current_id": current_id, "id_timer_start": None, "attacks_done": 0, "phase": "START_CYCLE"}

    while True:
        try:
            bot_adb.check_pause_point(allow_raise=True)
            active_id = runtime_state["current_id"]
            
            print("\n" + "=" * 74)
            print(f" MASTER CYCLE #{cycle_count} | MODE: [{bot_mode}] | ID: #{active_id}/{total_ids} | Speed: {bot_config.get_bot_speed_multiplier():.2f}x")
            print("=" * 74)

            bot_popups.run_zone2_home_periodic_checks()

            # -----------------------------------------------------
            # STANDARD MODES (1 to 7)
            # -----------------------------------------------------
            if bot_mode == "1":
                bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 1, phase_label="MODE 1 (INFINITY)")
            
            elif bot_mode == "2":
                bot_modes.run_combined_building_and_wall_upgrade("MODE 2 COMBINED UPGRADE", stop_builders=1)
                print(" [MODE 2] Waiting 1 Minute (60s) before next Combined Upgrade resource check...")
                bot_adb.smart_sleep(60.0, apply_speed=False)
                
            elif bot_mode == "3":
                bot_modes.run_full_smart_upgrade_sequence(do_bldg=False, do_wall=False, stop_builders=1)
                bot_adb.smart_sleep(60.0, apply_speed=False)
                
            elif bot_mode == "4":
                bot_modes.run_combined_building_and_wall_upgrade("MODE 4 COMBINED UPGRADE", stop_builders=1)
                runtime_state["attacks_done"] = 0
                bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 10, phase_label="MODE 4 (10 ATTACKS)")
                
            elif bot_mode == "5":
                print(f" [MODE 5] Holding 2 Seconds on ID #{active_id}...")
                bot_popups.perform_home_cleanup_once(max_age_sec=1.0)
                bot_adb.smart_sleep(2.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                
            elif bot_mode == "6":
                if runtime_state["id_timer_start"] is None:
                    runtime_state["id_timer_start"] = time.time()
                elapsed = time.time() - runtime_state["id_timer_start"]
                if elapsed >= 600.0:
                    print(f"\n [10 MIN COMPLETE] Switching from ID #{active_id}...")
                    next_id = (active_id % total_ids) + 1
                    bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["id_timer_start"] = None
                else:
                    bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 1, phase_label=f"MODE 6 ({elapsed/60.0:.1f}m / 10m)")
                    
            elif bot_mode == "7":
                bot_modes.run_full_smart_upgrade_sequence(stop_builders=1)
                runtime_state["attacks_done"] = 0
                bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 10, phase_label=f"MODE 7 | ID #{active_id}")
                bot_modes.run_full_smart_upgrade_sequence(stop_builders=1)
                next_id = (active_id % total_ids) + 1
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id

            # -----------------------------------------------------
            # ADVANCED MODES (9 to 14)
            # -----------------------------------------------------
            elif bot_mode == "9":
                runtime_state["attacks_done"] = 0
                bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 5, phase_label=f"MODE 9 | ID #{active_id}")
                bot_modes.run_full_smart_upgrade_sequence(do_spell=False, do_pet=False, do_equip=False, stop_builders=1)
                bot_adb.smart_sleep(1.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                
            elif bot_mode == "10":
                runtime_state["attacks_done"] = 0
                bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 5, phase_label=f"MODE 10 | ID #{active_id}")
                bot_modes.run_full_smart_upgrade_sequence(do_spell=True, do_pet=True, do_equip=True, stop_builders=0)
                bot_adb.smart_sleep(1.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                
            elif bot_mode == "11":
                bot_modes.run_full_smart_upgrade_sequence(stop_builders=1)
                runtime_state["attacks_done"] = 0
                bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 5, phase_label=f"MODE 11 | ID #{active_id}")
                bot_modes.run_full_smart_upgrade_sequence(stop_builders=1)
                bot_adb.smart_sleep(1.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                
            elif bot_mode == "12":
                for r in range(1, 4):
                    runtime_state["attacks_done"] = 0
                    bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 4, phase_label=f"MODE 12 | Round {r}")
                    rem_bldrs = bot_modes.run_full_smart_upgrade_sequence(stop_builders=0)
                    if rem_bldrs == 0: break
                bot_adb.smart_sleep(1.0, apply_speed=True)
                next_id = (active_id % total_ids) + 1
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
                
            elif bot_mode == "13":
                if runtime_state["id_timer_start"] is None:
                    runtime_state["id_timer_start"] = time.time()
                elapsed = time.time() - runtime_state["id_timer_start"]
                if elapsed >= 1200.0:
                    bot_adb.smart_sleep(1.0, apply_speed=True)
                    next_id = (active_id % total_ids) + 1
                    bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["id_timer_start"] = None
                else:
                    runtime_state["attacks_done"] = 0
                    bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, 3, phase_label=f"MODE 13 MARATHON | ID #{active_id}")
                    bot_modes.run_full_smart_upgrade_sequence(stop_builders=1)
                
            elif bot_mode == "14":
                combo = custom_cfg.get("combo_type", "1+2+3")
                atk_target = int(custom_cfg.get("attacks_per_round", 5))
                upg_order = custom_cfg.get("upgrade_order", "BUILDING_THEN_WALL")
                chk_store = bool(custom_cfg.get("check_storage", False))
                stop_b = int(custom_cfg.get("stop_builders", 0))
                max_rounds = int(custom_cfg.get("rounds_per_id", 3)) if "3" in combo else 1

                for r_no in range(1, max_rounds + 1):
                    runtime_state["attacks_done"] = 0
                    bot_modes.run_n_fast_attacks_with_resume_memory(runtime_state, atk_target, phase_label=f"CUSTOM 14 | ID #{active_id} (Round {r_no})")
                    if "2" in combo:
                        do_upg = True
                        if chk_store:
                            bot_popups.perform_home_cleanup_once(max_age_sec=1.5)
                            do_upg = bot_popups.check_resources_full_for_upgrade()
                        if do_upg:
                            do_b = ("BUILDING" in upg_order)
                            do_w = ("WALL" in upg_order)
                            rem_b = bot_modes.run_full_smart_upgrade_sequence(do_bldg=do_b, do_wall=do_w, stop_builders=stop_b)
                            if rem_b <= stop_b: break
                
                if "3" in combo:
                    bot_adb.smart_sleep(1.0, apply_speed=True)
                    next_id = (active_id % total_ids) + 1
                    bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id

            bot_adb.clean_ram_garbage()
            consecutive_errors = 0
            cycle_count += 1
            bot_adb.smart_sleep(random.uniform(0.40, 0.70), apply_speed=True)

        except BotPausedResumeHomeException as resume_sig:
            print(f"\n[RESUME HANDLER] {resume_sig}")
            bot_popups.ensure_return_to_home_page_a14()
            bot_adb.zoom_out_village_a14(passes=2, reason="RESUME HOME ZOOM-OUT")
            bot_adb.human_sleep(0.6, 0.10)
            continue

        except KeyboardInterrupt:
            print("\n[!] Bot manually stopped (Ctrl+C). Generating Final Report...")
            bot_report.print_previous_progress_report(report_stage="STOPPED (FINAL SESSION REPORT)")
            break

        except Exception as e:
            consecutive_errors += 1
            bot_report.record_stat("stuck_recoveries", 1)
            print("\n==================================================")
            print(f"[! CRITICAL ERROR #{consecutive_errors} !] Main Loop Error:")
            traceback.print_exc()
            print("==================================================")
            time.sleep(2.5)
            
            bot_popups.ensure_return_to_home_page_a14()
            bot_adb.zoom_out_village_a14(passes=2, reason="ERROR RECOVERY ZOOM-OUT")

            if consecutive_errors >= 5 and int(bot_mode) >= 5 and total_ids > 1:
                next_id = (runtime_state["current_id"] % total_ids) + 1
                print(f" [🛡 NIGHT WATCHDOG] 5 errors on ID #{runtime_state['current_id']}! Switching to ID #{next_id}...")
                bot_id_switch.switch_to_target_id(next_id, total_ids, current_id_index=runtime_state["current_id"])
                runtime_state["current_id"] = next_id
                consecutive_errors = 0
                runtime_state["attacks_done"] = 0

if __name__ == "__main__":
    main_loop()
