import streamlit as st
import pandas as pd
import json
from utils import commit_to_github, sync_external_data

def render_admin_tab():
    CATEGORIES = ["MOTORS", "FLIGHT_CONTROLLERS", "SBCS", "INTEGRATED_BOARDS", "FRAMES", "BATTERIES"]
    
    st.subheader("Database Management & Cloud Synchronization")
    st.caption("Add, modify, or deprecate hardware components. Changes persist in the active session and can be pushed to the central repository.")
    
    if "admin_notify" in st.session_state:
        if "❌" in st.session_state.admin_notify or "Validation" in st.session_state.admin_notify:
            # Restored corrupted emojis
            st.error(st.session_state.admin_notify, icon="⚠️")
        else:
            st.success(st.session_state.admin_notify, icon="✅")
        del st.session_state.admin_notify

    admin_pass = st.text_input("Enter System Admin Password to unlock:", type="password")
    
    if admin_pass == st.secrets.get("ADMIN_PASSWORD", "local_test_pass"):
        st.success("Authentication successful. Engineering database unlocked.")
        
        tab_add, tab_edit, tab_del, tab_sync = st.tabs([
            "➕ Add Component", 
            "✏️ Edit Component", 
            "🗑️ Remove Component", 
            "☁️ Cloud Sync & Audit"
        ])
        
        # ==========================================
        # 1. ADD COMPONENT SECTION
        # ==========================================
        with tab_add:
            st.markdown("### Provision New Hardware")
            target_category = st.selectbox("Target Category:", CATEGORIES, key="add_cat")
            
            with st.form("add_part_form", clear_on_submit=False):
                st.markdown("**General Information**")
                row1_col1, row1_col2 = st.columns([2, 2])
                new_comp_name = row1_col1.text_input("Component Model Name*", placeholder="e.g., T-Motor F1507")
                buy_url = row1_col2.text_input("Vendor / Purchase URL*", placeholder="https://...")
                
                row2_col1, row2_col2 = st.columns(2)
                price_egp = row2_col1.number_input("Price (EGP)*", min_value=0.0, value=None, step=50.0)
                price_usd = row2_col2.number_input("Price (USD)*", min_value=0.0, value=None, step=1.0)
                
                st.divider()
                st.markdown(f"**{target_category} Specifications**")
                new_entry = {}
                
                if target_category == "MOTORS":
                    m_c1, m_c2, m_c3 = st.columns(3)
                    weight = m_c1.number_input("Weight (g)*", min_value=0.1, value=None, step=0.5)
                    thrust = m_c2.number_input("Max Thrust (g)*", min_value=1.0, value=None, step=10.0)
                    kv = m_c3.number_input("KV Rating*", min_value=100, value=None, step=50)
                    m_c4, m_c5, m_c6 = st.columns(3)
                    stator = m_c4.text_input("Stator Size*", placeholder="22 x 07 mm")
                    prop = m_c5.text_input("Supported Propeller*", placeholder="5\"")
                    eff = m_c6.number_input("Hover Efficiency (g/W)*", min_value=1.0, value=None, step=0.1)
                    m_c7, m_c8 = st.columns([2, 1])
                    source = m_c7.text_input("Retailer Type*", placeholder="Global / FPV shops")
                    cells = m_c8.multiselect("Cell Counts (S)*", options=[1, 2, 3, 4, 5, 6, 8], default=[])
                    notes = st.text_input("Engineering Notes (Optional)")
                    new_entry = {
                        "stator": stator, "weight": weight, "kv": int(kv) if kv is not None else None, "cells": cells,
                        "prop": prop, "thrust": thrust, "source": source, "price_egp": price_egp, "price_usd": price_usd,
                        "efficiency_hover_gw": eff, "notes": notes, "buy_url": buy_url
                    }
                elif target_category == "FRAMES":
                    f_c1, f_c2, f_c3 = st.columns(3)
                    wheelbase_mm = f_c1.number_input("Wheelbase (mm)*", min_value=50, value=None, step=10)
                    weight_g = f_c2.number_input("Bare Weight (g)*", min_value=1.0, value=None, step=5.0)
                    payload_limit_g = f_c3.number_input("Max Structural Payload (g)*", min_value=10.0, value=None, step=10.0)
                    f_c4, f_c5, f_c6 = st.columns(3)
                    motor_count = f_c4.number_input("Motor Count*", min_value=3, max_value=8, value=None, step=1)
                    max_prop = f_c5.text_input("Max Propeller*", placeholder="5\"")
                    ducted = f_c6.checkbox("Enclosed / Ducted Props?")
                    notes = st.text_input("Engineering Notes (Optional)")
                    new_entry = {
                        "wheelbase_mm": int(wheelbase_mm) if wheelbase_mm is not None else None, "weight_g": weight_g,
                        "payload_limit_g": payload_limit_g, "motor_count": int(motor_count) if motor_count is not None else None,
                        "max_prop": max_prop, "ducted": ducted, "price_egp": price_egp, "price_usd": price_usd,
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
                    dimensions = b_c7.text_input("Dimensions (L x W x H mm)*", placeholder="100 x 35 x 25 mm")
                    notes = b_c8.text_input("Engineering Notes (Optional)")
                    new_entry = {
                        "cells": int(cells_count) if cells_count is not None else None, "mah": int(mah) if mah is not None else None,
                        "weight_g": weight_g, "c_rating": int(c_rating) if c_rating is not None else None,
                        "voltage": voltage, "wh": wh, "price_egp": price_egp, "price_usd": price_usd,
                        "dimensions": dimensions, "notes": notes, "buy_url": buy_url
                    }
                elif target_category == "FLIGHT_CONTROLLERS":
                    fc_c1, fc_c2 = st.columns(2)
                    mcu = fc_c1.text_input("MCU Target*", placeholder="STM32H743")
                    weight = fc_c2.number_input("Weight (g)*", min_value=0.5, value=None, step=0.5)
                    fc_c3, fc_c4 = st.columns(2)
                    dim = fc_c3.text_input("Dimensions (mm)*", placeholder="36 x 36 x 5 mm")
                    firmware = fc_c4.text_input("Supported Firmware*", placeholder="PX4, ArduPilot")
                    notes = st.text_input("Engineering Notes (Optional)")
                    new_entry = {
                        "mcu": mcu, "weight": weight, "dim": dim, "firmware": firmware,
                        "price_egp": price_egp, "price_usd": price_usd, "notes": notes, "buy_url": buy_url
                    }
                elif target_category == "SBCS":
                    s_c1, s_c2, s_c3 = st.columns(3)
                    cpu = s_c1.text_input("Processor / RAM*", placeholder="Quad-core ARM / 8GB")
                    ai_tops = s_c2.number_input("AI Compute (TOPS)*", min_value=0.0, value=None, step=1.0)
                    power_w = s_c3.number_input("Avg Power Draw (W)*", min_value=0.1, value=None, step=0.5)
                    s_c4, s_c5 = st.columns(2)
                    weight = s_c4.number_input("Weight (g)*", min_value=1.0, value=None, step=1.0)
                    dim = s_c5.text_input("Dimensions (mm)*", placeholder="85 x 56 x 15 mm")
                    best_for = st.text_input("Primary Workload / Best For*", placeholder="ROS 2 SLAM Nodes")
                    new_entry = {
                        "cpu": cpu, "ai_tops": ai_tops, "weight": weight, "dim": dim,
                        "power_w": power_w, "price_egp": price_egp, "price_usd": price_usd,
                        "best_for": best_for, "buy_url": buy_url
                    }
                elif target_category == "INTEGRATED_BOARDS":
                    ib_c1, ib_c2 = st.columns(2)
                    arch = ib_c1.text_input("Architecture Type*", placeholder="Unified Carrier")
                    compute = ib_c2.text_input("Compute Engine*", placeholder="Jetson Orin")
                    ib_c3, ib_c4, ib_c5 = st.columns(3)
                    weight = ib_c3.number_input("Weight (g)*", min_value=1.0, value=None, step=1.0)
                    power_w = ib_c4.number_input("Avg Power Draw (W)*", min_value=0.5, value=None, step=0.5)
                    dim = ib_c5.text_input("Dimensions (mm)*", placeholder="100 x 80 x 25 mm")
                    best_for = st.text_input("Primary Workload / Best For*")
                    new_entry = {
                        "arch": arch, "compute": compute, "dim": dim, "weight": weight,
                        "power_w": power_w, "price_egp": price_egp, "price_usd": price_usd,
                        "best_for": best_for, "buy_url": buy_url
                    }
                    
                submitted = st.form_submit_button("Add Component to Database", type="primary")
                if submitted:
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
                        st.error(f"❌ **Validation Failed:** Missing required inputs: {', '.join(missing_fields)}")
                    else:
                        st.session_state[target_category][new_comp_name.strip()] = new_entry
                        st.session_state.admin_notify = f"Successfully added '{new_comp_name.strip()}' to {target_category}."
                        st.rerun()

        # ==========================================
        # 2. EDIT COMPONENT SECTION
        # ==========================================
        with tab_edit:
            st.markdown("### Modify Existing Hardware")
            edit_category = st.selectbox("Select Category:", CATEGORIES, key="edit_cat")
            edit_available_items = list(st.session_state[edit_category].keys())
            
            if edit_available_items:
                item_to_edit = st.selectbox("Select Component to Edit:", edit_available_items, key="edit_item")
                cur_data = st.session_state[edit_category][item_to_edit]
                
                with st.form("edit_part_form", clear_on_submit=False):
                    st.markdown("**General Information**")
                    e_r1_c1, e_r1_c2 = st.columns([2, 2])
                    edit_comp_name = e_r1_c1.text_input("Component Model Name*", value=item_to_edit)
                    edit_url = e_r1_c2.text_input("Vendor / Purchase URL*", value=cur_data.get("buy_url", ""))
                    
                    e_r2_c1, e_r2_c2 = st.columns(2)
                    edit_price_egp = e_r2_c1.number_input("Price (EGP)*", min_value=0.0, value=float(cur_data.get("price_egp", 0.0)), step=50.0)
                    edit_price_usd = e_r2_c2.number_input("Price (USD)*", min_value=0.0, value=float(cur_data.get("price_usd", 0.0)), step=1.0)
                    
                    st.divider()
                    st.markdown(f"**{edit_category} Specifications**")
                    edit_entry = {}
                    
                    if edit_category == "MOTORS":
                        em_c1, em_c2, em_c3 = st.columns(3)
                        e_weight = em_c1.number_input("Weight (g)*", min_value=0.1, value=float(cur_data.get("weight", 30.0)), step=0.5)
                        e_thrust = em_c2.number_input("Max Thrust (g)*", min_value=1.0, value=float(cur_data.get("thrust", 1200.0)), step=10.0)
                        e_kv = em_c3.number_input("KV Rating*", min_value=100, value=int(cur_data.get("kv", 1800)), step=50)
                        em_c4, em_c5, em_c6 = st.columns(3)
                        e_stator = em_c4.text_input("Stator Size*", value=cur_data.get("stator", ""))
                        e_prop = em_c5.text_input("Supported Propeller*", value=cur_data.get("prop", ""))
                        e_eff = em_c6.number_input("Hover Efficiency (g/W)*", min_value=1.0, value=float(cur_data.get("efficiency_hover_gw", 7.0)), step=0.1)
                        em_c7, em_c8 = st.columns([2, 1])
                        e_source = em_c7.text_input("Retailer Type*", value=cur_data.get("source", ""))
                        e_cells = em_c8.multiselect("Cell Counts (S)*", options=[1, 2, 3, 4, 5, 6, 8], default=cur_data.get("cells", []))
                        e_notes = st.text_input("Engineering Notes (Optional)", value=cur_data.get("notes", ""))
                        edit_entry = {
                            "stator": e_stator, "weight": e_weight, "kv": int(e_kv), "cells": e_cells,
                            "prop": e_prop, "thrust": e_thrust, "source": e_source, "price_egp": edit_price_egp,
                            "price_usd": edit_price_usd, "efficiency_hover_gw": e_eff, "notes": e_notes, "buy_url": edit_url
                        }
                    elif edit_category == "FRAMES":
                        ef_c1, ef_c2, ef_c3 = st.columns(3)
                        e_wheelbase_mm = ef_c1.number_input("Wheelbase (mm)*", min_value=50, value=int(cur_data.get("wheelbase_mm", 330)), step=10)
                        e_weight_g = ef_c2.number_input("Bare Weight (g)*", min_value=1.0, value=float(cur_data.get("weight_g", 150.0)), step=5.0)
                        e_payload_limit_g = ef_c3.number_input("Max Structural Payload (g)*", min_value=10.0, value=float(cur_data.get("payload_limit_g", 400.0)), step=10.0)
                        ef_c4, ef_c5, ef_c6 = st.columns(3)
                        e_motor_count = ef_c4.number_input("Motor Count*", min_value=3, max_value=8, value=int(cur_data.get("motor_count", 4)), step=1)
                        e_max_prop = ef_c5.text_input("Max Propeller*", value=cur_data.get("max_prop", ""))
                        e_ducted = ef_c6.checkbox("Enclosed / Ducted Props?", value=bool(cur_data.get("ducted", False)))
                        e_notes = st.text_input("Engineering Notes (Optional)", value=cur_data.get("notes", ""))
                        edit_entry = {
                            "wheelbase_mm": int(e_wheelbase_mm), "weight_g": e_weight_g, "payload_limit_g": e_payload_limit_g,
                            "motor_count": int(e_motor_count), "max_prop": e_max_prop, "ducted": e_ducted,
                            "price_egp": edit_price_egp, "price_usd": edit_price_usd, "notes": e_notes, "buy_url": edit_url
                        }
                    elif edit_category == "BATTERIES":
                        eb_c1, eb_c2, eb_c3 = st.columns(3)
                        e_cells_count = eb_c1.number_input("Cell Count (S)*", min_value=1, max_value=12, value=int(cur_data.get("cells", 4)), step=1)
                        e_mah = eb_c2.number_input("Capacity (mAh)*", min_value=100, value=int(cur_data.get("mah", 4000)), step=100)
                        e_voltage = eb_c3.number_input("Nominal Voltage (V)*", min_value=1.0, value=float(cur_data.get("voltage", 14.8)), step=0.1)
                        eb_c4, eb_c5, eb_c6 = st.columns(3)
                        e_batt_weight_g = eb_c4.number_input("Weight (g)*", min_value=1.0, value=float(cur_data.get("weight_g", 250.0) or 250.0), step=5.0)
                        e_wh = eb_c5.number_input("Watt-Hours (Wh)*", min_value=1.0, value=float(cur_data.get("wh", 50.0)), step=0.5)
                        e_c_rating = eb_c6.number_input("C-Rating*", min_value=1, value=int(cur_data.get("c_rating", 40)), step=5)
                        eb_c7, eb_c8 = st.columns(2)
                        e_dimensions = eb_c7.text_input("Dimensions (L x W x H mm)*", value=cur_data.get("dimensions", ""))
                        e_notes = eb_c8.text_input("Engineering Notes (Optional)", value=cur_data.get("notes", ""))
                        edit_entry = {
                            "cells": int(e_cells_count), "mah": int(e_mah), "weight_g": e_batt_weight_g,
                            "c_rating": int(e_c_rating), "voltage": e_voltage, "wh": e_wh,
                            "price_egp": edit_price_egp, "price_usd": edit_price_usd,
                            "dimensions": e_dimensions, "notes": e_notes, "buy_url": edit_url
                        }
                    elif edit_category == "FLIGHT_CONTROLLERS":
                        efc_c1, efc_c2 = st.columns(2)
                        e_mcu = efc_c1.text_input("MCU Target*", value=cur_data.get("mcu", ""))
                        e_fc_weight = efc_c2.number_input("Weight (g)*", min_value=0.5, value=float(cur_data.get("weight", 10.0)), step=0.5)
                        efc_c3, efc_c4 = st.columns(2)
                        e_dim = efc_c3.text_input("Dimensions (mm)*", value=cur_data.get("dim", ""))
                        e_firmware = efc_c4.text_input("Supported Firmware*", value=cur_data.get("firmware", ""))
                        e_notes = st.text_input("Engineering Notes (Optional)", value=cur_data.get("notes", ""))
                        edit_entry = {
                            "mcu": e_mcu, "weight": e_fc_weight, "dim": e_dim, "firmware": e_firmware,
                            "price_egp": edit_price_egp, "price_usd": edit_price_usd, "notes": e_notes, "buy_url": edit_url
                        }
                    elif edit_category == "SBCS":
                        es_c1, es_c2, es_c3 = st.columns(3)
                        e_cpu = es_c1.text_input("Processor / RAM*", value=cur_data.get("cpu", ""))
                        e_ai_tops = es_c2.number_input("AI Compute (TOPS)*", min_value=0.0, value=float(cur_data.get("ai_tops", 0.0)), step=1.0)
                        e_power_w = es_c3.number_input("Avg Power Draw (W)*", min_value=0.1, value=float(cur_data.get("power_w", 5.0)), step=0.5)
                        es_c4, es_c5 = st.columns(2)
                        e_sbc_weight = es_c4.number_input("Weight (g)*", min_value=1.0, value=float(cur_data.get("weight", 45.0)), step=1.0)
                        e_dim = es_c5.text_input("Dimensions (mm)*", value=cur_data.get("dim", ""))
                        e_best_for = st.text_input("Primary Workload / Best For*", value=cur_data.get("best_for", ""))
                        edit_entry = {
                            "cpu": e_cpu, "ai_tops": e_ai_tops, "weight": e_sbc_weight, "dim": e_dim,
                            "power_w": e_power_w, "price_egp": edit_price_egp, "price_usd": edit_price_usd,
                            "best_for": e_best_for, "buy_url": edit_url
                        }
                    elif edit_category == "INTEGRATED_BOARDS":
                        eib_c1, eib_c2 = st.columns(2)
                        e_arch = eib_c1.text_input("Architecture Type*", value=cur_data.get("arch", ""))
                        e_compute = eib_c2.text_input("Compute Engine*", value=cur_data.get("compute", ""))
                        eib_c3, eib_c4, eib_c5 = st.columns(3)
                        e_ib_weight = eib_c3.number_input("Weight (g)*", min_value=1.0, value=float(cur_data.get("weight", 100.0)), step=1.0)
                        e_ib_power_w = eib_c4.number_input("Avg Power Draw (W)*", min_value=0.5, value=float(cur_data.get("power_w", 10.0)), step=0.5)
                        e_dim = eib_c5.text_input("Dimensions (mm)*", value=cur_data.get("dim", ""))
                        e_best_for = st.text_input("Primary Workload / Best For*", value=cur_data.get("best_for", ""))
                        edit_entry = {
                            "arch": e_arch, "compute": e_compute, "dim": e_dim, "weight": e_ib_weight,
                            "power_w": e_ib_power_w, "price_egp": edit_price_egp, "price_usd": edit_price_usd,
                            "best_for": e_best_for, "buy_url": edit_url
                        }
                        
                    edit_submitted = st.form_submit_button("Update Component Profile", type="primary")
                    if edit_submitted:
                        missing_fields = []
                        if not edit_comp_name.strip(): missing_fields.append("Component Model Name")
                        if not edit_url.strip(): missing_fields.append("Vendor URL")
                        for key, val in edit_entry.items():
                            if key not in ["notes", "ducted"]:
                                if val is None or val == "" or val == []:
                                    missing_fields.append(key.replace("_", " ").title())
                                    
                        if missing_fields:
                            st.error(f"❌ **Validation Failed:** Missing required inputs: {', '.join(missing_fields)}")
                        else:
                            clean_name = edit_comp_name.strip()
                            if clean_name != item_to_edit:
                                st.session_state[edit_category].pop(item_to_edit, None)
                            st.session_state[edit_category][clean_name] = edit_entry
                            st.session_state.admin_notify = f"Successfully updated '{clean_name}'."
                            st.rerun()
            else:
                st.info(f"No components available to edit in {edit_category}.")
                
        # ==========================================
        # 3. REMOVE COMPONENT SECTION
        # ==========================================
        with tab_del:
            st.markdown("### Deprecate Hardware")
            del_category = st.selectbox("Target Category:", CATEGORIES, key="del_cat")
            available_items = list(st.session_state[del_category].keys())
            
            if available_items:
                del_c1, del_c2 = st.columns([3, 1], gap="small")
                with del_c1:
                    item_to_delete = st.selectbox("Select Component to Remove:", available_items, label_visibility="collapsed")
                with del_c2:
                    if st.button("🗑️ Delete Component", use_container_width=True):
                        st.session_state[del_category].pop(item_to_delete, None)
                        st.session_state.admin_notify = f"Successfully removed '{item_to_delete}' from {del_category}."
                        st.rerun()
            else:
                st.info(f"Database contains no legacy components in {del_category}.")
                
        # ==========================================
        # 4. CLOUD REPOSITORY SYNC
        # ==========================================
        with tab_sync:
            st.markdown("### ☁️ Remote Database Synchronization")
            st.caption("Review the local session changes below before pushing the updated JSON payload to the master GitHub repository.")
            # Inside with tab_sync:
            st.markdown("### 🔄 Ingest Remote Catalogs (UAVs.fyi & UAS-Forge)")
            st.caption("Fetch external parts feeds and merge new entries into the live session and local JSON file.")

            if st.button("🚀 Pull & Merge Remote Parts", use_container_width=True):
                with st.spinner("Connecting to external databases..."):
                    new_parts = sync_external_data(st.session_state)
                    st.session_state.admin_notify = f"Sync complete: {new_parts} components added/updated."
                    st.rerun()

            st.divider()
            full_catalog = {cat: st.session_state[cat] for cat in CATEGORIES}
            
            with st.expander("🔍 View JSON Payload Preview", expanded=False):
                st.json(full_catalog)
                
            st.warning("Executing this commit will overwrite the live database file, updating metrics for all active users.", icon="⚠️")
            
            if st.button("🚀 Push Local Changes to GitHub Master", type="primary", use_container_width=True):
                with st.spinner("Authenticating and pushing payload to GitHub..."):
                    success, msg = commit_to_github(full_catalog)
                    if success:
                        st.session_state.admin_notify = f"Push successful: {msg}"
                        st.rerun()
                    else:
                        st.error(f"GitHub API Rejection: {msg}")