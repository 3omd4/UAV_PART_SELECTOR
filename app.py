import streamlit as st
import json
from tabs import catalogs, builder, admin, combinations

# Restored the corrupted page configuration and missing quotes
st.set_page_config(
    page_title="Indoor UAV Part list",
    page_icon="✈️",
    layout="wide"
)

# ==========================================
# DATABASE & SESSION INITIALIZATION
# ==========================================
# Removed the unused "WEIGHT_PRESETS" category to prevent memory bloat
CATEGORIES = ["MOTORS", "FLIGHT_CONTROLLERS", "SBCS", "INTEGRATED_BOARDS", "FRAMES", "BATTERIES"]

# Load permanent component database from JSON file
try:
    with open("custom_database.json", "r", encoding="utf-8") as f:
        db_from_file = json.load(f)
except Exception:
    db_from_file = {}

# Initialize session state for each catalog category
for cat in CATEGORIES:
    if cat not in st.session_state:
        st.session_state[cat] = db_from_file.get(cat, {})

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