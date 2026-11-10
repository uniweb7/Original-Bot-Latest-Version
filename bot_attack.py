import time
import subprocess
import random
import traceback
import bot_tools
from bot_tools import (
    RestartLoopException,
    BotPausedResumeHomeException,
    FAST_ATTACK,
    tap,
    fast_serial_taps,
    batch_tap_sequence,
    get_screenshot,
    smart_sleep,
    human_sleep,
    check_pause_point,
    check_wrong_buttons_a14,
    check_clan_chat_drawer_a14,
    is_on_home_page_a14,
    check_wrong_and_home_page_a14,
    ensure_return_to_home_page_a14,
    click_gold_storage_3_times,
    record_stat,
    record_duration
)

# Full 45.0s Battle Timer
BATTLE_TIMER_DURATION_SEC = 45.0

# 100% Valid Outer-Grass Perimeter Coordinates (Never hits Red Zone inside wide bases!)
OUTER_GRASS_DEPLOY_POINTS = [
    (195, 495), (210, 520), (225, 545),
    (240, 465), (262, 440), (288, 412),
    (220, 570), (245, 595), (272, 620)
]

# Fast 4-Point Outer Grass for Single-Unit Cards (Siege Machine & Heroes)
HERO_SIEGE_DEPLOY_POINTS = [
    (210, 520), (225, 545), (240, 465), (262, 440)
]

# ==========================================
# 1. CLOUD, BATTLEFIELD & EARLY VICTORY DETECTORS
# ==========================================

def is_cloud_screen_a14(img):
    """
    Detects if the screen is currently covered in white/light-gray/hazy matchmaking clouds
    so the bot NEVER confuses matchmaking clouds with the Home Page or an active battlefield.
    """
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
    """
    Verifies that:
      1. We are NOT in matchmaking clouds.
      2. We are NOT on the Home Page (Green '+' is absent).
      3. The red/white Surrender / End Battle button at (181, 800) is clearly visible.
      4. The bottom troop deployment bar (y = 955..1025) has active card contrast.
    """
    if is_cloud_screen_a14(img):
        return False
    if is_on_home_page_a14(img):
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
    for tx in range(440, min(w - 100, 1650), 60):
        r, g, b = px_map[tx, min(h - 10, 985)]
        if (r + g + b) > 140:
            bar_bright_px += 1

    return bar_bright_px >= 4

def is_return_home_victory_button_visible_a14(img):
    """
    Checks if the green 'Return Home' button at (1222, 918) has appeared on screen.
    """
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

def scan_battlefield_or_restart(stage_name, img=None):
    """
    Checks Wrong Buttons and Home Page Green '+' icon during attack pauses.
    If clouds are still visible after 18s, waits up to 8s extra for clouds to clear.
    """
    check_pause_point(allow_raise=True)
    print(f" [SCAN] [{stage_name}] Checking Battlefield, Wrong Buttons & Home Page status...")
    if img is None:
        img = get_screenshot(force_fresh=True)

    cloud_wait_extra = 0.0
    while is_cloud_screen_a14(img) and cloud_wait_extra < 8.0:
        print(f" [EXTENDED CLOUD GUARD] [{stage_name}] Clouds still visible ({cloud_wait_extra:.1f}s/8.0s extra)... Waiting 1.0s...")
        smart_sleep(1.0, apply_speed=False)
        cloud_wait_extra += 1.0
        img = get_screenshot(force_fresh=True)

    if is_cloud_screen_a14(img):
        reason = "Clouds did not clear after extended 26s wait"
        print(f" [!] [ALERT at {stage_name}] {reason}! Restarting Attack Loop...")
        raise RestartLoopException(reason)

    wrong_found, home_found, latest_img = check_wrong_and_home_page_a14(img, check_clan_chat=False)
    if wrong_found or home_found:
        reason = "Wrong Button detected" if wrong_found else "Still stuck on Home Page (Green '+' visible)"
        print(f" [!] [ALERT at {stage_name}] {reason}! Restarting Attack Loop...")
        raise RestartLoopException(reason)

    return latest_img

def wait_for_enemy_base_load_smart(max_wait_sec=18.0):
    """
    Starts checking for Enemy Battlefield / Clouds just 0.5s after clicking Attack (1980, 972).
    Polls every 0.55s up to 18.0s max.
    """
    min_initial_wait = 0.5
    poll_interval = 0.55
    print(f" [SMART 18s LOAD] Waiting initial {min_initial_wait:.1f}s (Max {max_wait_sec:.0f}s) for Enemy Base...")
    start_t = time.time()
    smart_sleep(min_initial_wait, apply_speed=False)

    while (time.time() - start_t) < max_wait_sec:
        check_pause_point(allow_raise=True)
        img = get_screenshot(force_fresh=True)
        elapsed = time.time() - start_t

        if is_cloud_screen_a14(img):
            print(f" [CLOUDS] Matchmaking clouds visible ({elapsed:.1f}s/{max_wait_sec:.0f}s)... Waiting for base...")
        elif is_enemy_battlefield_loaded_a14(img):
            print(f" [✔] [BASE LOADED EARLY] Enemy Battlefield & Troop Bar confirmed in {elapsed:.1f}s (Saved {max_wait_sec - elapsed:.1f}s)!")
            return True
        else:
            if elapsed >= 2.8:
                wrong_found, home_found, _ = check_wrong_and_home_page_a14(img, check_clan_chat=True)
                if wrong_found or home_found:
                    reason = "Wrong Button / Clan Chat blocked matchmaking" if wrong_found else f"Stuck on Home Page at {elapsed:.1f}s after Attack click"
                    print(f" [!] [FAST MATCHMAKING RETRY] {reason}! Restarting Attack Loop...")
                    raise RestartLoopException(reason)

        rem = max_wait_sec - (time.time() - start_t)
        if rem <= 0:
            break
        smart_sleep(min(poll_interval, rem), apply_speed=False)

    return False

# ==========================================
# 2. CONTINUOUS COLORFUL vs BLACK-&-WHITE CARD SCANNER & FAST ADB BATCH ENGINE
# ==========================================

def _run_fast_adb_cmd_sync(cmd_str, timeout_sec=3.5):
    """
    Executes a batch of ADB tap commands synchronously so the ADB pipe NEVER lags behind
    or overlaps with the next screenshot!
    """
    check_pause_point(allow_raise=True)
    bot_tools._invalidate_screen_cache()
    if not cmd_str:
        return
    try:
        subprocess.run(
            ["adb", "shell", cmd_str],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_sec
        )
    except Exception:
        bot_tools._exec_adb_shell_cmd(cmd_str)

def _analyze_card_window_at_x(px_map, w, h, center_x):
    """
    Analyzes a single card window around center_x (width ~96px, y = 895..1035):
      - Checks if the card is COLORFUL (Undeployed / Active) vs BLACK & WHITE (Depleted / Gray) vs EMPTY (Dashed).
      - Ignores the green Hero health bar at y = 888..914 so a deployed Hero with a grayscale portrait
        is accurately recognized as ALREADY DEPLOYED (Black & White)!
      - Detects if the card has a colored top quantity badge ('x9', 'x11') at y = 895..926.
    """
    x1 = max(0, center_x - 46)
    x2 = min(w - 1, center_x + 46)

    body_colorful_px = 0
    body_total_px = 0
    top_badge_colorful_px = 0
    top_badge_white_px = 0

    # 1. Scan Top Header Badge (y = 896..926) for Troop/Spell colored bar + white 'xN' text
    for sy in range(896, min(h - 1, 926), 3):
        for sx in range(x1 + 6, x2 - 6, 4):
            r, g, b = px_map[sx, sy]
            sat = max(r, g, b) - min(r, g, b)
            # Ignore pure green Hero HP bar (g >> r and g >> b)
            if g > 135 and g > r + 30 and g > b + 30:
                continue
            if sat >= 26 and max(r, g, b) >= 95:
                top_badge_colorful_px += 1
            elif r > 210 and g > 210 and b > 210 and sat <= 25:
                top_badge_white_px += 1

    # 2. Scan Main Portrait Body (y = 932..1032) — completely below any Hero HP bar!
    for sy in range(932, min(h - 1, 1032), 4):
        for sx in range(x1 + 4, x2 - 4, 4):
            r, g, b = px_map[sx, sy]
            body_total_px += 1
            sat = max(r, g, b) - min(r, g, b)
            if sat >= 26 and max(r, g, b) >= 88:
                body_colorful_px += 1

    body_color_ratio = (body_colorful_px / float(max(1, body_total_px)))
    has_top_xn_badge = (top_badge_colorful_px >= 10 and top_badge_white_px >= 3)

    # A card is active/colorful if its body portrait has color OR its top badge is brightly colored (like Spell/P.E.K.K.A)
    is_colorful = (body_color_ratio >= 0.16) or (has_top_xn_badge and body_color_ratio >= 0.08)
    return is_colorful, has_top_xn_badge, body_color_ratio

def scan_all_colorful_cards_classified_a14(img=None):
    """
    Continuously scans across (355, 884) to (2213, 1071) to find EVERY colorful card on screen:
      - Never misses shifted cards or Spell cards with bright white bottle centers!
      - Automatically classifies each colorful card into:
          * 'SPELL' (Rightmost cards with top badge / x >= 1465)
          * 'TROOP' (Leftmost multi-unit cards at x < 820 or with top 'xN' badge before Heroes)
          * 'HERO_OR_SIEGE' (Single-unit middle cards at 820 <= x < 1465 without top 'xN' badge)
    Returns (spells_list, troops_list, heroes_siege_list, all_centers_list).
    """
    if img is None:
        img = get_screenshot(force_fresh=True)

    w, h = img.size
    px_map = img.load()
    cx1, cy1, cx2, cy2 = FAST_ATTACK["ARMY_CARD_SCAN_BOX"]

    # Step 1: Scan horizontal columns every 4px from x=365 to x=2190
    active_cols = []
    for x in range(max(365, cx1), min(w - 10, cx2), 4):
        col_color_hits = 0
        for y in range(898, min(h - 10, 1034), 4):
            r, g, b = px_map[x, y]
            # Skip Hero green health bar at top (y <= 914)
            if y <= 914 and (g > 135 and g > r + 28 and g > b + 28):
                continue
            sat = max(r, g, b) - min(r, g, b)
            if sat >= 25 and max(r, g, b) >= 88:
                col_color_hits += 1
        if col_color_hits >= 5:
            active_cols.append(x)

    # Step 2: Group active columns into contiguous card spans (bridging up to 24px internal gaps like white spell bottles)
    spans = []
    if active_cols:
        seg_start = active_cols[0]
        seg_prev = active_cols[0]
        for x in active_cols[1:]:
            if (x - seg_prev) <= 24:
                seg_prev = x
            else:
                if (seg_prev - seg_start) >= 44:
                    spans.append((seg_start, seg_prev))
                seg_start = x
                seg_prev = x
        if (seg_prev - seg_start) >= 44:
            spans.append((seg_start, seg_prev))

    # Step 3: Split wide spans (adjacent cards touching) into individual ~122px card centers
    candidate_centers = []
    for (s_x1, s_x2) in spans:
        span_w = s_x2 - s_x1
        if span_w <= 148:
            candidate_centers.append((s_x1 + s_x2) // 2)
        else:
            n_cards = max(2, int(round(span_w / 124.0)))
            step_w = span_w / float(n_cards)
            for i in range(n_cards):
                c_x = int(round(s_x1 + (i + 0.5) * step_w))
                candidate_centers.append(c_x)

    # Step 4: Verify each candidate window & classify into SPELL, TROOP, or HERO_OR_SIEGE
    verified_cards = []
    for c_x in candidate_centers:
        # Avoid duplicate centers within 65px
        if any(abs(c_x - prev_x) < 65 for (prev_x, _, _) in verified_cards):
            continue
        is_col, has_badge, ratio = _analyze_card_window_at_x(px_map, w, h, c_x)
        if is_col:
            verified_cards.append((c_x, has_badge, ratio))

    spells = []
    troops = []
    heroes_siege = []
    all_centers = []

    for idx, (c_x, has_badge, ratio) in enumerate(verified_cards):
        coord = (c_x, 980)
        all_centers.append(coord)

        # Classification Rule:
        # 1. Any colorful card at x >= 1465 is a SPELL card (like Card 9 'x11' at x~1580 in the user's screenshot).
        # 2. Or if a card is at x >= 1150, is one of the rightmost 2 cards, and has a top 'xN' colored badge -> SPELL card.
        # 3. Cards on the left (x < 820) or with top 'xN' badge at x < 1150 -> TROOP card (multi-unit).
        # 4. Cards in the middle (820 <= x < 1465) without top 'xN' badge -> HERO or SIEGE (single-unit).
        is_rightmost_two = (idx >= max(0, len(verified_cards) - 2))
        if c_x >= 1465 or (c_x >= 1150 and is_rightmost_two and has_badge):
            spells.append(coord)
        elif c_x < 820 or (has_badge and c_x < 1150):
            troops.append(coord)
        else:
            heroes_siege.append(coord)

    return spells, troops, heroes_siege, all_centers

def _build_tap_cmd_list(select_coord, deploy_points, rounds=1, jitter=3):
    """Builds a fast ADB shell command string that selects a card and taps deploy_points."""
    cmds = []
    sx = int(select_coord[0]) + random.randint(-2, 2)
    sy = int(select_coord[1]) + random.randint(-2, 2)
    cmds.append(f"input tap {sx} {sy}")
    for _ in range(rounds):
        for (px, py) in deploy_points:
            jx = int(px) + random.randint(-jitter, jitter)
            jy = int(py) + random.randint(-jitter, jitter)
            cmds.append(f"input tap {jx} {jy}")
    return cmds

def deploy_all_cards_under_10s_until_black_and_white():
    """
    MASTER ULTRA-FAST DEPLOYMENT ENGINE (Completes in ~6 to 9.5 Seconds!):
      1. PASS #1 (SPELLS FIRST -> THEN TROOPS -> THEN SIEGE & HEROES):
         - Selects & deploys all Spell cards FIRST on SPELL_DEPLOY_LIST (2 full rounds = 22 taps per spell card).
         - Selects & deploys all Troop cards on 100% valid OUTER_GRASS_DEPLOY_POINTS (4 rounds = 36 troops per card).
         - Selects & deploys Siege Machine + Hero cards on HERO_SIEGE_DEPLOY_POINTS (1 round = 4 taps each, saving 12+ seconds!).
      2. PASS #2 & PASS #3 (BLACK & WHITE VERIFICATION LOOP):
         - Takes a fresh screenshot immediately after Pass #1.
         - Checks if ANY Spell card or Troop card or Hero card is STILL COLORFUL (not yet Black & White / x0).
         - Fires targeted fast bursts on ONLY the remaining colorful cards until every card turns Black & White!
    Returns (total_deployed_cards, remembered_hero_coords).
    """
    deploy_start_t = time.time()
    remembered_heroes = []
    total_initial_cards = 0

    for pass_no in range(1, 4):
        check_pause_point(allow_raise=True)
        elapsed_so_far = time.time() - deploy_start_t
        if pass_no > 1 and elapsed_so_far >= 10.5:
            break

        img = get_screenshot(force_fresh=True)
        spells, troops, heroes_siege, all_cards = scan_all_colorful_cards_classified_a14(img)

        if pass_no == 1:
            total_initial_cards = len(all_cards)
            remembered_heroes = list(heroes_siege)
            print(f" [SCAN PASS #1] Detected {len(all_cards)} Colorful Cards -> Spells={len(spells)} | Troops={len(troops)} | Siege/Heroes={len(heroes_siege)}")
            if spells:
                print(f"   -> Spell Card Coords     : {spells}")
            if troops:
                print(f"   -> Troop Card Coords     : {troops}")
            if heroes_siege:
                print(f"   -> Siege/Hero Card Coords: {heroes_siege}")
        else:
            if not spells and not troops and not heroes_siege:
                print(f" [✔] [BLACK & WHITE VERIFIED on Pass #{pass_no}] All Spell, Troop, Siege & Hero cards are now Black & White (0 colorful left) in {elapsed_so_far:.1f}s!")
                break
            print(f" [RE-VERIFY PASS #{pass_no} at {elapsed_so_far:.1f}s] Remaining Colorful Cards -> Spells={len(spells)} | Troops={len(troops)} | Heroes/Siege={len(heroes_siege)}")

        # ----------------------------------------------------------
        # A. DEPLOY SPELL CARDS FIRST (Rightmost Colorful Cards)
        # ----------------------------------------------------------
        if spells:
            spell_cmds = []
            spell_rounds = 2 if pass_no == 1 else 2
            for sp_coord in spells:
                print(f" [⚡ SPELL DEPLOY] Selecting Spell Card at {sp_coord} -> Deploying {spell_rounds}x on Enemy Base...")
                spell_cmds.extend(_build_tap_cmd_list(sp_coord, FAST_ATTACK["SPELL_DEPLOY_LIST"], rounds=spell_rounds, jitter=4))
            _run_fast_adb_cmd_sync("; ".join(spell_cmds), timeout_sec=3.5)

        # ----------------------------------------------------------
        # B. DEPLOY MULTI-UNIT TROOP CARDS ON 100% VALID OUTER GRASS
        # ----------------------------------------------------------
        if troops:
            troop_rounds = 4 if pass_no == 1 else 3
            for tr_coord in troops:
                print(f" [⚔ TROOP DEPLOY] Selecting Troop Card at {tr_coord} -> Deploying {troop_rounds}x9 ({troop_rounds*9} taps) on Outer Grass...")
                tr_cmds = _build_tap_cmd_list(tr_coord, OUTER_GRASS_DEPLOY_POINTS, rounds=troop_rounds, jitter=3)
                _run_fast_adb_cmd_sync("; ".join(tr_cmds), timeout_sec=3.2)

        # ----------------------------------------------------------
        # C. DEPLOY SINGLE-UNIT SIEGE & HERO CARDS (FAST 4-TAP BURST)
        # ----------------------------------------------------------
        if heroes_siege:
            hs_cmds = []
            for hs_coord in heroes_siege:
                if hs_coord not in remembered_heroes:
                    remembered_heroes.append(hs_coord)
                print(f" [👑 HERO/SIEGE DEPLOY] Selecting Card at {hs_coord} -> Deploying on Outer Grass...")
                hs_cmds.extend(_build_tap_cmd_list(hs_coord, HERO_SIEGE_DEPLOY_POINTS, rounds=1, jitter=3))
            _run_fast_adb_cmd_sync("; ".join(hs_cmds), timeout_sec=3.0)

        smart_sleep(0.18, apply_speed=False)

    return total_initial_cards, remembered_heroes

def _fallback_fixed_deploy_sequence():
    """Fallback deployment if 0 cards were detected on first pass."""
    print(" [FALLBACK DEPLOY] Running fallback Spell + Troop + Hero deployment...")
    sp_cmds = _build_tap_cmd_list(FAST_ATTACK["SPELL_SELECT"], FAST_ATTACK["SPELL_DEPLOY_LIST"], rounds=2, jitter=3)
    _run_fast_adb_cmd_sync("; ".join(sp_cmds), timeout_sec=3.0)

    for key in ["ARMY_1_SELECT", "ARMY_2_SELECT"]:
        tr_cmds = _build_tap_cmd_list(FAST_ATTACK[key], OUTER_GRASS_DEPLOY_POINTS, rounds=3, jitter=3)
        _run_fast_adb_cmd_sync("; ".join(tr_cmds), timeout_sec=3.0)

    hs_cmds = []
    for key in ["SIEGE_SELECT", "HERO_1_SELECT", "HERO_2_SELECT", "HERO_3_SELECT", "HERO_4_SELECT"]:
        hs_cmds.extend(_build_tap_cmd_list(FAST_ATTACK[key], HERO_SIEGE_DEPLOY_POINTS, rounds=1, jitter=3))
    _run_fast_adb_cmd_sync("; ".join(hs_cmds), timeout_sec=3.0)

# ==========================================
# 3. MASTER FAST ATTACK EXECUTION (<10s DEPLOY + B&W VERIFY + HERO ABILITIES + EARLY 3-STAR)
# ==========================================

def execute_attack(is_first_attack=True):
    for attempt in range(1, 4):
        atk_attempt_start_t = time.time()
        try:
            check_pause_point(allow_raise=True)
            print("\n======================================================================")
            print(f" || [FAST ATTACK LOOP - 45s TIMER] - ATTEMPT #{attempt}/3 ||")
            print("======================================================================")

            # 1. Home Page: 0.6s Wait + Clan Chat & Wrong Button Check + Single 3x Gold Storage Click
            print(" [0.6s] Checking Home Page, Clan Chat Drawer & clicking Gold Storage 3x...")
            smart_sleep(0.60, apply_speed=True)
            check_wrong_buttons_a14(check_clan_chat=True)
            click_gold_storage_3_times()

            # 2. Matchmaking (0.20s -> Battle -> 0.35s -> Find Match -> 0.65s -> Attack)
            print(" [0.20s] Clicking Battle Button (182, 961)...")
            smart_sleep(0.20, apply_speed=True)
            tap(*FAST_ATTACK["BATTLE_BTN"], delay_range=(0.0, 0.0), jitter=3)

            print(" [0.35s] Waiting 0.35s -> Clicking Find Match (364, 808)...")
            smart_sleep(0.35, apply_speed=True)
            tap(*FAST_ATTACK["FIND_MATCH_BTN"], delay_range=(0.0, 0.0), jitter=3)

            print(" [0.65s] Waiting 0.65s -> Clicking Attack Button (1980, 972)...")
            smart_sleep(0.65, apply_speed=True)
            tap(*FAST_ATTACK["ATTACK_BTN"], delay_range=(0.0, 0.0), jitter=3)

            # 3. Smart Enemy Base Load (Starts checking at 0.5s!)
            loaded_early = wait_for_enemy_base_load_smart(max_wait_sec=18.0)
            if not loaded_early:
                scan_battlefield_or_restart("Post-18s Base Load Check")

            # ==================================================================
            # PHASE 1: SPELLS FIRST + TROOPS + HEROES & BLACK-&-WHITE VERIFICATION (<10s)
            # ==================================================================
            print(" [FAST <10s DEPLOY] Deploying Spells First -> Troops -> Heroes until cards turn Black & White...")
            spell_select_timer = time.time()

            cards_count, hero_coords = deploy_all_cards_under_10s_until_black_and_white()
            if cards_count == 0:
                _fallback_fixed_deploy_sequence()

            deploy_elapsed = time.time() - spell_select_timer
            print(f" [✔] [DEPLOYMENT FINISHED in {deploy_elapsed:.2f}s] Waiting 3.5s before triggering Hero Abilities...")

            # ==================================================================
            # PHASE 2: ACTIVATE HERO ABILITIES (SKIPPING SIEGE MACHINE)
            # ==================================================================
            smart_sleep(3.5, apply_speed=False)

            ability_targets = hero_coords[-4:] if len(hero_coords) >= 2 else [
                FAST_ATTACK["HERO_1_SELECT"],
                FAST_ATTACK["HERO_2_SELECT"],
                FAST_ATTACK["HERO_3_SELECT"],
                FAST_ATTACK["HERO_4_SELECT"]
            ]
            print(f" [HERO ABILITIES] Activating Hero Abilities at {ability_targets}...")
            batch_tap_sequence(ability_targets, inter_delay=0.06, jitter=2)

            post_ability_img = get_screenshot(force_fresh=True)
            battle_ended_early = False
            if is_return_home_victory_button_visible_a14(post_ability_img):
                print(" [✔] [INSTANT VICTORY] Return Home button (1222, 918) already visible!")
                battle_ended_early = True
            else:
                scan_battlefield_or_restart("Post-Hero-Ability Check", img=post_ability_img)

            # ==================================================================
            # PHASE 3: 45s BATTLE TIMER WITH 8s BLACK-&-WHITE SWEEP & EARLY 3-STAR EXIT
            # ==================================================================
            last_sweep_t = time.time()

            while not battle_ended_early:
                check_pause_point(allow_raise=True)
                elapsed_since_spell = time.time() - spell_select_timer
                rem_wait = BATTLE_TIMER_DURATION_SEC - elapsed_since_spell
                if rem_wait <= 0:
                    break

                b_img = get_screenshot(force_fresh=True)

                if is_return_home_victory_button_visible_a14(b_img):
                    print(f" [✔] [EARLY BATTLE END] Return Home button (1222, 918) detected at {elapsed_since_spell:.1f}s! Skipping Surrender...")
                    battle_ended_early = True
                    break

                # Every 8 seconds, check if any Spell or Troop card is still colorful and deploy it immediately!
                if (time.time() - last_sweep_t) >= 8.0:
                    last_sweep_t = time.time()
                    rem_spells, rem_troops, rem_hs, _ = scan_all_colorful_cards_classified_a14(b_img)
                    if rem_spells or rem_troops or rem_hs:
                        print(f" [8s CLEANUP SWEEP] Found remaining colorful cards (Spells={len(rem_spells)}, Troops={len(rem_troops)}, Hero/Siege={len(rem_hs)}) -> Deploying...")
                        sweep_cmds = []
                        for sp_c in rem_spells:
                            sweep_cmds.extend(_build_tap_cmd_list(sp_c, FAST_ATTACK["SPELL_DEPLOY_LIST"], rounds=2, jitter=4))
                        for tr_c in rem_troops:
                            sweep_cmds.extend(_build_tap_cmd_list(tr_c, OUTER_GRASS_DEPLOY_POINTS, rounds=3, jitter=3))
                        for hs_c in rem_hs:
                            sweep_cmds.extend(_build_tap_cmd_list(hs_c, HERO_SIEGE_DEPLOY_POINTS, rounds=1, jitter=3))
                        _run_fast_adb_cmd_sync("; ".join(sweep_cmds), timeout_sec=3.5)

                chunk = min(2.5 if elapsed_since_spell >= 18.0 else 3.5, rem_wait)
                print(f" [45s TIMER] {rem_wait:.1f}s remaining in 45s Battle Timer...")
                smart_sleep(chunk, apply_speed=False)

            # ==================================================================
            # PHASE 4: FIXED RETURN HOME SEQUENCE (4.2s RELIABLE SEQUENCE)
            # ==================================================================
            if not battle_ended_early:
                print(" [SURRENDER] Clicking Surrender Button (181, 800) 3 times...")
                batch_tap_sequence([FAST_ATTACK["SURRENDER_BTN"]] * 3, inter_delay=0.08, jitter=3)

                print(" [0.6s] Waiting 0.6s -> Clicking Okay Button (1419, 701)...")
                smart_sleep(0.60, apply_speed=False)
                tap(*FAST_ATTACK["OKAY_BTN"], delay_range=(0.08, 0.14), jitter=3, apply_speed=False)

                print(" [2.2s GAP] Waiting 2.2 seconds after Okay for Return Home button to appear...")
                smart_sleep(2.20, apply_speed=False)

            print(" [RETURN HOME #1/2] Clicking Return Home Button (1222, 918) [1st Click]...")
            tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.05, 0.08), jitter=3, apply_speed=False)
            print(" [1.0s GAP] Waiting 1.0 second before 2nd Return Home click...")
            smart_sleep(1.00, apply_speed=False)

            print(" [RETURN HOME #2/2] Clicking Return Home Button (1222, 918) [2nd Click]...")
            tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.05, 0.08), jitter=3, apply_speed=False)
            print(" [1.0s SETTLE] Waiting 1.0 second to settle on Home Page...")
            smart_sleep(1.00, apply_speed=False)

            # Strictly verify we returned to Home Page before marking Attack as Successful!
            ret_img = get_screenshot(force_fresh=True)
            _, home_verified, ret_img = check_wrong_and_home_page_a14(ret_img, check_clan_chat=True)

            if not home_verified:
                print(" [!] [RETURN HOME GUARD] Home Page Green '+' abhi nahi dikha! Running extra Return Home tap & recovery...")
                tap(*FAST_ATTACK["RETURN_HOME_BTN"], delay_range=(0.10, 0.18), jitter=3, apply_speed=False)
                smart_sleep(1.00, apply_speed=False)
                home_verified = ensure_return_to_home_page_a14()

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
            ensure_return_to_home_page_a14()
            smart_sleep(0.40, apply_speed=True)
            continue
        except Exception:
            record_stat("attacks_failed", 1)
            print("\n[! ERROR!] Fast Attack Loop me error aayi:")
            traceback.print_exc()
            ensure_return_to_home_page_a14()
            return False

    print(" [!] [3 ATTEMPTS FAILED] Running Full In-Game Home Recovery...")
    ensure_return_to_home_page_a14()
    return False
