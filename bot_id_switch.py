# bot_id_switch.py
# Flawless Zero-Inertia ID Switcher with Visited-ID Memory & LANCZOS OCR

import os
import json
import time
import re
import traceback

import bot_config
from bot_coords import ID_SWITCH_A14
import bot_adb
import bot_vision
import bot_popups
import bot_report

MEMORY_FILE_PATH = "bot_id_memory.json"

_VISITED_IDS_IN_CYCLE = set()
_LAST_OPENED_UID = ""

# ==========================================
# 1. PERSISTENT ID MEMORY & STATE MANAGER
# ==========================================
def load_id_memory():
    default_mem = {
        "current_id_index": 1,
        "total_ids": 1,
        "known_ids": {}
    }
    if not os.path.exists(MEMORY_FILE_PATH):
        return default_mem
    try:
        with open(MEMORY_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                default_mem.update(data)
    except Exception:
        pass
    return default_mem

def save_id_memory(mem_data):
    try:
        with open(MEMORY_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(mem_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_id_role_label(id_index):
    return "MAIN ID" if int(id_index) <= 4 else "SECONDARY ID"

def get_saved_unique_id_name(id_index):
    mem = load_id_memory()
    known = mem.get("known_ids", {})
    entry = known.get(str(id_index), {})
    uid = entry.get("unique_id", "").strip()
    th = entry.get("th", "").strip()
    if uid and th:
        return f"{uid} (TH{th})"
    elif uid:
        return uid
    return f"ID #{id_index}"

def sync_initial_id_to_report(id_index):
    global _LAST_OPENED_UID
    uname = get_saved_unique_id_name(id_index)
    bot_report.set_report_active_id(id_index, id_name=uname, is_switch=False)
    mem = load_id_memory()
    uid_raw = mem.get("known_ids", {}).get(str(id_index), {}).get("unique_id", "")
    if uid_raw:
        _VISITED_IDS_IN_CYCLE.add(_normalize_uid_key(uid_raw))
        _LAST_OPENED_UID = _normalize_uid_key(uid_raw)

def _normalize_uid_key(uid_str):
    if not uid_str:
        return ""
    return re.sub(r'[^a-z0-9]', '', uid_str.lower())

# ==========================================
# 2. SUPERCELL LOGO VERIFIER & FAST SCROLLER
# ==========================================
def _check_supercell_logo_pixel_fast(img):
    w, h = img.size
    px_map = img.load()
    lx1, ly1, lx2, ly2 = ID_SWITCH_A14["SUPERCELL_LOGO_BOX"]

    blue_bg_px = sum(1 for y in range(max(0, ly1 - 8), min(h, ly2 + 8), 2)
                     for x in range(max(0, lx1 - 8), min(w, lx2 + 8), 2)
                     if px_map[x,y][2] > 95 and px_map[x,y][2] > px_map[x,y][0] + 25 and px_map[x,y][2] > px_map[x,y][1] + 15)
    
    div_x = ID_SWITCH_A14["DIVIDER_X"]
    left_blue = sum(1 for sy in [250, 400, 550, 700, 850] if sy < h and px_map[max(0, div_x - 120), sy][2] > px_map[max(0, div_x - 120), sy][0] + 20 and px_map[max(0, div_x - 120), sy][2] > 60)
    right_light = sum(1 for sy in [250, 400, 550, 700, 850] if sy < h and px_map[min(w - 1, div_x + 120), sy][0] > 210 and px_map[min(w - 1, div_x + 120), sy][1] > 210 and px_map[min(w - 1, div_x + 120), sy][2] > 210)

    divider_valid = (left_blue >= 3 and right_light >= 3)
    return (blue_bg_px >= 35 and divider_valid), divider_valid

def verify_supercell_id_list_box_twice(img=None):
    confirmations = 0
    for check_num in range(1, 3):
        cur_img = img if (check_num == 1 and img is not None) else bot_adb.get_screenshot(force_fresh=True)
        ok, div_ok = _check_supercell_logo_pixel_fast(cur_img)
        if ok or div_ok:
            confirmations += 1
            print(f" [✔] [ID LIST VERIFY #{check_num}/2] Supercell ID Box Confirmed!")
        else:
            print(f" [!] [ID LIST VERIFY #{check_num}/2] Not confirmed yet.")
        if check_num == 1:
            bot_adb.human_sleep(0.15, 0.03)
    return confirmations >= 1

def open_supercell_id_list_from_home():
    for attempt in range(1, 4):
        bot_adb.check_pause_point(allow_raise=True)
        print(f"\n [ID SWITCH NAV] Opening Supercell ID List (Attempt #{attempt}/3)...")

        bot_popups.check_wrong_buttons_a14(check_clan_chat=True)

        print(" [>] [STEP (i)] Clicking Profile Button (142, 122)...")
        bot_adb.tap(*ID_SWITCH_A14["PROFILE_BTN"], delay_range=(0.25, 0.40), jitter=3)
        bot_adb.human_sleep(0.55, 0.06)

        print(" [>] [STEP (ii)] Clicking Settings Tab (1755, 92)...")
        bot_adb.tap(*ID_SWITCH_A14["SETTINGS_BTN"], delay_range=(0.25, 0.40), jitter=3)
        bot_adb.human_sleep(0.55, 0.06)

        print(" [>] [STEP (iii)] Clicking Switch ID Icon (1507, 207)...")
        bot_adb.tap(*ID_SWITCH_A14["SWITCH_ICON_BTN"], delay_range=(0.30, 0.45), jitter=3)
        bot_adb.human_sleep(0.95, 0.10)

        if verify_supercell_id_list_box_twice():
            return True

        chk = bot_adb.get_screenshot(force_fresh=True)
        if bot_popups.check_wrong_buttons_a14(chk, check_clan_chat=True) or bot_popups.is_on_home_page_a14(chk):
            continue

        bot_adb.tap(*ID_SWITCH_A14["SWITCH_ICON_BTN"], delay_range=(0.30, 0.45), jitter=3)
        bot_adb.human_sleep(1.0, 0.10)
        if verify_supercell_id_list_box_twice():
            return True

        bot_popups.ensure_return_to_home_page_a14()
        bot_adb.human_sleep(0.60, 0.08)
    return False

def perform_smooth_id_list_scroll(scroll_num=1, total_scrolls=1):
    bot_adb.check_pause_point(allow_raise=True)
    sx1, sy1 = ID_SWITCH_A14["SCROLL_START"]
    sx2, sy2 = ID_SWITCH_A14["SCROLL_END"]
    dur = ID_SWITCH_A14["SCROLL_DURATION_MS"]
    print(f" [v] [ID LIST SCROLL {scroll_num}/{total_scrolls}] Controlled Zero-Inertia Scroll ({sx1},{sy1} -> {sx2},{sy2} @ {dur}ms)...")
    bot_adb.swipe(sx1, sy1, sx2, sy2, duration=dur, post_sleep=1.10, apply_speed=False)

def compute_scroll_and_slot_for_id(target_id_index):
    n = max(1, int(target_id_index))
    return (n - 1) // 3, ((n - 1) % 3) + 1

# ==========================================
# 3. ID CARD SCANNER & MATCHER
# ==========================================
def read_town_hall_from_card(img, card_top):
    w, h = img.size
    tx1, _, tx2, _ = ID_SWITCH_A14["TOWN_HALL_BOX"]
    ty1 = max(0, card_top + ID_SWITCH_A14["TH_REL_Y1"] - 3)
    ty2 = min(h, card_top + ID_SWITCH_A14["TH_REL_Y2"] + 3)
    if ty2 - ty1 < 14: return ""

    import pytesseract
    from PIL import ImageOps, Image
    crop = img.crop((tx1, ty1, tx2, ty2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS).convert('L')

    for thresh in [165, 145, 180]:
        bw = upscaled.point(lambda p: 0 if p < thresh else 255, '1').convert('L')
        padded = ImageOps.expand(bw, border=12, fill=255)
        txt = pytesseract.image_to_string(padded, config='--oem 3 --psm 7').strip()
        matches = re.findall(r'\b(1[0-8]|[1-9])\b', txt)
        if matches: return matches[-1]
        m_any = re.search(r'(1[0-8]|[1-9])', txt)
        if m_any: return m_any.group(1)
    return ""

def read_supercell_unique_id_from_card(img, card_top):
    w, h = img.size
    ux1, _, ux2, _ = ID_SWITCH_A14["UNIQUE_ID_BOX"]
    uy1 = max(0, card_top + ID_SWITCH_A14["UNIQUE_ID_REL_Y1"] - 3)
    uy2 = min(h, card_top + ID_SWITCH_A14["UNIQUE_ID_REL_Y2"] + 3)
    if uy2 - uy1 < 18: return ""

    import pytesseract
    from PIL import ImageOps, Image
    crop = img.crop((ux1, uy1, ux2, uy2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    cw, ch = upscaled.size
    src = upscaled.load()

    best_read, best_alnum_len = "", 0
    cfg = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-'

    for thresh in [120, 142, 105]:
        bw = Image.new('L', (cw, ch), 255)
        dst = bw.load()
        for py in range(ch):
            for px in range(cw):
                r, g, b = src[px, py]
                if r < thresh and g < thresh and b < thresh and (max(r,g,b) - min(r,g,b) <= 45):
                    dst[px, py] = 0
        padded = ImageOps.expand(bw, border=12, fill=255)
        raw = pytesseract.image_to_string(padded, config=cfg).strip()
        cleaned = re.sub(r'[^a-zA-Z0-9\s_\-]', '', raw)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        alnum_only = re.sub(r'[^a-zA-Z0-9]', '', cleaned)
        if len(alnum_only) > best_alnum_len:
            best_alnum_len = len(alnum_only)
            best_read = cleaned
        if best_alnum_len >= 6: break
    return best_read

def find_visible_coc_id_cards(img):
    w, h = img.size
    px_map = img.load()
    scan_x_points = [1763, 2020, 2110]
    in_card, card_top, raw_spans = False, 0, []

    for y in range(160, min(h - 4, 1075), 2):
        white_hits = sum(1 for sx in scan_x_points if px_map[sx,y][0] >= 247 and px_map[sx,y][1] >= 247 and px_map[sx,y][2] >= 247 and (max(px_map[sx,y]) - min(px_map[sx,y]) <= 8))
        if white_hits >= 2 and not in_card:
            in_card, card_top = True, y
        elif white_hits < 2 and in_card:
            in_card = False
            if y - card_top >= 45: raw_spans.append((card_top, y))

    if in_card and (1075 - card_top) >= 45:
        raw_spans.append((card_top, 1075))

    detected_cards = []
    for idx, (y1, y2) in enumerate(raw_spans):
        span_h = y2 - y1
        is_full = (175 <= span_h <= 265)
        cy = (y1 + y2) // 2
        safe_cy = max(250, min(920, cy)) if is_full else min(h - 15, y1 + 65)
        detected_cards.append({
            "slot": idx + 1, "top": y1, "bottom": y2, "height": span_h,
            "center_y": cy, "click_x": 1763, "click_y": safe_cy, "is_full": is_full
        })
    return detected_cards

def scan_visible_cards_with_ocr(img):
    cards = find_visible_coc_id_cards(img)
    enriched = []
    for c in cards:
        uid, th = "", ""
        if c["top"] + ID_SWITCH_A14["UNIQUE_ID_REL_Y2"] <= img.height - 5:
            uid = read_supercell_unique_id_from_card(img, c["top"])
            if c["top"] + ID_SWITCH_A14["TH_REL_Y2"] <= img.height - 4:
                th = read_town_hall_from_card(img, c["top"])
        c_copy = dict(c)
        c_copy["unique_id"] = uid
        c_copy["th"] = th
        enriched.append(c_copy)
    return enriched

def ids_roughly_match(id_a, id_b, th_a="", th_b=""):
    if not id_a or not id_b: return False
    if th_a and th_b and th_a.isdigit() and th_b.isdigit() and int(th_a) != int(th_b):
        return False
    a, b = _normalize_uid_key(id_a), _normalize_uid_key(id_b)
    if not a or not b: return False
    if a == b: return True
    if len(a) >= 5 and len(b) >= 5:
        if a in b or b in a or a[:5] == b[:5] or a[-5:] == b[-5:]: return True
        common = sum(1 for i, ch in enumerate(a[:min(len(a), len(b))]) if ch == b[i])
        if common >= max(5, int(min(len(a), len(b)) * 0.72)): return True
    return False

# ==========================================
# 4. MASTER SWITCH EXECUTION
# ==========================================
def switch_to_target_id(target_id_index, total_ids, current_id_index=None, max_load_wait=None):
    global _VISITED_IDS_IN_CYCLE, _LAST_OPENED_UID
    switch_start_t = time.time()
    target_id_index = int(target_id_index)
    total_ids = max(1, min(100, int(total_ids)))

    if total_ids <= 1:
        print(" [i] [SINGLE ID BYPASS] Total IDs = 1. Skipping Supercell ID switch menu...")
        bot_popups.ensure_return_to_home_page_a14()
        bot_adb.zoom_out_village_a14(passes=2, reason="SINGLE-ID HOME VIEW")
        return True

    if target_id_index > total_ids or target_id_index < 1:
        target_id_index = 1
    if target_id_index == 1:
        _VISITED_IDS_IN_CYCLE.clear()

    role_str = get_id_role_label(target_id_index)
    mem = load_id_memory()
    known_ids = mem.get("known_ids", {})

    if current_id_index is not None and str(current_id_index) in known_ids:
        leaving_uid = _normalize_uid_key(known_ids[str(current_id_index)].get("unique_id", ""))
        if leaving_uid:
            _VISITED_IDS_IN_CYCLE.add(leaving_uid)
            _LAST_OPENED_UID = leaving_uid

    print("\n======================================================================")
    print(f" || [ID SWITCH SYSTEM] Switching to ID #{target_id_index} / {total_ids} [{role_str}] ||")
    print("======================================================================")

    for nav_retry in range(1, 3):
        if not open_supercell_id_list_from_home():
            print(" [!] [ERROR] Could not open Supercell ID List Box! Staying on Home Page.")
            bot_popups.ensure_return_to_home_page_a14()
            return False

        scrolls_needed, expected_slot = compute_scroll_and_slot_for_id(target_id_index)
        print(f" [i] [SCROLL PLAN] Target ID #{target_id_index} -> Smooth Scrolls: {scrolls_needed} | Slot: #{expected_slot}")

        pre_click_interrupted = False
        for s_i in range(1, scrolls_needed + 1):
            perform_smooth_id_list_scroll(s_i, scrolls_needed)
            if s_i < scrolls_needed and s_i % 3 == 0:
                chk_img = bot_adb.get_screenshot()
                if not _check_supercell_logo_pixel_fast(chk_img)[0]:
                    print(" [!] [PRE-CLICK GUARD] Intermediate scroll interrupted!")
                    bot_popups.check_wrong_buttons_a14(chk_img, check_clan_chat=True)
                    pre_click_interrupted = True
                    break
            elif s_i == scrolls_needed:
                chk_img = bot_adb.get_screenshot(force_fresh=True)
                if not verify_supercell_id_list_box_twice(chk_img):
                    print(" [!] [PRE-CLICK GUARD] Final scroll missing Supercell ID List Box! Re-starting...")
                    pre_click_interrupted = True
                    break

        if not pre_click_interrupted:
            break

    img_now = bot_adb.get_screenshot(force_fresh=True)
    if not _check_supercell_logo_pixel_fast(img_now)[0]:
        if not open_supercell_id_list_from_home(): return False
        for s_i in range(1, scrolls_needed + 1): perform_smooth_id_list_scroll(s_i, scrolls_needed)
        img_now = bot_adb.get_screenshot(force_fresh=True)

    visible_cards = scan_visible_cards_with_ocr(img_now)
    for c in visible_cards:
        if scrolls_needed == 0 and 1 <= c["slot"] <= 3 and c["unique_id"]:
            known_ids[str(c["slot"])] = {"unique_id": c["unique_id"], "th": c["th"], "scrolls": 0, "slot": c["slot"]}

    chosen_click_x, chosen_click_y = ID_SWITCH_A14["ID_SLOTS"][expected_slot - 1]
    chosen_uid, chosen_th, chosen_slot_num = "", "", expected_slot
    target_key, prev_key = str(target_id_index), str(target_id_index - 1) if target_id_index > 1 else None
    matched_by_ocr = False

    if target_key in known_ids and known_ids[target_key].get("unique_id"):
        for c in visible_cards:
            if ids_roughly_match(c["unique_id"], known_ids[target_key]["unique_id"], c["th"], known_ids[target_key].get("th", "")):
                chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = c["click_x"], c["click_y"], c["unique_id"], c["th"], c["slot"]
                matched_by_ocr = True
                print(f" [✔] [OCR MEMORY MATCH] Found ID #{target_id_index} at Slot #{chosen_slot_num}!")
                break

    if not matched_by_ocr and prev_key in known_ids and known_ids[prev_key].get("unique_id"):
        for idx, c in enumerate(visible_cards):
            if ids_roughly_match(c["unique_id"], known_ids[prev_key]["unique_id"], c["th"], known_ids[prev_key].get("th", "")):
                if idx + 1 < len(visible_cards):
                    nxt = visible_cards[idx + 1]
                    chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = nxt["click_x"], nxt["click_y"], nxt["unique_id"], nxt["th"], nxt["slot"]
                    matched_by_ocr = True
                    print(f" [✔] [RELATIVE MATCH] Selecting next card below ID #{target_id_index-1} at Slot #{chosen_slot_num}!")
                break

    if not matched_by_ocr:
        for c in visible_cards:
            if c["slot"] == expected_slot and c["is_full"] and (250 <= c["click_y"] <= 920):
                chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = c["click_x"], c["click_y"], c["unique_id"], c["th"], c["slot"]
                break
        
        # Anti-Repeat Guard
        norm_chosen = _normalize_uid_key(chosen_uid)
        if norm_chosen and (norm_chosen == _LAST_OPENED_UID or norm_chosen in _VISITED_IDS_IN_CYCLE):
            print(f" [ANTI-REPEAT GUARD] Slot #{chosen_slot_num} was already visited! Shifting down...")
            for c in visible_cards:
                c_norm = _normalize_uid_key(c["unique_id"])
                if c["slot"] > expected_slot and c["is_full"] and c_norm and (c_norm != _LAST_OPENED_UID) and (c_norm not in _VISITED_IDS_IN_CYCLE):
                    chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = c["click_x"], c["click_y"], c["unique_id"], c["th"], c["slot"]
                    break

    print(f" [SLOT LOCK] Selecting ID #{target_id_index} via Slot #{chosen_slot_num} at ({chosen_click_x}, {chosen_click_y}) [UniqueID='{chosen_uid}']")

    if chosen_uid:
        known_ids[target_key] = {"unique_id": chosen_uid, "th": chosen_th, "scrolls": scrolls_needed, "slot": chosen_slot_num}
        _VISITED_IDS_IN_CYCLE.add(_normalize_uid_key(chosen_uid))
        _LAST_OPENED_UID = _normalize_uid_key(chosen_uid)
    elif target_key in known_ids and known_ids[target_key].get("unique_id"):
        chosen_uid = known_ids[target_key]["unique_id"]
        chosen_th = known_ids[target_key].get("th", "")

    mem["current_id_index"], mem["total_ids"], mem["known_ids"] = target_id_index, total_ids, known_ids
    save_id_memory(mem)

    report_name = f"{chosen_uid} (TH{chosen_th})" if (chosen_uid and chosen_th) else (chosen_uid if chosen_uid else f"ID #{target_id_index}")
    bot_report.set_report_active_id(target_id_index, id_name=report_name, is_switch=True)

    bot_adb.tap(chosen_click_x, chosen_click_y, delay_range=(0.25, 0.40), jitter=3)

    initial_wait = float(ID_SWITCH_A14.get("ID_INITIAL_WAIT_SEC", 3.5))
    print(f" [SMART ID LOAD] Waiting initial {initial_wait:.1f}s before Alternating Home -> Popup Check...")
    load_start_t = time.time()
    bot_adb.smart_sleep(initial_wait, apply_speed=False)

    while True:
        bot_adb.check_pause_point(allow_raise=True)
        chk_img = bot_adb.get_screenshot(force_fresh=True)
        elapsed_load = time.time() - load_start_t

        if bot_popups.is_on_home_page_a14(chk_img):
            print(f" [✔] [HOME DETECTED] Home Page visible at {elapsed_load:.1f}s! Running 1-pass Popup verification...")
            bot_adb.human_sleep(0.40, 0.05)
            post_img = bot_adb.get_screenshot(force_fresh=True)
            if bot_popups.check_welcome_back_chief_a14(post_img) or bot_popups.check_daily_reward_popup(post_img) or bot_popups.check_clan_chat_drawer_a14(post_img):
                bot_adb.human_sleep(0.50, 0.05)
                post_img = bot_adb.get_screenshot(force_fresh=True)
            if bot_popups.is_on_home_page_a14(post_img):
                print(f" [✔] [VILLAGE LOADED] ID #{target_id_index} verified on Home Page in {time.time()-load_start_t:.1f}s!")
                break

        if elapsed_load >= 6.0: bot_popups.check_and_handle_maintenance_break(chk_img)

        popup_acted = False
        if bot_popups.check_welcome_back_chief_a14(chk_img): popup_acted = True
        elif bot_popups.check_daily_reward_popup(chk_img): popup_acted = True
        elif bot_popups.check_wrong_buttons_a14(chk_img, check_clan_chat=True): popup_acted = True

        if popup_acted:
            bot_adb.human_sleep(0.60, 0.06)
            if bot_popups.is_on_home_page_a14(bot_adb.get_screenshot(force_fresh=True)):
                print(f" [✔] [VILLAGE LOADED AFTER POPUP CLEAR] ID #{target_id_index} verified on Home Page in {time.time()-load_start_t:.1f}s!")
                break

        if elapsed_load >= 24.0:
            print(f" [WATCHDOG RECOVERY] {elapsed_load:.0f}s elapsed. Running safe Home Recovery...")
            if bot_popups.ensure_return_to_home_page_a14(): break

        bot_adb.smart_sleep(1.0, apply_speed=False)

    bot_popups.double_click_storage_bars()
    bot_adb.zoom_out_village_a14(passes=2, reason=f"NEW ID #{target_id_index} HOME PAGE")
    sw_dur = time.time() - switch_start_t
    bot_report.record_duration("id_switch", sw_dur)

    print(f" [✔] [ID SWITCH COMPLETE in {sw_dur:.1f}s] Now active on ID #{target_id_index} / {total_ids} [{role_str}] ('{report_name}')!\n")
    return True
