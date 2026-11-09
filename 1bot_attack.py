# bot_attack.py
# Fast Dynamic Attack Engine: Zero Siege Machine, 6-Round Deploy & Early 3-Star Check

import time
import traceback
import bot_config
from bot_coords import FAST_ATTACK
import bot_adb
import bot_vision
import bot_popups
from bot_report import record_stat, record_duration

class RestartLoopException(Exception):
    pass

def wait_for_enemy_base_load_smart(max_wait_sec=18.0):
    """Starts checking for Enemy Battlefield / Clouds just 0.5s after clicking Attack."""
    min_initial_wait = 0.5
    poll_interval = 0.55
    print(f" [SMART 18s LOAD] Waiting initial {min_initial_wait:.1f}s (Max {max_wait_sec:.0f}s) for Enemy Base...")
    start_t = time.time()
    bot_adb.smart_sleep(min_initial_wait, apply_speed=False)

    while (time.time() - start_t) < max_wait_sec:
        bot_adb.check_pause_point(allow_raise=True)
        img = bot_adb.get_screenshot(force_fresh=True)
        elapsed = time.time() - start_t

        if bot_vision.is_cloud_screen_a14(img):
            print(f" [☁️ CLOUDS] Matchmaking clouds visible ({elapsed:.1f}s/{max_wait_sec:.0f}s)... Waiting...")
        elif bot_vision.is_enemy_battlefield_loaded_a14(img):
            print(f" [✔] [BASE LOADED] Enemy Battlefield confirmed in {elapsed:.1f}s (Saved {max_wait_sec - elapsed:.1f}s)!")
            return True
        else:
            if elapsed >= 2.8:
                wrong_found, home_found, _ = bot_popups.check_wrong_and_home_page_a14(img, check_clan_chat=True)
                if wrong_found or home_found:
                    reason = "Wrong Button / Clan Chat blocked matchmaking" if wrong_found else f"Stuck on Home Page at {elapsed:.1f}s"
                    print(f" [!] [FAST MATCHMAKING RETRY] {reason}! Restarting Attack Loop...")
                    raise RestartLoopException(reason)

        rem = max_wait_sec - (time.time() - start_t)
        if rem <= 0: break
        bot_adb.smart_sleep(min(poll_interval, rem), apply_speed=False)
    return False

def _dynamic_deploy_pass(img, is_first_pass=False):
    """
    Scans the bottom army card bar for colorful cards.
    - If is_first_pass: Rightmost 1 or 2 cards are deployed to Spells. Remaining to Army (6 rounds).
    - If NOT is_first_pass: ALL colorful cards (Abilities/Leftovers) are deployed to Army (6 rounds).
    Returns the number of colorful cards found.
    """
    colorful_centers = bot_vision.scan_colorful_army_cards_a14(img, scan_box=FAST_ATTACK["ARMY_CARD_SCAN_BOX"])
    if not colorful_centers:
        return 0

    spells = []
    armies = []

    if is_first_pass:
        num_spells = 2 if len(colorful_centers) >= 4 else 1
        spells = colorful_centers[-num_spells:]
        armies = colorful_centers[:-num_spells]
    else:
        armies = colorful_centers

    for sp_coord in spells:
        bot_adb.check_pause_point(allow_raise=True)
        print(f" [DEPLOY] Selecting Spell at {sp_coord} -> Deploying on Spell Coords...")
        bot_adb.tap(sp_coord[0], sp_coord[1], delay_range=(0.03, 0.05), jitter=2)
        bot_adb.fast_serial_taps(FAST_ATTACK["SPELL_DEPLOY_LIST"], rounds=1, jitter=3)

    for army_coord in armies:
        bot_adb.check_pause_point(allow_raise=True)
        print(f" [DEPLOY] Selecting Unit/Hero at {army_coord} -> Deploying 6 Rounds on Army Coords...")
        bot_adb.tap(army_coord[0], army_coord[1], delay_range=(0.03, 0.05), jitter=2)
        bot_adb.fast_serial_taps(FAST_ATTACK["ARMY_DEPLOY_LIST"], rounds=6, jitter=3)

    return len(colorful_centers)

def execute_attack(is_first_attack=True):
    for attempt in range(1, 4):
        atk_attempt_start_t = time.time()
        try:
            bot_adb.check_pause_point(allow_raise=True)
            print("\n======================================================================")
            print(f" || [FAST ATTACK LOOP - 45s TIMER] - ATTEMPT #{attempt}/3 ||")
            print("======================================================================")

            print(" [0.6s] Checking Home Page, Clan Chat Drawer & clicking Gold Storage 3x...")
            bot_adb.smart_sleep(0.60, apply_speed=True)
            bot_popups.check_wrong_buttons_a14(check_clan_chat=True)
            bot_popups.click_gold_storage_3_times()

            print(" [0.20s] Clicking Battle Button (182, 961)...")
            bot_adb.smart_sleep(0.20, apply_speed=True)
            bot_adb.tap(*FAST_ATTACK["BATTLE_BTN"], delay_range=(0.0, 0.0), jitter=3)

            print(" [0.35s] Waiting 0.35s -> Clicking Find Match (364, 808)...")
            bot_adb.smart_sleep(0.35, apply_speed=True)
            bot_adb.tap(*FAST_ATTACK["FIND_MATCH_BTN"], delay_range=(0.0, 0.0), jitter=3)

            print(" [0.65s] Waiting 0.65s -> Clicking Attack Button (1980, 972)...")
            bot_adb.smart_sleep(0.65, apply_speed=True)
            bot_adb.tap(*FAST_ATTACK["ATTACK_BTN"], delay_range=(0.0, 0.0), jitter=3)

            loaded_early = wait_for_enemy_base_load_smart(max_wait_sec=18.0)
            if not loaded_early:
                img_scan = bot_adb.get_screenshot(force_fresh=True)
                if bot_vision.is_cloud_screen_a14(img_scan):
                    raise RestartLoopException("Clouds did not clear after extended wait")

            # ==================================================================
            # PHASE 1: DYNAMIC DEPLOYMENT (FIRST PASS + SECOND PASS)
            # ==================================================================
            print("\n [⏱ DEPLOYMENT PHASE] Scanning & Deploying all Units/Heroes...")
            spell_select_timer = time.time()
            
            img_deploy = bot_adb.get_screenshot(force_fresh=True)
            cards_found = _dynamic_deploy_pass(img_deploy, is_first_pass=True)
            
            if cards_found == 0:
                print(" [!] [WARNING] No colorful cards found! Re-checking...")

            # Immediate Second Pass for Hero Abilities / Leftover units
            print(" [⚡ ABILITY/RE-SCAN] Instantly re-scanning for remaining active cards (Abilities)...")
            img_rescan = bot_adb.get_screenshot(force_fresh=True)
            _dynamic_deploy_pass(img_rescan, is_first_pass=False)

            # ==================================================================
            # PHASE 2: 45s TIMER WITH PERIODIC ABILITY TRIGGER & 3-STAR CHECK
            # ==================================================================
            battle_ended_early = False
            last_ability_scan_t = time.time()

            while not battle_ended_early:
                bot_adb.check_pause_point(allow_raise=True)
                elapsed_since_spell = time.time() - spell_select_timer
                rem_wait = bot_config.BATTLE_TIMER_DURATION_SEC - elapsed_since_spell
                if rem_wait <= 0:
                    break

                b_img = bot_adb.get_screenshot(force_fresh=True)

                # Periodic 10s Re-Scan for Abilities
                if (time.time() - last_ability_scan_t) >= 10.0:
                    last_ability_scan_t = time.time()
                    print(f" [🔍 10s RE-SCAN] Checking for unused abilities at {elapsed_since_spell:.1f}s mark...")
                    _dynamic_deploy_pass(b_img, is_first_pass=False)

                # Periodic 5s Early 3-Star Check (after 20 seconds)
                if elapsed_since_spell >= 20.0:
                    colorful_left = len(bot_vision.scan_colorful_army_cards_a14(b_img))
                    victory_btn_visible = bot_vision.is_return_home_victory_button_visible_a14(b_img)
                    
                    if colorful_left == 0 and victory_btn_visible:
                        print(f" [✔] [EARLY 3-STAR DETECTED] No army cards left & Return Home visible at {elapsed_since_spell:.1f}s! Exiting early...")
                        battle_ended_early = True
                        break
                    
                    bot_adb.smart_sleep(min(2.5, rem_wait), apply_speed=False)
                else:
                    bot_adb.smart_sleep(min(5.0, rem_wait), apply_speed=False)

            # ==================================================================
            # 10. FIXED RETURN HOME SEQUENCE (4.2s RELIABLE SEQUENCE)
            # ==================================================================
            if not battle_ended_early:
                print(" [SURRENDER] Clicking Surrender Button (181, 800) 3 times...")
                bot_adb.batch_tap_sequence([FAST_ATTACK["SURRENDER_BTN"]] * 3, inter_delay=0.08, jitter=3)

                print(" [0.6s] Waiting 0.6s -> Clicking Okay Button (1419, 701)...")
                bot_adb.smart_sleep(0.60, apply_speed=False)
                bot_adb.tap(*FAST_ATTACK["OKAY_BTN"], delay_range=(0.08, 0.14), jitter=3, apply_speed=False)

                print(" [2.2s GAP] Waiting 2.2 seconds after Okay for Return Home button to appear...")
                bot_adb.smart_sleep(2.20, apply_speed=False)

            print(" [RETURN HOME #1/2] Clicking Return Home Button (1222, 918) [1st Click]...")
            bot_adb.tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.05, 0.08), jitter=3, apply_speed=False)
            print(" [1.0s GAP] Waiting 1.0 second before 2nd Return Home click...")
            bot_adb.smart_sleep(1.00, apply_speed=False)

            print(" [RETURN HOME #2/2] Clicking Return Home Button (1222, 918) [2nd Click]...")
            bot_adb.tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.05, 0.08), jitter=3, apply_speed=False)
            print(" [1.0s SETTLE] Waiting 1.0 second to settle on Home Page...")
            bot_adb.smart_sleep(1.00, apply_speed=False)

            ret_img = bot_adb.get_screenshot(force_fresh=True)
            _, home_verified, ret_img = bot_popups.check_wrong_and_home_page_a14(ret_img, check_clan_chat=True)

            if not home_verified:
                print(" [!] [RETURN HOME GUARD] Home Page Green '+' missing! Running extra Return Home tap & recovery...")
                bot_adb.tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.10, 0.18), jitter=3, apply_speed=False)
                bot_adb.smart_sleep(1.00, apply_speed=False)
                home_verified = bot_popups.ensure_return_to_home_page_a14()

            if not home_verified:
                raise RestartLoopException("Could not verify Home Page after Return Home clicks")

            atk_dur = time.time() - atk_attempt_start_t
            record_stat("attacks_success", 1)
            record_duration("attack", atk_dur)
            print(f" [✔] [FAST ATTACK COMPLETE in {atk_dur:.1f}s] Verified back on Home Page!\n")
            return True

        except BotPausedResumeHomeException:
            raise
        except RestartLoopException as re_err:
            record_stat("attacks_failed", 1)
            print(f"\n [RESTARTING ATTACK] Attempt #{attempt}/3 interrupted ({re_err}). Recovering Home Page...")
            bot_popups.ensure_return_to_home_page_a14()
            bot_adb.smart_sleep(0.40, apply_speed=True)
            continue
        except Exception as e:
            record_stat("attacks_failed", 1)
            print("\n[! ERROR!] Fast Attack Loop me error aayi:")
            traceback.print_exc()
            bot_popups.ensure_return_to_home_page_a14()
            return False

    print(" [!] [3 ATTEMPTS FAILED] Running Full In-Game Home Recovery...")
    bot_popups.ensure_return_to_home_page_a14()
    return False
