import streamlit as st
import json
from tabs import catalogs, builder, admin, combinations

st.set_page_config(
    page_title="Indoor UAV Part list",
    page_icon="🛸",
    layout="wide"
)

# ==========================================
#DATABASE & SESSION INITIALIZATION
# ==========================================

CATEGORIES = ["MOTORS", "FLIGHT_CONTROLLERS", "SBCS", "INTEGRATED_BOARDS", "FRAMES", "BATTERIES", "WEIGHT_PRESETS"]

# Load permanent component database from JSON file
try:
    with open("custom_database.json", "r", encoding="utf-8") as f:
        db_from_file = json.load(f)
except Exception:
    db_from_file = {}

# Initialize session state for each category
for cat in CATEGORIES:
    if cat not in st.session_state:
        st.session_state[cat] = db_from_file.get(cat, {})




# Function to load a specific combination into the Drone Builder's session state
def load_into_builder(row):
    st.session_state["builder_frame"] = row["Frame"]
    st.session_state["builder_motor"] = row["Motor"]
    st.session_state["builder_battery"] = row["Battery"]
    
    avionics = row["Avionics"]
    if " + " in avionics:
        st.session_state["builder_arch"] = "Modular (Separate FC + SBC)"
        st.session_state["builder_fc"] = avionics.split(" + ")[0]
        st.session_state["builder_sbc"] = avionics.split(" + ")[1]
    else:
        st.session_state["builder_arch"] = "Integrated Board (All-in-One)"
        st.session_state["builder_int_board"] = avionics
        
    st.session_state["build_loaded_success"] = True

# ==========================================
# APPLICATION LAYOUT
# ==========================================
st.title("Indoor UAV Components List & Builder")
st.caption("Systems engineering evaluator for localized decentralized SLAM & RF/RSSI mapping platforms.")

tab_catalogs, tab_builder, tab_admin, tab_combinations = st.tabs([
    "Component Catalogs", "Drone Builder", "Admin (Add Parts)", "Valid Combinations"
])

# Route each tab to its respective module function
with tab_catalogs:
    catalogs.render_catalogs_tab()

with tab_builder:
    builder.render_builder_tab()

with tab_admin:
    admin.render_admin_tab()

with tab_combinations:
    combinations.render_combinations_tab()