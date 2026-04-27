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
class AnyString:
    string_id: int
    string: str
    blocked: bool


@dataclass(frozen=True)
class BlockedHotkey:
    hotkey_id: int
    hotkey: str

@dataclass(frozen=True)
class AnyHotkey:
    hotkey_id: int
    hotkey: str
    blocked: bool


@dataclass(frozen=True)
class BlockedPair:
    hotkey_string_combination_id: int
    hotkey_id: int
    hotkey: str
    string_id: int
    string: str

@dataclass(frozen=True)
class AnyPair:
    hotkey_string_combination_id: int
    hotkey_id: int
    hotkey: str
    string_id: int
    string: str
    blocked: bool


class QueryService:
    def __init__(self, db_path: str = "keyDB.sqlite3", sql_path: Optional[str] = None) -> None:
        self.db_path = str(Path(db_path).expanduser().resolve())
        if sql_path is None:
            sql_path = str(Path(__file__).with_name("queries.sql"))
        print(sql_path + "\n")
        self.sql_path = str(Path(sql_path).expanduser().resolve())

        print(sql_path + "\n")

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.queries = aiosql.from_path(self.sql_path, "sqlite3")
        self.ensure_schema()

        # Store all strings, hotkeys, and pairs in memory to avoid expensive database queries whenever comparison is needed
        self.__strings = self.__get_strings()
        self.__hotkeys = self.__get_hotkeys()
        self.__pairs = self.__get_hotkey_string_pairs()

        # Store blocked strings, hotkeys, and pairs in memory to avoid expensive database queries whenever comparison is needed
        self.__blocked_strings = self.__get_blocked_strings()
        self.__blocked_hotkeys = self.__get_blocked_hotkeys()
        self.__blocked_pairs = self.__get_blocked_hotkey_string_pairs()

    
    def close(self) -> None:
        """ Shut down database connection """
        self.conn.close()


    def ensure_schema(self) -> None:
        """ Ensures db structure is as expected """
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

    @staticmethod
    def normalize_hotkey(hotkey_text: str) -> str:
        """ Convert hotkey to standardized string form to store in DB """
        parts = [p.strip().upper() for p in hotkey_text.split("+") if p.strip()]
        return "+".join(sorted(parts))



    def __get_blocked_strings(self) -> List[BlockedString]:
        """ Returns full list of blocked strings with accompanying ids from DB """
        rows = self.queries.get_blocked_strings(self.conn)
        return [BlockedString(row["string_id"], row["string"]) for row in rows]
    
    def refresh_blocked_strings(self) -> None:
        """ Refreshes blocked strings """
        self.__blocked_strings = self.__get_blocked_strings

    def get_blocked_strings(self) -> List[BlockedString]:
        """ Returns list of blocked strings """
        return self.__blocked_strings


    def __get_strings(self) -> List[AnyString]:
        """ Returns full list of strings with accompanying ids from DB """
        rows = self.queries.get_strings(self.conn)
        return [AnyString(row["string_id"], row["string"], row["blocked"]) for row in rows]
    
    def refresh_strings(self) -> None:
        """ Refreshes blocked strings """
        self.__strings = self.__get_strings

    def get_strings(self) -> List[AnyString]:
        """ Returns list of strings """
        return self.__strings



    def __get_blocked_hotkeys(self) -> List[BlockedHotkey]:
        """ Returns full list of blocked hotkeys with accompanying ids from DB """
        rows = self.queries.get_blocked_hotkeys(self.conn)
        return [BlockedHotkey(row["hotkey_id"], row["hotkey"]) for row in rows]
    
    def refresh_blocked_hotkeys(self) -> None:
        """ Refreshes blocked hotkeys """
        self.__blocked_hotkeys = self.__get_blocked_hotkeys

    def get_blocked_hotkeys(self) -> List[BlockedHotkey]:
        """ Returns list of blocked hotkeys """
        return self.__blocked_hotkeys


    def __get_hotkeys(self) -> List[AnyHotkey]:
        """ Returns full list of hotkeys with accompanying ids from DB """
        rows = self.queries.get_hotkeys(self.conn)
        return [AnyHotkey(row["hotkey_id"], row["hotkey"], row["blocked"]) for row in rows]
    
    def refresh_hotkeys(self) -> None:
        """ Refreshes hotkeys """
        self.__hotkeys = self.__get_hotkeys

    def get_hotkeys(self) -> List[AnyHotkey]:
        """ Returns list of blocked hotkeys """
        return self.__hotkeys



    def __get_blocked_hotkey_string_pairs(self) -> List[BlockedPair]:
        """ Returns full list of blocked hotkey-string pairs with accompanying ids from DB """
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
    
    def refresh_blocked_pairs(self) -> None:
        """ Refreshes blocked hotkeys-string pairs """
        self.__blocked_pairs = self.__get_blocked_hotkey_string_pairs


    def __get_hotkey_string_pairs(self) -> List[AnyPair]:
        """ Returns full list of hotkey-string pairs with accompanying ids from DB """
        rows = self.queries.get_hotkey_string_pairs(self.conn)
        return [
            AnyPair(
                hotkey_string_combination_id=row["hotkey_string_combination_id"],
                hotkey_id=row["hotkey_id"],
                hotkey=self.normalize_hotkey(row["hotkey"]),
                string_id=row["string_id"],
                string=row["string"],
                blocked=row["blocked"]
            )
            for row in rows
        ]
    
    def refresh_pairs(self) -> None:
        """ Refreshes hotkeys-string pairs """
        self.__pairs = self.__get_hotkey_string_pairs



    def blocked_string_match(self, text_snapshot: str) -> Optional[BlockedString]:
        """ Checks if given string is blocked """
        lowered = text_snapshot.lower()
        for item in self.__blocked_strings:
            if item.string.lower() in lowered:
                return item
        return None

    def blocked_hotkey_match(self, hotkey_text: str) -> Optional[BlockedHotkey]:
        """ Checks if given hotkey is blocked """
        normalized = self.normalize_hotkey(hotkey_text)
        for item in self.__blocked_hotkeys:
            if self.normalize_hotkey(item.hotkey) == normalized:
                return item
        return None

    def blocked_pair_match(self, hotkey_id: int, string_id: int) -> Optional[BlockedPair]:
        """ Checks if given hotkey-string pair is blocked """
        for item in self.__blocked_pairs:
            if item.hotkey_id == hotkey_id and item.string_id == string_id:
                return item
        return None

    def add_speed_detection(self, info: str, detected_at: str) -> None:
        """ Adds speed detection log to DB """
        self.queries.add_speed_detection(self.conn, info=info, detected_at=detected_at)
        self.conn.commit()

    def add_blacklist_detection_hotkey(self, hotkey_id: int, detected_at: str) -> None:
        """ Adds hotkey blacklist detection log to DB """
        self.queries.add_blacklist_detection_hotkey(self.conn, hotkey_id=hotkey_id, detected_at=detected_at)
        self.conn.commit()

    def add_blacklist_detection_string(self, string_id: int, detected_at: str) -> None:
        """ Adds string blacklist detection log to DB """
        self.queries.add_blacklist_detection_string(self.conn, string_id=string_id, detected_at=detected_at)
        self.conn.commit()

    def add_blacklist_detection_pair(self, hotkey_string_combination_id: int, detected_at: str) -> None:
        """ Adds hotkey-string pair detection log to DB """
        self.queries.add_blacklist_detection_pair(
            self.conn,
            hotkey_string_combination_id=hotkey_string_combination_id,
            detected_at=detected_at,
        )
        self.conn.commit()
