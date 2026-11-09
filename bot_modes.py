# bot_modes.py
# Master Controller for All 14 Modes (Including New Turbo, Dominator & Marathon Modes)

import time
import random
import os
import json

from bot_coords import UPGRADE_A14
import bot_adb
import bot_popups
import bot_attack
import bot_upgrade_buildings
import bot_upgrade_special
from bot_report import record_duration

# ==========================================
# UNIVERSAL HELPERS
# ==========================================
def run_n_attacks(target_attacks, phase_label="ATTACK SERIES"):
    """Executes N consecutive Fast Attacks with safe 3-Step recovery."""
    attacks_done = 0
    consecutive_fails = 0
    while attacks_done < target_attacks:
        bot_adb.check_pause_point(allow_raise=True)
        print(f"\n [{phase_label}] Attack #{attacks_done + 1} / {target_attacks} starting...")
        bot_adb.smart_sleep(random.uniform(0.20, 0.38))
        
        if bot_attack.execute_attack(is_first_attack=(attacks_done == 0)):
            attacks_done += 1
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails >= 2:
                print(" [🛡 SMART RECOVERY] 2 consecutive attacks failed! Breaking series to prevent stuck loop...")
                bot_popups.ensure_return_to_home_page_a14()
                break
        
        if attacks_done > 0 and attacks_done % 5 == 0 and attacks_done < target_attacks:
            bot_popups.run_zone2_home_periodic_checks()

def run_full_smart_upgrade_sequence(do_bldg=True, do_wall=True, do_spell=True, do_pet=True, do_equip=True, stop_builders=1):
    """
    Unified In-Menu Smart Upgrade Sequence:
    Building -> Wall -> Spell -> Pet -> Equipment (Skips instantly if Goblin Builder is found).
    Returns remaining_builders.
    """
    upg_start_t = time.time()
    print("\n======================================================================")
    print(f"|| [SMART UPGRADE SEQUENCE] Target Stop Builders <= {stop_builders} ||")
    print("======================================================================")
    
    bot_adb.tap(*UPGRADE_A14["BUILD_CLICK"], delay_range=(0.20, 0.32), jitter=3)
    bot_adb.human_sleep(0.45, 0.05)
    
    goblin_found = False
    rem_bldrs = 0

    # 1. Building Phase
    if do_bldg and not goblin_found:
        _, rem_bldrs, _, goblin_found = bot_upgrade_buildings.run_condition_1_buildings(
            handoff_to_wall=True, stop_at_builders=max(1, stop_builders)
        )
    
    # 2. Wall Phase
    if do_wall and not goblin_found and rem_bldrs >= 1:
        _, goblin_found = bot_upgrade_buildings.run_wall_upgrade_process(
            from_building_handoff=do_bldg, close_menu_on_exit=False
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

    # Close Menu & Zoom Out
    print(" [x] Smart Upgrade Sequence Finished. Closing Menu (2322, 45)...")
    bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.30), jitter=3)
    bot_adb.human_sleep(0.35, 0.05)
    bot_popups.perform_home_cleanup_once(max_age_sec=0.0)
    bot_adb.zoom_out_village_a14(passes=2, reason="POST-UPGRADE HOME RESET")
    
    record_duration("upgrade", time.time() - upg_start_t)
    return rem_bldrs

# ==========================================
# ADVANCED MODES LOGIC (Modes 9 to 14)
# ==========================================
def execute_mode_9_fast_1(active_id):
    """Mode 9: 5 Attacks -> Building & Wall Upgrade -> Switch ID"""
    run_n_attacks(5, phase_label=f"MODE 9 | ID #{active_id}")
    print("\n [⚡ MODE 9] 5 Attacks done! Directly running Building & Wall Upgrade...")
    run_full_smart_upgrade_sequence(do_spell=False, do_pet=False, do_equip=False, stop_builders=1)

def execute_mode_10_fast_2(active_id):
    """Mode 10: 5 Attacks -> Full Upgrade until 0 Builders -> Switch ID"""
    run_n_attacks(5, phase_label=f"MODE 10 | ID #{active_id}")
    print("\n [⚡ MODE 10] 5 Attacks done! Upgrading everything until 0 Builders...")
    run_full_smart_upgrade_sequence(do_spell=True, do_pet=True, do_equip=True, stop_builders=0)

def execute_mode_11_smart_loot_first_turbo(active_id):
    """Mode 11 (M1): Upgrade First -> 5 Attacks -> Upgrade Again -> Switch ID"""
    print("\n [🔥 MODE 11 TURBO] Step 1: Pre-Attack Smart Upgrade (Emptying Storages)...")
    run_full_smart_upgrade_sequence(stop_builders=1)
    
    run_n_attacks(5, phase_label=f"MODE 11 | ID #{active_id} (Refilling Storages)")
    
    print("\n [🔥 MODE 11 TURBO] Step 3: Post-Attack Smart Upgrade (Using Loot)...")
    run_full_smart_upgrade_sequence(stop_builders=1)

def execute_mode_12_builder_zero_dominator(active_id):
    """Mode 12 (M2): Up to 3 Rounds of [4 Attacks + Upgrade(0)]. Exits early if 0 builders."""
    max_rounds = 3
    for r in range(1, max_rounds + 1):
        print(f"\n [🏆 MODE 12 DOMINATOR] ID #{active_id} - Round {r}/{max_rounds}...")
        run_n_attacks(4, phase_label=f"MODE 12 | Round {r}")
        
        rem_bldrs = run_full_smart_upgrade_sequence(stop_builders=0)
        
        if rem_bldrs == 0:
            print(f" [✔] [DOMINATOR EXIT] All builders busy (0 left) on Round {r}! Switching ID early to save time...")
            break

def execute_mode_13_overnight_marathon(active_id):
    """Mode 13 (M7): Continuous [3 Attacks + Smart Upgrade] for exactly 20 Minutes per ID."""
    print(f"\n [🌙 MODE 13 MARATHON] Starting 20-Minute Marathon on ID #{active_id}...")
    start_t = time.time()
    marathon_duration = 1200.0 # 20 Minutes
    
    while (time.time() - start_t) < marathon_duration:
        bot_adb.check_pause_point(allow_raise=True)
        elapsed = time.time() - start_t
        print(f"\n [🌙 MARATHON TIME] {elapsed/60.0:.1f}m / 20.0m elapsed. Starting next wave...")
        
        run_n_attacks(3, phase_label=f"MODE 13 MARATHON | ID #{active_id}")
        run_full_smart_upgrade_sequence(stop_builders=1)

def execute_mode_14_custom(active_id, custom_cfg):
    """Mode 14 (M8): Fully Customizable Routine from bot_custom_preset.json."""
    combo = custom_cfg.get("combo_type", "1+2+3")
    atk_target = int(custom_cfg.get("attacks_per_round", 5))
    upg_order = custom_cfg.get("upgrade_order", "BUILDING_THEN_WALL")
    chk_store = bool(custom_cfg.get("check_storage", False))
    stop_b = int(custom_cfg.get("stop_builders", 0))
    max_rounds = int(custom_cfg.get("rounds_per_id", 3)) if "3" in combo else 1

    for r_no in range(1, max_rounds + 1):
        print(f"\n [🛠️ CUSTOM MODE 14] ID #{active_id} | Round #{r_no}/{max_rounds} | Combo={combo} | Order={upg_order}")
        
        # 1. Attacks
        run_n_attacks(atk_target, phase_label=f"CUSTOM 14 | ID #{active_id} (Round {r_no})")
        
        # 2. Upgrade
        if "2" in combo:
            do_upg = True
            if chk_store:
                bot_popups.perform_home_cleanup_once(max_age_sec=1.5)
                do_upg = bot_popups.check_resources_full_for_upgrade()
            
            if do_upg:
                do_b = ("BUILDING" in upg_order)
                do_w = ("WALL" in upg_order)
                # For custom mode, we do a full sequence based on selections
                rem_bldrs = run_full_smart_upgrade_sequence(
                    do_bldg=do_b, do_wall=do_w, do_spell=True, do_pet=True, do_equip=True, stop_builders=stop_b
                )
                
                if rem_bldrs <= stop_b:
                    print(f" [✔] [CUSTOM 14] Builders reached target ({stop_b}) on Round #{r_no}! Proceeding to ID Switch...")
                    break
