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
# TAB 2: INTERACTIVE DRONE BUILDER
# ==========================================
with tab_builder:
    st.subheader("Configure Platform & Evaluate Compatibility")
    
    col_cfg, col_results = st.columns([1.1, 1.2], gap="large")
    
    # --- INPUTS (LEFT COLUMN) ---
    with col_cfg:
        st.markdown("#### 1. Airframe Selection")
        selected_frame_name = st.selectbox("Frame Architecture:", list(FRAMES.keys()), index=0)
        frame = FRAMES[selected_frame_name]
        
        st.markdown("#### 2. Autonomy & Avionics Stack")
        arch_choice = st.radio("Avionics Architecture:", ["Modular (Separate FC + SBC)", "Integrated Board (All-in-One)"])
        
        fc_weight, fc_price_egp, fc_price_usd = 0.0, 0.0, 0.0
        sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = 0.0, 0.0, 0.0, 0.0
        int_board_name = None
        fc_name = None
        sbc_name = None
        
        if arch_choice == "Modular (Separate FC + SBC)":
            fc_name = st.selectbox("Flight Controller:", list(FLIGHT_CONTROLLERS.keys()), index=1)
            sbc_name = st.selectbox("Companion Computer (SBC):", list(SBCS.keys()), index=1)
            fc = FLIGHT_CONTROLLERS[fc_name]
            sbc = SBCS[sbc_name]
            
            fc_weight, fc_price_egp, fc_price_usd = fc["weight"], fc["price_egp"], fc["price_usd"]
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = sbc["weight"], sbc["price_egp"], sbc["price_usd"], sbc["power_w"]
            ai_tops = sbc["ai_tops"]
        else:
            int_board_name = st.selectbox("Integrated Autonomy Board:", list(INTEGRATED_BOARDS.keys()), index=0)
            int_board = INTEGRATED_BOARDS[int_board_name]
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = int_board["weight"], int_board["price_egp"], int_board["price_usd"], int_board["power_w"]
            ai_tops = 15.0 if "VOXL" in int_board_name else (40.0 if "Jetson" in int_board_name else 0.0)

        st.markdown("#### 3. Propulsion System")
        motor_name = st.selectbox("Brushless Motors:", list(MOTORS.keys()), index=2)
        motor = MOTORS[motor_name]
        
        st.markdown("#### 4. Energy Storage")
        battery_name = st.selectbox("Battery Pack:", list(BATTERIES.keys()), index=0)
        battery = BATTERIES[battery_name]
        
        st.markdown("#### 5. Mission Payload (Sensors & ESP32)")
        esp32_sniffer = st.checkbox("ESP32-S3 SDR Sniffer + Dual Antennas (~25g, 1.5W)", value=True)
        lidar_cam = st.selectbox("Perception Sensor:", [
            "Lightweight 2D LiDAR (e.g. LD06 / RPLidar) (~45g, 1.5W)",
            "Stereo VIO Depth Camera (e.g. RealSense D435i) (~75g, 2.5W)",
            "Optical Flow + Downward ToF (~15g, 0.5W)",
            "None (Pre-mapped / Motion Capture Only) (0g, 0W)"
        ])
        
        # Sensor payload math
        sensor_weight = 0.0
        sensor_power = 0.0
        if esp32_sniffer:
            sensor_weight += 25.0
            sensor_power += 1.5
        if "LiDAR" in lidar_cam:
            sensor_weight += 45.0
            sensor_power += 1.5
        elif "Stereo" in lidar_cam:
            sensor_weight += 75.0
            sensor_power += 2.5
        elif "Optical" in lidar_cam:
            sensor_weight += 15.0
            sensor_power += 0.5
            
        esc_wiring_weight = 40.0  # standard 4-in-1 ESC + wiring harness

    # --- COMPUTATIONS (Script level to be shared across columns) ---
    num_motors = frame["motor_count"]
    propulsion_weight = (motor["weight"] * num_motors) + esc_wiring_weight
    compute_and_fc_weight = fc_weight + sbc_weight
    total_payload_weight = compute_and_fc_weight + sensor_weight
    
    # Safe weight handling if battery weight is null/None in data
    batt_weight = battery["weight_g"] if battery["weight_g"] is not None else 0.0
    batt_price_egp = battery["price_egp"] if battery["price_egp"] is not None else 0.0
    batt_price_usd = battery["price_usd"] if battery["price_usd"] is not None else 0.0
    
    # All-Up Weight (AUW)
    auw_g = frame["weight_g"] + propulsion_weight + batt_weight + total_payload_weight
    auw_kg = auw_g / 1000.0
    
    # Thrust and TWR
    total_max_thrust_g = motor["thrust"] * num_motors
    twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
    
    # Costs
    motor_total_cost_egp = motor["price_egp"] * num_motors
    motor_total_cost_usd = motor["price_usd"] * num_motors
    esc_cost_egp = 1500.0  # est 4-in-1 40A ESC
    esc_cost_usd = 30.0
    
    total_cost_egp = frame["price_egp"] + motor_total_cost_egp + esc_cost_egp + fc_price_egp + sbc_price_egp + batt_price_egp
    total_cost_usd = frame["price_usd"] + motor_total_cost_usd + esc_cost_usd + fc_price_usd + sbc_price_usd + batt_price_usd

    # Hover Endurance Calculation
    hover_mech_power_w = auw_g / motor["efficiency_hover_gw"]
    total_elec_power_w = sbc_power_w + sensor_power + 3.0  # 3W FC/Receiver baseline
    total_hover_power_w = hover_mech_power_w + total_elec_power_w
    
    usable_wh = battery["wh"] * 0.85
    flight_time_minutes = (usable_wh / total_hover_power_w) * 60.0

    # --- ADD POWER & MASS BREAKDOWN TO LEFT COLUMN ---
    with col_cfg:
        st.markdown("---")
        st.markdown("#### Power & Mass Breakdown")
        
        b1, b2 = st.columns(2)
        with b1:
            st.markdown("**Mass Distribution:**")
            st.write(f"- Frame & Cowlings: `{frame['weight_g']} g`")
            st.write(f"- Propulsion: `{propulsion_weight:.1f} g`")
            st.write(f"- Battery Pack: `{batt_weight:.1f} g`")
            st.write(f"- Compute & Avionics: `{compute_and_fc_weight:.1f} g`")
            st.write(f"- Sensors & RF Payload: `{sensor_weight:.1f} g`")
            
        with b2:
            st.markdown("**Electrical Draw (Hover):**")
            st.write(f"- Motors (Mech): `{hover_mech_power_w:.1f} W`")
            st.write(f"- Compute Board: `{sbc_power_w:.1f} W`")
            st.write(f"- Sensors/RF: `{sensor_power:.1f} W`")
            st.write(f"- **Total Draw:** `{total_hover_power_w:.1f} W`")

    # --- METRICS & RESULTS (RIGHT COLUMN) ---
    with col_results:
        st.markdown("### System Spec & Viability Assessment")
        
        # Metrics display
        m1, m2, m3 = st.columns(3)
        m1.metric("All-Up Weight (AUW)", f"{auw_g:.1f} g", help="Includes frame, motors, ESC, battery, compute, sensors.")
        m2.metric("Thrust-to-Weight", f"{twr:.2f} : 1", delta="Optimal: 2.0 - 3.5" if 2.0 <= twr <= 3.8 else "Warning")
        m3.metric("Est. Hover Time", f"{flight_time_minutes:.1f} mins", help="Based on 85% battery discharge, electrical + mechanical draw.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Build Cost", f"{total_cost_egp:,.0f} EGP")
        c2.metric("Cost in USD", f"${total_cost_usd:,.1f}")
        c3.metric("AI Compute", f"{ai_tops} TOPS")

        st.markdown("---")
        
        # --- PAYLOAD VISUALIZER ---
        st.markdown("#### Payload Capacity Limits")
        
        # Structural Payload Limit
        payload_pct = min((total_payload_weight / frame["payload_limit_g"]), 1.0)
        st.caption(f"**Structural Payload Used:** {total_payload_weight:.1f}g out of {frame['payload_limit_g']}g frame limit")
        st.progress(payload_pct)
        
        # Dynamic Payload Limit (Thrust constraint for TWR >= 2.0)
        max_safe_auw = total_max_thrust_g / 2.0
        remaining_thrust_payload_g = max_safe_auw - auw_g
        
        col_p1, col_p2 = st.columns(2)
        col_p1.metric("Remaining Frame Payload", f"{max(0, frame['payload_limit_g'] - total_payload_weight):.1f} g", help="Maximum weight the carbon fiber/plastic frame can structurally support.")
        col_p2.metric("Remaining Safe Lift", f"{remaining_thrust_payload_g:.1f} g", help="Maximum weight you can add before the TWR drops below the safe 2.0 threshold required for indoor stability.")

        st.markdown("---")

        # --- SPATIAL & DIMENSIONAL FOOTPRINT ---
        st.markdown("#### Spatial & Dimensional Footprint")
        st.write(f"- **Airframe Span (Wheelbase):** `{frame['wheelbase_mm']} mm` (Motor-to-motor diagonal)")
        st.write(f"- **Motor Stator Dimensions:** `{motor['stator']}`")
        if arch_choice == "Modular (Separate FC + SBC)":
            st.write(f"- **Flight Controller Size:** `{fc['dim']}`")
            st.write(f"- **Companion PC (SBC) Size:** `{sbc['dim']}`")
        else:
            st.write(f"- **Integrated Avionics Size:** `{int_board['dim']}`")

        st.markdown("---")
        
        # --- MATHEMATICAL BREAKDOWN EXPANDER ---
        with st.expander("View Step-by-Step Physics Calculations"):
            st.markdown("**1. All-Up Weight (AUW)**")
            st.latex(r"AUW = W_{frame} + (W_{motor} \times N) + W_{esc} + W_{batt} + W_{avionics} + W_{sensors}")
            st.markdown(f"AUW = {frame['weight_g']}g + ({motor['weight']}g × {num_motors}) + {esc_wiring_weight}g + {batt_weight}g + {compute_and_fc_weight}g + {sensor_weight}g = **{auw_g:.1f} g**")
            
            st.markdown("**2. Thrust-to-Weight Ratio (TWR)**")
            st.latex(r"TWR = \frac{Thrust_{max} \times N}{AUW}")
            st.markdown(f"TWR = ({motor['thrust']}g × {num_motors}) / {auw_g:.1f}g = **{twr:.2f}**")
            
            st.markdown("**3. Continuous Hover Power Draw**")
            st.latex(r"P_{hover} = \frac{AUW}{\eta_{motor}} + P_{avionics} + P_{sensors} + P_{misc}")
            st.markdown(f"P_hover = ({auw_g:.1f}g / {motor['efficiency_hover_gw']} g/W) + {sbc_power_w}W + {sensor_power}W + 3.0W = **{total_hover_power_w:.1f} W**")
            
            st.markdown("**4. Estimated Flight Time**")
            st.latex(r"T_{flight} = \frac{E_{batt} \times 0.85}{P_{hover}} \times 60")
            st.markdown(f"Flight Time = ({battery['wh']} Wh × 0.85 / {total_hover_power_w:.1f} W) × 60 = **{flight_time_minutes:.1f} minutes**")

        st.markdown("#### Engineering & Safety Rules Verification")
        
        # Validation checks
        checks_passed = True
        
        if battery["cells"] not in motor["cells"]:
            st.error(f"❌ **Voltage Incompatibility:** Motor '{motor_name}' supports {motor['cells']}S, but battery is {battery['cells']}S. Motor will overheat or brown out.")
            checks_passed = False
        else:
            st.success(f"✅ Voltage match: {battery['cells']}S pack is supported by the motor.")

        if total_payload_weight > frame["payload_limit_g"]:
            st.error(f"❌ **Overweight:** Total payload ({total_payload_weight:.1f}g) exceeds frame payload limit ({frame['payload_limit_g']}g).")
            checks_passed = False
        else:
            st.success(f"✅ Payload budget safe: Carrying {total_payload_weight:.1f}g of {frame['payload_limit_g']}g allowed.")

        if twr < 1.8:
            st.error(f"❌ **Underpowered (TWR = {twr:.2f}):** Platform will struggle to stabilize during turbulent indoor downwash. Target ≥ 2.0.")
            checks_passed = False
        elif twr > 4.5:
            st.warning(f"⚠️ **Overpowered (TWR = {twr:.2f}):** Aggressive racing profile. High motor KV might induce high throttle sensitivity in hover.")
        else:
            st.success(f"✅ Dynamic thrust adequate for indoor recovery maneuvers.")

        if frame["wheelbase_mm"] > 400:
            st.warning(f"⚠️ **Spatial Footprint Caution:** Wheelbase ({frame['wheelbase_mm']}mm) exceeds the 400mm strict indoor limit. Swarm collision and downwash risks are elevated.")
        else:
            st.success(f"✅ Dimensionally compliant ({frame['wheelbase_mm']}mm ≤ 400mm).")
            
        if not frame["ducted"]:
            st.warning("⚠️ **Safety Hazard:** Open propellers selected. Wall strikes or mid-air node touches risk instant motor stalls and crashes.")
        else:
            st.success("✅ Enclosed / ducted propeller protection enabled.")

        if checks_passed:
            st.info("**Supervisor Pitch Takeaway:** This configuration satisfies all physical and electrical laws. It represents an actionable, stable build for your lab presentation.")

    # ==========================================
    # DYNAMIC BILL OF MATERIALS (BOM)
    # ==========================================
    st.markdown("---")
    st.markdown("### Selected Bill of Materials (BoM)")
    
    bom_data = []
    bom_data.append({"Component": "Frame", "Model": selected_frame_name, "Weight (g)": frame["weight_g"], "Cost (EGP)": frame["price_egp"], "Where to Buy": frame["buy_url"]})
    bom_data.append({"Component": f"Motors (x{num_motors})", "Model": motor_name, "Weight (g)": motor["weight"] * num_motors, "Cost (EGP)": motor["price_egp"] * num_motors, "Where to Buy": motor["buy_url"]})
    bom_data.append({"Component": "ESC & Wiring", "Model": "4-in-1 40A ESC", "Weight (g)": esc_wiring_weight, "Cost (EGP)": esc_cost_egp, "Where to Buy": "https://makerselectronics.com"})
    bom_data.append({"Component": "Battery", "Model": battery_name, "Weight (g)": batt_weight, "Cost (EGP)": batt_price_egp, "Where to Buy": battery["buy_url"]})
    
    if arch_choice == "Modular (Separate FC + SBC)":
        bom_data.append({"Component": "Flight Controller", "Model": fc_name, "Weight (g)": fc_weight, "Cost (EGP)": fc_price_egp, "Where to Buy": fc["buy_url"]})
        bom_data.append({"Component": "SBC", "Model": sbc_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Where to Buy": sbc["buy_url"]})
    else:
        bom_data.append({"Component": "Integrated Board", "Model": int_board_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Where to Buy": int_board["buy_url"]})
        
    if esp32_sniffer:
        bom_data.append({"Component": "Payload Sensor", "Model": "ESP32-S3 SDR Sniffer", "Weight (g)": 25.0, "Cost (EGP)": 0.0, "Where to Buy": "https://makerselectronics.com"})
    if "LiDAR" in lidar_cam:
        bom_data.append({"Component": "Payload Sensor", "Model": "2D LiDAR", "Weight (g)": 45.0, "Cost (EGP)": 0.0, "Where to Buy": "https://makerselectronics.com"})
    elif "Stereo" in lidar_cam:
        bom_data.append({"Component": "Payload Sensor", "Model": "Stereo VIO Depth Camera", "Weight (g)": 75.0, "Cost (EGP)": 0.0, "Where to Buy": "https://www.intelrealsense.com/depth-camera-d435i/"})
    elif "Optical" in lidar_cam:
        bom_data.append({"Component": "Payload Sensor", "Model": "Optical Flow + ToF", "Weight (g)": 15.0, "Cost (EGP)": 0.0, "Where to Buy": "https://makerselectronics.com"})

    df_bom = pd.DataFrame(bom_data)
    st.dataframe(
        df_bom, 
        column_config={
            "Where to Buy": st.column_config.LinkColumn("Where to Buy", display_text="Link ↗"),
            "Cost (EGP)": st.column_config.NumberColumn(format="EGP %.2f")
        },
        use_container_width=True, hide_index=True
    )
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