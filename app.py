import streamlit as st
import pandas as pd
import numpy as np
import json
import base64
import requests

st.set_page_config(
    page_title="Indoor UAV Part list",
    page_icon="🛩️",
    layout="wide"
)

# ==========================================
# 1. DATABASE & SESSION INITIALIZATION
# ==========================================

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

# Assign direct shortcuts so all downstream calculation code remains identical
MOTORS = st.session_state.MOTORS
FLIGHT_CONTROLLERS = st.session_state.FLIGHT_CONTROLLERS
SBCS = st.session_state.SBCS
INTEGRATED_BOARDS = st.session_state.INTEGRATED_BOARDS
FRAMES = st.session_state.FRAMES
BATTERIES = st.session_state.BATTERIES

# Remote GitHub commit handler
def commit_to_github(payload_dict, target_file="custom_database.json"):
    if "GITHUB_TOKEN" not in st.secrets or "GITHUB_REPO" not in st.secrets:
        return False, "GitHub credentials missing in st.secrets."

    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["GITHUB_REPO"]
    url = f"https://api.github.com/repos/{repo}/contents/{target_file}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    res = requests.get(url, headers=headers)
    sha = res.json().get("sha") if res.status_code == 200 else None

    b64_content = base64.b64encode(json.dumps(payload_dict, indent=2).encode("utf-8")).decode("utf-8")
    data = {"message": f"Update {target_file} from web UI", "content": b64_content}
    if sha:
        data["sha"] = sha

    put_res = requests.put(url, headers=headers, json=data)
    if put_res.status_code in [200, 201]:
        return True, "Successfully committed updates to GitHub repository."
    return False, f"API Error: {put_res.json().get('message', 'Failed to commit')}"

# ==========================================
# 2. APPLICATION LAYOUT
# ==========================================

st.title("UAV Trade Component Lists & Builder")
st.caption("Systems engineering evaluator for localized decentralized SLAM & RF/RSSI mapping platforms.")

tab_catalogs, tab_builder, tab_admin = st.tabs(["Component Catalogs", "Drone Builder", "Admin (Add Parts)"])

# ==========================================
# TAB 1: COMPONENT CATALOGS
# ==========================================
with tab_catalogs:
    st.subheader("Component Technical Specifications & Cost Tables")
    
    st.markdown("#### Single Board Computers (SBC)")
    st.dataframe(pd.DataFrame.from_dict(SBCS, orient="index"), column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗")}, use_container_width=True)
    
    st.markdown("#### Integrated Autonomy Boards")
    st.dataframe(pd.DataFrame.from_dict(INTEGRATED_BOARDS, orient="index"), column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗")}, use_container_width=True)
    
    st.markdown("#### Flight Controllers (FC)")
    st.dataframe(pd.DataFrame.from_dict(FLIGHT_CONTROLLERS, orient="index"), column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗")}, use_container_width=True)
    
    st.markdown("#### Brushless DC Motors")
    st.dataframe(pd.DataFrame.from_dict(MOTORS, orient="index"), column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗")}, use_container_width=True)
    
    st.markdown("#### Frame Kits")
    st.dataframe(pd.DataFrame.from_dict(FRAMES, orient="index"), column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗")}, use_container_width=True)
    
    st.markdown("#### Battery Packs")
    st.dataframe(pd.DataFrame.from_dict(BATTERIES, orient="index"), column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗")}, use_container_width=True)

# ==========================================
# TAB 3: ADMIN & PERSISTENCE
# ==========================================
with tab_admin:
    st.subheader("Database Management")
    
    # Check for pending notifications from a previous action and display them
    if "admin_notify" in st.session_state:
        if "⚠️" in st.session_state.admin_notify or "❌" in st.session_state.admin_notify:
            st.error(st.session_state.admin_notify)
        else:
            st.success(st.session_state.admin_notify)
        del st.session_state.admin_notify

    admin_pass = st.text_input("Enter Admin Password to unlock:", type="password")
    
    if admin_pass == st.secrets.get("ADMIN_PASSWORD", "local_test_pass"):
        st.success("Admin access granted.")
        
        # ------------------------------------------
        # 1. ADD COMPONENT SECTION
        # ------------------------------------------
        st.markdown("### Add New Component")
        st.caption("All fields marked with * are required.")
        
        target_category = st.selectbox("Target Category for Addition:", CATEGORIES, key="add_cat")
        
        with st.form("add_part_form", clear_on_submit=False):
            # --- COMMON ATTRIBUTES ---
            st.markdown("**General Information**")
            row1_col1, row1_col2 = st.columns([2, 2])
            new_comp_name = row1_col1.text_input("Component Model Name*", value="", placeholder="e.g., T-Motor F1507")
            buy_url = row1_col2.text_input("Vendor / Purchase URL*", value="", placeholder="https://...")
            
            row2_col1, row2_col2 = st.columns(2)
            price_egp = row2_col1.number_input("Price (EGP)*", min_value=0.0, value=None, step=50.0)
            price_usd = row2_col2.number_input("Price (USD)*", min_value=0.0, value=None, step=1.0)
            
            st.markdown("---")
            st.markdown(f"**{target_category} Specifications**")
            
            new_entry = {}
            
            # --- DYNAMIC CELLS PER CATEGORY ---
            if target_category == "MOTORS":
                m_c1, m_c2, m_c3 = st.columns(3)
                weight = m_c1.number_input("Weight (g)*", min_value=0.1, value=None, step=0.5)
                thrust = m_c2.number_input("Max Thrust (g)*", min_value=1.0, value=None, step=10.0)
                kv = m_c3.number_input("KV Rating*", min_value=100, value=None, step=50)
                
                m_c4, m_c5, m_c6 = st.columns(3)
                stator = m_c4.text_input("Stator Size*", value="", placeholder="22 x 07 mm")
                prop = m_c5.text_input("Supported Propeller Size*", value="", placeholder="5\"")
                eff = m_c6.number_input("Hover Efficiency (g/W)*", min_value=1.0, value=None, step=0.1)
                
                m_c7, m_c8 = st.columns([2, 1])
                source = m_c7.text_input("Source / Retailer Type*", value="", placeholder="Global / FPV shops")
                cells = m_c8.multiselect("Supported Cell Counts (S)*", options=[1, 2, 3, 4, 5, 6, 8], default=[])
                notes = st.text_input("Engineering Notes (Optional)", value="")
                
                new_entry = {
                    "stator": stator, "weight": weight, "kv": int(kv) if kv is not None else None, "cells": cells,
                    "prop": prop, "thrust": thrust, "source": source,
                    "price_egp": price_egp, "price_usd": price_usd,
                    "efficiency_hover_gw": eff, "notes": notes, "buy_url": buy_url
                }
                
            elif target_category == "FRAMES":
                f_c1, f_c2, f_c3 = st.columns(3)
                wheelbase_mm = f_c1.number_input("Wheelbase (mm)*", min_value=50, value=None, step=10)
                weight_g = f_c2.number_input("Bare Frame Weight (g)*", min_value=1.0, value=None, step=5.0)
                payload_limit_g = f_c3.number_input("Max Structural Payload (g)*", min_value=10.0, value=None, step=10.0)
                
                f_c4, f_c5, f_c6 = st.columns(3)
                motor_count = f_c4.number_input("Motor Count*", min_value=3, max_value=8, value=None, step=1)
                max_prop = f_c5.text_input("Max Propeller Size*", value="", placeholder="5\"")
                ducted = f_c6.checkbox("Enclosed / Ducted Props?", value=False)
                notes = st.text_input("Engineering Notes (Optional)", value="")
                
                new_entry = {
                    "wheelbase_mm": int(wheelbase_mm) if wheelbase_mm is not None else None, "weight_g": weight_g,
                    "payload_limit_g": payload_limit_g, "motor_count": int(motor_count) if motor_count is not None else None,
                    "max_prop": max_prop, "ducted": ducted,
                    "price_egp": price_egp, "price_usd": price_usd,
                    "notes": notes, "buy_url": buy_url
                }
                
            elif target_category == "BATTERIES":
                b_c1, b_c2, b_c3 = st.columns(3)
                cells_count = b_c1.number_input("Cell Count (S)*", min_value=1, max_value=12, value=None, step=1)
                mah = b_c2.number_input("Capacity (mAh)*", min_value=100, value=None, step=100)
                voltage = b_c3.number_input("Nominal Voltage (V)*", min_value=1.0, value=None, step=0.1)
                
                b_c4, b_c5, b_c6 = st.columns(3)
                weight_g = b_c4.number_input("Weight (g)*", min_value=1.0, value=None, step=5.0)
                wh = b_c5.number_input("Watt-Hours (Wh)*", min_value=1.0, value=None, step=0.5)
                c_rating = b_c6.number_input("C-Rating*", min_value=1, value=None, step=5)
                
                b_c7, b_c8 = st.columns(2)
                dimensions = b_c7.text_input("Dimensions (L x W x H mm)*", value="", placeholder="100 × 35 × 25 mm")
                notes = b_c8.text_input("Engineering Notes (Optional)", value="")
                
                new_entry = {
                    "cells": int(cells_count) if cells_count is not None else None, "mah": int(mah) if mah is not None else None, 
                    "weight_g": weight_g, "c_rating": int(c_rating) if c_rating is not None else None, 
                    "voltage": voltage, "wh": wh, "price_egp": price_egp, "price_usd": price_usd,
                    "dimensions": dimensions, "notes": notes, "buy_url": buy_url
                }
                
            elif target_category == "FLIGHT_CONTROLLERS":
                fc_c1, fc_c2 = st.columns(2)
                mcu = fc_c1.text_input("MCU Model*", value="", placeholder="STM32H743")
                weight = fc_c2.number_input("Weight (g)*", min_value=0.5, value=None, step=0.5)
                
                fc_c3, fc_c4 = st.columns(2)
                dim = fc_c3.text_input("Dimensions (mm)*", value="", placeholder="36 x 36 x 5 mm")
                firmware = fc_c4.text_input("Supported Firmware*", value="", placeholder="PX4, ArduPilot")
                notes = st.text_input("Engineering Notes (Optional)", value="")
                
                new_entry = {
                    "mcu": mcu, "weight": weight, "dim": dim, "firmware": firmware,
                    "price_egp": price_egp, "price_usd": price_usd,
                    "notes": notes, "buy_url": buy_url
                }
                
            elif target_category == "SBCS":
                s_c1, s_c2, s_c3 = st.columns(3)
                cpu = s_c1.text_input("Processor / Memory*", value="", placeholder="Quad-core ARM / 8GB")
                ai_tops = s_c2.number_input("AI TOPS*", min_value=0.0, value=None, step=1.0)
                power_w = s_c3.number_input("Average Power Draw (W)*", min_value=0.1, value=None, step=0.5)
                
                s_c4, s_c5 = st.columns(2)
                weight = s_c4.number_input("Weight (g)*", min_value=1.0, value=None, step=1.0)
                dim = s_c5.text_input("Dimensions (mm)*", value="", placeholder="85 x 56 x 15 mm")
                best_for = st.text_input("Primary Workload / Best For*", value="", placeholder="ROS 2 SLAM Nodes")
                
                new_entry = {
                    "cpu": cpu, "ai_tops": ai_tops, "weight": weight, "dim": dim,
                    "power_w": power_w, "price_egp": price_egp, "price_usd": price_usd,
                    "best_for": best_for, "buy_url": buy_url
                }
                
            elif target_category == "INTEGRATED_BOARDS":
                ib_c1, ib_c2 = st.columns(2)
                arch = ib_c1.text_input("Architecture Type*", value="", placeholder="Unified Carrier")
                compute = ib_c2.text_input("Onboard Compute Engine*", value="", placeholder="Jetson Orin")
                
                ib_c3, ib_c4, ib_c5 = st.columns(3)
                weight = ib_c3.number_input("Weight (g)*", min_value=1.0, value=None, step=1.0)
                power_w = ib_c4.number_input("Average Power Draw (W)*", min_value=0.5, value=None, step=0.5)
                dim = ib_c5.text_input("Dimensions (mm)*", value="", placeholder="100 x 80 x 25 mm")
                best_for = st.text_input("Primary Workload / Best For*", value="")
                
                new_entry = {
                    "arch": arch, "compute": compute, "dim": dim, "weight": weight,
                    "power_w": power_w, "price_egp": price_egp, "price_usd": price_usd,
                    "best_for": best_for, "buy_url": buy_url
                }
                
            submitted = st.form_submit_button("Add Component to Active Session")
            
            if submitted:
                # Validation Logic
                missing_fields = []
                if not new_comp_name.strip(): missing_fields.append("Component Model Name")
                if not buy_url.strip(): missing_fields.append("Vendor URL")
                if price_egp is None: missing_fields.append("Price (EGP)")
                if price_usd is None: missing_fields.append("Price (USD)")
                
                for key, val in new_entry.items():
                    if key not in ["notes", "ducted"]:
                        if val is None or val == "" or val == []:
                            missing_fields.append(key.replace("_", " ").title())
                
                if missing_fields:
                    st.error(f"⚠️ **Validation Failed!** Please fill in the following required fields: {', '.join(missing_fields)}")
                else:
                    st.session_state[target_category][new_comp_name.strip()] = new_entry
                    st.session_state.admin_notify = f"✅ Added '{new_comp_name.strip()}' to {target_category} successfully!"
                    st.rerun()

        # ------------------------------------------
        # 2. REMOVE COMPONENT SECTION
        # ------------------------------------------
        st.markdown("---")
        st.markdown("### Remove Existing Component")
        st.caption("Select a category and choose a component to delete from the active database.")
        
        del_category = st.selectbox("Category to Delete From:", CATEGORIES, key="del_cat")
        available_items = list(st.session_state[del_category].keys())
        
        if available_items:
            del_c1, del_c2 = st.columns([3, 1], gap="small")
            with del_c1:
                item_to_delete = st.selectbox("Select Component to Remove:", available_items, label_visibility="collapsed")
            with del_c2:
                if st.button("🗑️ Delete Component", use_container_width=True):
                    st.session_state[del_category].pop(item_to_delete, None)
                    st.session_state.admin_notify = f"🗑️ Removed '{item_to_delete}' from {del_category} successfully."
                    st.rerun()
        else:
            st.info(f"No components found in {del_category}.")
                    
        # ------------------------------------------
        # 3. CLOUD REPOSITORY SYNC
        # ------------------------------------------
        st.markdown("---")
        st.markdown("#### Cloud Repository Sync")
        st.caption("Push additions or removals permanently to the JSON file on GitHub.")
        if st.button("🚀 Commit All Changes to GitHub Repository"):
            with st.spinner("Pushing database to GitHub..."):
                full_catalog = {cat: st.session_state[cat] for cat in CATEGORIES}
                success, msg = commit_to_github(full_catalog)
                if success:
                    st.session_state.admin_notify = f"☁️ {msg}"
                    st.rerun()
                else:
                    st.error(msg)
    elif admin_pass:
        st.error("❌ Incorrect password. Access denied.")