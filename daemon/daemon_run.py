"""
daemon_run.py

Host-side keystroke detection daemon.
- global keyboard monitoring via pynput
- recent 4-word average typing-speed detection
- blacklist string / hotkey / hotkey+string pair detection
- SQLite logging via queries.py + aiosql

"""

from __future__ import annotations

import argparse
import logging
import time
import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, List, Optional, Set

from pynput import keyboard

from queries import QueryService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

WORD_WINDOW_SIZE = 4
HUMAN_THRESHOLD_MS = 240.0
DETECTION_COOLDOWN_S = 1.5
HOTKEY_STRING_WINDOW_S = 4.0
WORD_DELIMITERS = {" ", "\n", "\t"}

# time consistency detection parameters
AVG_DELAY_HISTORY_SIZE = 8
CONSISTENCY_WINDOW_SIZE = 4

# this is starting point for stddev threshold
# this number will decide the rate of false positives
# if the stddev of recent average char delays is below this threshold, it may indicate non-human typing patterns
CONSISTENCY_STDDEV_THRESHOLD_MS = 8.0 # could be tuned ex) 5, 10, 15 


CONSISTENCY_MIN_AVG_DELAY_MS = 40.0


@dataclass
class CompletedWord:
    text: str
    char_count: int
    elapsed_ms: float


@dataclass
class RecentHotkeyEvent:
    hotkey_id: int
    hotkey: str
    timestamp: float


class KeystrokeDaemon:
    def __init__(self, query_service: QueryService) -> None:
        self.q = query_service

        self.pressed_modifiers: Set[str] = set()
        self.current_word_chars: List[str] = []
        self.current_word_start_ts: Optional[float] = None
        self.current_word_last_ts: Optional[float] = None

        self.recent_words: Deque[CompletedWord] = deque(maxlen=WORD_WINDOW_SIZE)
        self.avg_delay_history: Deque[float] = deque(maxlen=AVG_DELAY_HISTORY_SIZE)
        self.text_history: Deque[str] = deque(maxlen=400)
        self.recent_hotkey: Optional[RecentHotkeyEvent] = None

        self.last_detection_signature: Optional[str] = None
        self.last_detection_ts: float = 0.0

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def normalize_modifier(key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "CTRL"
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "SHIFT"
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return "ALT"
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            return "GUI"
        return None

    @staticmethod
    def normalize_non_modifier(key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
        if isinstance(key, keyboard.KeyCode):
            if key.char is None:
                return None
            return key.char.upper()

        special_map = {
            keyboard.Key.enter: "ENTER",
            keyboard.Key.tab: "TAB",
            keyboard.Key.space: "SPACE",
            keyboard.Key.backspace: "BACKSPACE",
            keyboard.Key.delete: "DELETE",
            keyboard.Key.esc: "ESCAPE",
            keyboard.Key.up: "UP_ARROW",
            keyboard.Key.down: "DOWN_ARROW",
            keyboard.Key.left: "LEFT_ARROW",
            keyboard.Key.right: "RIGHT_ARROW",
            keyboard.Key.home: "HOME",
            keyboard.Key.end: "END",
            keyboard.Key.page_up: "PAGE_UP",
            keyboard.Key.page_down: "PAGE_DOWN",
            keyboard.Key.insert: "INSERT",
            keyboard.Key.f1: "F1",
            keyboard.Key.f2: "F2",
            keyboard.Key.f3: "F3",
            keyboard.Key.f4: "F4",
            keyboard.Key.f5: "F5",
            keyboard.Key.f6: "F6",
            keyboard.Key.f7: "F7",
            keyboard.Key.f8: "F8",
            keyboard.Key.f9: "F9",
            keyboard.Key.f10: "F10",
            keyboard.Key.f11: "F11",
            keyboard.Key.f12: "F12",
        }
        return special_map.get(key)

    @staticmethod
    def char_from_key(key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
        if isinstance(key, keyboard.KeyCode) and key.char is not None:
            return key.char
        if key == keyboard.Key.space:
            return " "
        if key == keyboard.Key.enter:
            return "\n"
        if key == keyboard.Key.tab:
            return "\t"
        return None

    @staticmethod
    def is_printable_text_char(ch: str) -> bool:
        return ch not in ("\n", "\t") and len(ch) == 1

    def finalize_current_word(self, delimiter_char: str) -> None:
        if not self.current_word_chars or self.current_word_start_ts is None or self.current_word_last_ts is None:
            self.current_word_chars = []
            self.current_word_start_ts = None
            self.current_word_last_ts = None
            return

        word_text = "".join(self.current_word_chars)
        elapsed_ms = max((self.current_word_last_ts - self.current_word_start_ts) * 1000.0, 1.0)

        self.recent_words.append(
            CompletedWord(
                text=word_text,
                char_count=len(word_text),
                elapsed_ms=elapsed_ms,
            )
        )

        self.text_history.append(word_text)
        self.text_history.append(delimiter_char)

        self.current_word_chars = []
        self.current_word_start_ts = None
        self.current_word_last_ts = None

    def update_word_buffer(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        now = time.monotonic()
        ch = self.char_from_key(key)
        if ch is None:
            return

        if ch in WORD_DELIMITERS:
            self.finalize_current_word(ch)
            return

        if not self.is_printable_text_char(ch):
            return

        if self.current_word_start_ts is None:
            self.current_word_start_ts = now
        self.current_word_last_ts = now
        self.current_word_chars.append(ch)

    def average_char_delay_ms(self) -> Optional[float]:
        if len(self.recent_words) < WORD_WINDOW_SIZE:
            return None

        total_chars = sum(item.char_count for item in self.recent_words)
        total_ms = sum(item.elapsed_ms for item in self.recent_words)
        if total_chars <= 0:
            return None
        return total_ms / total_chars

    def timing_consistency_suspicious(self) -> Optional[tuple[float, float]]:
        if len(self.avg_delay_history) < CONSISTENCY_WINDOW_SIZE:
            return None

        recent = list(self.avg_delay_history)[-CONSISTENCY_WINDOW_SIZE:]

        mean_ms = sum(recent) / len(recent)
        stddev_ms = statistics.pstdev(recent)

        if mean_ms < CONSISTENCY_MIN_AVG_DELAY_MS:
            return None

        if stddev_ms < CONSISTENCY_STDDEV_THRESHOLD_MS:
            return mean_ms, stddev_ms

        return None

    def current_text_snapshot(self) -> str:
        return "".join(self.text_history) + "".join(self.current_word_chars)

    def build_hotkey(self, key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
        non_modifier = self.normalize_non_modifier(key)
        if not non_modifier or not self.pressed_modifiers:
            return None
        parts = set(self.pressed_modifiers)
        parts.add(non_modifier)
        return "+".join(sorted(parts))

    def should_suppress(self, signature: str) -> bool:
        now = time.monotonic()
        if self.last_detection_signature == signature and (now - self.last_detection_ts) < DETECTION_COOLDOWN_S:
            return True
        self.last_detection_signature = signature
        self.last_detection_ts = now
        return False

    def log_speed_detection(self, avg_ms: float) -> None:
        info = f"avg_char_delay_ms={avg_ms:.2f} threshold_ms={HUMAN_THRESHOLD_MS:.2f}"
        signature = f"speed|{info}"
        if self.should_suppress(signature):
            return
        self.q.add_speed_detection(info=info, detected_at=self.utc_now())
        logging.info("SPEED DETECTION | %s", info)
    
    def log_timing_consistency_detection(self, mean_ms: float, stddev_ms: float) -> None:
        info = (
            f"timing_consistency mean_avg_char_delay_ms={mean_ms:.2f} "
            f"stddev_ms={stddev_ms:.2f} "
            f"window={CONSISTENCY_WINDOW_SIZE} "
            f"threshold_stddev_ms={CONSISTENCY_STDDEV_THRESHOLD_MS:.2f}"
        )

        signature = f"timing_consistency|{mean_ms:.2f}|{stddev_ms:.2f}"

        if self.should_suppress(signature):
            return

        self.q.add_speed_detection(info=info, detected_at=self.utc_now())
        logging.info("TIMING CONSISTENCY DETECTION | %s", info)

    def log_hotkey_detection(self, hotkey_id: int, hotkey_text: str) -> None:
        signature = f"hotkey|{hotkey_id}|{hotkey_text}"
        if self.should_suppress(signature):
            return
        self.q.add_blacklist_detection_hotkey(hotkey_id=hotkey_id, detected_at=self.utc_now())
        logging.info("HOTKEY DETECTION | %s", hotkey_text)

    def log_string_detection(self, string_id: int, string_value: str) -> None:
        signature = f"string|{string_id}|{string_value}"
        if self.should_suppress(signature):
            return
        self.q.add_blacklist_detection_string(string_id=string_id, detected_at=self.utc_now())
        logging.info("STRING DETECTION | %s", string_value)

    def log_pair_detection(self, pair_id: int, value: str) -> None:
        signature = f"pair|{pair_id}|{value}"
        if self.should_suppress(signature):
            return
        self.q.add_blacklist_detection_pair(hotkey_string_combination_id=pair_id, detected_at=self.utc_now())
        logging.info("PAIR DETECTION | %s", value)

    def on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        modifier = self.normalize_modifier(key)
        if modifier is not None:
            self.pressed_modifiers.add(modifier)
            return

        self.update_word_buffer(key)

        avg_ms = self.average_char_delay_ms()
        if avg_ms is not None:
            self.avg_delay_history.append(avg_ms)

            if avg_ms < HUMAN_THRESHOLD_MS:
                self.log_speed_detection(avg_ms)

            consistency_result = self.timing_consistency_suspicious()
            if consistency_result is not None:
                mean_ms, stddev_ms = consistency_result
                self.log_timing_consistency_detection(mean_ms, stddev_ms)

        hotkey_text = self.build_hotkey(key)
        if hotkey_text is not None:
            hotkey_match = self.q.blocked_hotkey_match(hotkey_text)
            if hotkey_match is not None:
                self.recent_hotkey = RecentHotkeyEvent(
                    hotkey_id=hotkey_match.hotkey_id,
                    hotkey=hotkey_text,
                    timestamp=time.monotonic(),
                )
                self.log_hotkey_detection(hotkey_match.hotkey_id, hotkey_text)

        text_snapshot = self.current_text_snapshot()
        string_match = self.q.blocked_string_match(text_snapshot)
        if string_match is not None:
            self.log_string_detection(string_match.string_id, string_match.string)

            if self.recent_hotkey is not None:
                if (time.monotonic() - self.recent_hotkey.timestamp) <= HOTKEY_STRING_WINDOW_S:
                    pair_match = self.q.blocked_pair_match(
                        hotkey_id=self.recent_hotkey.hotkey_id,
                        string_id=string_match.string_id,
                    )
                    if pair_match is not None:
                        self.log_pair_detection(
                            pair_match.hotkey_string_combination_id,
                            f"{self.recent_hotkey.hotkey} + {string_match.string}",
                        )

    def on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        modifier = self.normalize_modifier(key)
        if modifier is not None and modifier in self.pressed_modifiers:
            self.pressed_modifiers.remove(modifier)

    def run(self) -> None:
        logging.info("Starting daemon | threshold=%.2f ms/char | window=%d words", HUMAN_THRESHOLD_MS, WORD_WINDOW_SIZE)
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release, suppress=False) as listener:
            listener.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keystroke injection detection daemon")
    parser.add_argument("--db", default="keyDB.sqlite3", help="Path to SQLite database")
    parser.add_argument("--sql", default=None, help="Path to queries SQL file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    q = QueryService(db_path=args.db, sql_path=args.sql)
    try:
        daemon = KeystrokeDaemon(q)
        daemon.run()
    finally:
        q.close()


if __name__ == "__main__":
    main()
