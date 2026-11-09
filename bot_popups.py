# bot_popups.py
# Handlers for Connection Lost, Maintenance, Clan Chat, Daily Reward & Wrong Buttons
# (100% Original Bot v8 Logic)

import time
import re
from PIL import Image, ImageOps
import pytesseract

import bot_config
from bot_coords import (
    HOME_PAGE_CHECK_COORDS, WRONG_BUTTON_CUT_COORDS, CLAN_CHAT_DRAWER_BOX,
    CLAN_CHAT_CLICK_COORD, WELCOME_CHIEF_RED_BANNER_BOX, WELCOME_CHIEF_GREEN_BTN_BOX,
    WELCOME_CHIEF_CLICK_COORD, DAILY_REWARD_OUTER_BOX, DAILY_REWARD_CLOSE_BTN,
    DAILY_REWARD_GREEN_BOXES, MAINTENANCE_BREAK_BOX, MAINTENANCE_CLICK_COORD,
    CONNECTION_LOST_OUTER_BOX, CONNECTION_LOST_TEXT_BOX_LEFT, CONNECTION_LOST_TEXT_BOX_WIDE,
    TRY_AGAIN_BTN_BOX, TRY_AGAIN_CLICK_COORD, GOLD_STORAGE_BAR, ELIXIR_STORAGE_BAR,
    GOLD_STORAGE_CHECK_BOX, ELIXIR_STORAGE_CHECK_BOX, UPGRADE_A14, FAST_ATTACK
)
import bot_adb
import bot_vision
import bot_report

LAST_HOME_CLEANUP_TIME = 0.0
_LAST_CONN_LOST_OCR_TIME = 0.0
_IN_CONN_LOST_HANDLER = False

# ==========================================
# 1. CONNECTION LOST / TRY AGAIN ENGINE
# ==========================================

def _has_connection_lost_dark_box_pixels(img):
    w, h = img.size
    px_map = img.load()
    ox1, oy1, ox2, oy2 = CONNECTION_LOST_OUTER_BOX

    dark_slate_px = 0
    total_bg_px = 0
    for sy in range(max(0, oy1 + 25), min(h, oy2 - 25), 14):
        for sx in range(max(0, ox1 + 35), min(w, ox2 - 35), 28):
            r, g, b = px_map[sx, sy]
            total_bg_px += 1
            if (24 <= r <= 68) and (26 <= g <= 70) and (28 <= b <= 74) and (max(r, g, b) - min(r, g, b) <= 14):
                dark_slate_px += 1

    if total_bg_px == 0 or (dark_slate_px / float(total_bg_px)) < 0.52:
        return False

    tx1, ty1, tx2, ty2 = CONNECTION_LOST_TEXT_BOX_LEFT
    header_white_px = 0
    for sy in range(max(0, ty1), min(h, ty2), 3):
        for sx in range(max(0, tx1), min(w, tx2), 4):
            r, g, b = px_map[sx, sy]
            if r > 195 and g > 195 and b > 195 and (max(r, g, b) - min(r, g, b) <= 25):
                header_white_px += 1

    bx1, by1, bx2, by2 = TRY_AGAIN_BTN_BOX
    btn_white_px = 0
    for sy in range(max(0, by1), min(h, by2), 3):
        for sx in range(max(0, bx1), min(w, bx2), 4):
            r, g, b = px_map[sx, sy]
            if r > 195 and g > 195 and b > 195 and (max(r, g, b) - min(r, g, b) <= 25):
                btn_white_px += 1

    return header_white_px >= 10 and btn_white_px >= 8

def _ocr_white_text_on_dark_box(img, box_coords):
    w, h = img.size
    x1, y1, x2, y2 = box_coords
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if (x2 - x1) < 15 or (y2 - y1) < 12:
        return ""

    crop = img.crop((x1, y1, x2, y2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    uw, uh = upscaled.size
    src = upscaled.load()

    bw = Image.new("L", (uw, uh), 255)
    dst = bw.load()
    ink_px = 0
    for py in range(uh):
        for px in range(uw):
            r, g, b = src[px, py]
            if r > 165 and g > 165 and b > 165 and (max(r, g, b) - min(r, g, b) <= 35):
                dst[px, py] = 0
                ink_px += 1

    if ink_px < 12:
        return ""
    padded = ImageOps.expand(bw, border=12, fill=255)
    return pytesseract.image_to_string(padded, config="--oem 3 --psm 6").strip()

def is_connection_lost_popup_visible_a14(img, force_ocr=False):
    has_pixels = _has_connection_lost_dark_box_pixels(img)
    if not has_pixels and not force_ocr:
        return False, ""

    header_txt = _ocr_white_text_on_dark_box(img, CONNECTION_LOST_TEXT_BOX_LEFT)
    if not header_txt:
        header_txt = _ocr_white_text_on_dark_box(img, CONNECTION_LOST_TEXT_BOX_WIDE)
    btn_txt = _ocr_white_text_on_dark_box(img, TRY_AGAIN_BTN_BOX)

    combined_clean = re.sub(r"[^a-zA-Z\s]", " ", f"{header_txt} {btn_txt}").lower()
    keywords = ["connection", "conection", "lost", "try again", "try", "again", "server", "internet"]
    matched_kw = any(kw in combined_clean for kw in keywords)

    if matched_kw:
        return True, f"Header='{header_txt}' | Button='{btn_txt}'"

    if has_pixels:
        full_txt = _ocr_white_text_on_dark_box(img, CONNECTION_LOST_OUTER_BOX)
        full_clean = re.sub(r"[^a-zA-Z\s]", " ", full_txt).lower()
        if any(kw in full_clean for kw in keywords):
            return True, f"FullBox='{full_txt[:45]}'"

    return False, ""

def check_and_handle_connection_lost_a14(img=None, force_ocr=False):
    global _IN_CONN_LOST_HANDLER, _LAST_CONN_LOST_OCR_TIME
    if _IN_CONN_LOST_HANDLER:
        return False

    _IN_CONN_LOST_HANDLER = True
    try:
        if img is None:
            img = bot_adb.capture_raw_screenshot_once()
            if img is None:
                return False

        is_lost, ocr_info = is_connection_lost_popup_visible_a14(img, force_ocr=force_ocr)
        _LAST_CONN_LOST_OCR_TIME = time.time()
        if not is_lost:
            return False

        outage_start_t = time.time()
        attempt = 1

        while True:
            elapsed_total = time.time() - outage_start_t
            print("\n==============================================================================")
            print(f"|| [📡 CONNECTION LOST DETECTED] {ocr_info}")
            print(f"|| [RELOAD ATTEMPT #{attempt}/{bot_config.CONNECTION_MAX_ATTEMPTS}] Clicking 'Try again' (1256, 978)... (Outage: {elapsed_total/60.0:.1f}m / 60.0m)")
            print("==============================================================================")

            bot_report.record_stat("connection_lost_reloads", 1)
            bot_adb.tap(*TRY_AGAIN_CLICK_COORD, delay_range=(0.18, 0.30), jitter=4, check_pause=False, apply_speed=False)

            bot_adb.smart_sleep(10.0, apply_speed=False)

            chk_img = bot_adb.capture_raw_screenshot_once()
            if chk_img is not None:
                still_lost, _ = is_connection_lost_popup_visible_a14(chk_img, force_ocr=True)
                if not still_lost:
                    bot_adb.smart_sleep(5.0, apply_speed=False)
                    chk_img2 = bot_adb.capture_raw_screenshot_once()
                    if chk_img2 is not None:
                        still_lost2, _ = is_connection_lost_popup_visible_a14(chk_img2, force_ocr=False)
                        if not still_lost2:
                            print(f" [✔] [WIFI RECONNECTED] Game reloaded successfully on Attempt #{attempt}!")
                            _LAST_CONN_LOST_OCR_TIME = time.time()
                            return True

            elapsed_total = time.time() - outage_start_t
            if elapsed_total >= bot_config.CONNECTION_MAX_OUTAGE_SEC:
                bot_adb._shutdown_bot_into_sleep_mode(
                    f"Wi-Fi / Server Connection Lost for 1 Full Hour ({attempt} Reload Attempts Failed)"
                )

            rem_window = max(30.0, min(bot_config.CONNECTION_RETRY_GAP_SEC, bot_config.CONNECTION_MAX_OUTAGE_SEC - elapsed_total))
            print(f" [⏳ WIFI RECOVERY WAIT] Connection still down after Attempt #{attempt}. Waiting {rem_window/60.0:.1f} minutes before next Try Again click...")
            wait_end = time.time() + rem_window
            recovered_during_wait = False

            while time.time() < wait_end:
                bot_adb.smart_sleep(min(30.0, max(1.0, wait_end - time.time())), apply_speed=False)
                probe_img = bot_adb.capture_raw_screenshot_once()
                if probe_img is not None:
                    lost_now, _ = is_connection_lost_popup_visible_a14(probe_img, force_ocr=False)
                    if not lost_now and is_on_home_page_a14(probe_img):
                        print(" [✔] [WIFI RECOVERED] Home Page detected during recovery wait!")
                        recovered_during_wait = True
                        break

            if recovered_during_wait:
                _LAST_CONN_LOST_OCR_TIME = time.time()
                return True

            attempt += 1
            fresh_img = bot_adb.capture_raw_screenshot_once()
            if fresh_img is not None:
                _, ocr_info = is_connection_lost_popup_visible_a14(fresh_img, force_ocr=True)
                if not ocr_info:
                    ocr_info = "Connection still offline / retrying reload"
    finally:
        _IN_CONN_LOST_HANDLER = False

# ==========================================
# 2. POPUP & SCREEN SCANNERS (Original v8 logic)
# ==========================================

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
        print(" [!] [CLAN CHAT DRAWER] Open Clan Chat detected at (792,423..863,457)! Clicking (827, 440) to close...")
        bot_adb.tap(*CLAN_CHAT_CLICK_COORD, delay_range=(0.12, 0.20), jitter=3)
        bot_adb.human_sleep(0.25, 0.04)
        bot_report.record_stat("clan_chat_closed", 1)
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
        print(" [SAFE IN-GAME RESET] Clicking Build (2233, 948) -> Close (2322, 45) to clear Clan Chat / Center Modal...")
        bot_adb.tap(*UPGRADE_A14["BUILD_CLICK"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.38, 0.05)
        bot_adb.tap(*UPGRADE_A14["CLOSE_MENU"], delay_range=(0.18, 0.28), jitter=3)
        bot_adb.human_sleep(0.32, 0.05)
        bot_report.record_stat("clan_chat_closed", 1)
        return True

    return False

def check_welcome_back_chief_a14(img=None):
    if img is None:
        img = bot_adb.get_screenshot()
    w, h = img.size
    px_map = img.load()

    rx1, ry1, rx2, ry2 = WELCOME_CHIEF_RED_BANNER_BOX
    red_px = 0
    r_total = 0
    for sy in range(max(0, ry1 + 2), min(h, ry2 - 2), 3):
        for sx in range(max(0, rx1 + 4), min(w, rx2 - 4), 5):
            r, g, b = px_map[sx, sy]
            r_total += 1
            if r > 165 and g < 75 and b < 75 and (r > g + 95):
                red_px += 1

    if r_total == 0 or (red_px / float(r_total)) < 0.60:
        return False

    gx1, gy1, gx2, gy2 = WELCOME_CHIEF_GREEN_BTN_BOX
    green_px = 0
    g_total = 0
    for sy in range(max(0, gy1 + 1), min(h, gy2 - 1), 2):
        for sx in range(max(0, gx1 + 4), min(w, gx2 - 4), 4):
            r, g, b = px_map[sx, sy]
            g_total += 1
            if g > 130 and g > (r + 25) and g > (b + 25):
                green_px += 1

    if g_total == 0 or (green_px / float(g_total)) < 0.55:
        return False

    print(" [!] [WELCOME BACK CHIEF] Red Banner + Green Button verified! Clicking (1227, 932)...")
    bot_adb.tap(*WELCOME_CHIEF_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3)
    bot_adb.human_sleep(0.35, 0.05)
    bot_report.record_stat("welcome_chief_closed", 1)
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

    if total_px == 0:
        return "OTHER", 0.0

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

    if is_on_home_page_a14(img):
        return False
    if bot_vision.is_red_x_box_at(img, *UPGRADE_A14["CLOSE_MENU"], radius=14):
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
    if not is_valid_board:
        return False

    print(f" [DAILY REWARD VERIFIED] GreenSlots={len(flat_green_boxes)}, GraySiblingSlots={modal_gray_count}, RedX_Before={has_close_red_x}")

    for idx, cx, cy in flat_green_boxes:
        print(f" [+] [DAILY REWARD] Clicking Green Box #{idx} at ({cx}, {cy})...")
        bot_adb.tap(cx, cy, delay_range=(0.15, 0.25), jitter=3)
        bot_adb.human_sleep(0.45, 0.06)

    print(f" [x] [DAILY REWARD] Clicking Top-Right Red 'X' Button ({close_x}, {close_y})...")
    bot_adb.tap(close_x, close_y, delay_range=(0.15, 0.25), jitter=3)
    bot_adb.human_sleep(0.30, 0.05)
    bot_report.record_stat("daily_rewards_claimed", 1)
    return True

def check_and_handle_maintenance_break(img=None):
    if img is None:
        img = bot_adb.get_screenshot()

    check_and_handle_connection_lost_a14(img, force_ocr=False)

    def _is_maintenance_banner_visible(cur_img):
        w, h = cur_img.size
        px_map = cur_img.load()
        mx1, my1, mx2, my2 = MAINTENANCE_BREAK_BOX
        yellow_px = 0
        black_px = 0
        total_px = 0
        for sy in range(max(0, my1), min(h, my2), 2):
            for sx in range(max(0, mx1), min(w, mx2), 3):
                r, g, b = px_map[sx, sy]
                total_px += 1
                if r > 185 and g > 145 and b < 95 and (r + g) > (b * 3):
                    yellow_px += 1
                elif r < 80 and g < 80 and b < 80:
                    black_px += 1

        if total_px == 0 or (yellow_px / total_px) < 0.25 or black_px < 12:
            return False, ""

        crop = cur_img.crop((mx1, my1, mx2, my2))
        upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
        uw, uh = upscaled.size
        u_src = upscaled.load()
        bw = Image.new("L", (uw, uh), 255)
        u_dst = bw.load()
        for py in range(uh):
            for px in range(uw):
                r, g, b = u_src[px, py]
                if r < 95 and g < 95 and b < 95:
                    u_dst[px, py] = 0
        padded = ImageOps.expand(bw, border=12, fill=255)
        cfg = "--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        txt = pytesseract.image_to_string(padded, config=cfg).strip().upper()
        clean_t = re.sub(r"[^A-Z]", "", txt)
        if "MAINT" in clean_t or "TENANCE" in clean_t or "BREAK" in clean_t:
            return True, txt
        return False, txt

    is_maint, read_txt = _is_maintenance_banner_visible(img)
    if not is_maint:
        return False

    bot_report.record_stat("maintenance_breaks", 1)
    cycle_idx = 1
    while True:
        print("\n======================================================================")
        print(f"|| [MAINTENANCE BREAK VERIFIED] Read: '{read_txt}' at (979,16..1442,63) ||")
        print(f"|| [REST #{cycle_idx}] Bot 10 Minute (600s) ke rest par ja raha hai...        ||")
        print("======================================================================\n")

        bot_adb.smart_sleep(bot_config.MAINTENANCE_REST_SEC, apply_speed=False)

        print(f" [MAINTENANCE CHECK #{cycle_idx}] 10 Min complete! Clicking (1210, 39) 2 times...")
        bot_adb.tap(*MAINTENANCE_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3, apply_speed=False)
        bot_adb.tap(*MAINTENANCE_CLICK_COORD, delay_range=(0.15, 0.25), jitter=3, apply_speed=False)
        bot_adb.smart_sleep(5.0, apply_speed=False)

        chk_img = bot_adb.get_screenshot(force_fresh=True)
        check_wrong_buttons_a14(chk_img)
        still_maint, read_txt = _is_maintenance_banner_visible(chk_img)
        if not still_maint:
            print(" [✔] [MAINTENANCE OVER] Maintenance Break khatam ho gaya hai! Resuming Bot...")
            return True
        cycle_idx += 1

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
            bot_report.record_stat("wrong_buttons_cut", 1)
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

def run_zone1_post_id_switch_checks(img=None):
    if img is None:
        img = bot_adb.get_screenshot(force_fresh=True)

    if check_and_handle_connection_lost_a14(img, force_ocr=False):
        img = bot_adb.get_screenshot(force_fresh=True)

    if is_on_home_page_a14(img):
        if check_clan_chat_drawer_a14(img, use_build_fallback=False):
            img = bot_adb.get_screenshot(force_fresh=True)
        return False, True, img

    acted = False
    if check_welcome_back_chief_a14(img):
        acted = True
        img = bot_adb.get_screenshot(force_fresh=True)

    if not is_on_home_page_a14(img) and check_daily_reward_popup(img):
        acted = True
        img = bot_adb.get_screenshot(force_fresh=True)

    if not is_on_home_page_a14(img) and check_wrong_buttons_a14(img, check_clan_chat=True):
        acted = True
        img = bot_adb.get_screenshot(force_fresh=True)

    is_home = is_on_home_page_a14(img)
    return acted, is_home, img

def run_zone2_home_periodic_checks(img=None):
    global _LAST_CONN_LOST_OCR_TIME
    if img is None:
        img = bot_adb.get_screenshot()

    do_periodic_ocr = ((time.time() - _LAST_CONN_LOST_OCR_TIME) >= bot_config.CONNECTION_OCR_INTERVAL_SEC)
    if check_and_handle_connection_lost_a14(img, force_ocr=do_periodic_ocr):
        img = bot_adb.get_screenshot(force_fresh=True)

    check_and_handle_maintenance_break(img)
    if check_clan_chat_drawer_a14(img, use_build_fallback=False):
        img = bot_adb.get_screenshot(force_fresh=True)
    if not is_on_home_page_a14(img):
        if check_daily_reward_popup(img):
            img = bot_adb.get_screenshot(force_fresh=True)
        if check_wrong_buttons_a14(img, check_clan_chat=False):
            img = bot_adb.get_screenshot(force_fresh=True)
    return is_on_home_page_a14(img), img

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

    bot_report.record_stat("stuck_recoveries", 1)
    return is_on_home_page_a14()

# ==========================================
# 3. HOME STORAGE BAR ACTIONS (V8 Original)
# ==========================================

def click_gold_storage_3_times():
    print(" [*] [HOME PAGE] Gold Storage Bar (2170, 63) par 3 baar click kar rahe hain...")
    bot_adb.batch_tap_sequence([GOLD_STORAGE_BAR] * 3, inter_delay=0.04, jitter=2)

def double_click_storage_bars():
    global LAST_HOME_CLEANUP_TIME
    bot_adb.batch_tap_sequence(
        [GOLD_STORAGE_BAR, GOLD_STORAGE_BAR, ELIXIR_STORAGE_BAR, ELIXIR_STORAGE_BAR],
        inter_delay=0.04,
        jitter=2
    )
    LAST_HOME_CLEANUP_TIME = time.time()

def perform_home_cleanup_once(max_age_sec=1.5):
    global LAST_HOME_CLEANUP_TIME
    if (time.time() - LAST_HOME_CLEANUP_TIME) <= max_age_sec:
        return False
    img = bot_adb.get_screenshot()
    check_wrong_buttons_a14(img, check_clan_chat=True)
    double_click_storage_bars()
    LAST_HOME_CLEANUP_TIME = time.time()
    return True

def check_resources_full_for_upgrade(img=None):
    if img is None:
        img = bot_adb.get_screenshot()

    def _scan_storage_bars(cur_img):
        px_map = cur_img.load()
        gx1, gy1, gx2, gy2 = GOLD_STORAGE_CHECK_BOX
        gold_total, gold_colored = 0, 0
        for y in range(gy1, gy2, 2):
            for x in range(gx1, gx2, 2):
                r, g, b = px_map[x, y]
                if r > 215 and g > 215 and b > 215:
                    continue
                gold_total += 1
                if r > 165 and g > 125 and b < 95 and (r + g) > (b * 3):
                    gold_colored += 1
        g_ratio = (gold_colored / gold_total) if gold_total > 0 else 0.0

        ex1, ey1, ex2, ey2 = ELIXIR_STORAGE_CHECK_BOX
        elixir_total, elixir_colored = 0, 0
        for y in range(ey1, ey2, 2):
            for x in range(ex1, ex2, 2):
                r, g, b = px_map[x, y]
                if r > 215 and g > 215 and b > 215:
                    continue
                elixir_total += 1
                if r > 145 and b > 110 and r > (g + 25):
                    elixir_colored += 1
        e_ratio = (elixir_colored / elixir_total) if elixir_total > 0 else 0.0
        return g_ratio, e_ratio

    gold_ratio, elixir_ratio = _scan_storage_bars(img)

    if gold_ratio < 0.05 and elixir_ratio < 0.05 and not is_on_home_page_a14(img):
        print(" [!] [STORAGE ANTI-COVER GUARD] Storage bars hidden by overlay! Recovering Home Page & re-scanning...")
        ensure_return_to_home_page_a14()
        img = bot_adb.get_screenshot(force_fresh=True)
        gold_ratio, elixir_ratio = _scan_storage_bars(img)

    is_gold_full = gold_ratio >= 0.45
    is_elixir_full = elixir_ratio >= 0.45
    print(f" [i] [STORAGE SCAN] Gold Yellow: {gold_ratio*100:.0f}% (Full={is_gold_full}) | Elixir Pink: {elixir_ratio*100:.0f}% (Full={is_elixir_full})")
    return is_gold_full or is_elixir_full

def check_wall_resources_full_a14(img=None):
    return check_resources_full_for_upgrade(img=img)
