# bot_upgrade_buildings.py
# Building & Wall Upgrade Engine with Filter Select and Goblin Builder Skip

import time
from bot_coords import UPGRADE_A14
import bot_adb
import bot_vision
import bot_popups
from bot_report import record_stat

_LAST_WALL_AFTER_IMG = None

def run_filter_selection_a14(builders):
    """Executes the Filter Select process if builders > 1."""
    if builders <= 1:
        return
    print(" [FILTER SELECT] Builders > 1. Executing Filter Selection (1788,43 -> 1145,715 -> 2021,51)...")
    bot_adb.tap(*UPGRADE_A14["FILTER_ENTER_BTN"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.25, 0.05)
    bot_adb.tap(*UPGRADE_A14["FILTER_SELECT_BTN"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.25, 0.05)
    bot_adb.tap(*UPGRADE_A14["FILTER_BACK_BTN"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.45, 0.06)

def check_goblin_builder_popup_a14(img=None):
    """
    Checks for the Goblin Builder Popup.
    Fast check for Red 'X' and Goblin page background before running full OCR.
    Returns True if Goblin Builder is detected.
    """
    if img is None:
        img = bot_adb.get_screenshot()
        
    # Fast pixel check for Red 'X' and Goblin Background
    if not bot_vision.is_red_x_box_at(img, *UPGRADE_A14["GOBLIN_RED_X_BOX"], radius=11):
        return False
        
    w, h = img.size
    px_map = img.load()
    bx1, by1, bx2, by2 = UPGRADE_A14["GOBLIN_PAGE_BOX"]
    bg_px = sum(1 for sy in range(by1+50, by2-50, 10) for sx in range(bx1+50, bx2-50, 10)
                if 180 <= px_map[sx, sy][0] <= 245 and 150 <= px_map[sx, sy][1] <= 215 and px_map[sx, sy][2] < 160)
    if bg_px < 5:
        return False

    chief_txt = bot_vision._ocr_card_box_region(img, *UPGRADE_A14["GOBLIN_CHIEF_BOX"], thresh=145, psm=7).lower()
    letter_txt = bot_vision._ocr_card_box_region(img, *UPGRADE_A14["GOBLIN_LETTER_BOX"], thresh=145, psm=6).lower()
    
    if "chief" in chief_txt or "busy" in letter_txt or "goblin" in letter_txt:
        print(" [!] [GOBLIN BUILDER DETECTED] Cutting Goblin Builder Popup (1961, 237)...")
        bot_adb.tap(*UPGRADE_A14["GOBLIN_RED_X_CLICK"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.45, 0.05)
        return True
    return False

def _find_cards_in_upgrade_list(img, expanded=False):
    lx1, ly1, lx2, ly2 = UPGRADE_A14["UPGRADE_LIST_BOX_EXPANDED"] if expanded else UPGRADE_A14["UPGRADE_LIST_BOX_INITIAL"]
    px_map = img.load()
    cards, in_card, card_top = [], False, 0
    
    def is_tan(r, g, b): return (142 <= r <= 225) and (118 <= g <= 200) and (88 <= b <= 172) and (r > g > b) and (g <= r + 8)

    for y in range(ly1 + 2, ly2 - 2, 1):
        r1, g1, b1 = px_map[2130, y]
        r2, g2, b2 = px_map[2000, y]
        tan_match = is_tan(r1, g1, b1) and is_tan(r2, g2, b2)

        # Ignore thin separator bars (height < 48px) like "Suggested upgrades"
        if tan_match and not in_card:
            in_card, card_top = True, y
        elif not tan_match and in_card:
            in_card, ch = False, y - card_top
            if 48 <= ch <= 105: cards.append((card_top, y))
            elif ch > 105:
                n_c = max(2, round(ch / 81.0))
                step = ch // n_c
                for i in range(n_c): cards.append((card_top + i * step, min(y, card_top + (i + 1) * step)))

    if in_card:
        ch = (ly2 - 2) - card_top
        if 48 <= ch <= 105: cards.append((card_top, ly2 - 2))
        elif ch > 105:
            n_c = max(2, round(ch / 81.0))
            step = ch // n_c
            for i in range(n_c): cards.append((card_top + i * step, min(ly2 - 2, card_top + (i + 1) * step)))
    return cards

def run_condition_1_buildings(handoff_to_wall=True, initial_builders=None, stop_at_builders=1):
    upgraded_any_building = False
    avail_builders = initial_builders if initial_builders is not None else bot_vision.read_builder_check_box_a14()

    print("\n======================================================================")
    print(f"|| [STEP 1: BUILDINGS UPGRADE] ACTIVE (Target Stop Builders <= {stop_at_builders}) ||")
    print("======================================================================")

    run_filter_selection_a14(avail_builders)

    max_scrolls, scroll_idx = 8, 0
    last_bottom_sig = ""
    same_bottom_name_streak = 0
    goblin_found = False

    while scroll_idx <= max_scrolls:
        bot_adb.check_pause_point(allow_raise=True)
        img = bot_popups.ensure_upgrade_list_is_open()
        cards = _find_cards_in_upgrade_list(img, expanded=(scroll_idx > 0))
        
        view_items = []
        cur_view_sigs = []
        
        for (c_top, c_bot) in cards:
            bot_adb.check_pause_point(allow_raise=True)
            # Fast Cost Pre-Check: Skips OCR if RED or NONE (Time-Cut #T2)
            cost_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img, c_top, c_bot)
            if cost_color != "WHITE":
                continue
                
            raw_name = bot_vision.read_card_name_a14(img, c_top, c_bot)
            category, clean_name = bot_vision.classify_building_name_a14(raw_name)
            sig = bot_vision._normalize_card_signature_for_last_page(clean_name if category != "UNKNOWN" else raw_name)
            if sig: cur_view_sigs.append(sig)
            view_items.append((c_top, c_bot, cost_color, click_x, click_y, raw_name, category, clean_name))

        if scroll_idx > 0:
            cur_bottom = cur_view_sigs[-1] if cur_view_sigs else ""
            if cur_bottom and cur_bottom == last_bottom_sig:
                same_bottom_name_streak += 1
            else:
                same_bottom_name_streak = 0

            if same_bottom_name_streak >= 2:
                print(f" [✔] [LAST PAGE DETECTED] Scroll #{scroll_idx} par same building name repeat hua! Last Page reached.")
                break

        reopened_after_red_x = False
        upgraded_in_this_view = False
        post_confirm_img = None

        for (c_top, c_bot, cost_color, click_x, click_y, raw_name, category, clean_name) in view_items:
            bot_adb.check_pause_point(allow_raise=True)
            if category in ["UNKNOWN", "EXCLUDED", "WALL"]: continue

            print(f" [+] [MATCH FOUND] Upgrading '{clean_name}'! Clicking Safe Row at ({click_x}, {click_y})...")
            bot_adb.tap(click_x, click_y, delay_range=(0.18, 0.28), jitter=2)
            bot_adb.human_sleep(0.35, 0.05)

            bot_adb.tap(*UPGRADE_A14["C1_CONFIRM_CLICK"], delay_range=(0.18, 0.28), jitter=3)
            bot_adb.human_sleep(0.42, 0.05)
            
            check_img = bot_adb.get_screenshot(force_fresh=True)
            
            if check_goblin_builder_popup_a14(check_img):
                goblin_found = True
                break

            if bot_vision.is_red_x_box_at(check_img, *UPGRADE_A14["C1_WRONG_BTN"], radius=12):
                print(" [!] Red 'X' found! Upgrade Failed.")
                record_stat("wrong_buttons_cut", 1)
                bot_adb.tap(*UPGRADE_A14["C1_WRONG_BTN"], delay_range=(0.15, 0.25), jitter=3)
                bot_adb.human_sleep(0.30, 0.04)
                bot_adb.tap(*UPGRADE_A14["C1_REOPEN_LIST"], delay_range=(0.18, 0.28), jitter=3)
                bot_adb.human_sleep(0.42, 0.05)
                reopened_after_red_x = True
                same_bottom_name_streak = 0
                break
            else:
                post_confirm_img = bot_popups.ensure_upgrade_list_is_open(check_img)
                upgraded_in_this_view = True
                upgraded_any_building = True
                record_stat("buildings_upgraded", 1)
                same_bottom_name_streak = 0
                break

        if goblin_found:
            print(" [⚡ GOBLIN SKIP] Goblin Builder detected! Skipping remaining Building & Wall Upgrades...")
            return upgraded_any_building, avail_builders, scroll_idx, True

        if reopened_after_red_x:
            avail_builders = bot_vision.read_builder_check_box_a14(bot_popups.ensure_upgrade_list_is_open())
            if avail_builders <= stop_at_builders: break
            continue

        if upgraded_in_this_view:
            prev_builders = avail_builders
            expected_after_one = max(0, prev_builders - 1)
            img_now = post_confirm_img if post_confirm_img is not None else bot_popups.ensure_upgrade_list_is_open()
            read_b = bot_vision.read_builder_check_box_a14(img_now)

            if expected_after_one > stop_at_builders and read_b <= stop_at_builders:
                bot_adb.human_sleep(0.32, 0.04)
                read_b2 = bot_vision.read_builder_check_box_a14(bot_popups.ensure_upgrade_list_is_open(bot_adb.get_screenshot(force_fresh=True)))
                avail_builders = expected_after_one if read_b2 <= stop_at_builders and expected_after_one >= (stop_at_builders + 1) else read_b2
            else:
                avail_builders = read_b

            print(f" [i] Remaining Available Builders: {avail_builders} (Stop Target <= {stop_at_builders})")
            if avail_builders <= stop_at_builders: break
            continue

        if scroll_idx < max_scrolls:
            if cur_view_sigs: last_bottom_sig = cur_view_sigs[-1]
            scroll_idx += 1
            print(f" [v] [BUILDING SCROLL {scroll_idx}/{max_scrolls}] Scrolling list...")
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.38)
        else:
            break

    return upgraded_any_building, avail_builders, scroll_idx, goblin_found

def _wait_for_wall_upgrade_list_settle():
    bot_adb.human_sleep(0.38, 0.04)
    img_after = bot_adb.get_screenshot(force_fresh=True)
    for poll_i in range(3):
        if len(_find_cards_in_upgrade_list(img_after, expanded=True)) >= 2: return img_after
        if poll_i == 1 and not is_upgrade_list_open_a14(img_after):
            bot_adb.tap(*UPGRADE_A14["WALL_REOPEN_LIST_CLICK"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.24, 0.03)
        img_after = bot_adb.get_screenshot(force_fresh=True)
    return img_after

def _upgrade_wall_card_until_red(initial_top, initial_bot, initial_click_x, initial_click_y):
    """
    Wall Streak Engine:
    Integrates Time-Cut #T1 (Instant Pixel White-Cost Check) + Strict Wall OCR Check
    so it NEVER falsely clicks a building!
    """
    global _LAST_WALL_AFTER_IMG
    cur_top, cur_bot = initial_top, initial_bot
    click_x, click_y = initial_click_x, initial_click_y
    upgrade_count = 0
    goblin_found = False

    while True:
        bot_adb.check_pause_point(allow_raise=True)
        print(f" [WALL] Clicking Safe Wall Row at ({click_x}, {click_y}) [Streak #{upgrade_count + 1}]...")
        bot_adb.tap(click_x, click_y, delay_range=(0.16, 0.25), jitter=2)
        bot_adb.human_sleep(0.30, 0.04)

        bot_adb.tap(*UPGRADE_A14["WALL_STEP_A1_CLICK"], delay_range=(0.16, 0.25), jitter=3)
        bot_adb.human_sleep(0.30, 0.04)

        bot_adb.batch_tap_sequence([UPGRADE_A14["WALL_CONFIRM_CLICK"], UPGRADE_A14["WALL_CONFIRM_CLICK"]], inter_delay=0.14, jitter=3)
        upgrade_count += 1
        record_stat("walls_upgraded", 1)

        img_after = _wait_for_wall_upgrade_list_settle()
        _LAST_WALL_AFTER_IMG = img_after
        
        if check_goblin_builder_popup_a14(img_after):
            goblin_found = True
            break

        cards = _find_cards_in_upgrade_list(img_after, expanded=True)
        best_card, best_dist = None, 999
        for (c_top, c_bot) in cards:
            dist = abs(c_top - cur_top)
            if dist <= 52:
                if bot_vision.verify_card_is_wall_carefully(img_after, c_top, c_bot)[0]:
                    best_card = (c_top, c_bot)
                    best_dist = dist
        
        is_wall_now = False
        if best_card:
            cur_top, cur_bot = best_card
            is_wall_now = True
        else:
            for (c_top, c_bot) in cards:
                if bot_vision.verify_card_is_wall_carefully(img_after, c_top, c_bot)[0]:
                    cur_top, cur_bot = (c_top, c_bot)
                    is_wall_now = True
                    break

        new_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img_after, cur_top, cur_bot)

        if not is_wall_now or new_color == "NONE":
            bot_adb.human_sleep(0.32, 0.04)
            img_after = bot_popups.ensure_upgrade_list_is_open(bot_adb.get_screenshot(force_fresh=True))
            _LAST_WALL_AFTER_IMG = img_after
            cards2 = _find_cards_in_upgrade_list(img_after, expanded=True)
            for (c_top, c_bot) in cards2:
                if bot_vision.verify_card_is_wall_carefully(img_after, c_top, c_bot)[0]:
                    cur_top, cur_bot = (c_top, c_bot)
                    is_wall_now = True
                    break
            new_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img_after, cur_top, cur_bot)

        if not is_wall_now:
            return "TURNED_RED", goblin_found

        if new_color == "WHITE":
            # Time-Cut #T1: Verified Wall + White Cost -> Instant Continue!
            bot_adb.human_sleep(0.04, 0.01, min_floor=0.02)
            continue
        elif new_color == "RED":
            bot_adb.human_sleep(0.20, 0.03)
            img_confirm_red = bot_adb.get_screenshot(force_fresh=True)
            _LAST_WALL_AFTER_IMG = img_confirm_red
            if bot_vision.check_card_cost_color_a14(img_confirm_red, cur_top, cur_bot)[0] == "WHITE":
                continue
            return "TURNED_RED", goblin_found
        else:
            return "TURNED_RED", goblin_found
            
    return "TURNED_RED", goblin_found

def run_wall_upgrade_process(from_building_handoff=False, building_scrolls_done=0):
    global _LAST_WALL_AFTER_IMG
    print("\n======================================================================")
    print("|| [STEP 2: WALL UPGRADE SYSTEM] ACTIVE (SINGLE/MULTI WALL) ||")
    print("======================================================================")

    if from_building_handoff and building_scrolls_done > 0:
        bot_adb.batch_tap_sequence([UPGRADE_A14["WALL_REOPEN_LIST_CLICK"], UPGRADE_A14["WALL_REOPEN_LIST_CLICK"]], inter_delay=0.20, jitter=3)
        bot_adb.human_sleep(0.45, 0.05)

    max_scrolls = 25
    scroll_idx = 0
    has_upgraded_any_wall = False
    upgraded_wall_rows_count = 0
    max_wall_rows_limit = 4
    last_bottom_sig = ""
    same_name_repeat_count = 0
    goblin_found = False

    while scroll_idx <= max_scrolls:
        bot_adb.check_pause_point(allow_raise=True)
        img = bot_popups.ensure_upgrade_list_is_open()
        cards = _find_cards_in_upgrade_list(img, expanded=(scroll_idx > 0))

        found_white_wall_in_view = False
        cur_view_sigs = []

        for (c_top, c_bot) in cards:
            bot_adb.check_pause_point(allow_raise=True)
            cost_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img, c_top, c_bot)
            is_wall, raw_name = bot_vision.verify_card_is_wall_carefully(img, c_top, c_bot)
            sig = bot_vision._normalize_card_signature_for_last_page("Wall" if is_wall else raw_name)
            if sig: cur_view_sigs.append(sig)

            if not is_wall or cost_color != "WHITE":
                continue

            found_white_wall_in_view = True
            result, g_found = _upgrade_wall_card_until_red(c_top, c_bot, click_x, click_y)
            goblin_found = g_found

            if goblin_found:
                print(" [⚡ GOBLIN SKIP] Goblin Builder detected! Skipping remaining Walls...")
                return has_upgraded_any_wall, True

            if result == "TURNED_RED":
                has_upgraded_any_wall = True
                upgraded_wall_rows_count += 1
                same_name_repeat_count = 0
                last_bottom_sig = ""

                if upgraded_wall_rows_count >= max_wall_rows_limit:
                    break
                max_scrolls = 22
                scroll_idx = 0
                break

        if goblin_found or upgraded_wall_rows_count >= max_wall_rows_limit:
            break

        if found_white_wall_in_view and scroll_idx == 0 and has_upgraded_any_wall:
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.38)
            scroll_idx = 1
            continue

        if scroll_idx > 0 and not found_white_wall_in_view:
            cur_bottom_sig = cur_view_sigs[-1] if cur_view_sigs else ""
            if cur_bottom_sig and cur_bottom_sig == last_bottom_sig:
                same_name_repeat_count += 1
            else:
                same_name_repeat_count = 1 if cur_bottom_sig else 0

            if same_name_repeat_count >= 2:
                print(f" [✔] [WALL LAST PAGE DETECTED] Upgrade List Last Page reached.")
                break

        if scroll_idx < max_scrolls:
            if cur_view_sigs: last_bottom_sig = cur_view_sigs[-1]
            scroll_idx += 1
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.38)
        else:
            break

    return has_upgraded_any_wall, goblin_found
