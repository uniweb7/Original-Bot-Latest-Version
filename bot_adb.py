# bot_adb.py
# ADB Shell, Screenshot Pipeline, and Touch Control Engine

import os
import io
import gc
import time
import random
import threading
import subprocess
from PIL import Image

import bot_config
from bot_coords import GOLD_STORAGE_BAR

class RestartLoopException(Exception):
    """Raised when bot detects Home Page or Wrong Button during Attack."""
    pass

class BotPausedResumeHomeException(Exception):
    """Raised when bot is paused via 'ZX' and resumed via 'QW'."""
    pass

# Global Pause State for Keyboard Listener
_PAUSE_STATE = {
    "paused": False,
    "resumed_just_now": False,
    "buffer": "",
    "listener_started": False
}
_PAUSE_LOCK = threading.Lock()

_ADB_SHELL_PROC = None
_ADB_LOCK = threading.Lock()
_MONKEY_SCRIPT_READY = False

_SCREENSHOT_CACHE = {
    "img": None,
    "timestamp": 0.0
}

def check_pause_point(allow_raise=True):
    """Checks if user typed 'ZX' to pause the bot."""
    was_paused = False
    while True:
        with _PAUSE_LOCK:
            is_paused = _PAUSE_STATE["paused"]
            resumed_flag = _PAUSE_STATE["resumed_just_now"]
        if is_paused:
            was_paused = True
            time.sleep(0.20)
            continue
        if was_paused or resumed_flag:
            with _PAUSE_LOCK:
                _PAUSE_STATE["resumed_just_now"] = False
            if allow_raise:
                raise BotPausedResumeHomeException("Resumed via QW -> Resetting to Home Page")
        break

def smart_sleep(seconds, apply_speed=True, min_floor=0.08):
    """Sleeps with speed scaling and pause checking."""
    raw_sec = max(0.0, float(seconds))
    if raw_sec <= 0.0:
        check_pause_point(allow_raise=True)
        return
    dur = bot_config.scale_time_by_speed(raw_sec, min_floor=min_floor) if apply_speed else raw_sec
    end_time = time.time() + dur
    while time.time() < end_time:
        check_pause_point(allow_raise=True)
        rem = end_time - time.time()
        if rem <= 0:
            break
        time.sleep(min(0.18, rem))
        check_pause_point(allow_raise=True)

def human_sleep(base_sec, variance=0.04, apply_speed=True, min_floor=0.08):
    check_pause_point(allow_raise=True)
    raw_t = max(0.02, float(base_sec) + random.uniform(-variance, variance))
    smart_sleep(raw_t, apply_speed=apply_speed, min_floor=min_floor)

def _invalidate_screen_cache():
    _SCREENSHOT_CACHE["img"] = None
    _SCREENSHOT_CACHE["timestamp"] = 0.0

def reset_persistent_adb_shell():
    global _ADB_SHELL_PROC
    with _ADB_LOCK:
        if _ADB_SHELL_PROC is not None:
            try:
                _ADB_SHELL_PROC.stdin.close()
                _ADB_SHELL_PROC.terminate()
            except Exception:
                pass
            _ADB_SHELL_PROC = None

def _exec_adb_shell_cmd(cmd_str):
    global _ADB_SHELL_PROC
    _invalidate_screen_cache()
    with _ADB_LOCK:
        try:
            if _ADB_SHELL_PROC is None or _ADB_SHELL_PROC.poll() is not None:
                _ADB_SHELL_PROC = subprocess.Popen(
                    ["adb", "shell"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )
            _ADB_SHELL_PROC.stdin.write(cmd_str + "\n")
            _ADB_SHELL_PROC.stdin.flush()
            return
        except Exception:
            _ADB_SHELL_PROC = None
    try:
        subprocess.run(["adb", "shell", cmd_str], timeout=5)
    except Exception:
        pass

def tap(x, y, delay_range=(0.03, 0.07), jitter=2, check_pause=True, apply_speed=True):
    if check_pause:
        check_pause_point(allow_raise=True)
    jx = int(x) + random.randint(-jitter, jitter)
    jy = int(y) + random.randint(-jitter, jitter)
    _exec_adb_shell_cmd(f"input tap {jx} {jy}")
    if delay_range and delay_range[1] > 0:
        wait_t = random.uniform(*delay_range)
        if apply_speed:
            wait_t = bot_config.scale_time_by_speed(wait_t, min_floor=0.025)
        if check_pause:
            smart_sleep(wait_t, apply_speed=False)
        else:
            time.sleep(wait_t)

def fast_serial_taps(coord_list, rounds=1, jitter=2):
    """Sends multiple serial taps in a single ADB batch command."""
    check_pause_point(allow_raise=True)
    cmds = []
    for _ in range(rounds):
        for (x, y) in coord_list:
            jx = int(x) + random.randint(-jitter, jitter)
            jy = int(y) + random.randint(-jitter, jitter)
            cmds.append(f"input tap {jx} {jy}")
    if cmds:
        _exec_adb_shell_cmd("; ".join(cmds))

def batch_tap_sequence(coord_list, inter_delay=0.04, jitter=2):
    check_pause_point(allow_raise=True)
    cmds = []
    scaled_gap = bot_config.scale_time_by_speed(inter_delay, min_floor=0.025) if inter_delay > 0 else 0.0
    for idx, (x, y) in enumerate(coord_list):
        jx = int(x) + random.randint(-jitter, jitter)
        jy = int(y) + random.randint(-jitter, jitter)
        cmds.append(f"input tap {jx} {jy}")
        if scaled_gap >= 0.08 and idx < len(coord_list) - 1:
            cmds.append(f"sleep {scaled_gap:.2f}")
    if cmds:
        _exec_adb_shell_cmd("; ".join(cmds))
    if 0 < scaled_gap < 0.08:
        smart_sleep(0.04, apply_speed=False)

def swipe(x1, y1, x2, y2, duration=350, post_sleep=0.38, apply_speed=True):
    check_pause_point(allow_raise=True)
    sx1 = int(x1) + random.randint(-3, 3)
    sy1 = int(y1) + random.randint(-3, 3)
    sx2 = int(x2) + random.randint(-3, 3)
    sy2 = int(y2) + random.randint(-3, 3)
    if apply_speed:
        scaled_dur = int(max(220, bot_config.scale_time_by_speed(duration, min_floor=220) + random.randint(-15, 20)))
    else:
        scaled_dur = int(max(220, duration + random.randint(-15, 20)))
    _exec_adb_shell_cmd(f"input swipe {sx1} {sy1} {sx2} {sy2} {scaled_dur}")
    human_sleep(post_sleep, 0.04, apply_speed=apply_speed, min_floor=0.12)

def zoom_out_village_a14(passes=2, reason="HOME PAGE VIEW"):
    """Symmetric 2-Finger Pinch-In Zoom-Out ONLY executed on the Home Page."""
    global _MONKEY_SCRIPT_READY
    check_pause_point(allow_raise=True)
    _invalidate_screen_cache()
    print(f" [HOME ZOOM-OUT] Executing Symmetric 2-Finger Pinch-In ({passes}x) [{reason}]...")

    try:
        if not _MONKEY_SCRIPT_READY:
            mks_content = (
                "type= raw events\n"
                "count= 1\n"
                "speed= 1.0\n"
                "start data >>\n"
                "PinchZoom(400,200,1100,500,2000,880,1300,580,18)\n"
                "UserWait(120)\n"
                "PinchZoom(400,200,1100,500,2000,880,1300,580,18)\n"
            )
            setup_cmd = f"cat << 'EOM' > /data/local/tmp/coc_pinch_out.mks\n{mks_content}EOM\n"
            subprocess.run(["adb", "shell", setup_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            _MONKEY_SCRIPT_READY = True

        subprocess.run(
            ["adb", "shell", "monkey -f /data/local/tmp/coc_pinch_out.mks 1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
    except Exception:
        _MONKEY_SCRIPT_READY = False

    human_sleep(0.20, 0.03)
    tap(*GOLD_STORAGE_BAR, delay_range=(0.04, 0.07), jitter=2)
    _invalidate_screen_cache()

def capture_raw_screenshot_once():
    """Captures a single screenshot via RAM pipe."""
    try:
        proc = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=6
        )
        if proc.returncode == 0 and proc.stdout and len(proc.stdout) > 1024:
            bio = io.BytesIO(proc.stdout)
            loaded_img = Image.open(bio)
            loaded_img.load()
            img = loaded_img.convert("RGB")
            bio.close()
            return img
    except Exception:
        pass

    try:
        if os.path.exists("screen.png"):
            os.remove("screen.png")
        subprocess.run("adb exec-out screencap -p > screen.png", shell=True, timeout=6)
        if os.path.exists("screen.png") and os.path.getsize("screen.png") > 1024:
            return Image.open("screen.png").convert("RGB")
    except Exception:
        pass
    return None

def get_screenshot(check_pause=True, force_fresh=False):
    """In-Memory RAM Screenshot with 0.24s micro-cache."""
    if check_pause:
        check_pause_point(allow_raise=True)

    now = time.time()
    if (not force_fresh) and (_SCREENSHOT_CACHE["img"] is not None) and ((now - _SCREENSHOT_CACHE["timestamp"]) <= 0.24):
        return _SCREENSHOT_CACHE["img"]

    img = capture_raw_screenshot_once()
    if img is None:
        reset_persistent_adb_shell()
        img = capture_raw_screenshot_once()
    
    if img is not None:
        _SCREENSHOT_CACHE["img"] = img
        _SCREENSHOT_CACHE["timestamp"] = time.time()
    
    return img

def clean_ram_garbage():
    _invalidate_screen_cache()
    reset_persistent_adb_shell()
    gc.collect()
