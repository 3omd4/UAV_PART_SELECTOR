import streamlit as st
import pandas as pd
import numpy as np
import json
import base64
import requests
import itertools
import re

st.set_page_config(
    page_title="Indoor UAV Part list",
    page_icon="🛸",
    layout="wide"
)

# ==========================================
# 1. DATABASE & SESSION INITIALIZATION
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

# Ensure there is at least a fallback for weight presets if the JSON is completely empty
if not st.session_state.WEIGHT_PRESETS:
    st.session_state.WEIGHT_PRESETS = {
        "Balanced Default": {"auw": 1.0, "twr": 1.0, "hover": 1.0, "cost": 1.0},
        "Endurance Optimized": {"auw": 0.5, "twr": 0.5, "hover": 2.5, "cost": 1.0},
        "Budget Friendly": {"auw": 1.0, "twr": 1.0, "hover": 1.0, "cost": 3.0}
    }

# Assign direct shortcuts
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
# 2. APPLICATION LAYOUT
# ==========================================

st.title("UAV Trade Component Lists & Builder")
st.caption("Systems engineering evaluator for localized decentralized SLAM & RF/RSSI mapping platforms.")

tab_catalogs, tab_builder, tab_admin, tab_combinations = st.tabs(["Component Catalogs", "Drone Builder", "Admin (Add Parts)", "Valid Combinations"])

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
    if st.session_state.get("build_loaded_success"):
        st.success("✅ **Combination Successfully Loaded!** The configuration below has been automatically updated.")
        st.session_state["build_loaded_success"] = False 

    st.subheader("Configure Platform & Evaluate Compatibility")
    col_cfg, col_results = st.columns([1.1, 1.2], gap="large")
    
    with col_cfg:
        st.markdown("#### 1. Airframe Selection")
        frame_list = list(FRAMES.keys())
        def_frame = st.session_state.get("builder_frame", frame_list[0] if frame_list else None)
        frame_idx = frame_list.index(def_frame) if def_frame in frame_list else 0
        selected_frame_name = st.selectbox("Frame Architecture:", frame_list, index=frame_idx)
        frame = FRAMES[selected_frame_name] if selected_frame_name else None
        
        st.markdown("#### 2. Autonomy & Avionics Stack")
        arch_options = ["Modular (Separate FC + SBC)", "Integrated Board (All-in-One)"]
        def_arch = st.session_state.get("builder_arch", arch_options[0])
        arch_idx = arch_options.index(def_arch) if def_arch in arch_options else 0
        arch_choice = st.radio("Avionics Architecture:", arch_options, index=arch_idx)
        
        fc_weight, fc_price_egp, fc_price_usd = 0.0, 0.0, 0.0
        sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = 0.0, 0.0, 0.0, 0.0
        int_board_name, fc_name, sbc_name = None, None, None
        
        if arch_choice == "Modular (Separate FC + SBC)":
            fc_list = list(FLIGHT_CONTROLLERS.keys())
            def_fc = st.session_state.get("builder_fc", fc_list[1] if len(fc_list) > 1 else fc_list[0] if fc_list else None)
            fc_idx = fc_list.index(def_fc) if def_fc in fc_list else 0
            fc_name = st.selectbox("Flight Controller:", fc_list, index=fc_idx)
            
            sbc_list = list(SBCS.keys())
            def_sbc = st.session_state.get("builder_sbc", sbc_list[1] if len(sbc_list) > 1 else sbc_list[0] if sbc_list else None)
            sbc_idx = sbc_list.index(def_sbc) if def_sbc in sbc_list else 0
            sbc_name = st.selectbox("Companion Computer (SBC):", sbc_list, index=sbc_idx)
            
            fc = FLIGHT_CONTROLLERS.get(fc_name, {})
            sbc = SBCS.get(sbc_name, {})
            fc_weight, fc_price_egp, fc_price_usd = fc.get("weight", 0), fc.get("price_egp", 0), fc.get("price_usd", 0)
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = sbc.get("weight", 0), sbc.get("price_egp", 0), sbc.get("price_usd", 0), sbc.get("power_w", 0)
            ai_tops = sbc.get("ai_tops", 0)
        else:
            ib_list = list(INTEGRATED_BOARDS.keys())
            def_ib = st.session_state.get("builder_int_board", ib_list[0] if ib_list else None)
            ib_idx = ib_list.index(def_ib) if def_ib in ib_list else 0
            int_board_name = st.selectbox("Integrated Autonomy Board:", ib_list, index=ib_idx)
            
            int_board = INTEGRATED_BOARDS.get(int_board_name, {})
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = int_board.get("weight", 0), int_board.get("price_egp", 0), int_board.get("price_usd", 0), int_board.get("power_w", 0)
            ai_tops = 15.0 if int_board_name and "VOXL" in int_board_name else (40.0 if int_board_name and "Jetson" in int_board_name else 0.0)
            
        st.markdown("#### 3. Propulsion System")
        motor_list = list(MOTORS.keys())
        def_motor = st.session_state.get("builder_motor", motor_list[2] if len(motor_list) > 2 else motor_list[0] if motor_list else None)
        motor_idx = motor_list.index(def_motor) if def_motor in motor_list else 0
        motor_name = st.selectbox("Brushless Motors:", motor_list, index=motor_idx)
        motor = MOTORS.get(motor_name, {})
        
        st.markdown("#### 4. Energy Storage")
        batt_list = list(BATTERIES.keys())
        def_batt = st.session_state.get("builder_battery", batt_list[0] if batt_list else None)
        batt_idx = batt_list.index(def_batt) if def_batt in batt_list else 0
        battery_name = st.selectbox("Battery Pack:", batt_list, index=batt_idx)
        battery = BATTERIES.get(battery_name, {})
        
        st.markdown("#### 5. Mission Payload (Sensors & ESP32)")
        esp32_sniffer = st.checkbox("ESP32-S3 SDR Sniffer + Dual Antennas (~25g, 1.5W)", value=True)
        lidar_cam = st.selectbox("Perception Sensor:", [
            "Lightweight 2D LiDAR (e.g. LD06 / RPLidar) (~45g, 1.5W)",
            "Stereo VIO Depth Camera (e.g. RealSense D435i) (~75g, 2.5W)",
            "Optical Flow + Downward ToF (~15g, 0.5W)",
            "None (Pre-mapped / Motion Capture Only) (0g, 0W)"
        ])
        
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
        esc_wiring_weight = 40.0 

    if frame and motor and battery:
        num_motors = frame.get("motor_count", 4)
        propulsion_weight = (motor.get("weight", 0) * num_motors) + esc_wiring_weight
        compute_and_fc_weight = fc_weight + sbc_weight
        total_payload_weight = compute_and_fc_weight + sensor_weight
        
        batt_weight = battery.get("weight_g")
        if batt_weight is None:
            batt_weight = float(battery.get("wh", 0)) * 6.5
        else:
            batt_weight = float(batt_weight)

        batt_price_egp = battery.get("price_egp", 0.0) if battery.get("price_egp") is not None else 0.0
        batt_price_usd = battery.get("price_usd", 0.0) if battery.get("price_usd") is not None else 0.0
        
        auw_g = frame.get("weight_g", 0) + propulsion_weight + batt_weight + total_payload_weight
        auw_kg = auw_g / 1000.0
        
        total_max_thrust_g = motor.get("thrust", 0) * num_motors
        twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
        
        motor_total_cost_egp = motor.get("price_egp", 0) * num_motors
        motor_total_cost_usd = motor.get("price_usd", 0) * num_motors
        esc_cost_egp = 1500.0
        esc_cost_usd = 30.0
        total_cost_egp = frame.get("price_egp", 0) + motor_total_cost_egp + esc_cost_egp + fc_price_egp + sbc_price_egp + batt_price_egp
        total_cost_usd = frame.get("price_usd", 0) + motor_total_cost_usd + esc_cost_usd + fc_price_usd + sbc_price_usd + batt_price_usd
        
        hover_mech_power_w = auw_g / motor.get("efficiency_hover_gw", 1)
        total_elec_power_w = sbc_power_w + sensor_power + 3.0
        total_hover_power_w = hover_mech_power_w + total_elec_power_w
        usable_wh = battery.get("wh", 0) * 0.85
        flight_time_minutes = (usable_wh / total_hover_power_w) * 60.0

        with col_cfg:
            st.markdown("---")
            st.markdown("#### Power & Mass Breakdown")
            b1, b2 = st.columns(2)
            with b1:
                st.markdown("**Mass Distribution:**")
                st.write(f"- Frame & Cowlings: `{frame.get('weight_g', 0)} g`")
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

        with col_results:
            st.markdown("### System Spec & Viability Assessment")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("All-Up Weight (AUW)", f"{auw_g:.1f} g", help="Includes frame, motors, ESC, battery, compute, sensors.")
            m2.metric("Thrust-to-Weight", f"{twr:.2f} : 1", delta="Optimal: 2.0 - 3.5" if 2.0 <= twr <= 3.8 else "Warning")
            m3.metric("Est. Hover Time", f"{flight_time_minutes:.1f} mins", help="Based on 85% battery discharge, electrical + mechanical draw.")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Build Cost", f"{total_cost_egp:,.0f} EGP")
            c2.metric("Cost in USD", f"${total_cost_usd:,.1f}")
            c3.metric("AI Compute", f"{ai_tops} TOPS")
            
            st.markdown("---")
            st.markdown("#### Payload Capacity Limits")
            
            frame_limit = frame.get("payload_limit_g", 1)
            payload_pct = min((total_payload_weight / frame_limit), 1.0)
            st.caption(f"**Structural Payload Used:** {total_payload_weight:.1f}g out of {frame_limit}g frame limit")
            st.progress(payload_pct)
            
            max_safe_auw = total_max_thrust_g / 2.0
            remaining_thrust_payload_g = max_safe_auw - auw_g
            col_p1, col_p2 = st.columns(2)
            col_p1.metric("Remaining Frame Payload", f"{max(0, frame_limit - total_payload_weight):.1f} g", help="Maximum weight the carbon fiber/plastic frame can structurally support.")
            col_p2.metric("Remaining Safe Lift", f"{remaining_thrust_payload_g:.1f} g", help="Maximum weight you can add before the TWR drops below the safe 2.0 threshold required for indoor stability.")
            
            st.markdown("---")
            st.markdown("#### Spatial & Dimensional Footprint")
            st.write(f"- **Airframe Span (Wheelbase):** `{frame.get('wheelbase_mm')} mm` (Motor-to-motor diagonal)")
            st.write(f"- **Motor Stator Dimensions:** `{motor.get('stator')}`")
            if arch_choice == "Modular (Separate FC + SBC)":
                st.write(f"- **Flight Controller Size:** `{fc.get('dim')}`")
                st.write(f"- **Companion PC (SBC) Size:** `{sbc.get('dim')}`")
            else:
                st.write(f"- **Integrated Avionics Size:** `{int_board.get('dim')}`")
                
            st.markdown("---")
            with st.expander("View Step-by-Step Physics Calculations"):
                st.markdown("**1. All-Up Weight (AUW)**")
                st.latex(r"AUW = W_{frame} + (W_{motor} \times N) + W_{esc} + W_{batt} + W_{avionics} + W_{sensors}")
                st.markdown(f"AUW = {frame.get('weight_g')}g + ({motor.get('weight')}g × {num_motors}) + {esc_wiring_weight}g + {batt_weight}g + {compute_and_fc_weight}g + {sensor_weight}g = **{auw_g:.1f} g**")
                st.markdown("**2. Thrust-to-Weight Ratio (TWR)**")
                st.latex(r"TWR = \frac{Thrust_{max} \times N}{AUW}")
                st.markdown(f"TWR = ({motor.get('thrust')}g × {num_motors}) / {auw_g:.1f}g = **{twr:.2f}**")
                st.markdown("**3. Continuous Hover Power Draw**")
                st.latex(r"P_{hover} = \frac{AUW}{\eta_{motor}} + P_{avionics} + P_{sensors} + P_{misc}")
                st.markdown(f"P_hover = ({auw_g:.1f}g / {motor.get('efficiency_hover_gw',1)} g/W) + {sbc_power_w}W + {sensor_power}W + 3.0W = **{total_hover_power_w:.1f} W**")
                st.markdown("**4. Estimated Flight Time**")
                st.latex(r"T_{flight} = \frac{E_{batt} \times 0.85}{P_{hover}} \times 60")
                st.markdown(f"Flight Time = ({battery.get('wh',0)} Wh × 0.85 / {total_hover_power_w:.1f} W) × 60 = **{flight_time_minutes:.1f} minutes**")
                
            st.markdown("#### Engineering & Safety Rules Verification")
            checks_passed = True
            
            if battery.get("cells") not in motor.get("cells", []):
                st.error(f"❌ **Voltage Incompatibility:** Motor '{motor_name}' supports {motor.get('cells')}S, but battery is {battery.get('cells')}S. Motor will overheat or brown out.")
                checks_passed = False
            else:
                st.success(f"✅ Voltage match: {battery.get('cells')}S pack is supported by the motor.")
                
            if total_payload_weight > frame_limit:
                st.error(f"❌ **Overweight:** Total payload ({total_payload_weight:.1f}g) exceeds frame payload limit ({frame_limit}g).")
                checks_passed = False
            else:
                st.success(f"✅ Payload budget safe: Carrying {total_payload_weight:.1f}g of {frame_limit}g allowed.")
                
            if twr < 1.8:
                st.error(f"❌ **Underpowered (TWR = {twr:.2f}):** Platform will struggle to stabilize during turbulent indoor downwash. Target ≥ 2.0.")
                checks_passed = False
            elif twr > 4.5:
                st.warning(f"⚠️ **Overpowered (TWR = {twr:.2f}):** Aggressive racing profile. High motor KV might induce high throttle sensitivity in hover.")
            else:
                st.success(f"✅ Dynamic thrust adequate for indoor recovery maneuvers.")
                
            frame_wb = frame.get("wheelbase_mm", 400)
            if frame_wb > 400:
                st.warning(f"⚠️ **Spatial Footprint Caution:** Wheelbase ({frame_wb}mm) exceeds the 400mm strict indoor limit. Swarm collision and downwash risks are elevated.")
            else:
                st.success(f"✅ Dimensionally compliant ({frame_wb}mm ≤ 400mm).")
                
            if not frame.get("ducted"):
                st.warning("⚠️ **Safety Hazard:** Open propellers selected. Wall strikes or mid-air node touches risk instant motor stalls and crashes.")
            else:
                st.success("✅ Enclosed / ducted propeller protection enabled.")
                
            batt_is_valid = True
            max_batt_weight = frame_wb * 2.5 
            if batt_weight > max_batt_weight:
                st.error(f"❌ **Battery Too Heavy:** The {battery_name} (est. {batt_weight:.0f}g) is too heavy for a {frame_wb}mm frame (Max recommended: {max_batt_weight:.0f}g).")
                checks_passed = False
                batt_is_valid = False
                
            dims = battery.get("dimensions", "")
            if dims and dims != "N/A":
                nums = re.findall(r'\d+', dims)
                if nums:
                    max_dim = max([int(n) for n in nums])
                    if max_dim > (frame_wb * 1.15):
                        st.error(f"❌ **Battery Too Large (Dimensional):** The battery length ({max_dim}mm) exceeds the frame geometry tolerance ({frame_wb * 1.15:.0f}mm). It will physically protrude into the propellers.")
                        checks_passed = False
                        batt_is_valid = False
                        
            if batt_is_valid:
                st.success(f"✅ Battery physical size and mass are appropriate for the frame footprint.")

            if checks_passed:
                st.info("**Supervisor Pitch Takeaway:** This configuration satisfies all physical and electrical laws. It represents an actionable, stable build for your lab presentation.")

        # ==========================================
        # DYNAMIC BILL OF MATERIALS (BOM)
        # ==========================================
        st.markdown("---")
        st.markdown("### Selected Bill of Materials (BoM)")
        bom_data = []
        bom_data.append({"Component": "Frame", "Model": selected_frame_name, "Weight (g)": frame.get("weight_g"), "Cost (EGP)": frame.get("price_egp"), "Where to Buy": frame.get("buy_url")})
        bom_data.append({"Component": f"Motors (x{num_motors})", "Model": motor_name, "Weight (g)": motor.get("weight",0) * num_motors, "Cost (EGP)": motor.get("price_egp",0) * num_motors, "Where to Buy": motor.get("buy_url")})
        bom_data.append({"Component": "ESC & Wiring", "Model": "4-in-1 40A ESC", "Weight (g)": esc_wiring_weight, "Cost (EGP)": esc_cost_egp, "Where to Buy": "https://makerselectronics.com"})
        bom_data.append({"Component": "Battery", "Model": battery_name, "Weight (g)": batt_weight, "Cost (EGP)": batt_price_egp, "Where to Buy": battery.get("buy_url")})
        if arch_choice == "Modular (Separate FC + SBC)":
            bom_data.append({"Component": "Flight Controller", "Model": fc_name, "Weight (g)": fc_weight, "Cost (EGP)": fc_price_egp, "Where to Buy": fc.get("buy_url")})
            bom_data.append({"Component": "SBC", "Model": sbc_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Where to Buy": sbc.get("buy_url")})
        else:
            bom_data.append({"Component": "Integrated Board", "Model": int_board_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Where to Buy": int_board.get("buy_url")})
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
    if "admin_notify" in st.session_state:
        if "❌" in st.session_state.admin_notify or "Validation" in st.session_state.admin_notify:
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
        # Only allow adding to standard component lists, not the presets here
        add_categories = [c for c in CATEGORIES if c != "WEIGHT_PRESETS"]
        target_category = st.selectbox("Target Category for Addition:", add_categories, key="add_cat")
        with st.form("add_part_form", clear_on_submit=False):
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
                    "prop": prop, "thrust": thrust, "source": source, "price_egp": price_egp, "price_usd": price_usd,
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
                    "price_egp": price_egp, "price_usd": price_usd, "notes": notes, "buy_url": buy_url
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
                    st.error(f"❌ **Validation Failed!** Please fill in the following required fields: {', '.join(missing_fields)}")
                else:
                    st.session_state[target_category][new_comp_name.strip()] = new_entry
                    st.session_state.admin_notify = f"✅ Added '{new_comp_name.strip()}' to {target_category} successfully!"
                    st.rerun()

        # ------------------------------------------
        # 2. EDIT COMPONENT SECTION
        # ------------------------------------------
        st.markdown("---")
        st.markdown("### Edit Existing Component")
        st.caption("Select a component to modify its properties.")
        edit_category = st.selectbox("Category to Edit From:", add_categories, key="edit_cat")
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
                st.markdown("---")
                st.markdown(f"**{edit_category} Specifications**")
                
                edit_entry = {}
                if edit_category == "MOTORS":
                    em_c1, em_c2, em_c3 = st.columns(3)
                    e_weight = em_c1.number_input("Weight (g)*", min_value=0.1, value=float(cur_data.get("weight", 30.0)), step=0.5)
                    e_thrust = em_c2.number_input("Max Thrust (g)*", min_value=1.0, value=float(cur_data.get("thrust", 1200.0)), step=10.0)
                    e_kv = em_c3.number_input("KV Rating*", min_value=100, value=int(cur_data.get("kv", 1800)), step=50)
                    em_c4, em_c5, em_c6 = st.columns(3)
                    e_stator = em_c4.text_input("Stator Size*", value=cur_data.get("stator", ""))
                    e_prop = em_c5.text_input("Supported Propeller Size*", value=cur_data.get("prop", ""))
                    e_eff = em_c6.number_input("Hover Efficiency (g/W)*", min_value=1.0, value=float(cur_data.get("efficiency_hover_gw", 7.0)), step=0.1)
                    em_c7, em_c8 = st.columns([2, 1])
                    e_source = em_c7.text_input("Source / Retailer Type*", value=cur_data.get("source", ""))
                    e_cells = em_c8.multiselect("Supported Cell Counts (S)*", options=[1, 2, 3, 4, 5, 6, 8], default=cur_data.get("cells", []))
                    e_notes = st.text_input("Engineering Notes (Optional)", value=cur_data.get("notes", ""))
                    edit_entry = {
                        "stator": e_stator, "weight": e_weight, "kv": int(e_kv), "cells": e_cells,
                        "prop": e_prop, "thrust": e_thrust, "source": e_source, "price_egp": edit_price_egp,
                        "price_usd": edit_price_usd, "efficiency_hover_gw": e_eff, "notes": e_notes, "buy_url": edit_url
                    }
                elif edit_category == "FRAMES":
                    ef_c1, ef_c2, ef_c3 = st.columns(3)
                    e_wheelbase_mm = ef_c1.number_input("Wheelbase (mm)*", min_value=50, value=int(cur_data.get("wheelbase_mm", 330)), step=10)
                    e_weight_g = ef_c2.number_input("Bare Frame Weight (g)*", min_value=1.0, value=float(cur_data.get("weight_g", 150.0)), step=5.0)
                    e_payload_limit_g = ef_c3.number_input("Max Structural Payload (g)*", min_value=10.0, value=float(cur_data.get("payload_limit_g", 400.0)), step=10.0)
                    ef_c4, ef_c5, ef_c6 = st.columns(3)
                    e_motor_count = ef_c4.number_input("Motor Count*", min_value=3, max_value=8, value=int(cur_data.get("motor_count", 4)), step=1)
                    e_max_prop = ef_c5.text_input("Max Propeller Size*", value=cur_data.get("max_prop", ""))
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
                    e_mcu = efc_c1.text_input("MCU Model*", value=cur_data.get("mcu", ""))
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
                    e_cpu = es_c1.text_input("Processor / Memory*", value=cur_data.get("cpu", ""))
                    e_ai_tops = es_c2.number_input("AI TOPS*", min_value=0.0, value=float(cur_data.get("ai_tops", 0.0)), step=1.0)
                    e_power_w = es_c3.number_input("Average Power Draw (W)*", min_value=0.1, value=float(cur_data.get("power_w", 5.0)), step=0.5)
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
                    e_compute = eib_c2.text_input("Onboard Compute Engine*", value=cur_data.get("compute", ""))
                    eib_c3, eib_c4, eib_c5 = st.columns(3)
                    e_ib_weight = eib_c3.number_input("Weight (g)*", min_value=1.0, value=float(cur_data.get("weight", 100.0)), step=1.0)
                    e_ib_power_w = eib_c4.number_input("Average Power Draw (W)*", min_value=0.5, value=float(cur_data.get("power_w", 10.0)), step=0.5)
                    e_dim = eib_c5.text_input("Dimensions (mm)*", value=cur_data.get("dim", ""))
                    e_best_for = st.text_input("Primary Workload / Best For*", value=cur_data.get("best_for", ""))
                    edit_entry = {
                        "arch": e_arch, "compute": e_compute, "dim": e_dim, "weight": e_ib_weight,
                        "power_w": e_ib_power_w, "price_egp": edit_price_egp, "price_usd": edit_price_usd,
                        "best_for": e_best_for, "buy_url": edit_url
                    }
                    
                edit_submitted = st.form_submit_button("Save Changes to Active Session")
                if edit_submitted:
                    missing_fields = []
                    if not edit_comp_name.strip(): missing_fields.append("Component Model Name")
                    if not edit_url.strip(): missing_fields.append("Vendor URL")
                    for key, val in edit_entry.items():
                        if key not in ["notes", "ducted"]:
                            if val is None or val == "" or val == []:
                                missing_fields.append(key.replace("_", " ").title())
                    if missing_fields:
                        st.error(f"❌ **Validation Failed!** Please fill in: {', '.join(missing_fields)}")
                    else:
                        clean_name = edit_comp_name.strip()
                        if clean_name != item_to_edit:
                            st.session_state[edit_category].pop(item_to_edit, None)
                        st.session_state[edit_category][clean_name] = edit_entry
                        st.session_state.admin_notify = f"✅ Updated '{clean_name}' successfully!"
                        st.rerun()
        else:
            st.info(f"No components available to edit in {edit_category}.")

        # ------------------------------------------
        # 3. REMOVE COMPONENT SECTION
        # ------------------------------------------
        st.markdown("---")
        st.markdown("### Remove Existing Component")
        st.caption("Select a category and choose a component to delete from the active database.")
        del_category = st.selectbox("Category to Delete From:", add_categories, key="del_cat")
        available_items = list(st.session_state[del_category].keys())
        if available_items:
            del_c1, del_c2 = st.columns([3, 1], gap="small")
            with del_c1:
                item_to_delete = st.selectbox("Select Component to Remove:", available_items, label_visibility="collapsed")
            with del_c2:
                if st.button("🗑️ Delete Component", use_container_width=True):
                    st.session_state[del_category].pop(item_to_delete, None)
                    st.session_state.admin_notify = f"✅ Removed '{item_to_delete}' from {del_category} successfully."
                    st.rerun()
        else:
            st.info(f"No components found in {del_category}.")

        # ------------------------------------------
        # 4. CLOUD REPOSITORY SYNC
        # ------------------------------------------
        st.markdown("---")
        st.markdown("#### Cloud Repository Sync")
        st.caption("Push additions, edits, or removals permanently to the JSON file on GitHub.")
        if st.button("☁️ Commit All Changes to GitHub Repository"):
            with st.spinner("Pushing database to GitHub..."):
                full_catalog = {cat: st.session_state[cat] for cat in CATEGORIES}
                success, msg = commit_to_github(full_catalog)
                if success:
                    st.session_state.admin_notify = f"✅ {msg}"
                    st.rerun()
                else:
                    st.error(msg)
    elif admin_pass:
        st.error("❌ Incorrect password. Access denied.")

# ==========================================
# TAB 4: VALID COMBINATIONS (NEW)
# ==========================================
with tab_combinations:
    st.subheader("Explore All Valid Component Combinations")
    st.caption("This tool computes every possible combination of frames, motors, batteries, and avionics based on your database, but only lists builds that strictly pass all physical safety and power checks.")

    if "combo_notify" in st.session_state:
        st.success(st.session_state.combo_notify)
        del st.session_state.combo_notify

    st.markdown("#### 1. Select Standard Payload for Analysis")
    combo_c1, combo_c2 = st.columns(2)
    with combo_c1:
        combo_esp32 = st.checkbox("ESP32-S3 SDR Sniffer + Dual Antennas (~25g, 1.5W)", value=True, key="combo_esp32_key")
    with combo_c2:
        combo_lidar = st.selectbox("Perception Sensor:", [
            "Lightweight 2D LiDAR (e.g. LD06 / RPLidar) (~45g, 1.5W)",
            "Stereo VIO Depth Camera (e.g. RealSense D435i) (~75g, 2.5W)",
            "Optical Flow + Downward ToF (~15g, 0.5W)",
            "None (Pre-mapped / Motion Capture Only) (0g, 0W)"
        ], key="combo_lidar_key")

    combo_sensor_weight = 0.0
    combo_sensor_power = 0.0
    if combo_esp32:
        combo_sensor_weight += 25.0
        combo_sensor_power += 1.5
    if "LiDAR" in combo_lidar:
        combo_sensor_weight += 45.0
        combo_sensor_power += 1.5
    elif "Stereo" in combo_lidar:
        combo_sensor_weight += 75.0
        combo_sensor_power += 2.5
    elif "Optical" in combo_lidar:
        combo_sensor_weight += 15.0
        combo_sensor_power += 0.5

    def evaluate_combination(frame_name, motor_name, battery_name, fc_name, sbc_name, int_board_name, sensor_weight, sensor_power):
        frame = FRAMES[frame_name]
        motor = MOTORS[motor_name]
        battery = BATTERIES[battery_name]
        fc_weight, fc_price_egp = 0.0, 0.0
        sbc_weight, sbc_price_egp, sbc_power_w = 0.0, 0.0, 0.0
        if int_board_name is None:
            fc = FLIGHT_CONTROLLERS[fc_name]
            sbc = SBCS[sbc_name]
            fc_weight, fc_price_egp = fc["weight"], fc["price_egp"]
            sbc_weight, sbc_price_egp, sbc_power_w = sbc["weight"], sbc["price_egp"], sbc["power_w"]
            ai_tops = sbc["ai_tops"]
        else:
            int_board = INTEGRATED_BOARDS[int_board_name]
            sbc_weight, sbc_price_egp, sbc_power_w = int_board["weight"], int_board["price_egp"], int_board["power_w"]
            ai_tops = 15.0 if "VOXL" in int_board_name else (40.0 if "Jetson" in int_board_name else 0.0)

        esc_wiring_weight = 40.0
        num_motors = frame["motor_count"]
        propulsion_weight = (motor["weight"] * num_motors) + esc_wiring_weight
        compute_and_fc_weight = fc_weight + sbc_weight
        total_payload_weight = compute_and_fc_weight + sensor_weight
        
        batt_weight_raw = battery.get("weight_g")
        batt_weight = float(batt_weight_raw) if batt_weight_raw is not None else float(battery.get("wh", 0) * 6.5)
        batt_price_egp = battery["price_egp"] if battery["price_egp"] is not None else 0.0
        
        auw_g = frame["weight_g"] + propulsion_weight + batt_weight + total_payload_weight
        total_max_thrust_g = motor["thrust"] * num_motors
        twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
        
        motor_total_cost_egp = motor["price_egp"] * num_motors
        esc_cost_egp = 1500.0
        total_cost_egp = frame["price_egp"] + motor_total_cost_egp + esc_cost_egp + fc_price_egp + sbc_price_egp + batt_price_egp
        
        hover_mech_power_w = auw_g / motor["efficiency_hover_gw"]
        total_elec_power_w = sbc_power_w + sensor_power + 3.0
        total_hover_power_w = hover_mech_power_w + total_elec_power_w
        
        usable_wh = battery["wh"] * 0.85
        flight_time_minutes = (usable_wh / total_hover_power_w) * 60.0

        is_valid = True
        if battery["cells"] not in motor["cells"]: is_valid = False
        if total_payload_weight > frame["payload_limit_g"]: is_valid = False
        if twr < 1.8: is_valid = False
        max_batt_weight = frame["wheelbase_mm"] * 2.5
        if batt_weight > max_batt_weight: is_valid = False
        dims = battery.get("dimensions", "")
        if dims and dims != "N/A":
            nums = re.findall(r'\d+', dims)
            if nums:
                max_dim = max([int(n) for n in nums])
                if max_dim > (frame["wheelbase_mm"] * 1.15): is_valid = False
            
        if not is_valid: return None
        avionics_str = f"{fc_name} + {sbc_name}" if int_board_name is None else int_board_name
        
        return {
            "Frame": frame_name,
            "Motor": motor_name,
            "Battery": battery_name,
            "Avionics": avionics_str,
            "AUW (g)": round(float(auw_g), 1),
            "TWR": round(float(twr), 2),
            "Hover Time (min)": round(float(flight_time_minutes), 1),
            "Cost (EGP)": round(float(total_cost_egp), 0),
            "AI TOPS": float(ai_tops)
        }

    if st.button("Generate & Rank Combinations", type="primary"):
        with st.spinner("Calculating physical limits for all possible combinations..."):
            valid_combos = []
            for f, m, b, fc, sbc in itertools.product(FRAMES.keys(), MOTORS.keys(), BATTERIES.keys(), FLIGHT_CONTROLLERS.keys(), SBCS.keys()):
                res = evaluate_combination(f, m, b, fc, sbc, None, combo_sensor_weight, combo_sensor_power)
                if res: valid_combos.append(res)
            for f, m, b, int_bd in itertools.product(FRAMES.keys(), MOTORS.keys(), BATTERIES.keys(), INTEGRATED_BOARDS.keys()):
                res = evaluate_combination(f, m, b, None, None, int_bd, combo_sensor_weight, combo_sensor_power)
                if res: valid_combos.append(res)
            
            if valid_combos:
                st.session_state.combos_df = pd.DataFrame(valid_combos)
            else:
                st.session_state.combos_df = pd.DataFrame()
                st.warning("No combinations currently satisfy all engineering and safety rules. Try adjusting the target payload.")

    if "combos_df" in st.session_state and not st.session_state.combos_df.empty:
        df = st.session_state.combos_df.copy()
        
        st.markdown("---")
        st.markdown("#### 2. Advanced Sorting & Weights")
        
        preset_names = ["Custom"] + list(st.session_state.WEIGHT_PRESETS.keys())
        if "selected_preset_name" not in st.session_state:
            st.session_state.selected_preset_name = "Custom"
            
        selected_preset = st.selectbox(
            "Load Weights Preset", 
            preset_names, 
            index=preset_names.index(st.session_state.selected_preset_name) if st.session_state.selected_preset_name in preset_names else 0
        )
        st.session_state.selected_preset_name = selected_preset
        
        if selected_preset != "Custom":
            w_auw_def = st.session_state.WEIGHT_PRESETS[selected_preset]["auw"]
            w_twr_def = st.session_state.WEIGHT_PRESETS[selected_preset]["twr"]
            w_hover_def = st.session_state.WEIGHT_PRESETS[selected_preset]["hover"]
            w_cost_def = st.session_state.WEIGHT_PRESETS[selected_preset]["cost"]
        else:
            w_auw_def, w_twr_def, w_hover_def, w_cost_def = 1.0, 1.0, 1.0, 1.0
        
        cw1, cw2, cw3, cw4 = st.columns(4)
        w_auw = cw1.number_input("Weight: AUW (Lower is better)", value=float(w_auw_def), step=0.1)
        w_twr = cw2.number_input("Weight: TWR (Higher is better)", value=float(w_twr_def), step=0.1)
        w_hover = cw3.number_input("Weight: Hover Time (Higher is better)", value=float(w_hover_def), step=0.1)
        w_cost = cw4.number_input("Weight: Cost (Lower is better)", value=float(w_cost_def), step=0.1)
        
        with st.expander("💾 Save / Delete Presets", expanded=True):
            new_preset_name = st.text_input("New Preset Name", placeholder="e.g., Fast Scout Build")
            colA, colB = st.columns(2)
            if colA.button("Save Current Weights as Preset"):
                if new_preset_name:
                    st.session_state.WEIGHT_PRESETS[new_preset_name] = {"auw": w_auw, "twr": w_twr, "hover": w_hover, "cost": w_cost}
                    st.session_state.selected_preset_name = new_preset_name
                    st.session_state.combo_notify = f"✅ Preset '{new_preset_name}' saved! Commit to GitHub in the Admin tab to make it permanent."
                    st.rerun()
            if colB.button("Delete Selected Preset"):
                if selected_preset != "Custom" and selected_preset in st.session_state.WEIGHT_PRESETS:
                    del st.session_state.WEIGHT_PRESETS[selected_preset]
                    st.session_state.selected_preset_name = "Custom"
                    st.session_state.combo_notify = f"🗑️ Preset '{selected_preset}' deleted! Commit to GitHub in the Admin tab to remove it permanently."
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 3. View Options")
        
        normal_sort_param = st.selectbox("Normal Sorting Parameter", ["Hover Time (min)", "Cost (EGP)", "AUW (g)", "TWR"])
        enable_weighted_score = st.checkbox("Calculate & Enable Weighted Score", value=True)
        
        if enable_weighted_score:
            superimpose_score = st.checkbox("Superimpose Weighted Score sorting on top of normal sorting")
        else:
            superimpose_score = False

        view_mode = st.radio("Display Format", ["Table View", "Grid View"], horizontal=True)
        
        # --- EXECUTE SCORE CALCULATION ---
        if enable_weighted_score:
            max_auw, min_auw = df["AUW (g)"].max(), df["AUW (g)"].min()
            max_twr, min_twr = df["TWR"].max(), df["TWR"].min()
            max_hover, min_hover = df["Hover Time (min)"].max(), df["Hover Time (min)"].min()
            max_cost, min_cost = df["Cost (EGP)"].max(), df["Cost (EGP)"].min()

            def calculate_score(row):
                n_auw = (max_auw - row["AUW (g)"]) / (max_auw - min_auw) if max_auw != min_auw else 1.0
                n_cost = (max_cost - row["Cost (EGP)"]) / (max_cost - min_cost) if max_cost != min_cost else 1.0
                n_twr = (row["TWR"] - min_twr) / (max_twr - min_twr) if max_twr != min_twr else 1.0
                n_hover = (row["Hover Time (min)"] - min_hover) / (max_hover - min_hover) if max_hover != min_hover else 1.0
                return (w_auw * n_auw) + (w_twr * n_twr) + (w_hover * n_hover) + (w_cost * n_cost)
                
            df["Weighted Score"] = df.apply(calculate_score, axis=1)

        # --- EXECUTE SORTING ---
        asc_map = {"Hover Time (min)": False, "Cost (EGP)": True, "AUW (g)": True, "TWR": False}
        if enable_weighted_score and superimpose_score:
            df = df.sort_values(by=["Weighted Score", normal_sort_param], ascending=[False, asc_map[normal_sort_param]])
        else:
            df = df.sort_values(by=[normal_sort_param], ascending=[asc_map[normal_sort_param]])
            
        cols = list(df.columns)
        if "Weighted Score" in cols:
            cols.insert(0, cols.pop(cols.index("Weighted Score")))
            df = df[cols]

        df = df.reset_index(drop=True)

        # --- RENDER UI ---
        st.success(f"Displaying {len(df)} configurations.")
        
        if view_mode == "Table View":
            format_dict = {
                "Cost (EGP)": st.column_config.NumberColumn(format="EGP %.0f"),
                "Hover Time (min)": st.column_config.NumberColumn(format="%.1f min"),
                "AUW (g)": st.column_config.NumberColumn(format="%.1f g")
            }
            if enable_weighted_score:
                format_dict["Weighted Score"] = st.column_config.NumberColumn(format="%.2f")
                
            st.dataframe(df, use_container_width=True, column_config=format_dict)
            
            st.markdown("##### Load Configuration into Drone Builder")
            t_col1, t_col2 = st.columns([1, 3])
            with t_col1:
                row_to_load = st.number_input("Enter Row Index (from table above)", min_value=0, max_value=len(df)-1 if len(df)>0 else 0, value=0, step=1)
                if st.button("Load Row to Builder", use_container_width=True):
                    load_into_builder(df.iloc[row_to_load])
                    st.rerun()
            with t_col2:
                st.info("👈 Enter the index number shown on the far left of the table row to map those exact components into the interactive Drone Builder tab.")
            
        else:
            grid_cols = st.columns(3)
            for idx, (i, row) in enumerate(df.iterrows()):
                with grid_cols[idx % 3]:
                    with st.container(border=True):
                        if enable_weighted_score:
                            st.markdown(f"### 🏆 Score: {row['Weighted Score']:.2f}")
                            st.markdown("---")
                        
                        st.markdown(f"**🛠️ Frame:** {row['Frame']}")
                        st.markdown(f"**⚙️ Motors:** {row['Motor']}")
                        st.markdown(f"**🔋 Battery:** {row['Battery']}")
                        st.markdown(f"**💻 Avionics:** {row['Avionics']}")
                        
                        m1, m2 = st.columns(2)
                        m1.metric("Hover Time", f"{row['Hover Time (min)']} m")
                        m2.metric("AUW", f"{row['AUW (g)']} g")
                        
                        m3, m4 = st.columns(2)
                        m3.metric("Cost", f"EGP {row['Cost (EGP)']:.0f}")
                        m4.metric("TWR", f"{row['TWR']}")
                        
                        if st.button(f"Load into Builder", key=f"load_grid_{idx}", use_container_width=True):
                            load_into_builder(row)
                            st.rerun()