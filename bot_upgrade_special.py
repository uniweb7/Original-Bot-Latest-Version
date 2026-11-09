# bot_upgrade_special.py
# Engine for Spell, Pet, and Hero Equipment Upgrades (In-Menu Tab Switching)

import time
from bot_coords import UPGRADE_A14
import bot_adb
import bot_vision
import bot_popups
from bot_report import record_stat
from bot_upgrade_buildings import _find_cards_in_upgrade_list, check_goblin_builder_popup_a14

def _run_generic_tab_upgrade(tab_click_coord, max_scrolls=3, is_equipment=False):
    """
    Generic logic for scrolling up to 3 times and clicking a WHITE cost card.
    Returns (upgraded_bool, goblin_found_bool).
    """
    print(f" [TAB UPGRADE] Switching to Tab at {tab_click_coord}...")
    bot_adb.tap(*tab_click_coord, delay_range=(0.20, 0.30), jitter=3)
    bot_adb.human_sleep(0.45, 0.05)

    scroll_idx = 0
    upgraded_any = False
    goblin_found = False

    while scroll_idx <= max_scrolls:
        bot_adb.check_pause_point(allow_raise=True)
        img = bot_popups.ensure_upgrade_list_is_open()
        cards = _find_cards_in_upgrade_list(img, expanded=True)

        view_items = []
        for (c_top, c_bot) in cards:
            bot_adb.check_pause_point(allow_raise=True)
            cost_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img, c_top, c_bot)
            raw_name = bot_vision.read_card_name_a14(img, c_top, c_bot)
            view_items.append((c_top, c_bot, cost_color, click_x, click_y, raw_name))

        upgraded_in_this_view = False

        for (c_top, c_bot, cost_color, click_x, click_y, raw_name) in view_items:
            bot_adb.check_pause_point(allow_raise=True)
            print(f" [SCAN TAB] Item: '{raw_name}' | Cost Color: {cost_color}")

            if cost_color == "WHITE":
                print(f" [+] [MATCH] Upgrading '{raw_name}' at ({click_x}, {click_y})...")
                bot_adb.tap(click_x, click_y, delay_range=(0.18, 0.28), jitter=2)
                bot_adb.human_sleep(0.35, 0.05)

                bot_adb.tap(*UPGRADE_A14["C1_CONFIRM_CLICK"], delay_range=(0.18, 0.28), jitter=3)
                bot_adb.human_sleep(0.45, 0.05)
                
                check_img = bot_adb.get_screenshot(force_fresh=True)
                
                if not is_equipment and check_goblin_builder_popup_a14(check_img):
                    goblin_found = True
                    break

                if bot_vision.is_red_x_box_at(check_img, *UPGRADE_A14["C1_WRONG_BTN"], radius=12):
                    print(" [!] Red 'X' found! Tab Upgrade Failed.")
                    bot_adb.tap(*UPGRADE_A14["C1_WRONG_BTN"], delay_range=(0.15, 0.25), jitter=3)
                    bot_adb.human_sleep(0.30, 0.04)
                    bot_adb.tap(*UPGRADE_A14["C1_REOPEN_LIST"], delay_range=(0.18, 0.28), jitter=3)
                    bot_adb.human_sleep(0.40, 0.05)
                    break
                else:
                    upgraded_in_this_view = True
                    upgraded_any = True
                    record_stat("buildings_upgraded", 1)  # Tracked globally as an upgrade
                    break

        if goblin_found or upgraded_in_this_view or (is_equipment and upgraded_any):
            break

        if scroll_idx < max_scrolls:
            scroll_idx += 1
            print(f" [v] [TAB SCROLL {scroll_idx}/{max_scrolls}] Scrolling list...")
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.40)
        else:
            break

    return upgraded_any, goblin_found

def run_spell_upgrade_process():
    """Checks Spell Tab builder availability and upgrades if >= 1."""
    print("\n======================================================================")
    print("|| [STEP 3: SPELL UPGRADE SYSTEM] ACTIVE                            ||")
    print("======================================================================")
    
    img = bot_popups.ensure_upgrade_list_is_open()
    spell_b = bot_vision.read_fraction_box_a14(img, UPGRADE_A14["SPELL_CHECK_BOX"])
    print(f" [i] Spell Lab/Builders Available: {spell_b}")
    
    if spell_b >= 1:
        return _run_generic_tab_upgrade(UPGRADE_A14["SPELL_TAB_CLICK"], max_scrolls=3, is_equipment=False)
    else:
        print(" [-] 0 Spell Builders free. Skipping Spell Upgrade...")
        return False, False

def run_pet_upgrade_process():
    """Checks Pet Tab builder availability and upgrades if >= 1."""
    print("\n======================================================================")
    print("|| [STEP 4: PET UPGRADE SYSTEM] ACTIVE                              ||")
    print("======================================================================")
    
    img = bot_popups.ensure_upgrade_list_is_open()
    pet_b = bot_vision.read_fraction_box_a14(img, UPGRADE_A14["PET_CHECK_BOX"])
    print(f" [i] Pet Builders Available: {pet_b}")
    
    if pet_b >= 1:
        return _run_generic_tab_upgrade(UPGRADE_A14["PET_TAB_CLICK"], max_scrolls=3, is_equipment=False)
    else:
        print(" [-] 0 Pet Builders free. Skipping Pet Upgrade...")
        return False, False

def run_equipment_upgrade_process():
    """Clicks Equipment Tab directly and performs exactly 1 upgrade if ores are available."""
    print("\n======================================================================")
    print("|| [STEP 5: HERO EQUIPMENT UPGRADE SYSTEM] ACTIVE                   ||")
    print("======================================================================")
    
    _run_generic_tab_upgrade(UPGRADE_A14["EQUIPMENT_TAB_CLICK"], max_scrolls=3, is_equipment=True)
    return True
