# bot_upgrade_buildings.py
# Building & Wall Upgrade Engine (100% Original V8 Logic + V9 Goblin Skip & Filter Select)

import time
import bot_adb
import bot_vision
import bot_popups
import bot_report
from bot_coords import UPGRADE_A14

# Tracks whether any building or wall was upgraded in the current loop call
LAST_UPGRADE_SUCCESS = False
LAST_BUILDING_UPGRADED = False
LAST_WALL_UPGRADED = False
_LAST_WALL_AFTER_IMG = None

# ==========================================
# 1. UPGRADE UI HELPERS & GOBLIN SKIPPER
# ==========================================

def is_tan_card_background(r, g, b):
    if g > r + 8:
        return False
    return (142 <= r <= 225) and (118 <= g <= 200) and (88 <= b <= 172) and (r > g > b)

def find_cards_in_upgrade_list(img, expanded=False):
    """Detects individual upgrade card vertical spans (c_top, c_bot)"""
    lx1, ly1, lx2, ly2 = UPGRADE_A14["UPGRADE_LIST_BOX_EXPANDED"] if expanded else UPGRADE_A14["UPGRADE_LIST_BOX_INITIAL"]
    px_map = img.load()
    cards = []
    in_card = False
    card_top = 0

    for y in range(ly1 + 2, ly2 - 2, 1):
        r1, g1, b1 = px_map[2130, y]
        r2, g2, b2 = px_map[2000, y]
        is_tan = is_tan_card_background(r1, g1, b1) and is_tan_card_background(r2, g2, b2)

        if is_tan and not in_card:
            in_card = True
            card_top = y
        elif not is_tan and in_card:
            in_card = False
            ch = y - card_top
            if 48 <= ch <= 105:
                cards.append((card_top, y))
            elif ch > 105:
                n_cards = max(2, round(ch / 81.0))
                step = ch // n_cards
                for i in range(n_cards):
                    cards.append((card_top + i * step, min(y, card_top + (i + 1) * step)))

    if in_card:
        ch = (ly2 - 2) - card_top
        if 48 <= ch <= 105:
            cards.append((card_top, ly2 - 2))
        elif ch > 105:
            n_cards = max(2, round(ch / 81.0))
            step = ch // n_cards
            for i in range(n_cards):
                cards.append((card_top + i * step, min(ly2 - 2, card_top + (i + 1) * step)))

    return cards

def capture_upgrade_list_fingerprint(img):
    """Samples pixels across the Upgrade List Box to detect bottom of list."""
    if img is None:
        return None
    px_map = img.load()
    lx1, ly1, lx2, ly2 = UPGRADE_A14["UPGRADE_LIST_BOX_INITIAL"]
    samples = []
    for sy in range(ly1 + 20, ly2 - 20, 14):
        for sx in range(lx1 + 25, lx2 - 25, 30):
            samples.append(px_map[sx, sy])
    return samples

def is_same_upgrade_list_page(fp_before, fp_after, diff_threshold=9.5):
    if not fp_before or not fp_after or len(fp_before) != len(fp_after):
        return False
    total_diff = 0
    n = len(fp_before)
    for (r1, g1, b1), (r2, g2, b2) in zip(fp_before, fp_after):
        total_diff += (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) / 3.0
    mean_diff = total_diff / float(n)
    return mean_diff <= diff_threshold

def is_upgrade_list_open_a14(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
    if bot_vision.is_red_x_box_at(img, *UPGRADE_A14["CLOSE_MENU"], radius=14):
        return True
    cards = find_cards_in_upgrade_list(img)
    return len(cards) > 0

def ensure_upgrade_list_is_open(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
    if is_upgrade_list_open_a14(img):
        return img

    print(" [*] [LIST GUARD] Upgrade List dikh nahi rahi. (2050, 56) / (2233, 948) se open kar rahe hain...")
    bot_adb.tap(*UPGRADE_A14["C1_REOPEN_LIST"], delay_range=(0.20, 0.32), jitter=3)
    bot_adb.human_sleep(0.42, 0.05)
    img = bot_adb.get_screenshot(force_fresh=True)
    if not is_upgrade_list_open_a14(img):
        bot_adb.tap(*UPGRADE_A14["BUILD_CLICK"], delay_range=(0.22, 0.35), jitter=3)
        bot_adb.human_sleep(0.50, 0.06)
        img = bot_adb.get_screenshot(force_fresh=True)
    return img

def check_goblin_builder_popup_a14(img=None):
    """V9 FEATURE: Detects and cuts Goblin Builder popup instantly."""
    if img is None:
        img = bot_adb.get_screenshot()
    if not bot_vision.is_red_x_box_at(img, *UPGRADE_A14["GOBLIN_RED_X_BOX"], radius=11):
        return False
    print(" [!] [GOBLIN BUILDER DETECTED] Goblin Builder Popup mila! Cutting (1961, 237)...")
    bot_adb.tap(*UPGRADE_A14["GOBLIN_RED_X_CLICK"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.45, 0.05)
    return True

def run_filter_selection_a14(builders):
    """V9 FEATURE: Executes the Filter Select Process if builders > 1."""
    if builders <= 1:
        return
    print(" [FILTER SELECT] Builders > 1. Executing Filter Selection (1788,43 -> 1145,715 -> 2021,51)...")
    bot_adb.tap(*UPGRADE_A14["FILTER_ENTER_BTN"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.25, 0.05)
    bot_adb.tap(*UPGRADE_A14["FILTER_SELECT_BTN"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.25, 0.05)
    bot_adb.tap(*UPGRADE_A14["FILTER_BACK_BTN"], delay_range=(0.18, 0.28), jitter=3)
    bot_adb.human_sleep(0.45, 0.06)

# ==========================================
# 2. BUILDING UPGRADE PROCESS (STRICT RED-COST VETO)
# ==========================================

def run_condition_1_buildings(handoff_to_wall=True, initial_builders=None, stop_at_builders=1):
    global LAST_UPGRADE_SUCCESS, LAST_BUILDING_UPGRADED
    upgraded_any_building = False
    
    if initial_builders is not None:
        avail_builders = initial_builders
    elif bot_vision.LAST_DETECTED_BUILDERS is not None:
        avail_builders = bot_vision.LAST_DETECTED_BUILDERS
    else:
        avail_builders = 2

    print("\n======================================================================")
    print(f"|| [STEP 1: BUILDINGS UPGRADE] ACTIVE (Target Stop Builders <= {stop_at_builders}) ||")
    print("======================================================================")

    run_filter_selection_a14(avail_builders)

    max_scrolls = 8
    scroll_idx = 0
    last_page_fp = None
    last_view_signatures = []
    same_bottom_name_streak = 0
    goblin_found = False

    while scroll_idx <= max_scrolls:
        bot_adb.check_pause_point(allow_raise=True)
        upgraded_in_this_view = False
        reopened_after_red_x = False
        post_confirm_img = None

        img = ensure_upgrade_list_is_open()
        cur_fp = capture_upgrade_list_fingerprint(img)
        cards = find_cards_in_upgrade_list(img, expanded=(scroll_idx > 0))

        view_items = []
        current_view_sigs = []
        for (c_top, c_bot) in cards:
            bot_adb.check_pause_point(allow_raise=True)
            cost_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img, c_top, c_bot)
            raw_name = bot_vision.read_card_name_a14(img, c_top, c_bot)
            category, clean_name = bot_vision.classify_building_name_a14(raw_name)
            sig = bot_vision._normalize_card_signature_for_last_page(clean_name if category != "UNKNOWN" else raw_name)
            if sig:
                current_view_sigs.append(sig)
            view_items.append((c_top, c_bot, cost_color, click_x, click_y, raw_name, category, clean_name))

        if scroll_idx > 0:
            fp_same = (last_page_fp is not None and is_same_upgrade_list_page(last_page_fp, cur_fp))
            names_same = (
                len(current_view_sigs) > 0 and len(last_view_signatures) > 0
                and (current_view_sigs == last_view_signatures or current_view_sigs[-1] == last_view_signatures[-1])
            )
            if names_same:
                same_bottom_name_streak += 1
            else:
                same_bottom_name_streak = 0

            if fp_same or same_bottom_name_streak >= 2:
                print(f" [✔] [LAST PAGE DETECTED] Scroll #{scroll_idx} par same building name ('{current_view_sigs[-1] if current_view_sigs else 'Bottom'}') repeat hua!")
                break

        for (c_top, c_bot, cost_color, click_x, click_y, raw_name, category, clean_name) in view_items:
            bot_adb.check_pause_point(allow_raise=True)
            if category == "UNKNOWN" or cost_color != "WHITE":
                continue

            if category in ["EXCLUDED", "WALL"]:
                print(f" [-] Skipping Excluded/Wall Item in Building Phase: '{clean_name}'")
                continue

            if category == "BUILDING" and cost_color == "WHITE":
                print(f" [+] [MATCH FOUND] Upgrading '{clean_name}'! Clicking White Cost at ({click_x}, {click_y})...")
                bot_adb.tap(click_x, click_y, delay_range=(0.18, 0.28), jitter=2)
                bot_adb.human_sleep(0.35, 0.05)

                print(" [>] [STEP (i)] Clicking Confirm Upgrade (1582, 930)...")
                bot_adb.tap(*UPGRADE_A14["C1_CONFIRM_CLICK"], delay_range=(0.18, 0.28), jitter=3)
                bot_adb.human_sleep(0.42, 0.05)

                check_img = bot_adb.get_screenshot(force_fresh=True)
                
                if check_goblin_builder_popup_a14(check_img):
                    goblin_found = True
                    break

                if bot_vision.is_red_x_box_at(check_img, *UPGRADE_A14["C1_WRONG_BTN"], radius=12):
                    print(" [!] Red 'X' found! Upgrade Failed.")
                    bot_report.record_stat("wrong_buttons_cut", 1)
                    bot_adb.tap(*UPGRADE_A14["C1_WRONG_BTN"], delay_range=(0.15, 0.25), jitter=3)
                    bot_adb.human_sleep(0.30, 0.04)
                    bot_adb.tap(*UPGRADE_A14["C1_REOPEN_LIST"], delay_range=(0.18, 0.28), jitter=3)
                    bot_adb.human_sleep(0.42, 0.05)
                    reopened_after_red_x = True
                    last_page_fp = None
                    same_bottom_name_streak = 0
                    break
                else:
                    post_confirm_img = ensure_upgrade_list_is_open(check_img)
                    upgraded_in_this_view = True
                    upgraded_any_building = True
                    LAST_BUILDING_UPGRADED = True
                    LAST_UPGRADE_SUCCESS = True
                    bot_report.record_stat("buildings_upgraded", 1)
                    last_page_fp = None
                    same_bottom_name_streak = 0
                    break

        if goblin_found:
            print(" [⚡ GOBLIN SKIP] Goblin Builder detected! Breaking Building Upgrades early...")
            break

        if reopened_after_red_x:
            img_now = ensure_upgrade_list_is_open()
            avail_builders = bot_vision.read_builder_check_box_a14(img_now)
            if avail_builders <= stop_at_builders:
                break
            continue

        if upgraded_in_this_view:
            prev_builders = avail_builders
            expected_after_one = max(0, prev_builders - 1)
            img_now = post_confirm_img if post_confirm_img is not None else ensure_upgrade_list_is_open()
            read_b = bot_vision.read_builder_check_box_a14(img_now)

            if expected_after_one > stop_at_builders and read_b <= stop_at_builders:
                bot_adb.human_sleep(0.32, 0.04)
                img_recheck = ensure_upgrade_list_is_open(bot_adb.get_screenshot(force_fresh=True))
                read_b2 = bot_vision.read_builder_check_box_a14(img_recheck)
                if read_b2 <= stop_at_builders and expected_after_one >= (stop_at_builders + 1):
                    avail_builders = expected_after_one
                else:
                    avail_builders = read_b2
            else:
                avail_builders = read_b

            print(f" [i] Remaining Available Builders: {avail_builders} (Stop Target <= {stop_at_builders})")
            if avail_builders <= stop_at_builders:
                if handoff_to_wall and avail_builders >= 1:
                    print(f" [DIRECT HANDOFF] Builders = {avail_builders}! Jumping to Wall Upgrade...")
                elif not handoff_to_wall:
                    bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
                    bot_adb.human_sleep(0.35, 0.05)
                break
            continue

        if scroll_idx < max_scrolls:
            last_page_fp = cur_fp
            if current_view_sigs: last_view_signatures = current_view_sigs
            scroll_idx += 1
            print(f" [v] [BUILDING SCROLL {scroll_idx}/{max_scrolls}] Scrolling list...")
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.38)
        else:
            break

    if not handoff_to_wall:
        img_chk = bot_adb.get_screenshot()
        if is_upgrade_list_open_a14(img_chk):
            bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
            bot_adb.human_sleep(0.35, 0.05)

    return upgraded_any_building, avail_builders, scroll_idx, goblin_found

# ==========================================
# 3. WALL UPGRADE PROCESS (STREAK LOCK FIX)
# ==========================================

def find_matching_wall_card_at_spot(img, prev_top, prev_bot):
    cards = find_cards_in_upgrade_list(img, expanded=True)
    best_card = None
    best_dist = 999
    for (c_top, c_bot) in cards:
        dist = abs(c_top - prev_top)
        if dist <= 52:
            is_wall, _ = bot_vision.verify_card_is_wall_carefully(img, c_top, c_bot)
            if is_wall and dist < best_dist:
                best_dist = dist
                best_card = (c_top, c_bot)
    if best_card is not None:
        return best_card[0], best_card[1], True

    for (c_top, c_bot) in cards:
        is_wall, _ = bot_vision.verify_card_is_wall_carefully(img, c_top, c_bot)
        if is_wall:
            return c_top, c_bot, True

    for (c_top, c_bot) in cards:
        if abs(c_top - prev_top) <= 28:
            return c_top, c_bot, False
    return prev_top, prev_bot, False

def _wait_for_wall_upgrade_list_settle(max_polls=3):
    bot_adb.human_sleep(0.38, 0.04)
    img_after = bot_adb.get_screenshot(force_fresh=True)
    for poll_i in range(max_polls):
        cards = find_cards_in_upgrade_list(img_after, expanded=True)
        if len(cards) >= 2:
            return img_after
        if poll_i == 1 and not is_upgrade_list_open_a14(img_after):
            bot_adb.tap(*UPGRADE_A14["WALL_REOPEN_LIST_CLICK"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.24, 0.03)
        img_after = bot_adb.get_screenshot(force_fresh=True)
    return img_after

def upgrade_wall_card_until_red(initial_top, initial_bot, initial_click_x, initial_click_y):
    global LAST_UPGRADE_SUCCESS, LAST_WALL_UPGRADED, _LAST_WALL_AFTER_IMG
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
        LAST_WALL_UPGRADED = True
        LAST_UPGRADE_SUCCESS = True
        bot_report.record_stat("walls_upgraded", 1)

        img_after = _wait_for_wall_upgrade_list_settle(max_polls=3)
        _LAST_WALL_AFTER_IMG = img_after
        
        if check_goblin_builder_popup_a14(img_after):
            goblin_found = True
            break

        cur_top, cur_bot, is_wall_now = find_matching_wall_card_at_spot(img_after, cur_top, cur_bot)
        new_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img_after, cur_top, cur_bot)

        if not is_wall_now or new_color == "NONE":
            bot_adb.human_sleep(0.32, 0.04)
            img_after = ensure_upgrade_list_is_open(bot_adb.get_screenshot(force_fresh=True))
            _LAST_WALL_AFTER_IMG = img_after
            cur_top, cur_bot, is_wall_now = find_matching_wall_card_at_spot(img_after, cur_top, cur_bot)
            new_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img_after, cur_top, cur_bot)

        if not is_wall_now:
            is_still_w, _ = bot_vision.verify_card_is_wall_carefully(img_after, cur_top, cur_bot)
            if not is_still_w:
                return "TURNED_RED", goblin_found

        if new_color == "WHITE":
            bot_adb.human_sleep(0.04, 0.01, min_floor=0.02)
            continue
        elif new_color == "RED":
            bot_adb.human_sleep(0.20, 0.03)
            img_confirm_red = bot_adb.get_screenshot(force_fresh=True)
            _LAST_WALL_AFTER_IMG = img_confirm_red
            confirm_color, click_x, click_y = bot_vision.check_card_cost_color_a14(img_confirm_red, cur_top, cur_bot)
            if confirm_color == "WHITE":
                continue
            return "TURNED_RED", goblin_found
        else:
            return "TURNED_RED", goblin_found

    return "TURNED_RED", goblin_found

def run_wall_upgrade_process(from_building_handoff=False, building_scrolls_done=0, close_menu_on_exit=True):
    global LAST_UPGRADE_SUCCESS, LAST_WALL_UPGRADED, _LAST_WALL_AFTER_IMG
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
    last_page_fp = None
    last_bottom_card_sig = ""
    last_view_sigs = []
    same_name_repeat_count = 0
    goblin_found = False

    while scroll_idx <= max_scrolls:
        bot_adb.check_pause_point(allow_raise=True)

        if scroll_idx > 0 and (scroll_idx % 4 == 0):
            chk_img = bot_adb.get_screenshot()
            if not is_upgrade_list_open_a14(chk_img):
                bot_popups.check_wrong_buttons_a14(chk_img)
                if bot_popups.is_on_home_page_a14(chk_img) and not is_upgrade_list_open_a14(chk_img):
                    bot_adb.tap(*UPGRADE_A14["WALL_REOPEN_LIST_CLICK"], delay_range=(0.20, 0.32), jitter=3)
                    bot_adb.human_sleep(0.42, 0.05)
                    chk_img = bot_adb.get_screenshot(force_fresh=True)
                    if not is_upgrade_list_open_a14(chk_img):
                        bot_adb.tap(*UPGRADE_A14["BUILD_CLICK"], delay_range=(0.22, 0.35), jitter=3)
                        bot_adb.human_sleep(0.50, 0.06)

        img = ensure_upgrade_list_is_open()
        cur_fp = capture_upgrade_list_fingerprint(img)
        cards = find_cards_in_upgrade_list(img, expanded=(scroll_idx > 0))

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
            result, g_found = upgrade_wall_card_until_red(c_top, c_bot, click_x, click_y)
            goblin_found = g_found

            if goblin_found:
                print(" [⚡ GOBLIN SKIP] Goblin Builder detected! Skipping remaining Walls...")
                return has_upgraded_any_wall or LAST_WALL_UPGRADED, True

            if result == "TURNED_RED":
                has_upgraded_any_wall = True
                LAST_WALL_UPGRADED = True
                LAST_UPGRADE_SUCCESS = True
                upgraded_wall_rows_count += 1
                last_page_fp = None
                same_name_repeat_count = 0
                last_bottom_card_sig = ""
                last_view_sigs = []

                if upgraded_wall_rows_count >= max_wall_rows_limit:
                    break

                max_scrolls = 22
                scroll_idx = 0
                break
                
            elif result == "NOT_WALL_REOPENED":
                if not has_upgraded_any_wall: max_scrolls = 12
                last_page_fp = None
                same_name_repeat_count = 0
                break

        if goblin_found or upgraded_wall_rows_count >= max_wall_rows_limit:
            break

        if found_white_wall_in_view and scroll_idx == 0 and has_upgraded_any_wall:
            ref_img = _LAST_WALL_AFTER_IMG if _LAST_WALL_AFTER_IMG is not None else bot_adb.get_screenshot()
            last_page_fp = capture_upgrade_list_fingerprint(ref_img)
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.38)
            scroll_idx = 1
            continue

        if scroll_idx > 0 and not found_white_wall_in_view:
            fp_same = (last_page_fp is not None and is_same_upgrade_list_page(last_page_fp, cur_fp))
            cur_bottom_sig = cur_view_sigs[-1] if cur_view_sigs else ""
            if (cur_bottom_sig and cur_bottom_sig == last_bottom_card_sig) or (cur_view_sigs and cur_view_sigs == last_view_sigs):
                same_name_repeat_count += 1
            else:
                same_name_repeat_count = 1 if cur_bottom_sig else 0

            if fp_same or same_name_repeat_count >= 2:
                break

        if scroll_idx < max_scrolls:
            last_page_fp = cur_fp
            if cur_view_sigs:
                last_bottom_card_sig = cur_view_sigs[-1]
                last_view_sigs = cur_view_sigs
            scroll_idx += 1
            bot_adb.swipe(*UPGRADE_A14["SCROLL_START"], *UPGRADE_A14["SCROLL_END"], duration=350, post_sleep=0.38)
        else:
            break

    if close_menu_on_exit:
        bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.35, 0.05)

    return has_upgraded_any_wall or LAST_WALL_UPGRADED, goblin_found
