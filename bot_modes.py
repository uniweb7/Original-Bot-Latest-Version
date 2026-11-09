# bot_modes.py
# Master Controller for Modes 1 to 14 (100% Original V8 Engine + V9 Extensions)
# Perfectly routes to bot_attack, bot_upgrade_buildings, and bot_upgrade_special

import time
import random
import bot_adb
import bot_popups
import bot_attack
import bot_upgrade_buildings
import bot_upgrade_special
import bot_report

# ==========================================
# 1. ORIGINAL V8 COMBINED UPGRADE LOOP
# ==========================================

def run_combined_building_and_wall_upgrade(loop_label="COMBINED UPGRADE", stop_builders=1):
    """
    100% Original V8 Logic: Checks storage full status first.
    If full, clicks Build, upgrades Buildings, hands off to Walls, then closes menu.
    """
    bot_adb.check_pause_point(allow_raise=True)
    print("\n----------------------------------------------------------------------")
    print(f" | [{loop_label}] Single Storage Check -> Building -> Wall Handoff |")
    print("----------------------------------------------------------------------")

    if bot_popups.perform_home_cleanup_once(max_age_sec=1.5):
        bot_adb.human_sleep(0.18, 0.04)

    img = bot_adb.get_screenshot()
    bot_popups.check_and_handle_maintenance_break(img)

    print(f"\n [{loop_label}] Checking Gold & Elixir Storage Boxes for Combined Upgrade...")
    if bot_popups.check_resources_full_for_upgrade(img):
        print(" [+] Storage Box is FULL! Starting Combined Upgrade in 0.20s...")
        bot_adb.human_sleep(0.20, 0.04)
        
        upg_start_t = time.time()
        bot_adb.tap(*bot_popups.UPGRADE_A14["BUILD_CLICK"], delay_range=(0.20, 0.32), jitter=3)
        bot_adb.human_sleep(0.45, 0.05)
        
        # Building Phase (Condition 1)
        b_up, rem_b, scrolls_done, g_found = bot_upgrade_buildings.run_condition_1_buildings(
            handoff_to_wall=True, stop_at_builders=stop_builders
        )
        
        # Wall Phase (Condition 2)
        w_up = False
        if rem_b >= 1 and not g_found:
            w_up, _ = bot_upgrade_buildings.run_wall_upgrade_process(
                from_building_handoff=True, building_scrolls_done=scrolls_done, close_menu_on_exit=True
            )
        else:
            bot_adb.tap(*bot_popups.UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
            bot_adb.human_sleep(0.35, 0.05)

        bot_popups.perform_home_cleanup_once(max_age_sec=0.0)
        bot_adb.zoom_out_village_a14(passes=2, reason="POST-UPGRADE HOME RESET")
        bot_report.record_duration("upgrade", time.time() - upg_start_t)
        
        any_up = b_up or w_up
    else:
        print(" [-] Storage Box is not full yet. Skipping Combined Upgrade...")
        b_up, w_up, any_up = False, False, False

    print(f" [{loop_label} RESULT] Building Upgraded: {b_up} | Wall Upgraded: {w_up} | Any Upgraded: {any_up}")
    return b_up, w_up, any_up

# ==========================================
# 2. ORIGINAL V8 FAST ATTACK SERIES LOOP
# ==========================================

def run_n_fast_attacks_with_resume_memory(state_dict, target_attacks, phase_label="ATTACK SERIES"):
    """
    100% Original V8 Logic: Runs N attacks, tracking success/fails.
    If 2 consecutive attacks fail (e.g., due to clouds/wrong buttons), breaks the loop cleanly.
    """
    consecutive_failed_attacks = 0

    while state_dict["attacks_done"] < target_attacks:
        bot_adb.check_pause_point(allow_raise=True)
        next_atk_num = state_dict["attacks_done"] + 1
        pre_attack_wait = random.uniform(0.20, 0.38)
        print(f"\n [{phase_label}] Attack #{next_atk_num} / {target_attacks} starting...")
        bot_adb.smart_sleep(pre_attack_wait, apply_speed=True)

        atk_ok = bot_attack.execute_attack(is_first_attack=(next_atk_num == 1))
        if atk_ok:
            consecutive_failed_attacks = 0
            state_dict["attacks_done"] += 1
            print(f" [✔] [{phase_label}] Completed Attack #{state_dict['attacks_done']} / {target_attacks}!")
        else:
            consecutive_failed_attacks += 1
            print(f" [!] [{phase_label}] Attack #{next_atk_num} unsuccessful (Consecutive Fails: {consecutive_failed_attacks}/2).")
            if consecutive_failed_attacks >= 2:
                print(" [SMART RECOVERY] 2 consecutive full attacks failed on this ID! Advancing to next phase...")
                bot_popups.ensure_return_to_home_page_a14()
                break

        # Periodic health check every 5 attacks
        if state_dict["attacks_done"] > 0 and (state_dict["attacks_done"] % 5 == 0) and (state_dict["attacks_done"] < target_attacks):
            bot_popups.run_zone2_home_periodic_checks()

    bot_popups.run_zone2_home_periodic_checks()

# ==========================================
# 3. V9 EXTENDED SMART UPGRADE (ALL TABS)
# ==========================================

def run_full_smart_upgrade_sequence(do_bldg=True, do_wall=True, do_spell=True, do_pet=True, do_equip=True, stop_builders=1):
    """
    V9 Advanced Upgrade Sequence: 
    Building -> Wall -> Spells -> Pets -> Equipment.
    Instant early-exit if Goblin Builder is detected.
    """
    upg_start_t = time.time()
    print("\n======================================================================")
    print(f"|| [SMART UPGRADE SEQUENCE] Target Stop Builders <= {stop_builders} ||")
    print("======================================================================")
    
    bot_adb.tap(*bot_popups.UPGRADE_A14["BUILD_CLICK"], delay_range=(0.20, 0.32), jitter=3)
    bot_adb.human_sleep(0.45, 0.05)
    
    goblin_found = False
    rem_bldrs = 0
    scrolls_done = 0

    # 1. Building Phase
    if do_bldg and not goblin_found:
        _, rem_bldrs, scrolls_done, goblin_found = bot_upgrade_buildings.run_condition_1_buildings(
            handoff_to_wall=True, stop_at_builders=max(1, stop_builders)
        )
    else:
        rem_bldrs = 2  # Fallback to allow further tabs if building was skipped
    
    # 2. Wall Phase
    if do_wall and not goblin_found and rem_bldrs >= 1:
        _, goblin_found = bot_upgrade_buildings.run_wall_upgrade_process(
            from_building_handoff=do_bldg, building_scrolls_done=scrolls_done, close_menu_on_exit=False
        )

    # 3. Spell Phase
    if do_spell and not goblin_found:
        _, goblin_found = bot_upgrade_special.run_spell_upgrade_process()

    # 4. Pet Phase
    if do_pet and not goblin_found:
        _, goblin_found = bot_upgrade_special.run_pet_upgrade_process()

    # 5. Equipment Phase
    if do_equip and not goblin_found:
        bot_upgrade_special.run_equipment_upgrade_process()

    # Clean Close & Zoom Out
    print(" [x] Smart Upgrade Sequence Finished. Closing Menu (2322, 45)...")
    bot_adb.tap(*bot_popups.UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.30), jitter=3)
    bot_adb.human_sleep(0.35, 0.05)
    bot_popups.perform_home_cleanup_once(max_age_sec=0.0)
    bot_adb.zoom_out_village_a14(passes=2, reason="POST-UPGRADE HOME RESET")
    
    bot_report.record_duration("upgrade", time.time() - upg_start_t)
    return rem_bldrs
