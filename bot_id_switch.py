# bot_id_switch.py
# Flawless Zero-Inertia ID Switcher with Visited-ID Memory & LANCZOS OCR
# (100% Original Bot v8 Logic + V9 Dynamic Integrations)

import os
import json
import time
import re
from PIL import Image, ImageOps
import pytesseract

import bot_config
from bot_coords import ID_SWITCH_A14
import bot_adb
import bot_popups
import bot_report

MEMORY_FILE_PATH = "bot_id_memory.json"

# Tracks IDs opened in the current 1..N cycle so the same ID is NEVER opened twice!
_VISITED_IDS_IN_CYCLE = set()
_LAST_OPENED_UID = ""

# ==========================================
# 1. PERSISTENT ID MEMORY & STATE MANAGER
# ==========================================

def load_id_memory():
    """
    Loads saved Supercell Unique IDs, Town Hall levels, scroll positions, and last active ID index.
    """
    default_mem = {
        "current_id_index": 1,
        "total_ids": 1,
        "known_ids": {}  # Maps str(id_num) -> {"unique_id": str, "th": str, "scrolls": int, "slot": int}
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
    """First 4 IDs are MAIN IDs; 5th to 100th IDs are SECONDARY IDs."""
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
    """Registers the starting ID and its saved Unique ID name in the Progress Report."""
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
# 2. SUPERCELL ID LIST BOX 2X VERIFIER
# ==========================================

def _check_supercell_logo_pixel_fast(img):
    """Fast pixel check for Supercell ID List Box using background & divider x=1118."""
    w, h = img.size
    px_map = img.load()
    lx1, ly1, lx2, ly2 = ID_SWITCH_A14["SUPERCELL_LOGO_BOX"]

    blue_bg_px = 0
    white_txt_px = 0

    for y in range(max(0, ly1 - 8), min(h, ly2 + 8), 2):
        for x in range(max(0, lx1 - 8), min(w, lx2 + 8), 2):
            r, g, b = px_map[x, y]
            if b > 95 and b > r + 25 and b > g + 15:
                blue_bg_px += 1
            elif r > 200 and g > 200 and b > 200 and (max(r, g, b) - min(r, g, b) <= 35):
                white_txt_px += 1

    div_x = ID_SWITCH_A14["DIVIDER_X"]
    left_blue_count = 0
    right_light_count = 0
    for sample_y in [250, 400, 550, 700, 850]:
        if sample_y < h:
            lr, lg, lb = px_map[max(0, div_x - 120), sample_y]
            rr, rg, rb = px_map[min(w - 1, div_x + 120), sample_y]
            if lb > lr + 20 and lb > 60:
                left_blue_count += 1
            if rr > 210 and rg > 210 and rb > 210:
                right_light_count += 1

    divider_valid = (left_blue_count >= 3 and right_light_count >= 3)
    pixel_logo_valid = (blue_bg_px >= 12 and white_txt_px >= 5) or (blue_bg_px >= 35 and divider_valid)
    return pixel_logo_valid, divider_valid, blue_bg_px, white_txt_px

def _check_supercell_logo_once(img):
    pixel_logo_valid, divider_valid, blue_bg_px, white_txt_px = _check_supercell_logo_pixel_fast(img)

    ox1, oy1, ox2, oy2 = ID_SWITCH_A14["SUPERCELL_LOGO_OCR_BOX"]
    crop = img.crop((ox1, oy1, ox2, oy2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    cw, ch = upscaled.size
    src = upscaled.load()

    ocr_matched = False
    ocr_read_str = ""
    for thresh in [185, 165]:
        bw = Image.new('L', (cw, ch), 255)
        dst = bw.load()
        for py in range(ch):
            for px in range(cw):
                r, g, b = src[px, py]
                if r > thresh and g > thresh and b > thresh:
                    dst[px, py] = 0
        padded = ImageOps.expand(bw, border=12, fill=255)
        txt = pytesseract.image_to_string(padded, config='--oem 3 --psm 7').strip()
        if txt:
            ocr_read_str = txt
            clean_t = re.sub(r'[^a-zA-Z]', '', txt).lower()
            if "super" in clean_t or "cell" in clean_t or "sup" in clean_t or clean_t.startswith("s"):
                ocr_matched = True
                break

    is_open = (pixel_logo_valid and divider_valid) or (ocr_matched and (pixel_logo_valid or divider_valid))
    return is_open, ocr_read_str, blue_bg_px, white_txt_px, divider_valid

def verify_supercell_id_list_box_twice(img=None):
    """Re-verifies 2 times whether the bot is inside the Supercell ID List Box."""
    confirmations = 0
    for check_num in range(1, 3):
        cur_img = img if (check_num == 1 and img is not None) else bot_adb.get_screenshot(force_fresh=True)
        ok, ocr_txt, blue_px, white_px, div_ok = _check_supercell_logo_once(cur_img)
        if ok:
            confirmations += 1
            print(f" [✔] [ID LIST VERIFY #{check_num}/2] Supercell ID Box Confirmed (OCR='{ocr_txt}', Blue={blue_px}, White={white_px}, DividerX1118={div_ok})")
        else:
            print(f" [!] [ID LIST VERIFY #{check_num}/2] Not confirmed yet (OCR='{ocr_txt}', Blue={blue_px}, White={white_px}, DividerX1118={div_ok})")
        if check_num == 1:
            bot_adb.human_sleep(0.15, 0.03)

    return confirmations >= 1

# ==========================================
# 3. ID CARD SCANNER & LANCZOS OCR (UNIQUE ID + TOWN HALL)
# ==========================================

def find_visible_coc_id_cards(img):
    w, h = img.size
    px_map = img.load()

    scan_x_points = [1763, 2020, 2110]
    in_card = False
    card_top = 0
    raw_spans = []

    for y in range(160, min(h - 4, 1075), 2):
        white_hits = sum(1 for sx in scan_x_points if px_map[sx, y][0] >= 247 and px_map[sx, y][1] >= 247 and px_map[sx, y][2] >= 247 and (max(px_map[sx, y]) - min(px_map[sx, y]) <= 8))
        is_card_row = (white_hits >= 2)
        if is_card_row and not in_card:
            in_card = True
            card_top = y
        elif not is_card_row and in_card:
            in_card = False
            span_h = y - card_top
            if span_h >= 45:
                raw_spans.append((card_top, y))

    if in_card and (1075 - card_top) >= 45:
        raw_spans.append((card_top, 1075))

    detected_cards = []
    for idx, (y1, y2) in enumerate(raw_spans):
        span_h = y2 - y1
        is_full_card = (175 <= span_h <= 265)
        cy = (y1 + y2) // 2
        safe_cy = max(250, min(920, cy)) if is_full_card else min(h - 15, y1 + 65)
        detected_cards.append({
            "slot": idx + 1, "top": y1, "bottom": y2, "height": span_h,
            "center_y": cy, "click_x": 1763, "click_y": safe_cy, "is_full": is_full_card
        })

    if len(detected_cards) < 2:
        blueprint_tops = [209, 451, 688, 932]
        blueprint_clicks = ID_SWITCH_A14["ID_SLOTS"]
        detected_cards = []
        for i in range(4):
            top_y = blueprint_tops[i]
            bot_y = min(h - 1, top_y + ID_SWITCH_A14["CARD_HEIGHT"])
            detected_cards.append({
                "slot": i + 1, "top": top_y, "bottom": bot_y, "height": bot_y - top_y,
                "center_y": blueprint_clicks[i][1], "click_x": blueprint_clicks[i][0],
                "click_y": blueprint_clicks[i][1], "is_full": (i < 3)
            })

    return detected_cards

def read_supercell_unique_id_from_card(img, card_top):
    w, h = img.size
    ux1, _, ux2, _ = ID_SWITCH_A14["UNIQUE_ID_BOX"]
    uy1 = max(0, card_top + ID_SWITCH_A14["UNIQUE_ID_REL_Y1"] - 3)
    uy2 = min(h, card_top + ID_SWITCH_A14["UNIQUE_ID_REL_Y2"] + 3)

    if uy2 - uy1 < 18: return ""

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
                if r < thresh and g < thresh and b < thresh and (max(r, g, b) - min(r, g, b) <= 45):
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

def read_town_hall_from_card(img, card_top):
    w, h = img.size
    tx1, _, tx2, _ = ID_SWITCH_A14["TOWN_HALL_BOX"]
    ty1 = max(0, card_top + ID_SWITCH_A14["TH_REL_Y1"] - 3)
    ty2 = min(h, card_top + ID_SWITCH_A14["TH_REL_Y2"] + 3)
    if ty2 - ty1 < 14: return ""

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

def is_end_of_id_list_visible(img):
    cards = find_visible_coc_id_cards(img)
    if sum(1 for c in cards if c.get("is_full", False)) >= 3: return False
    w, h = img.size
    crop = img.crop((1350, max(0, h - 380), min(w, 2150), h - 20))
    txt = pytesseract.image_to_string(crop.convert('L'), config='--oem 3 --psm 6').lower()
    return "other ids" in txt or "log in to" in txt or "login to" in txt

def ids_roughly_match(id_a, id_b, th_a="", th_b=""):
    if not id_a or not id_b: return False
    if th_a and th_b and th_a.isdigit() and th_b.isdigit() and int(th_a) != int(th_b): return False
    a, b = _normalize_uid_key(id_a), _normalize_uid_key(id_b)
    if not a or not b: return False
    if a == b: return True
    if len(a) >= 5 and len(b) >= 5:
        if a in b or b in a or a[:5] == b[:5] or a[-5:] == b[-5:]: return True
        if sum(1 for i, ch in enumerate(a[:min(len(a), len(b))]) if ch == b[i]) >= max(5, int(min(len(a), len(b)) * 0.72)): return True
    return False

def scan_visible_cards_with_ocr(img):
    enriched = []
    for c in find_visible_coc_id_cards(img):
        uid, th = "", ""
        if c["top"] + ID_SWITCH_A14["UNIQUE_ID_REL_Y2"] <= img.height - 5:
            uid = read_supercell_unique_id_from_card(img, c["top"])
            if c["top"] + ID_SWITCH_A14["TH_REL_Y2"] <= img.height - 4:
                th = read_town_hall_from_card(img, c["top"])
        c_copy = dict(c)
        c_copy["unique_id"], c_copy["th"] = uid, th
        enriched.append(c_copy)
    return enriched

# ==========================================
# 4. NAVIGATION & ZERO-INERTIA SLOW SMOOTH SCROLLING ENGINE
# ==========================================

def open_supercell_id_list_from_home():
    for attempt in range(1, 4):
        bot_adb.check_pause_point(allow_raise=True)
        print(f"\n [ID SWITCH NAV] Opening Supercell ID List (Attempt #{attempt}/3)...")
        bot_popups.check_wrong_buttons_a14(check_clan_chat=True)

        bot_adb.tap(*ID_SWITCH_A14["PROFILE_BTN"], delay_range=(0.25, 0.40), jitter=3)
        bot_adb.human_sleep(0.55, 0.06)
        bot_adb.tap(*ID_SWITCH_A14["SETTINGS_BTN"], delay_range=(0.25, 0.40), jitter=3)
        bot_adb.human_sleep(0.55, 0.06)
        bot_adb.tap(*ID_SWITCH_A14["SWITCH_ICON_BTN"], delay_range=(0.30, 0.45), jitter=3)
        bot_adb.human_sleep(0.95, 0.10)

        if verify_supercell_id_list_box_twice(): return True

        chk = bot_adb.get_screenshot(force_fresh=True)
        if bot_popups.check_wrong_buttons_a14(chk, check_clan_chat=True) or bot_popups.is_on_home_page_a14(chk):
            continue

        bot_adb.tap(*ID_SWITCH_A14["SWITCH_ICON_BTN"], delay_range=(0.30, 0.45), jitter=3)
        bot_adb.human_sleep(1.0, 0.10)
        if verify_supercell_id_list_box_twice(): return True
        bot_popups.ensure_return_to_home_page_a14()
        bot_adb.human_sleep(0.60, 0.08)
    return False

def perform_smooth_id_list_scroll(scroll_num=1, total_scrolls=1):
    bot_adb.check_pause_point(allow_raise=True)
    sx1, sy1 = ID_SWITCH_A14["SCROLL_START"]
    sx2, sy2 = ID_SWITCH_A14["SCROLL_END"]
    dur = 1050
    print(f" [v] [ID LIST SCROLL {scroll_num}/{total_scrolls}] Controlled Zero-Inertia Scroll ({sx1},{sy1} -> {sx2},{sy2} @ {dur}ms)...")
    bot_adb.swipe(sx1, sy1, sx2, sy2, duration=dur, post_sleep=1.10, apply_speed=False)

def compute_scroll_and_slot_for_id(target_id_index):
    n = max(1, int(target_id_index))
    return (n - 1) // 3, ((n - 1) % 3) + 1

# ==========================================
# 5. MASTER ID SWITCH EXECUTION
# ==========================================

def switch_to_target_id(target_id_index, total_ids, current_id_index=None, max_load_wait=None):
    global _VISITED_IDS_IN_CYCLE, _LAST_OPENED_UID
    switch_start_t = time.time()
    target_id_index, total_ids = int(target_id_index), max(1, min(100, int(total_ids)))

    if total_ids <= 1:
        bot_popups.ensure_return_to_home_page_a14()
        bot_adb.zoom_out_village_a14(passes=2, reason="SINGLE-ID HOME VIEW")
        return True

    target_id_index = 1 if (target_id_index > total_ids or target_id_index < 1) else target_id_index
    if target_id_index == 1: _VISITED_IDS_IN_CYCLE.clear()

    role_str = get_id_role_label(target_id_index)
    mem, known_ids = load_id_memory(), load_id_memory().get("known_ids", {})

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
            bot_popups.ensure_return_to_home_page_a14()
            return False

        scrolls_needed, expected_slot = compute_scroll_and_slot_for_id(target_id_index)
        
        if scrolls_needed > 0:
            for c in scan_visible_cards_with_ocr(bot_adb.get_screenshot()):
                if 1 <= c["slot"] <= 3 and c["unique_id"]:
                    known_ids[str(c["slot"])] = {"unique_id": c["unique_id"], "th": c["th"], "scrolls": 0, "slot": c["slot"]}
            mem["known_ids"] = known_ids
            save_id_memory(mem)

        pre_click_interrupted = False
        for s_i in range(1, scrolls_needed + 1):
            perform_smooth_id_list_scroll(s_i, scrolls_needed)
            if s_i < scrolls_needed and s_i % 3 == 0:
                chk_img = bot_adb.get_screenshot()
                if not _check_supercell_logo_pixel_fast(chk_img)[0]:
                    bot_popups.check_wrong_buttons_a14(chk_img, check_clan_chat=True)
                    pre_click_interrupted = True
                    break
                if is_end_of_id_list_visible(chk_img): break
            elif s_i == scrolls_needed:
                chk_img = bot_adb.get_screenshot(force_fresh=True)
                if not verify_supercell_id_list_box_twice(chk_img):
                    bot_popups.check_wrong_buttons_a14(chk_img, check_clan_chat=True)
                    pre_click_interrupted = True
                    break

        if not pre_click_interrupted: break

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
                chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = c["click_x"], c["click_y"], c["unique_id"], c["th"] or known_ids[target_key].get("th", ""), c["slot"]
                matched_by_ocr = True
                break

    if not matched_by_ocr and prev_key in known_ids and known_ids[prev_key].get("unique_id"):
        for idx, c in enumerate(visible_cards):
            if ids_roughly_match(c["unique_id"], known_ids[prev_key]["unique_id"], c["th"], known_ids[prev_key].get("th", "")):
                if idx + 1 < len(visible_cards):
                    nxt = visible_cards[idx + 1]
                    chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = nxt["click_x"], nxt["click_y"], nxt["unique_id"], nxt["th"], nxt["slot"]
                    matched_by_ocr = True
                break

    if not matched_by_ocr:
        for c in visible_cards:
            if c["slot"] == expected_slot and c["is_full"] and (250 <= c["click_y"] <= 920):
                chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = c["click_x"], c["click_y"], c["unique_id"], c["th"], c["slot"]
                break
        
        norm_chosen = _normalize_uid_key(chosen_uid)
        if norm_chosen and (norm_chosen == _LAST_OPENED_UID or norm_chosen in _VISITED_IDS_IN_CYCLE):
            found_unvisited = False
            for c in visible_cards:
                c_norm = _normalize_uid_key(c["unique_id"])
                if c["slot"] > expected_slot and c["is_full"] and c_norm and (c_norm != _LAST_OPENED_UID) and (c_norm not in _VISITED_IDS_IN_CYCLE):
                    chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num, found_unvisited = c["click_x"], c["click_y"], c["unique_id"], c["th"], c["slot"], True
                    break
            if not found_unvisited and expected_slot < 3 and len(visible_cards) >= (expected_slot + 1):
                nxt_c = visible_cards[expected_slot]
                if nxt_c["is_full"]:
                    chosen_click_x, chosen_click_y, chosen_uid, chosen_th, chosen_slot_num = nxt_c["click_x"], nxt_c["click_y"], nxt_c["unique_id"], nxt_c["th"], nxt_c["slot"]

    if chosen_uid:
        known_ids[target_key] = {"unique_id": chosen_uid, "th": chosen_th, "scrolls": scrolls_needed, "slot": chosen_slot_num}
        _VISITED_IDS_IN_CYCLE.add(_normalize_uid_key(chosen_uid))
        _LAST_OPENED_UID = _normalize_uid_key(chosen_uid)
    elif target_key in known_ids and known_ids[target_key].get("unique_id"):
        chosen_uid, chosen_th = known_ids[target_key]["unique_id"], known_ids[target_key].get("th", "")

    mem["current_id_index"], mem["total_ids"], mem["known_ids"] = target_id_index, total_ids, known_ids
    save_id_memory(mem)

    report_name = f"{chosen_uid} (TH{chosen_th})" if (chosen_uid and chosen_th) else (chosen_uid if chosen_uid else f"ID #{target_id_index}")
    bot_report.set_report_active_id(target_id_index, id_name=report_name, is_switch=True)

    bot_adb.tap(chosen_click_x, chosen_click_y, delay_range=(0.25, 0.40), jitter=3)

    load_start_t = time.time()
    last_watchdog_t = load_start_t
    bot_adb.smart_sleep(float(ID_SWITCH_A14.get("ID_INITIAL_WAIT_SEC", 3.5)), apply_speed=False)

    while True:
        bot_adb.check_pause_point(allow_raise=True)
        chk_img = bot_adb.get_screenshot(force_fresh=True)
        elapsed_load = time.time() - load_start_t

        if bot_popups.is_on_home_page_a14(chk_img):
            bot_adb.human_sleep(0.40, 0.05)
            post_img = bot_adb.get_screenshot(force_fresh=True)
            if bot_popups.check_welcome_back_chief_a14(post_img) or bot_popups.check_daily_reward_popup(post_img) or bot_popups.check_clan_chat_drawer_a14(post_img):
                bot_adb.human_sleep(0.50, 0.05)
                post_img = bot_adb.get_screenshot(force_fresh=True)
            if bot_popups.is_on_home_page_a14(post_img):
                break

        if elapsed_load >= 6.0: bot_popups.check_and_handle_maintenance_break(chk_img)

        popup_acted = False
        if bot_popups.check_welcome_back_chief_a14(chk_img) or bot_popups.check_daily_reward_popup(chk_img) or bot_popups.check_wrong_buttons_a14(chk_img, check_clan_chat=True):
            popup_acted = True

        if popup_acted:
            bot_adb.human_sleep(0.60, 0.06)
            if bot_popups.is_on_home_page_a14(bot_adb.get_screenshot(force_fresh=True)):
                break

        if (time.time() - last_watchdog_t) >= 12.0:
            last_watchdog_t = time.time()
            if _check_supercell_logo_pixel_fast(chk_img)[0] and _check_supercell_logo_pixel_fast(chk_img)[1]:
                bot_adb.tap(chosen_click_x, chosen_click_y, delay_range=(0.25, 0.40), jitter=3)
            elif elapsed_load >= 24.0:
                if bot_popups.ensure_return_to_home_page_a14(): break

        bot_adb.smart_sleep(1.0, apply_speed=False)

    bot_popups.double_click_storage_bars()
    bot_adb.zoom_out_village_a14(passes=2, reason=f"NEW ID #{target_id_index} HOME PAGE")

    sw_dur = time.time() - switch_start_t
    bot_report.record_duration("id_switch", sw_dur)
    return True
