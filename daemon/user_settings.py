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


if "hotkeys" not in st.session_state:
    data = query_service.get_hotkeys()
    st.session_state.hotkeys = pd.DataFrame([h.__dict__ for h in data])

def update_hotkeys():
    data = query_service.get_hotkeys()
    st.session_state.hotkeys = pd.DataFrame([h.__dict__ for h in data])
    st.rerun()



# Corresponds to tables within database.
class Table(StrEnum):
    STRINGS = "String Blacklist"
    HOTKEY = "Hotkey Blacklist"
    PAIR = "Hotkey String Pair Blacklist"
    BLACKLIST_DETECTION = "Blacklist Detection Log"
    KEYSTROKE_DETECTION = "Keystroke Speed Detection Log"


# save table location
if "table_selection" not in st.session_state:
    st.session_state.table_selection = Table.STRINGS

table = st.selectbox("Select a table to view:", 
                     options=Table, 
                     key="table_selection")

match table:
    case Table.STRINGS:
        string_table = st.session_state.strings

        # Dataframe + converting boolean values to "Yes" or "No"
        st.dataframe(
            string_table.style.format({"blocked": lambda x: "Yes" if x else "No"}), 
            width="stretch", 
            hide_index=True)

        # Add String
        with st.expander("Add New String:"):
            with st.form("new_string_form", clear_on_submit=True, width="stretch", height="content"):
                columns = st.columns(2)
                string = columns[0].text_input("String")
                blocked = columns[1].checkbox(label="Blacklisted")
                submitted = st.form_submit_button("Add String", type="primary", icon=":material/add:")

                if submitted:
                    query_service.add_string(string, blocked)
                    update_strings()

        # Update/Delete String
        if "string" in st.session_state.strings.columns:
            # tuple format: {id (int), string (str), blocked (bool/int)}
            string_tuples = list(string_table.itertuples(index=False, name=None))
        
            with st.expander("Update or Delete String:"):
                columns = st.columns(2)
                update_string = columns[0].selectbox(
                    "Select a string to update:", 
                    options=string_tuples,
                    format_func=lambda x: f"{x[1]} ({'Blacklisted' if x[2] else 'Not Blacklisted'})")
                
                blocked = columns[1].checkbox(label="Blacklist", value=update_string[2])

                button_columns = st.columns([1, 2, 1])
                if button_columns[0].button("Update", type="primary", icon=":material/edit_square:"):
                    query_service.update_string_by_id(update_string[0], blocked)
                    update_strings()

                if button_columns[2].button("Delete", type="primary", icon=":material/delete_forever:"):
                    query_service.remove_string_by_id(update_string[0])
                    update_strings()
                
                
        
        
    case Table.HOTKEY:
        hotkey_table = st.session_state.hotkeys

        # Dataframe + converting boolean values to "Yes" or "No"
        st.dataframe(
            hotkey_table.style.format({"blocked": lambda x: "Yes" if x else "No"}),
            width="stretch",
            hide_index=True)

        # Add Hotkey
        with st.expander("Add New Hotkey:"):
            with st.form("new_hotkey_form", clear_on_submit=True):
                columns = st.columns(2)
                hotkey = columns[0].text_input("Hotkey")
                blocked = columns[1].checkbox("Blacklisted")
                submitted = st.form_submit_button("Add Hotkey", type="primary", icon=":material/add:")

                if submitted:
                    query_service.add_hotkey(hotkey, blocked)
                    update_hotkeys()


        if "hotkey" in hotkey_table.columns:
            # tuple format: {id (int), hotkey (str), blocked (bool/int)}
            hotkey_tuples = list(hotkey_table.itertuples(index=False, name=None))

            # Update/Delete Hotkey
            with st.expander("Update or Delete Hotkey:"):
                columns = st.columns(2)
                update_hotkey = columns[0].selectbox(
                    "Select a hotkey to update:",
                    options=hotkey_tuples,
                    format_func=lambda x: f"{x[1]} ({'Blacklisted' if x[2] else 'Not Blacklisted'})")

                blocked = columns[1].checkbox("Blacklist", value=update_hotkey[2])

                button_columns = st.columns([1, 2, 1])
                if button_columns[0].button("Update Hotkey", type="primary", icon=":material/edit_square:"):
                    query_service.update_hotkey_by_id(update_hotkey[0], blocked)
                    update_hotkeys()

                if button_columns[2].button("Delete Hotkey", type="primary", icon=":material/delete_forever:"):
                    query_service.remove_hotkey_by_id(update_hotkey[0])
                    update_hotkeys()



        
    case Table.PAIR:
        if "pairs" not in st.session_state:
            data = query_service.get_pairs()
            st.session_state.pairs = pd.DataFrame([p.__dict__ for p in data])

        def update_pairs():
            data = query_service.get_pairs()
            st.session_state.pairs = pd.DataFrame([p.__dict__ for p in data])
            st.rerun()

        string_table = st.session_state.strings
        hotkey_table = st.session_state.hotkeys
        pair_table = st.session_state.pairs
        

        # Dataframe + converting boolean values to "Yes" or "No"
        st.dataframe(
            pair_table.style.format({"blocked": lambda x: "Yes" if x else "No"}), 
            width="stretch", 
            hide_index=True)
        
        # Add Pair
        if "hotkey" in hotkey_table.columns and "string" in st.session_state.strings.columns:
            # tuple format: {id (int), string (str), blocked (bool/int)}
            string_tuples = list(string_table.itertuples(index=False, name=None))
            # tuple format: {id (int), hotkey (str), blocked (bool/int)}
            hotkey_tuples = list(hotkey_table.itertuples(index=False, name=None))

            with st.expander("Add New Hotkey-String Pair:"):
                with st.form("new_hotkey_form", clear_on_submit=True):
                    columns = st.columns(3)
                    hotkey = columns[0].selectbox("Select a hotkey:", 
                                                  options=hotkey_tuples,
                                                  format_func=lambda x: f"{x[1]}")
                    string = columns[1].selectbox("Select a string:", 
                                                  options=string_tuples,
                                                  format_func=lambda x: f"{x[1]}")
                    blocked = columns[2].checkbox("Blacklist")
                    submitted = st.form_submit_button("Add Pair", type="primary", icon=":material/add:")

                    if submitted:
                        query_service.add_pair(hotkey_id=hotkey[0], string_id=string[0], blocked=blocked)
                        update_pairs()
        else:
            st.text("At least one hotkey and string must be present before pair can be added!")

        # Update/Delete Pair
        if "pair_id" in pair_table.columns:
            # tuple format: {id (int), hotkey_id (int), hotkey (str), string_id (int), string (str), blocked (bool/int)}
            pair_tuples = list(pair_table.itertuples(index=False, name=None))

            with st.expander("Update or Delete Pair:"):
                columns = st.columns(2)
                update_pair = columns[0].selectbox(
                    "Select a pair to update:",
                    options=pair_tuples,
                    format_func=lambda x: f"{x[2]} + {x[4]} ({'Blacklisted' if x[5] else 'Not Blacklisted'})")

                blocked = columns[1].checkbox("Blacklist", value=update_pair[5])

                button_columns = st.columns([1, 2, 1])
                if button_columns[0].button("Update Pair", type="primary", icon=":material/edit_square:"):
                    query_service.update_pair_by_id(update_pair[0], blocked)
                    update_pairs()

                if button_columns[2].button("Delete Pair", type="primary", icon=":material/delete_forever:"):
                    query_service.remove_pair_by_id(update_pair[0])
                    update_pairs()
            

        

    case Table.BLACKLIST_DETECTION:
        if "blacklist_detections" not in st.session_state:
            data = query_service.get_blacklist_detections()
            st.session_state.blacklist_detections = pd.DataFrame([bd.__dict__ for bd in data])

        def update_blacklist_detections():
            data = query_service.get_blacklist_detections()
            st.session_state.blacklist_detections = pd.DataFrame([bd.__dict__ for bd in data])
            st.rerun()

        blacklist_detection_table = st.session_state.blacklist_detections

        header = st.columns([0.5, 2.5, 2.5, 3.5, 1])
        header[0].markdown("**ID**")
        header[1].markdown("**Hotkey**")
        header[2].markdown("**String**")
        header[3].markdown("**Detected At**")
        header[4].markdown("**Delete**")

        for idx, row in blacklist_detection_table.iterrows():
            cols = st.columns([0.5, 2.5, 2.5, 3.5, 1])

            cols[0].write(row["detection_id"])
            cols[1].write(row["hotkey"])
            cols[2].write(row["string"])
            cols[3].write(row["detected_at"])

            delete_id = row["detection_id"]
            delete_detection = row['detection_id']
            if cols[4].button("", type="primary", icon=":material/delete_forever:", key=delete_detection, width=40):
                query_service.remove_blacklist_detection(delete_detection)
                update_blacklist_detections()

        # OLD FORMAT
        # # Dataframe + converting boolean values to "Yes" or "No"
        # st.dataframe(
        #     blacklist_detection_table.style.format({"blocked": lambda x: "Yes" if x else "No"}),
        #     column_config={
        #         "hotkey_id": st.column_config.NumberColumn(format="%.0f"),
        #         "string_id": st.column_config.NumberColumn(format="%.0f"),
        #         "pair_id": st.column_config.NumberColumn(format="%.0f")},
        #     width="stretch", 
        #     hide_index=True)
        
        # # Delete Detection Entry
        # if "detection_id" in blacklist_detection_table.columns:
        #     # tuple format: {detection_id, hotkey_id, hotkey, string_id, string, pair_id, detected_at}: <Integer, Integer, String, Integer, String, Integer, String, String>
        #     detection_tuples = list(blacklist_detection_table.itertuples(index=False, name=None))

        #     with st.expander("Delete Log Entry:"):
        #         delete_detection = st.selectbox(
        #             "Select a pair to update:",
        #             options=detection_tuples,
        #             format_func=lambda x: f"ID {x[0]} at {x[6]}")

        #         if st.button("Delete Detection", type="primary", icon=":material/delete_forever:"):
        #             query_service.remove_blacklist_detection(delete_detection[0])
        #             update_blacklist_detections()




    case Table.KEYSTROKE_DETECTION:
        if "speed_detections" not in st.session_state:
            data = query_service.get_speed_detections()
            st.session_state.speed_detections = pd.DataFrame([sd.__dict__ for sd in data])

        def update_speed_detections():
            data = query_service.get_speed_detections()
            st.session_state.speed_detections = pd.DataFrame([sd.__dict__ for sd in data])
            st.rerun()

        speed_detection_table = st.session_state.speed_detections

        header = st.columns([1, 5, 3, 1])
        header[0].markdown("**ID**")
        header[1].markdown("**Info**")
        header[2].markdown("**Detected At**")
        header[3].markdown("**Delete**")

        for idx, row in speed_detection_table.iterrows():
            cols = st.columns([1, 5, 3, 1])

            cols[0].write(row["detection_id"])
            cols[1].write(row["info"])
            cols[2].write(row["detected_at"])

            delete_detection = row['detection_id']
            if cols[3].button("", type="primary", icon=":material/delete_forever:", key=delete_detection, width=40):
                query_service.remove_speed_detection(delete_detection)
                update_speed_detections()




    case _:
        st.write("Not implemented!")


