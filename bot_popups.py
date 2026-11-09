# bot_popups.py
# Handlers for Connection Lost, Maintenance, Clan Chat, and Wrong Buttons

import time
import re
import subprocess
from bot_config import (
    CONNECTION_OCR_INTERVAL_SEC, CONNECTION_RETRY_GAP_SEC,
    CONNECTION_MAX_ATTEMPTS, CONNECTION_MAX_OUTAGE_SEC, MAINTENANCE_REST_SEC
)
from bot_coords import *
import bot_adb
import bot_vision
from bot_report import record_stat, print_previous_progress_report

_LAST_CONN_LOST_OCR_TIME = 0.0
_IN_CONN_LOST_HANDLER = False
LAST_HOME_CLEANUP_TIME = 0.0

def is_on_home_page_a14(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
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

def check_wrong_buttons_a14(img=None, check_clan_chat=False):
    if img is None:
        img = bot_adb.get_screenshot()
    clicked_any = False

    if check_and_handle_connection_lost_a14(img, force_ocr=False):
        clicked_any = True
        img = bot_adb.get_screenshot(force_fresh=True)

    if check_clan_chat:
        if check_clan_chat_drawer_a14(img, use_build_fallback=False):
            clicked_any = True
            img = bot_adb.get_screenshot(force_fresh=True)

    if is_on_home_page_a14(img):
        return clicked_any

    for label, x, y in WRONG_BUTTON_CUT_COORDS:
        if bot_vision.is_red_x_box_at(img, x, y, radius=11):
            print(f" [!] [WRONG BUTTON CUT] '{label}' ({x}, {y}) par Red 'X' mila! Cut kar rahe hain...")
            bot_adb.tap(x, y, delay_range=(0.10, 0.18), jitter=2)
            clicked_any = True
            record_stat("wrong_buttons_cut", 1)
            bot_adb.human_sleep(0.12, 0.03)
            img = bot_adb.get_screenshot(force_fresh=True)
            if is_on_home_page_a14(img):
                break

    return clicked_any

def check_wrong_and_home_page_a14(img=None, check_clan_chat=False):
    if img is None:
        img = bot_adb.get_screenshot()

    if check_and_handle_connection_lost_a14(img, force_ocr=False):
        img = bot_adb.get_screenshot(force_fresh=True)

    if check_clan_chat and check_clan_chat_drawer_a14(img, use_build_fallback=False):
        img = bot_adb.get_screenshot(force_fresh=True)

    if is_on_home_page_a14(img):
        return False, True, img

    was_cut = check_wrong_buttons_a14(img, check_clan_chat=False)
    if was_cut:
        img = bot_adb.get_screenshot(force_fresh=True)
    is_home = is_on_home_page_a14(img)
    return was_cut, is_home, img

def check_clan_chat_drawer_a14(img=None, use_build_fallback=False):
    if img is None:
        img = bot_adb.get_screenshot()
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
        print(" [!] [CLAN CHAT DRAWER] Open Clan Chat detected! Clicking (827, 440) to close...")
        bot_adb.tap(*CLAN_CHAT_CLICK_COORD, delay_range=(0.12, 0.20), jitter=3)
        bot_adb.human_sleep(0.25, 0.04)
        record_stat("clan_chat_closed", 1)
        chk = bot_adb.get_screenshot(force_fresh=True)
        px2 = chk.load()
        rem_orange = sum(
            1 for sy in range(max(0, cy1 + 2), min(h, cy2 - 2), 3)
            for sx in range(max(0, cx1 + 3), min(w, cx2 - 3), 4)
            if px2[sx, sy][0] > 195 and (105 <= px2[sx, sy][1] <= 205) and px2[sx, sy][2] < 75
        )
        if rem_orange <= 6 and not use_build_fallback:
            return True

    if use_build_fallback or is_drawer_open:
        print(" [SAFE IN-GAME RESET] Clicking Build (2233, 948) -> Close (2322, 45) to clear Center Modal...")
        bot_adb.tap(*UPGRADE_A14["BUILD_CLICK"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.38, 0.05)
        bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.32, 0.05)
        record_stat("clan_chat_closed", 1)
        return True
    return False

def check_welcome_back_chief_a14(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
    w, h = img.size
    px_map = img.load()

    rx1, ry1, rx2, ry2 = WELCOME_CHIEF_RED_BANNER_BOX
    red_px = sum(1 for sy in range(max(0, ry1 + 2), min(h, ry2 - 2), 3)
                 for sx in range(max(0, rx1 + 4), min(w, rx2 - 4), 5)
                 if px_map[sx, sy][0] > 165 and px_map[sx, sy][1] < 75 and px_map[sx, sy][2] < 75 and (px_map[sx, sy][0] > px_map[sx, sy][1] + 95))
    
    r_total = sum(1 for sy in range(max(0, ry1 + 2), min(h, ry2 - 2), 3) for sx in range(max(0, rx1 + 4), min(w, rx2 - 4), 5))
    if r_total == 0 or (red_px / float(r_total)) < 0.60:
        return False

    gx1, gy1, gx2, gy2 = WELCOME_CHIEF_GREEN_BTN_BOX
    green_px = sum(1 for sy in range(max(0, gy1 + 1), min(h, gy2 - 1), 2)
                   for sx in range(max(0, gx1 + 4), min(w, gx2 - 4), 4)
                   if px_map[sx, sy][1] > 130 and px_map[sx, sy][1] > (px_map[sx, sy][0] + 25) and px_map[sx, sy][1] > (px_map[sx, sy][2] + 25))
    
    g_total = sum(1 for sy in range(max(0, gy1 + 1), min(h, gy2 - 1), 2) for sx in range(max(0, gx1 + 4), min(w, gx2 - 4), 4))
    if g_total == 0 or (green_px / float(g_total)) < 0.55:
        return False

    print(" [!] [WELCOME BACK CHIEF] Red Banner + Green Button verified! Clicking (1227, 932)...")
    bot_adb.tap(*WELCOME_CHIEF_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3)
    bot_adb.human_sleep(0.35, 0.05)
    record_stat("welcome_chief_closed", 1)
    return True

def _analyze_daily_reward_slot(px_map, w, h, x1, y1, x2, y2):
    green_vals = []
    gray_dark_px = 0
    total_px = 0
    for sy in range(max(0, y1 + 3), min(h, y2 - 2), 2):
        for sx in range(max(0, x1 + 6), min(w, x2 - 5), 4):
            r, g, b = px_map[sx, sy]
            total_px += 1
            if g > 145 and g > (r + 35) and g > (b + 40) and r < 165 and b < 140:
                green_vals.append(g)
            elif (45 <= r <= 145) and (45 <= g <= 145) and (45 <= b <= 155) and (max(r, g, b) - min(r, g, b) <= 32):
                gray_dark_px += 1

    if total_px == 0: return "OTHER", 0.0
    green_ratio = len(green_vals) / float(total_px)
    if green_ratio >= 0.68 and len(green_vals) >= 12:
        mean_g = sum(green_vals) / float(len(green_vals))
        mean_dev = sum(abs(v - mean_g) for v in green_vals) / float(len(green_vals))
        if mean_dev <= 16.5:
            return "FLAT_GREEN", green_ratio
    gray_ratio = gray_dark_px / float(total_px)
    if gray_ratio >= 0.55:
        return "MODAL_GRAY", gray_ratio
    return "OTHER", 0.0

def check_daily_reward_popup(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
    if is_on_home_page_a14(img) or bot_vision.is_red_x_box_at(img, *UPGRADE_A14["CLOSE_MENU"], radius=14):
        return False

    w, h = img.size
    px_map = img.load()
    close_x, close_y = DAILY_REWARD_CLOSE_BTN
    has_close_red_x = bot_vision.is_red_x_box_at(img, close_x, close_y, radius=13)

    flat_green_boxes = []
    modal_gray_count = 0

    for idx, (bx1, by1, bx2, by2) in enumerate(DAILY_REWARD_GREEN_BOXES, start=1):
        slot_type, _ = _analyze_daily_reward_slot(px_map, w, h, bx1, by1, bx2, by2)
        if slot_type == "FLAT_GREEN":
            flat_green_boxes.append((idx, (bx1 + bx2) // 2, (by1 + by2) // 2))
        elif slot_type == "MODAL_GRAY":
            modal_gray_count += 1

    is_valid_board = has_close_red_x or (1 <= len(flat_green_boxes) <= 3 and modal_gray_count >= 4)
    if not is_valid_board: return False

    for idx, cx, cy in flat_green_boxes:
        print(f" [+] [DAILY REWARD] Clicking Green Box #{idx} at ({cx}, {cy})...")
        bot_adb.tap(cx, cy, delay_range=(0.15, 0.25), jitter=3)
        bot_adb.human_sleep(0.45, 0.06)

    print(f" [x] [DAILY REWARD] Clicking Top-Right Red 'X' Button ({close_x}, {close_y})...")
    bot_adb.tap(close_x, close_y, delay_range=(0.15, 0.25), jitter=3)
    bot_adb.human_sleep(0.30, 0.05)
    record_stat("daily_rewards_claimed", 1)
    return True

def _is_maintenance_banner_visible(img):
    w, h = img.size
    px_map = img.load()
    mx1, my1, mx2, my2 = MAINTENANCE_BREAK_BOX
    yellow_px, black_px, total_px = 0, 0, 0
    for sy in range(max(0, my1), min(h, my2), 2):
        for sx in range(max(0, mx1), min(w, mx2), 3):
            r, g, b = px_map[sx, sy]
            total_px += 1
            if r > 185 and g > 145 and b < 95 and (r + g) > (b * 3): yellow_px += 1
            elif r < 80 and g < 80 and b < 80: black_px += 1

    if total_px == 0 or (yellow_px / total_px) < 0.25 or black_px < 12:
        return False, ""
    
    txt = bot_vision._ocr_card_box_region(img, mx1, my1, mx2, my2, thresh=95, psm=7, whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ").upper()
    if "MAINT" in txt or "TENANCE" in txt or "BREAK" in txt:
        return True, txt
    return False, txt

def check_and_handle_maintenance_break(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
    check_and_handle_connection_lost_a14(img, force_ocr=False)

    is_maint, read_txt = _is_maintenance_banner_visible(img)
    if not is_maint: return False

    record_stat("maintenance_breaks", 1)
    cycle_idx = 1
    while True:
        print("\n======================================================================")
        print(f"|| [MAINTENANCE BREAK VERIFIED] Read: '{read_txt}' at (979,16..1442,63) ||")
        print(f"|| [REST #{cycle_idx}] Bot 10 Minute (600s) ke rest par ja raha hai...        ||")
        print("======================================================================\n")

        bot_adb.smart_sleep(MAINTENANCE_REST_SEC, apply_speed=False)
        bot_adb.tap(*MAINTENANCE_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3, apply_speed=False)
        bot_adb.tap(*MAINTENANCE_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3, apply_speed=False)
        bot_adb.smart_sleep(5.0, apply_speed=False)

        chk_img = bot_adb.get_screenshot(force_fresh=True)
        check_wrong_buttons_a14(chk_img)
        still_maint, _ = _is_maintenance_banner_visible(chk_img)
        if not still_maint:
            print(" [✔] [MAINTENANCE OVER] Maintenance Break khatam ho gaya hai! Resuming Bot...")
            return True
        cycle_idx += 1

def _shutdown_bot_into_sleep_mode(reason):
    print("\n==============================================================================")
    print(f"|| [AUTO-SLEEP & SHUTDOWN] {reason}")
    print("|| Device ko Sleep Mode me bhej kar Bot ko safely band kiya ja raha hai...  ||")
    print("==============================================================================")
    try: subprocess.run(["adb", "shell", "input", "keyevent", "223"], timeout=4)
    except: pass
    try: print_previous_progress_report(report_stage=f"AUTO-SHUTDOWN ({reason})")
    except: pass
    import os
    os._exit(0)

def is_connection_lost_popup_visible_a14(img, force_ocr=False):
    w, h = img.size
    px_map = img.load()
    ox1, oy1, ox2, oy2 = CONNECTION_LOST_OUTER_BOX
    dark_slate_px = sum(1 for sy in range(max(0, oy1 + 25), min(h, oy2 - 25), 14)
                        for sx in range(max(0, ox1 + 35), min(w, ox2 - 35), 28)
                        if (24 <= px_map[sx, sy][0] <= 68) and (26 <= px_map[sx, sy][1] <= 70) and 
                           (28 <= px_map[sx, sy][2] <= 74) and (max(px_map[sx, sy]) - min(px_map[sx, sy]) <= 14))
    
    total_bg = sum(1 for sy in range(max(0, oy1 + 25), min(h, oy2 - 25), 14) for sx in range(max(0, ox1 + 35), min(w, ox2 - 35), 28))
    has_pixels = (total_bg > 0 and (dark_slate_px / float(total_bg)) >= 0.52)
    
    if not has_pixels and not force_ocr: return False, ""

    header_txt = bot_vision._ocr_card_box_region(img, *CONNECTION_LOST_TEXT_BOX_LEFT, thresh=165, psm=6)
    if not header_txt: header_txt = bot_vision._ocr_card_box_region(img, *CONNECTION_LOST_TEXT_BOX_WIDE, thresh=165, psm=6)
    btn_txt = bot_vision._ocr_card_box_region(img, *TRY_AGAIN_BTN_BOX, thresh=165, psm=6)

    combined_clean = re.sub(r"[^a-zA-Z\s]", " ", f"{header_txt} {btn_txt}").lower()
    keywords = ["connection", "conection", "lost", "try again", "try", "again", "server", "internet"]
    
    if any(kw in combined_clean for kw in keywords):
        return True, f"Header='{header_txt}' | Button='{btn_txt}'"
    return False, ""

def check_and_handle_connection_lost_a14(img=None, force_ocr=False):
    global _IN_CONN_LOST_HANDLER, _LAST_CONN_LOST_OCR_TIME
    if _IN_CONN_LOST_HANDLER: return False
    _IN_CONN_LOST_HANDLER = True
    try:
        if img is None:
            img = bot_adb.capture_raw_screenshot_once()
            if img is None: return False

        is_lost, ocr_info = is_connection_lost_popup_visible_a14(img, force_ocr=force_ocr)
        _LAST_CONN_LOST_OCR_TIME = time.time()
        if not is_lost: return False

        outage_start_t = time.time()
        attempt = 1
        while True:
            elapsed_total = time.time() - outage_start_t
            print("\n==============================================================================")
            print(f"|| [📡 CONNECTION LOST DETECTED] {ocr_info}")
            print(f"|| [RELOAD ATTEMPT #{attempt}/{CONNECTION_MAX_ATTEMPTS}] Clicking 'Try again' (1256, 978)... (Outage: {elapsed_total/60.0:.1f}m / 60.0m)")
            print("==============================================================================")
            record_stat("connection_lost_reloads", 1)
            bot_adb.tap(*TRY_AGAIN_CLICK_COORD, delay_range=(0.18, 0.30), jitter=4, check_pause=False, apply_speed=False)
            bot_adb.smart_sleep(10.0, apply_speed=False)

            chk_img = bot_adb.capture_raw_screenshot_once()
            if chk_img is not None:
                still_lost, _ = is_connection_lost_popup_visible_a14(chk_img, force_ocr=True)
                if not still_lost:
                    bot_adb.smart_sleep(5.0, apply_speed=False)
                    if not is_connection_lost_popup_visible_a14(bot_adb.capture_raw_screenshot_once() or chk_img, force_ocr=False)[0]:
                        print(f" [✔] [WIFI RECONNECTED] Game reloaded successfully on Attempt #{attempt}!")
                        _LAST_CONN_LOST_OCR_TIME = time.time()
                        return True

            elapsed_total = time.time() - outage_start_t
            if elapsed_total >= CONNECTION_MAX_OUTAGE_SEC:
                _shutdown_bot_into_sleep_mode(f"Wi-Fi / Server Connection Lost for 1 Full Hour ({attempt} Reloads Failed)")

            rem_window = max(30.0, min(CONNECTION_RETRY_GAP_SEC, CONNECTION_MAX_OUTAGE_SEC - elapsed_total))
            print(f" [⏳ WIFI RECOVERY WAIT] Connection still down. Waiting {rem_window/60.0:.1f} minutes before next Try Again...")
            wait_end = time.time() + rem_window
            recovered_during_wait = False

            while time.time() < wait_end:
                bot_adb.smart_sleep(min(30.0, max(1.0, wait_end - time.time())), apply_speed=False)
                probe_img = bot_adb.capture_raw_screenshot_once()
                if probe_img is not None:
                    if not is_connection_lost_popup_visible_a14(probe_img, force_ocr=False)[0] and is_on_home_page_a14(probe_img):
                        print(" [✔] [WIFI RECOVERED] Home Page detected during recovery wait!")
                        recovered_during_wait = True
                        break

            if recovered_during_wait:
                _LAST_CONN_LOST_OCR_TIME = time.time()
                return True
            attempt += 1
    finally:
        _IN_CONN_LOST_HANDLER = False

def run_zone2_home_periodic_checks(img=None):
    global _LAST_CONN_LOST_OCR_TIME
    if img is None: img = bot_adb.get_screenshot()
    do_periodic_ocr = ((time.time() - _LAST_CONN_LOST_OCR_TIME) >= CONNECTION_OCR_INTERVAL_SEC)
    if check_and_handle_connection_lost_a14(img, force_ocr=do_periodic_ocr):
        img = bot_adb.get_screenshot(force_fresh=True)

    check_and_handle_maintenance_break(img)
    if check_clan_chat_drawer_a14(img, use_build_fallback=False): img = bot_adb.get_screenshot(force_fresh=True)
    if not is_on_home_page_a14(img):
        if check_daily_reward_popup(img): img = bot_adb.get_screenshot(force_fresh=True)
        if check_wrong_buttons_a14(img, check_clan_chat=False): img = bot_adb.get_screenshot(force_fresh=True)
    return is_on_home_page_a14(img), img

# FIXED: Added missing function `click_gold_storage_3_times`
def click_gold_storage_3_times():
    print(" [*] [HOME PAGE] Gold Storage Bar (2170, 63) par 3 baar click kar rahe hain...")
    bot_adb.batch_tap_sequence([GOLD_STORAGE_BAR] * 3, inter_delay=0.04, jitter=2)

def double_click_storage_bars():
    global LAST_HOME_CLEANUP_TIME
    bot_adb.batch_tap_sequence([GOLD_STORAGE_BAR, GOLD_STORAGE_BAR, ELIXIR_STORAGE_BAR, ELIXIR_STORAGE_BAR], inter_delay=0.04, jitter=2)
    LAST_HOME_CLEANUP_TIME = time.time()

def ensure_return_to_home_page_a14():
    print(" [*] [HOME RECOVERY] Ensuring bot is cleanly on the Home Page...")
    for attempt in range(1, 4):
        img = bot_adb.get_screenshot(check_pause=False, force_fresh=True)
        if check_and_handle_connection_lost_a14(img, force_ocr=(attempt >= 2)):
            img = bot_adb.get_screenshot(check_pause=False, force_fresh=True)
        check_and_handle_maintenance_break(img)

        if is_on_home_page_a14(img):
            check_clan_chat_drawer_a14(img, use_build_fallback=False)
            double_click_storage_bars()
            return True

        if bot_vision.is_red_x_box_at(img, *UPGRADE_A14["CLOSE_MENU"], radius=14):
            bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.15, 0.25), jitter=3, check_pause=False)
            bot_adb.human_sleep(0.32, 0.04, apply_speed=True)
            continue

        check_welcome_back_chief_a14(img)
        check_daily_reward_popup(img)
        check_clan_chat_drawer_a14(img, use_build_fallback=(attempt >= 2))
        check_wrong_buttons_a14(img)

        bot_adb.tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.10, 0.18), jitter=3, check_pause=False)
        double_click_storage_bars()
        bot_adb.human_sleep(0.45, 0.05, apply_speed=True)

    record_stat("stuck_recoveries", 1)
    return is_on_home_page_a14()

def perform_home_cleanup_once(max_age_sec=1.5):
    global LAST_HOME_CLEANUP_TIME
    if (time.time() - LAST_HOME_CLEANUP_TIME) <= max_age_sec: return False
    img = bot_adb.get_screenshot()
    check_wrong_buttons_a14(img, check_clan_chat=True)
    double_click_storage_bars()
    LAST_HOME_CLEANUP_TIME = time.time()
    return True
