"""
queries.py

SQLite + aiosql wrapper for the keystroke daemon project.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import aiosql


@dataclass(frozen=True)
class BlockedString:
    string_id: int
    string: str


@dataclass(frozen=True)
class BlockedHotkey:
    hotkey_id: int
    hotkey: str


@dataclass(frozen=True)
class BlockedPair:
    hotkey_string_combination_id: int
    hotkey_id: int
    hotkey: str
    string_id: int
    string: str


class QueryService:
    def __init__(self, db_path: str = "keyDB.sqlite3", sql_path: Optional[str] = None) -> None:
        self.db_path = str(Path(db_path).expanduser().resolve())
        if sql_path is None:
            sql_path = str(Path(__file__).with_name("queries_fixed.sql"))
        self.sql_path = str(Path(sql_path).expanduser().resolve())

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.queries = aiosql.from_path(self.sql_path, "sqlite3")
        self.ensure_schema()

        # Store blocked strings, hotkeys, and pairs in memory to avoid expensive database queries whenever comparison is needed
        self.__blocked_strings = self.__get_blocked_strings()
        self.__blocked_hotkeys = self.__get_blocked_hotkeys()
        self.__blocked_pairs = self.__get_blocked_hotkey_string_pairs()

    # Shutdown
    def close(self) -> None:
        self.conn.close()

    # Ensure db structure is as expected
    def ensure_schema(self) -> None:
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS strings (
            string_id INTEGER PRIMARY KEY AUTOINCREMENT,
            string TEXT NOT NULL UNIQUE,
            blocked INTEGER NOT NULL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS hotkeys (
            hotkey_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotkey TEXT NOT NULL UNIQUE,
            blocked INTEGER NOT NULL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS hotkey_string_combinations (
            hotkey_string_combination_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotkey_id INTEGER NOT NULL,
            string_id INTEGER NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0,
            UNIQUE(hotkey_id, string_id),
            FOREIGN KEY (hotkey_id) REFERENCES hotkeys(hotkey_id),
            FOREIGN KEY (string_id) REFERENCES strings(string_id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS speed_detections (
            speed_detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            info TEXT NOT NULL,
            detected_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS blacklist_detections (
            blacklist_detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotkey_id INTEGER,
            string_id INTEGER,
            hotkey_string_combination_id INTEGER,
            detected_at TEXT NOT NULL,
            FOREIGN KEY (hotkey_id) REFERENCES hotkeys(hotkey_id),
            FOREIGN KEY (string_id) REFERENCES strings(string_id),
            FOREIGN KEY (hotkey_string_combination_id) REFERENCES hotkey_string_combinations(hotkey_string_combination_id)
        )
        """)

        self.conn.commit()

    # Convert hotkey to standardized string form to store in DB
    @staticmethod
    def normalize_hotkey(hotkey_text: str) -> str:
        parts = [p.strip().upper() for p in hotkey_text.split("+") if p.strip()]
        return "+".join(sorted(parts))

    # Returns full list of blocked strings with accompanying ids from DB
    def __get_blocked_strings(self) -> List[BlockedString]:
        rows = self.queries.get_blocked_strings(self.conn)
        return [BlockedString(row["string_id"], row["string"]) for row in rows]
    
    # Refreshes blocked strings
    def refresh_blocked_strings(self) -> None:
        self.__blocked_strings = self.__get_blocked_strings

    # Returns full list of blocked ids with accompanying ids from DB
    def __get_blocked_hotkeys(self) -> List[BlockedHotkey]:
        rows = self.queries.get_blocked_hotkeys(self.conn)
        return [BlockedHotkey(row["hotkey_id"], row["hotkey"]) for row in rows]
    
    # Refreshes blocked hotkeys
    def refresh_blocked_hotkeys(self) -> None:
        self.__blocked_hotkeys = self.__get_blocked_hotkeys

    # Returns full list of blocked hotkey-string pairs with accompanying ids from DB
    def __get_blocked_hotkey_string_pairs(self) -> List[BlockedPair]:
        rows = self.queries.get_blocked_hotkey_string_pairs(self.conn)
        return [
            BlockedPair(
                hotkey_string_combination_id=row["hotkey_string_combination_id"],
                hotkey_id=row["hotkey_id"],
                hotkey=self.normalize_hotkey(row["hotkey"]),
                string_id=row["string_id"],
                string=row["string"],
            )
            for row in rows
        ]
    
    # Refreshes blocked hotkeys-string pairs
    def refresh_blocked_pairs(self) -> None:
        self.__blocked_pairs = self.__get_blocked_hotkey_string_pairs

    # Checks if given string is blocked
    def blocked_string_match(self, text_snapshot: str) -> Optional[BlockedString]:
        lowered = text_snapshot.lower()
        for item in self.__blocked_strings:
            if item.string.lower() in lowered:
                return item
        return None

    # Checks if given hotkey is blocked
    def blocked_hotkey_match(self, hotkey_text: str) -> Optional[BlockedHotkey]:
        normalized = self.normalize_hotkey(hotkey_text)
        for item in self.__blocked_hotkeys:
            if self.normalize_hotkey(item.hotkey) == normalized:
                return item
        return None

    # Checks if given hotkey-string pair is blocked
    def blocked_pair_match(self, hotkey_id: int, string_id: int) -> Optional[BlockedPair]:
        for item in self.__blocked_pairs:
            if item.hotkey_id == hotkey_id and item.string_id == string_id:
                return item
        return None

    # Adds speed detection log to DB
    def add_speed_detection(self, info: str, detected_at: str) -> None:
        self.queries.add_speed_detection(self.conn, info=info, detected_at=detected_at)
        self.conn.commit()

    # Adds hotkey blacklist detection log to DB
    def add_blacklist_detection_hotkey(self, hotkey_id: int, detected_at: str) -> None:
        self.queries.add_blacklist_detection_hotkey(self.conn, hotkey_id=hotkey_id, detected_at=detected_at)
        self.conn.commit()

    # Adds string blacklist detection log to DB
    def add_blacklist_detection_string(self, string_id: int, detected_at: str) -> None:
        self.queries.add_blacklist_detection_string(self.conn, string_id=string_id, detected_at=detected_at)
        self.conn.commit()

    # Adds hotkey-string pair detection log to DB
    def add_blacklist_detection_pair(self, hotkey_string_combination_id: int, detected_at: str) -> None:
        self.queries.add_blacklist_detection_pair(
            self.conn,
            hotkey_string_combination_id=hotkey_string_combination_id,
            detected_at=detected_at,
        )
        self.conn.commit()
