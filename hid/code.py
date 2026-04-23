
import time
import json
import os
import usb_hid

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

# ============================================================
# CircuitPython HID runner with fixed-delay speed sweep
# - Reads JSON or TXT event list
# - Runs the same dataset repeatedly at descending fixed speeds
# - No jitter
# - Supports TEXT, KEY, COMBO, DELAY
# ============================================================

# ----------------------------
# Main config
# ----------------------------
INPUT_PATH = "/safe_hid_starter_dataset.json"   # or "/safe_hid_starter_wordlist.txt"
USE_SAMPLE_SEQUENCES_IF_JSON = False            # False = run whole dataset vocabulary; True = sample_sequences only
INITIAL_DELAY_S = 3                             # wait after USB enumeration
INTER_RUN_DELAY_S = 10                          # cooldown between speed profiles
COMBO_HOLD_MS = 50                              # how long a combo is held before release

# Fixed speed sweep: 240 -> 0 by 20
SPEED_PROFILES_MS = [240, 220, 200, 180, 160, 140, 120, 100, 80, 60, 40, 20, 0]

# Optional log path on CIRCUITPY drive
LOG_PATH = "/speed_sweep_log.csv"

# ----------------------------
# HID setup
# ----------------------------
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)

# ----------------------------
# Key map
# ----------------------------
KEYMAP = {
    "CTRL": Keycode.CONTROL,
    "CONTROL": Keycode.CONTROL,
    "SHIFT": Keycode.SHIFT,
    "ALT": Keycode.ALT,
    "GUI": Keycode.GUI,
    "WINDOWS": Keycode.GUI,
    "COMMAND": Keycode.GUI,

    "ENTER": Keycode.ENTER,
    "RETURN": Keycode.ENTER,
    "TAB": Keycode.TAB,
    "SPACE": Keycode.SPACEBAR,
    "SPACEBAR": Keycode.SPACEBAR,
    "ESC": Keycode.ESCAPE,
    "ESCAPE": Keycode.ESCAPE,
    "BACKSPACE": Keycode.BACKSPACE,
    "DELETE": Keycode.DELETE,
    "DEL": Keycode.DELETE,
    "INSERT": Keycode.INSERT,
    "HOME": Keycode.HOME,
    "END": Keycode.END,
    "PAGEUP": Keycode.PAGE_UP,
    "PAGE_UP": Keycode.PAGE_UP,
    "PAGEDOWN": Keycode.PAGE_DOWN,
    "PAGE_DOWN": Keycode.PAGE_DOWN,
    "UP": Keycode.UP_ARROW,
    "UPARROW": Keycode.UP_ARROW,
    "UP_ARROW": Keycode.UP_ARROW,
    "DOWN": Keycode.DOWN_ARROW,
    "DOWNARROW": Keycode.DOWN_ARROW,
    "DOWN_ARROW": Keycode.DOWN_ARROW,
    "LEFT": Keycode.LEFT_ARROW,
    "LEFTARROW": Keycode.LEFT_ARROW,
    "LEFT_ARROW": Keycode.LEFT_ARROW,
    "RIGHT": Keycode.RIGHT_ARROW,
    "RIGHTARROW": Keycode.RIGHT_ARROW,
    "RIGHT_ARROW": Keycode.RIGHT_ARROW,
    "CAPSLOCK": Keycode.CAPS_LOCK,
    "CAPS_LOCK": Keycode.CAPS_LOCK,
    "PRINTSCREEN": Keycode.PRINT_SCREEN,
    "PRINT_SCREEN": Keycode.PRINT_SCREEN,
    "PAUSE": Keycode.PAUSE,

    "PLUS": Keycode.EQUALS,
    "MINUS": Keycode.MINUS,
    "EQUALS": Keycode.EQUALS,
    "ZERO": Keycode.ZERO,
    "ONE": Keycode.ONE,
    "TWO": Keycode.TWO,
    "THREE": Keycode.THREE,
    "FOUR": Keycode.FOUR,
    "FIVE": Keycode.FIVE,
    "SIX": Keycode.SIX,
    "SEVEN": Keycode.SEVEN,
    "EIGHT": Keycode.EIGHT,
    "NINE": Keycode.NINE,
}

for name in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEYMAP[name] = getattr(Keycode, name)

KEYMAP["0"] = Keycode.ZERO
KEYMAP["1"] = Keycode.ONE
KEYMAP["2"] = Keycode.TWO
KEYMAP["3"] = Keycode.THREE
KEYMAP["4"] = Keycode.FOUR
KEYMAP["5"] = Keycode.FIVE
KEYMAP["6"] = Keycode.SIX
KEYMAP["7"] = Keycode.SEVEN
KEYMAP["8"] = Keycode.EIGHT
KEYMAP["9"] = Keycode.NINE

for i in range(1, 13):
    KEYMAP["F{}".format(i)] = getattr(Keycode, "F{}".format(i))

# ----------------------------
# Helpers
# ----------------------------
def sleep_ms(ms):
    time.sleep(ms / 1000.0)

def normalize_token(token):
    return token.strip().upper()

def get_keycode(token):
    token = normalize_token(token)
    if token not in KEYMAP:
        raise ValueError("Unsupported key token: {}".format(token))
    return KEYMAP[token]

def ensure_log_header():
    try:
        need_header = False
        root_files = os.listdir("/")
        if LOG_PATH.strip("/") not in root_files:
            need_header = True
        with open(LOG_PATH, "a") as f:
            if need_header:
                f.write("monotonic_s,event,profile_ms,note\n")
    except Exception:
        pass

def log_event(event, profile_ms, note=""):
    try:
        with open(LOG_PATH, "a") as f:
            f.write("{:.3f},{},{},{}\n".format(time.monotonic(), event, profile_ms, note.replace(",", ";")))
    except Exception:
        pass

def type_text(text, char_delay_ms):
    for ch in text:
        layout.write(ch)
        if char_delay_ms > 0:
            sleep_ms(char_delay_ms)

def send_key(key_name):
    kbd.send(get_keycode(key_name))

def send_combo(keys):
    codes = [get_keycode(k) for k in keys]
    kbd.press(*codes)
    sleep_ms(COMBO_HOLD_MS)
    kbd.release_all()

# ----------------------------
# Event loading
# ----------------------------
def txt_line_to_event(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if line.startswith("TEXT:"):
        return {"type": "text", "value": line[len("TEXT:"):].strip()}

    if line.startswith("KEY:"):
        return {"type": "key", "key": line[len("KEY:"):].strip()}

    if line.startswith("COMBO:"):
        return {"type": "combo", "keys": line[len("COMBO:"):].strip().split()}

    if line.startswith("DELAY:"):
        return {"type": "delay", "ms": int(line[len("DELAY:"):].strip())}

    raise ValueError("Unsupported TXT line format: {}".format(line))

def load_events_from_txt(path):
    events = []
    with open(path, "r") as f:
        for raw_line in f:
            event = txt_line_to_event(raw_line)
            if event is not None:
                events.append(event)
    return events

def load_events_from_json(path):
    with open(path, "r") as f:
        data = json.load(f)

    # Raw event list
    if isinstance(data, list):
        return data

    # Sequence container
    if isinstance(data, dict):
        if USE_SAMPLE_SEQUENCES_IF_JSON and "sample_sequences" in data:
            events = []
            for seq in data["sample_sequences"]:
                for event in seq.get("events", []):
                    events.append(event)
            return events

        if "events" in data:
            return data["events"]

        # Vocabulary-style dataset -> convert to event list
        events = []
        for word in data.get("words", []):
            events.append({"type": "text", "value": word})

        for phrase in data.get("phrases", []):
            events.append({"type": "text", "value": phrase})

        for key in data.get("single_keys", []):
            events.append({"type": "key", "key": key})

        for combo in data.get("combos", []):
            if isinstance(combo, dict) and "keys" in combo:
                events.append({"type": "combo", "keys": combo["keys"]})

        return events

    raise ValueError("Unsupported JSON structure")

def load_events(path):
    lower = path.lower()
    if lower.endswith(".txt"):
        return load_events_from_txt(path)
    if lower.endswith(".json"):
        return load_events_from_json(path)
    raise ValueError("Unsupported input file type: {}".format(path))

# ----------------------------
# Event execution
# ----------------------------
def run_event(event, fixed_delay_ms):
    etype = event.get("type", "").lower()

    if etype == "text":
        type_text(event.get("value", ""), fixed_delay_ms)

    elif etype == "key":
        send_key(event["key"])
        if fixed_delay_ms > 0:
            sleep_ms(fixed_delay_ms)

    elif etype == "combo":
        send_combo(event["keys"])
        if fixed_delay_ms > 0:
            sleep_ms(fixed_delay_ms)

    elif etype == "delay":
        sleep_ms(int(event.get("ms", 0)))

    else:
        raise ValueError("Unknown event type: {}".format(etype))

def run_profile(events, fixed_delay_ms):
    log_event("START_PROFILE", fixed_delay_ms, "begin run")
    for idx, event in enumerate(events):
        run_event(event, fixed_delay_ms)
    log_event("END_PROFILE", fixed_delay_ms, "finished run")

# ----------------------------
# Main
# ----------------------------
def main():
    time.sleep(INITIAL_DELAY_S)
    ensure_log_header()
    events = load_events(INPUT_PATH)

    for profile_ms in SPEED_PROFILES_MS:
        run_profile(events, profile_ms)
        time.sleep(INTER_RUN_DELAY_S)

    log_event("DONE", -1, "all profiles finished")

try:
    main()
except Exception as e:
    try:
        log_event("ERROR", -1, str(e))
    except Exception:
        pass
    while True:
        time.sleep(1)
