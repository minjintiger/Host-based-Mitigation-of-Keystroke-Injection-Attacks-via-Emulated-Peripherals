"""
user_settings.py

Allows user to interact with database such as viewing and adjusting blacklist or logs.
"""



from queries import QueryService as QS
import pandas as pd
import streamlit as st
from enum import StrEnum
from queries import QueryService


# Setup and cache db connection
def close_db_service(q_service: QueryService):
    q_service.close()
    print("DB closed.")

# returns QueryService object
@st.cache_resource(on_release=close_db_service, scope="global")
def open_db_service():
    print("Opening DB.")
    return QueryService(db_path="keyDB.sqlite3")

query_service = open_db_service()

if "strings" not in st.session_state:
    data = query_service.get_strings()
    st.session_state.strings = pd.DataFrame([s.__dict__ for s in data])

def update_strings():
    data = query_service.get_strings()
    st.session_state.strings = pd.DataFrame([s.__dict__ for s in data])

    st.rerun()


# Corresponds to tables within database.
class Table(StrEnum):
    STRINGS = "String Blacklist"
    HOTKEY = "Hotkey Blacklist"
    PAIR = "Hotkey String Pair Blacklist"
    BLACKLIST_DETECTION = "Blacklist Detection Log"
    KEYSTROKE_DETECTION = "Keystroke Detection Log"


# save table location
if "table_selection" not in st.session_state:
    st.session_state.table_selection = Table.STRINGS

table = st.selectbox("Select a table to view:", 
                     options=Table, 
                     key="table_selection")

match table:
    case Table.STRINGS:
        string_table = st.session_state.strings
        st.dataframe(string_table.style.format({"blocked": lambda x: "Yes" if x else "No"}), width="stretch", hide_index=True)

        with st.expander("Add New String:"):
            with st.form("new_string_form", clear_on_submit=True, width="stretch", height="content"):
                columns = st.columns(2)
                string = columns[0].text_input("String")
                blocked = columns[1].checkbox(label="Blacklisted")
                submitted = st.form_submit_button("Add String")
                if submitted:
                    query_service.add_string(string, blocked)
                    update_strings()

        
        if "string" in st.session_state.strings.columns:
            with st.expander("Remove String:"):
                delete_string = st.selectbox("Select a string to delete:", 
                                            options=st.session_state.strings["string"].tolist())
                if st.button("Delete", type="primary"):
                    query_service.remove_string(delete_string)
                    update_strings()
        
        
        
            
        
    case Table.HOTKEY:
        st.write("hotkeys")
        # hotkeys_table = query_service.get_strings()
        # st.dataframe(hotkeys_table, width="stretch", height=600)

        
    case Table.PAIR:
        st.write("pairs")
    case Table.BLACKLIST_DETECTION:
        st.write("blacklist log")
    case Table.KEYSTROKE_DETECTION:
        st.write("keystroke log")
    case _:
        st.write("Not implemented!")








