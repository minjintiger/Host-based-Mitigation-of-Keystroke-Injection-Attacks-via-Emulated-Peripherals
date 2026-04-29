import time
import json
import os
import usb_hid
import random

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
INPUT_PATH = "/dataset.json"

INITIAL_DELAY_S = 10
INTER_SEQUENCE_DELAY_S = 2
INTER_PROFILE_DELAY_S = 20
COMBO_HOLD_MS = 50

# Speed typing feature
ENABLE_SPEED_SWEEP = True
SPEED_PROFILES_MS = [240, 220, 200, 180, 160, 140, 120, 100, 80, 60, 40, 20, 0]
DEFAULT_FIXED_DELAY_MS = 200   # used if ENABLE_SPEED_SWEEP = False

# human alike typing parameters
ENABLE_HUMAN_LIKE_RANDOM_AFTER_SWEEP = True
HUMAN_LIKE_RUNS = 3

HUMAN_MIN_DELAY_MS = 80
HUMAN_MAX_DELAY_MS = 320
HUMAN_PAUSE_CHANCE = 0.08
HUMAN_PAUSE_MIN_MS = 300
HUMAN_PAUSE_MAX_MS = 1200

LOG_PATH = "/result_log.csv"

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

def clean_csv(value):
    text = str(value)
    text = text.replace(",", ";")
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    return text

def safe_div(numerator, denominator):
    if denominator == 0:
        return 0.0
    return numerator / denominator

def new_stats():
    return {
        "elapsed_ms": 0.0,
        "text_elapsed_ms": 0.0,
        "text_chars": 0,
        "key_events": 0,
        "combo_events": 0,
        "delay_events": 0,
        "total_events": 0,
    }

def merge_stats(total, item):
    total["elapsed_ms"] += item.get("elapsed_ms", 0.0)
    total["text_elapsed_ms"] += item.get("text_elapsed_ms", 0.0)
    total["text_chars"] += item.get("text_chars", 0)
    total["key_events"] += item.get("key_events", 0)
    total["combo_events"] += item.get("combo_events", 0)
    total["delay_events"] += item.get("delay_events", 0)
    total["total_events"] += item.get("total_events", 0)

def ensure_log_header():
    try:
        need_header = False

        try:
            size = os.stat(LOG_PATH)[6]
            if size == 0:
                need_header = True
        except OSError:
            need_header = True

        with open(LOG_PATH, "a") as f:
            if need_header:
                f.write(
                    "monotonic_s,event,run_type,profile_ms,sequence_id,"
                    "elapsed_ms,text_elapsed_ms,text_chars,key_events,combo_events,"
                    "delay_events,total_events,avg_ms_per_char,text_avg_ms_per_char,"
                    "chars_per_sec,note\n"
                )
    except Exception:
        pass

def log_event(
    event,
    profile_ms,
    sequence_id="",
    note="",
    run_type="",
    stats=None
):
    if stats is None:
        stats = new_stats()

    elapsed_ms = stats.get("elapsed_ms", 0.0)
    text_elapsed_ms = stats.get("text_elapsed_ms", 0.0)
    text_chars = stats.get("text_chars", 0)

    avg_ms_per_char = safe_div(elapsed_ms, text_chars)
    text_avg_ms_per_char = safe_div(text_elapsed_ms, text_chars)
    chars_per_sec = safe_div(text_chars, safe_div(text_elapsed_ms, 1000.0))

    try:
        with open(LOG_PATH, "a") as f:
            f.write(
                "{:.3f},{},{},{},{},{:.2f},{:.2f},{},{},{},{},{},{:.2f},{:.2f},{:.2f},{}\n".format(
                    time.monotonic(),
                    clean_csv(event),
                    clean_csv(run_type),
                    profile_ms,
                    clean_csv(sequence_id),
                    elapsed_ms,
                    text_elapsed_ms,
                    text_chars,
                    stats.get("key_events", 0),
                    stats.get("combo_events", 0),
                    stats.get("delay_events", 0),
                    stats.get("total_events", 0),
                    avg_ms_per_char,
                    text_avg_ms_per_char,
                    chars_per_sec,
                    clean_csv(note),
                )
            )
    except Exception:
        pass

def log_wait_before_next(current_profile_ms, next_profile_ms, wait_s, run_type):
    note = "current profile finished; next_profile_ms={} starts_after_s={}".format(
        next_profile_ms,
        wait_s
    )
    log_event(
        "WAIT_BEFORE_NEXT_PROFILE",
        current_profile_ms,
        note=note,
        run_type=run_type
    )

    time.sleep(wait_s)

    log_event(
        "WAIT_DONE_NEXT_PROFILE_STARTING",
        next_profile_ms,
        note="wait finished; starting next profile now",
        run_type=run_type
    )

def type_text(text, char_delay_ms, human_like=False):
    for ch in text:
        layout.write(ch)

        if human_like:
            delay_ms = random.randint(HUMAN_MIN_DELAY_MS, HUMAN_MAX_DELAY_MS)
            sleep_ms(delay_ms)

            if ch == " " or random.random() < HUMAN_PAUSE_CHANCE:
                pause_ms = random.randint(HUMAN_PAUSE_MIN_MS, HUMAN_PAUSE_MAX_MS)
                sleep_ms(pause_ms)

        else:
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
def run_event(event, fixed_delay_ms, human_like=False):
    etype = event.get("type", "").lower()
    stats = new_stats()
    start = time.monotonic()

    if etype == "text":
        value = event.get("value", "")
        type_text(value, fixed_delay_ms, human_like)
        stats["text_chars"] = len(value)
        stats["total_events"] = 1

    elif etype == "key":
        send_key(event["key"])
        if fixed_delay_ms > 0:
            sleep_ms(fixed_delay_ms)
        stats["key_events"] = 1
        stats["total_events"] = 1

    elif etype == "combo":
        send_combo(event["keys"])
        if fixed_delay_ms > 0:
            sleep_ms(fixed_delay_ms)
        stats["combo_events"] = 1
        stats["total_events"] = 1

    elif etype == "delay":
        sleep_ms(int(event.get("ms", 0)))
        stats["delay_events"] = 1
        stats["total_events"] = 1

    else:
        raise ValueError("Unknown event type: {}".format(etype))

    elapsed_ms = (time.monotonic() - start) * 1000.0
    stats["elapsed_ms"] = elapsed_ms

    if etype == "text":
        stats["text_elapsed_ms"] = elapsed_ms

    return stats

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
def run_sequence(sequence, fixed_delay_ms, human_like=False):
    seq_id = sequence.get("id", "unknown")
    events = sequence.get("events", [])
    run_type = "human_like_random" if human_like else "fixed_speed"

    seq_stats = new_stats()
    seq_start = time.monotonic()

    log_event(
        "START_SEQUENCE",
        fixed_delay_ms,
        seq_id,
        "begin",
        run_type=run_type
    )

    for event in events:
        event_stats = run_event(event, fixed_delay_ms, human_like)
        merge_stats(seq_stats, event_stats)

    seq_stats["elapsed_ms"] = (time.monotonic() - seq_start) * 1000.0

    log_event(
        "END_SEQUENCE",
        fixed_delay_ms,
        seq_id,
        "sequence finished",
        run_type=run_type,
        stats=seq_stats
    )

    return seq_stats

def run_single_profile(sequences, profile_ms, human_like=False, run_index=0):
    run_type = "human_like_random" if human_like else "fixed_speed"
    profile_stats = new_stats()
    profile_start = time.monotonic()

    log_event(
        "START_PROFILE",
        profile_ms,
        "",
        "profile started; run_index={}".format(run_index),
        run_type=run_type
    )

    for sequence in sequences:
        sequence_stats = run_sequence(sequence, profile_ms, human_like)
        merge_stats(profile_stats, sequence_stats)

        log_event(
            "WAIT_BETWEEN_SEQUENCES",
            profile_ms,
            sequence.get("id", "unknown"),
            "sequence finished; next sequence starts_after_s={}".format(INTER_SEQUENCE_DELAY_S),
            run_type=run_type
        )

        time.sleep(INTER_SEQUENCE_DELAY_S)

    profile_stats["elapsed_ms"] = (time.monotonic() - profile_start) * 1000.0

    log_event(
        "END_PROFILE",
        profile_ms,
        "",
        "profile finished; run_index={}".format(run_index),
        run_type=run_type,
        stats=profile_stats
    )

    return profile_stats

# ----------------------------
# Main
# ----------------------------
def main():
    time.sleep(INITIAL_DELAY_S)
    ensure_log_header()

    log_event(
        "START_RUNNER",
        -1,
        "",
        "initial delay finished; loading dataset",
        run_type="setup"
    )

    sequences = load_sequences(INPUT_PATH)

    log_event(
        "DATASET_LOADED",
        -1,
        "",
        "sequence_count={}".format(len(sequences)),
        run_type="setup"
    )

    overall_stats = new_stats()
    overall_start = time.monotonic()

    if ENABLE_SPEED_SWEEP:
        for index, profile_ms in enumerate(SPEED_PROFILES_MS):
            profile_stats = run_single_profile(
                sequences,
                profile_ms,
                human_like=False,
                run_index=index
            )
            merge_stats(overall_stats, profile_stats)

            if index < len(SPEED_PROFILES_MS) - 1:
                next_profile_ms = SPEED_PROFILES_MS[index + 1]
                log_wait_before_next(
                    profile_ms,
                    next_profile_ms,
                    INTER_PROFILE_DELAY_S,
                    "fixed_speed"
                )

        log_event(
            "SPEED_SWEEP_FINISHED",
            -1,
            "",
            "fixed speed sweep finished",
            run_type="fixed_speed",
            stats=overall_stats
        )

        if ENABLE_HUMAN_LIKE_RANDOM_AFTER_SWEEP:
            log_event(
                "WAIT_BEFORE_HUMAN_LIKE_RUN",
                -100,
                "",
                "speed sweep finished; human-like run starts_after_s={}".format(INTER_PROFILE_DELAY_S),
                run_type="human_like_random"
            )

            time.sleep(INTER_PROFILE_DELAY_S)

            for i in range(HUMAN_LIKE_RUNS):
                human_stats = run_single_profile(
                    sequences,
                    -100,
                    human_like=True,
                    run_index=i
                )
                merge_stats(overall_stats, human_stats)

                if i < HUMAN_LIKE_RUNS - 1:
                    log_wait_before_next(
                        -100,
                        -100,
                        INTER_PROFILE_DELAY_S,
                        "human_like_random"
                    )

    else:
        profile_stats = run_single_profile(
            sequences,
            DEFAULT_FIXED_DELAY_MS,
            human_like=False,
            run_index=0
        )
        merge_stats(overall_stats, profile_stats)

    overall_stats["elapsed_ms"] = (time.monotonic() - overall_start) * 1000.0

    log_event(
        "DONE",
        -1,
        "",
        "all runs finished",
        run_type="summary",
        stats=overall_stats
    )

main()