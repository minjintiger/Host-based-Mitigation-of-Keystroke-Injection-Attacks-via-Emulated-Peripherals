import time
import json
import os
import usb_hid

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

# ============================================================
# CircuitPython HID runner
# - Reads merged sequence dataset
# - Supports TEXT, KEY, COMBO, DELAY
# - Runs sequences with fixed speed profiles
# - Preserves word boundaries if dataset includes SPACE events
# ============================================================

# ----------------------------
# Config
# ----------------------------
INPUT_PATH = "/merged_hid_event_dataset.json"

INITIAL_DELAY_S = 10
INTER_SEQUENCE_DELAY_S = 2
INTER_PROFILE_DELAY_S = 8
COMBO_HOLD_MS = 50

# Speed typing feature
ENABLE_SPEED_SWEEP = True
SPEED_PROFILES_MS = [240, 220, 200, 180, 160, 140, 120, 100, 80, 60, 40, 20, 0]
DEFAULT_FIXED_DELAY_MS = 200   # used if ENABLE_SPEED_SWEEP = False

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

def get_keycode(token):
    token = token.strip().upper()
    if token not in KEYMAP:
        raise ValueError("Unsupported key token: {}".format(token))
    return KEYMAP[token]

def ensure_log_header():
    try:
        need_header = False
        if LOG_PATH.strip("/") not in os.listdir("/"):
            need_header = True
        with open(LOG_PATH, "a") as f:
            if need_header:
                f.write("monotonic_s,event,profile_ms,sequence_id,note\n")
    except Exception:
        pass

def log_event(event, profile_ms, sequence_id="", note=""):
    try:
        with open(LOG_PATH, "a") as f:
            f.write("{:.3f},{},{},{},{}\n".format(
                time.monotonic(),
                event,
                profile_ms,
                sequence_id,
                note.replace(",", ";")
            ))
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

# ----------------------------
# Dataset loading
# ----------------------------
def load_sequences(path):
    with open(path, "r") as f:
        data = json.load(f)

    if isinstance(data, dict) and "sequences" in data:
        return data["sequences"]

    if isinstance(data, dict) and "events" in data:
        return [{"id": "seq_default", "label": "default", "events": data["events"]}]

    if isinstance(data, list):
        return [{"id": "seq_default", "label": "default", "events": data}]

    raise ValueError("Unsupported dataset structure")

# ----------------------------
# Sequence / profile execution
# ----------------------------
def run_sequence(sequence, fixed_delay_ms):
    seq_id = sequence.get("id", "unknown")
    events = sequence.get("events", [])

    log_event("START_SEQUENCE", fixed_delay_ms, seq_id, "begin")
    for event in events:
        run_event(event, fixed_delay_ms)
    log_event("END_SEQUENCE", fixed_delay_ms, seq_id, "done")

def run_single_profile(sequences, profile_ms):
    log_event("START_PROFILE", profile_ms, "", "profile begin")
    for sequence in sequences:
        run_sequence(sequence, profile_ms)
        time.sleep(INTER_SEQUENCE_DELAY_S)
    log_event("END_PROFILE", profile_ms, "", "profile done")

# ----------------------------
# Main
# ----------------------------
def main():
    time.sleep(INITIAL_DELAY_S)
    ensure_log_header()
    sequences = load_sequences(INPUT_PATH)

    if ENABLE_SPEED_SWEEP:
        for profile_ms in SPEED_PROFILES_MS:
            run_single_profile(sequences, profile_ms)
            time.sleep(INTER_PROFILE_DELAY_S)
    else:
        run_single_profile(sequences, DEFAULT_FIXED_DELAY_MS)

    log_event("DONE", -1, "", "all runs finished")

try:
    main()
except Exception as e:
    try:
        log_event("ERROR", -1, "", str(e))
    except Exception:
        pass
    while True:
        time.sleep(1)
