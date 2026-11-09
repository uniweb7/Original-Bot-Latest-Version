# bot_vision.py
# Vision Engine for Clash of Clans AI Bot
# (100% Original Bot v8 LANCZOS OCR & Pixel Checkers + V9 Dynamic Army Scanner)

import re
import os
import time
from PIL import Image, ImageOps
import pytesseract

from bot_coords import CARD_GEOMETRY, KNOWN_BUILDINGS, CONDITION_1_EXCLUDED, UPGRADE_A14, FAST_ATTACK

# Single-thread Tesseract lock to prevent CPU contention
os.environ["OMP_THREAD_LIMIT"] = "1"

LAST_DETECTED_BUILDERS = None
LAST_BUILDER_CHECK_TIME = 0.0

# ==========================================
# 1. CORE PIXEL CHECKERS & RED 'X' SCANNER
# ==========================================

def is_red_x_box_at(img, cx, cy, radius=10):
    w, h = img.size
    px_map = img.load()
    red_count = 0
    white_count = 0
    for dy in range(-radius, radius + 1, 2):
        for dx in range(-radius, radius + 1, 2):
            px = min(max(0, cx + dx), w - 1)
            py = min(max(0, cy + dy), h - 1)
            r, g, b = px_map[px, py]
            if r > 182 and g < 72 and b < 72 and (r > g + 115):
                red_count += 1
            elif r > 215 and g > 215 and b > 215 and (max(r, g, b) - min(r, g, b) <= 25):
                white_count += 1
    return red_count >= 7 and white_count >= 2

def check_card_cost_color_a14(img, card_top, card_bottom):
    """
    RED-FIRST PRIORITY VETO + DIGIT-ONLY COST SCANNER (100% Original v8):
    Scans ONLY the cost digits region to verify if cost is White or Red.
    """
    cx1 = CARD_GEOMETRY["COST_X1"]
    cx2 = min(2252, CARD_GEOMETRY["COST_X2"])
    cy1 = max(0, card_top + 28)
    cy2 = min(img.height - 1, max(cy1 + 14, min(card_bottom - 5, card_top + 74)))

    card_h = max(48, card_bottom - card_top)
    safe_offset_y = max(24, min(36, int(card_h * 0.42)))
    click_x = 2180
    click_y = min(card_bottom - 18, card_top + safe_offset_y)

    px_map = img.load()
    white_px = 0
    red_px = 0

    for sy in range(cy1, cy2, 2):
        for sx in range(cx1, cx2, 2):
            r, g, b = px_map[sx, sy]
            if r > 170 and g < 98 and b < 98 and (r > g + 75):
                red_px += 1
            elif r > 205 and g > 205 and b > 205 and (max(r, g, b) - min(r, g, b) <= 28):
                white_px += 1

    if red_px >= 4:
        return "RED", click_x, click_y
    if white_px >= 6 and red_px <= 1:
        return "WHITE", click_x, click_y
    return "NONE", click_x, click_y

# ==========================================
# 2. UPGRADE CARD TEXT OCR (DUAL-CROP LANCZOS)
# ==========================================

def _ocr_card_box_region(img, x1, y1, x2, y2, thresh=178, psm=7, whitelist=None):
    crop = img.crop((x1, y1, x2, y2))
    upscaled = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    w, h = upscaled.size
    src = upscaled.load()

    bw = Image.new('L', (w, h), 255)
    dst = bw.load()
    ink_count = 0
    for py in range(h):
        for px in range(w):
            r, g, b = src[px, py]
            if r > thresh and g > thresh and b > thresh and (max(r, g, b) - min(r, g, b) <= 40):
                dst[px, py] = 0
                ink_count += 1

    if ink_count < 8:
        return ""
    padded = ImageOps.expand(bw, border=12, fill=255)
    
    cfg = f'--oem 3 --psm {psm}'
    if whitelist:
        cfg += f' -c tessedit_char_whitelist={whitelist}'
        
    return pytesseract.image_to_string(padded, config=cfg).strip()

def read_card_name_a14(img, card_top, card_bottom, thresh=178):
    """Dual-Crop LANCZOS 2x OCR (100% Original v8): Ensures standalone 'Wall' is never missed!"""
    nx1 = CARD_GEOMETRY["NAME_X1"]
    nx2 = CARD_GEOMETRY["NAME_X2"]
    ny1 = max(0, card_top + CARD_GEOMETRY["NAME_DY1"] - 2)
    ny2 = min(img.height, card_top + CARD_GEOMETRY["NAME_DY2"] + 4)

    full_txt = _ocr_card_box_region(img, nx1, ny1, nx2, ny2, thresh=thresh, psm=7)
    clean_full = re.sub(r'[^a-zA-Z0-9]', '', full_txt)
    if len(clean_full) >= 3:
        return full_txt

    short_nx2 = min(nx2, nx1 + 150)
    short_txt = _ocr_card_box_region(img, nx1, ny1, short_nx2, ny2, thresh=thresh, psm=8)
    return short_txt if len(re.sub(r'[^a-zA-Z0-9]', '', short_txt)) > len(clean_full) else full_txt

def is_text_matching_wall(raw_text):
    if not raw_text:
        return False
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', raw_text).lower()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned:
        return False

    non_wall_w_words = ["wizard", "workshop", "warden", "watch", "witch", "weap", "war"]
    if any(nw in cleaned for nw in non_wall_w_words):
        return False

    first_token = cleaned.split()[0]
    wall_regexes = [
        r'^wall', r'^wa[l1i!|]{1,3}$', r'^w[a4o][l1i!|]{1,3}$',
        r'^vv?a[l1i!|]{1,2}$', r'^w[l1i!|]{2,3}$', r'\bwall\b',
        r'\bwalls\b', r'\bwali\b', r'\bwail\b', r'\bwa11\b',
        r'\bwal1\b', r'\bwa1l\b', r'\bwal\b'
    ]
    return any(re.search(pat, first_token) or re.search(pat, cleaned) for pat in wall_regexes)

def verify_card_is_wall_carefully(img, card_top, card_bottom):
    """Enhanced Single-Wall & Multi-Wall Verifier (100% Original v8)"""
    raw_1 = read_card_name_a14(img, card_top, card_bottom, thresh=178)
    if is_text_matching_wall(raw_1):
        return True, raw_1

    cleaned_1 = re.sub(r'[^a-zA-Z0-9\s]', '', raw_1).strip()
    starts_like_wall = cleaned_1.lower().startswith(('w', 'v', 'i', 'l')) or len(cleaned_1) <= 5

    if not starts_like_wall:
        return False, raw_1

    nx1 = CARD_GEOMETRY["NAME_X1"]
    short_nx2 = nx1 + 152
    ny1 = max(0, card_top + CARD_GEOMETRY["NAME_DY1"] - 2)
    ny2 = min(img.height, card_top + CARD_GEOMETRY["NAME_DY2"] + 4)

    for extra_thresh in [162, 190, 174]:
        raw_full = _ocr_card_box_region(img, nx1, ny1, CARD_GEOMETRY["NAME_X2"], ny2, thresh=extra_thresh, psm=7)
        if is_text_matching_wall(raw_full):
            return True, raw_full

        raw_short = _ocr_card_box_region(img, nx1, ny1, short_nx2, ny2, thresh=extra_thresh, psm=8)
        if is_text_matching_wall(raw_short):
            return True, raw_short

    return False, raw_1

def classify_building_name_a14(raw_ocr_text):
    if not raw_ocr_text:
        return "UNKNOWN", ""
    cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', '', raw_ocr_text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    base_name = re.sub(r'\b[xX]\s*\d+.*$', '', cleaned).strip()
    lower = (base_name if base_name else cleaned).lower().strip()
    
    if len(lower) < 2:
        return "UNKNOWN", base_name
    if is_text_matching_wall(lower) or is_text_matching_wall(cleaned):
        return "WALL", "Wall"
    
    for ex in CONDITION_1_EXCLUDED:
        if ex in lower:
            if ex == "archer" and "tower" in lower: continue
            return "EXCLUDED", base_name
            
    for known in KNOWN_BUILDINGS:
        if known in lower:
            return "BUILDING", known.title()
            
    alpha_only = re.sub(r'[^a-zA-Z]', '', lower)
    if len(alpha_only) >= 3:
        return "BUILDING", base_name
    return "UNKNOWN", base_name

def _normalize_card_signature_for_last_page(raw_name):
    if not raw_name:
        return ""
    _, clean_n = classify_building_name_a14(raw_name)
    s = re.sub(r'[^a-zA-Z]', '', clean_n if clean_n else raw_name).lower()
    return s[:10] if len(s) >= 3 else ""

# ==========================================
# 3. BUILDER / FRACTION OCR ENGINE
# ==========================================

def parse_builder_fraction(raw_text):
    if not raw_text:
        return None
    s = raw_text.strip().replace(" ", "")
    s = re.sub(r'^[|Il!i](?=/\d)', '1', s)
    s = re.sub(r'(?<=\d)[|Il!i](?=[56789]\b|10\b)', '/', s)

    if '/' in s:
        parts = s.split('/', 1)
        left = parts[0].strip()
        left = re.sub(r'[|Il!i]', '1', left)
        if not left:
            return None
        digits = re.sub(r'[^0-9]', '', left)
        if digits:
            if digits.endswith("10"): return 10
            val = int(digits[-1])
            if 0 <= val <= 10: return val
        return None

    digits_only = re.sub(r'[^0-9]', '', s)
    if len(digits_only) == 3 and digits_only[1] in ['1', '7'] and digits_only[2] in ['5', '6', '7', '8', '9']:
        return int(digits_only[0])
    if len(digits_only) == 2 and digits_only[1] in ['5', '6', '7', '8', '9']:
        return int(digits_only[0])
    return None

def read_fraction_box_a14(img, box_coords):
    """V9 Generalized Fraction Box Reader (Used for Spells, Pets & Builders)"""
    x1, y1, x2, y2 = box_coords
    w = x2 - x1
    crop = img.crop((x1 - 2, y1 - 2, x2 + 2, y2 + 2))
    large = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS).convert('L')
    cfg = '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789/|Il!'

    for thresh in [180, 168, 192]:
        bw = large.point(lambda p: 0 if p > thresh else 255, '1').convert('L')
        padded = ImageOps.expand(bw, border=14, fill=255)
        txt = pytesseract.image_to_string(padded, config=cfg).strip()
        val = parse_builder_fraction(txt)
        if val is not None:
            return val

    left_crop = img.crop((x1 - 2, y1, x1 + int(w * 0.44), y2))
    l_large = left_crop.resize((left_crop.width * 3, left_crop.height * 3), Image.Resampling.LANCZOS).convert('L')
    l_bw = ImageOps.expand(l_large.point(lambda p: 0 if p > 175 else 255, '1').convert('L'), border=14, fill=255)
    l_txt = pytesseract.image_to_string(l_bw, config='--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789|Il!').strip()
    
    if l_txt in ['|', 'I', 'l', '!']:
        return 1
    clean_d = re.sub(r'[^0-9]', '', l_txt)
    if clean_d:
        return 10 if clean_d.startswith("10") else int(clean_d[0])
    return 0

def read_builder_check_box_a14(img=None):
    global LAST_DETECTED_BUILDERS, LAST_BUILDER_CHECK_TIME
    if img is None:
        import bot_adb
        img = bot_adb.get_screenshot()
        
    val = read_fraction_box_a14(img, UPGRADE_A14["BUILDER_CHECK_BOX"])
    LAST_DETECTED_BUILDERS = val
    LAST_BUILDER_CHECK_TIME = time.time()
    return val

# ==========================================
# 4. BATTLEFIELD & EARLY VICTORY DETECTORS (CRASH FIX: Restored from v8)
# ==========================================

def is_cloud_screen_a14(img):
    w, h = img.size
    px_map = img.load()
    cloud_px = 0
    total_px = 0

    for sy in range(200, min(h - 180, 860), 28):
        for sx in range(350, min(w - 300, 2050), 40):
            r, g, b = px_map[sx, sy]
            total_px += 1
            if r > 175 and g > 175 and b > 165 and (max(r, g, b) - min(r, g, b) <= 38):
                cloud_px += 1

    return total_px > 0 and (cloud_px / float(total_px)) >= 0.55

def is_enemy_battlefield_loaded_a14(img):
    if is_cloud_screen_a14(img):
        return False
        
    # Check if Home Page Green '+' is present (we cannot be on battlefield if we are home)
    import bot_popups
    if bot_popups.is_on_home_page_a14(img):
        return False

    w, h = img.size
    px_map = img.load()
    sx_center, sy_center = FAST_ATTACK["SURRENDER_BTN"]

    red_btn_px = 0
    white_txt_px = 0
    for dy in range(-22, 23, 2):
        for dx in range(-45, 46, 3):
            px = min(max(0, sx_center + dx), w - 1)
            py = min(max(0, sy_center + dy), h - 1)
            r, g, b = px_map[px, py]
            if r > 165 and g < 90 and b < 90:
                red_btn_px += 1
            elif r > 200 and g > 200 and b > 200 and (max(r, g, b) - min(r, g, b) <= 30):
                white_txt_px += 1

    if not (red_btn_px >= 10 and white_txt_px >= 3):
        return False

    bar_bright_px = 0
    for tx in range(470, min(w - 100, 1530), 65):
        r, g, b = px_map[tx, min(h - 10, 985)]
        if (r + g + b) > 140:
            bar_bright_px += 1

    return bar_bright_px >= 4

def is_return_home_victory_button_visible_a14(img):
    w, h = img.size
    px_map = img.load()
    rx, ry = FAST_ATTACK["RETURN_HOME_BTN"]

    green_px = 0
    white_px = 0
    total_px = 0
    for dy in range(-20, 21, 2):
        for dx in range(-60, 61, 4):
            px = min(max(0, rx + dx), w - 1)
            py = min(max(0, ry + dy), h - 1)
            r, g, b = px_map[px, py]
            total_px += 1
            if g > 135 and g > (r + 25) and g > (b + 25):
                green_px += 1
            elif r > 210 and g > 210 and b > 210 and (max(r, g, b) - min(r, g, b) <= 28):
                white_px += 1

    return total_px > 0 and (green_px / float(total_px)) >= 0.30 and white_px >= 4

# ==========================================
# 5. NEW V9 DYNAMIC ARMY CARD SCANNER
# ==========================================

def scan_colorful_army_cards_a14(img, scan_box=(355, 884, 2213, 1071)):
    """
    V9 FEATURE: Scans the army deployment bar for colorful (active) cards.
    Ignores dashed empty slots and grayed-out depleted cards using color saturation.
    Returns a list of center coordinates for all colorful cards.
    """
    w, h = img.size
    px_map = img.load()
    cx1, cy1, cx2, cy2 = scan_box
    
    expected_centers = [456 + (i * 141) for i in range(13)]
    colorful_centers = []
    
    for center_x in expected_centers:
        if center_x > cx2: break
        
        colorful_px = 0
        total_px = 0
        for dy in range(-20, 21, 4):
            for dx in range(-20, 21, 4):
                px = min(max(0, center_x + dx), w - 1)
                py = min(max(0, 980 + dy), h - 1)
                r, g, b = px_map[px, py]
                total_px += 1
                if (max(r, g, b) - min(r, g, b)) > 36 and max(r, g, b) > 110:
                    colorful_px += 1
                    
        if (colorful_px / float(max(1, total_px))) >= 0.35:
            colorful_centers.append((center_x, 980))
            
    return colorful_centers
