"""
user_settings.py

Allows user to interact with database such as viewing and adjusting blacklist or logs.
"""


import sqlite3
from queries import QueryService as QS
import streamlit as st
from enum import StrEnum



def close_db_service(q_service: QueryService):
    q_service.close()
    print("DB closed.")

# returns QueryService object
@st.cache_resource(on_release=close_db, scope="session")
def open_db_service():
    print("Opening DB.")
    from queries import QueryService
    return QueryService


# Corresponds to tables within database.
class Table(StrEnum):
    STRINGS = "String Blacklist"
    HOTKEY = "Hotkey Blacklist"
    PAIR = "Hotkey String Pair Blacklist"
    BLACKLIST_DETECTION = "Blacklist Detection Log"
    KEYSTROKE_DETECTION = "Keystroke Detection Log"

table = st.selectbox("Select a table to view:", Table)

match table:
    case Table.STRINGS:
        st.write("You selected String Blacklist")
    case Table.HOTKEY:
        st.write("hotkeys")
    case Table.PAIR:
        st.write("pairs")
    case Table.BLACKLIST_DETECTION:
        st.write("blacklist log")
    case Table.KEYSTROKE_DETECTION:
        st.write("keystroke log")
    case _:
        st.write("Not implemented!")








