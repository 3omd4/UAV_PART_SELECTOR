import streamlit as st
import pandas as pd
import math
import re

def extract_inches(prop_string):
    """Helper to extract numeric propeller size from strings."""
    if not prop_string:
        return 0.0
    match = re.search(r"([0-9]*\.?[0-9]+)", str(prop_string))
    if match:
        return float(match.group(1))
    return 0.0

def render_builder_tab():
    # Retrieve active database from session state
    FRAMES = st.session_state.FRAMES
    MOTORS = st.session_state.MOTORS
    BATTERIES = st.session_state.BATTERIES
    FLIGHT_CONTROLLERS = st.session_state.FLIGHT_CONTROLLERS
    SBCS = st.session_state.SBCS
    INTEGRATED_BOARDS = st.session_state.INTEGRATED_BOARDS
    
    st.subheader("Configure Platform & Evaluate Compatibility")
    
    # Establish a cleaner 2-column layout
    col_inputs, col_physics = st.columns([1.1, 1.5], gap="large")
    
    # ==========================================
    # LEFT COLUMN: USER INPUTS
    # ==========================================
    with col_inputs:
        st.markdown("### ⚙️ Hardware Configuration")
        
        selected_frame_name = st.selectbox("1. Airframe Architecture:", list(FRAMES.keys()), index=0)
        frame = FRAMES[selected_frame_name]
        
        arch_choice = st.radio("2. Avionics Stack:", ["Modular (Separate FC + SBC)", "Integrated Board (All-in-One)"])
        fc_weight, fc_price_egp, fc_price_usd = 0.0, 0.0, 0.0
        sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = 0.0, 0.0, 0.0, 0.0
        int_board_name, fc_name, sbc_name = None, None, None
        
        if arch_choice == "Modular (Separate FC + SBC)":
            fc_name = st.selectbox("Flight Controller:", list(FLIGHT_CONTROLLERS.keys()), index=1)
            sbc_name = st.selectbox("Companion Computer (SBC):", list(SBCS.keys()), index=1)
            fc, sbc = FLIGHT_CONTROLLERS[fc_name], SBCS[sbc_name]
            fc_weight, fc_price_egp, fc_price_usd = fc["weight"], fc["price_egp"], fc["price_usd"]
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = sbc["weight"], sbc["price_egp"], sbc["price_usd"], sbc["power_w"]
            ai_tops = sbc["ai_tops"]
        else:
            int_board_name = st.selectbox("Integrated Autonomy Board:", list(INTEGRATED_BOARDS.keys()), index=0)
            int_board = INTEGRATED_BOARDS[int_board_name]
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = int_board["weight"], int_board["price_egp"], int_board["price_usd"], int_board["power_w"]
            ai_tops = 15.0 if "VOXL" in int_board_name else (40.0 if "Jetson" in int_board_name else 0.0)
            
        motor_name = st.selectbox("3. Brushless Motors:", list(MOTORS.keys()), index=2)
        motor = MOTORS[motor_name]
        
        battery_name = st.selectbox("4. Energy Storage:", list(BATTERIES.keys()), index=0)
        battery = BATTERIES[battery_name]
        
        lidar_cam = st.selectbox("5. Perception Sensor:", [
            "Lightweight 2D LiDAR (~45g, 1.5W)",
            "Stereo VIO Depth Camera (~75g, 2.5W)",
            "Optical Flow + Downward ToF (~15g, 0.5W)",
            "None (Pre-mapped / MoCap) (0g, 0W)"
        ])
        esp32_sniffer = st.checkbox("Include ESP32-S3 SDR Sniffer (+25g, 1.5W)", value=True)
        
        # Sensor payload math
        sensor_weight, sensor_power = 0.0, 0.0
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

    # ==========================================
    # BACKGROUND COMPUTATIONS
    # ==========================================
    num_motors = frame["motor_count"]
    propulsion_weight = (motor["weight"] * num_motors) + esc_wiring_weight
    compute_and_fc_weight = fc_weight + sbc_weight
    total_payload_weight = compute_and_fc_weight + sensor_weight
    
    batt_weight = battery["weight_g"] if battery["weight_g"] is not None else 0.0
    auw_g = frame["weight_g"] + propulsion_weight + batt_weight + total_payload_weight
    auw_kg = auw_g / 1000.0
    
    total_max_thrust_g = motor["thrust"] * num_motors
    twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
    hover_throttle_pct = (auw_g / total_max_thrust_g) * 100 if total_max_thrust_g > 0 else 100.0
    
    prop_size_in = extract_inches(frame["max_prop"]) or extract_inches(motor["prop"])
    if prop_size_in > 0:
        total_disk_area_m2 = (math.pi * (((prop_size_in * 0.0254) / 2.0) ** 2)) * num_motors
        disk_loading_kg_m2 = auw_kg / total_disk_area_m2 if total_disk_area_m2 > 0 else 0.0
    else:
        total_disk_area_m2, disk_loading_kg_m2 = 0.0, 0.0
        
    batt_max_discharge_amps = (battery["mah"] / 1000.0) * battery["c_rating"]
    total_elec_power_w = sbc_power_w + sensor_power + 3.0
    
    # Avoid division by zero if voltage is missing
    batt_voltage = battery["voltage"] if battery["voltage"] > 0 else 1.0
    total_peak_system_amps = ((motor["thrust"] / 3.0) / batt_voltage * num_motors) + (total_elec_power_w / batt_voltage)

    hover_mech_power_w = auw_g / motor["efficiency_hover_gw"]
    total_hover_power_w = hover_mech_power_w + total_elec_power_w
    flight_time_minutes = ((battery["wh"] * 0.85) / total_hover_power_w) * 60.0 if total_hover_power_w > 0 else 0.0

    # Costs
    total_cost_egp = frame["price_egp"] + (motor["price_egp"] * num_motors) + 1500.0 + fc_price_egp + sbc_price_egp + (battery["price_egp"] or 0)
    total_cost_usd = frame["price_usd"] + (motor["price_usd"] * num_motors) + 30.0 + fc_price_usd + sbc_price_usd + (battery["price_usd"] or 0)

    # ==========================================
    # RIGHT COLUMN: PHYSICS & VALIDATION
    # ==========================================
    with col_physics:
        st.markdown("### 📊 Executive KPIs")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("All-Up Weight", f"{auw_g:.1f} g")
        kpi2.metric("Thrust-to-Weight", f"{twr:.2f}:1", delta="Optimum" if 2.0 <= twr <= 3.8 else "Warning", delta_color="off")
        kpi3.metric("Est. Hover Time", f"{flight_time_minutes:.1f} min")
        kpi4.metric("AI Compute", f"{ai_tops} TOPS")
        
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Hover Throttle", f"{hover_throttle_pct:.1f}%")
        a2.metric("Disk Loading", f"{disk_loading_kg_m2:.1f} kg/m²")
        a3.metric("Peak Current", f"{total_peak_system_amps:.1f} A")
        a4.metric("Total Cost", f"${total_cost_usd:,.0f}")

        st.divider()
        
        st.markdown("### 🔬 Detailed System Telemetry")
        tel1, tel2, tel3 = st.columns(3)
        with tel1:
            st.markdown("**Mass Breakdown (g)**")
            st.write(f"- **Frame:** {frame['weight_g']}")
            st.write(f"- **Propulsion:** {propulsion_weight:.1f}")
            st.write(f"- **Avionics:** {compute_and_fc_weight:.1f}")
            st.write(f"- **Sensors:** {sensor_weight:.1f}")
            st.write(f"- **Battery:** {batt_weight:.1f}")
        with tel2:
            st.markdown("**Power Draw (W)**")
            st.write(f"- **Hover (Mech):** {hover_mech_power_w:.1f}")
            st.write(f"- **Compute:** {sbc_power_w:.1f}")
            st.write(f"- **Sensors:** {sensor_power:.1f}")
            st.write(f"- **Baseline:** 3.0")
            st.write(f"- **Total:** {total_hover_power_w:.1f}")
        with tel3:
            st.markdown("**Spatial Footprint**")
            st.write(f"- **Wheelbase:** {frame['wheelbase_mm']} mm")
            st.write(f"- **Max Prop:** {frame['max_prop']}")
            st.write(f"- **Stator:** {motor['stator']}")
            st.write(f"- **Avionics:** {int_board['dim'] if int_board_name else sbc['dim']}")
            
        st.markdown("**Payload Limits**")
        payload_pct = min((total_payload_weight / frame["payload_limit_g"]), 1.0) if frame["payload_limit_g"] > 0 else 1.0
        st.progress(payload_pct, text=f"Structural Payload Used: {total_payload_weight:.1f}g / {frame['payload_limit_g']}g")

        st.divider()
        
        st.markdown("### 📐 Live Physics Engine")
        math1, math2 = st.columns(2)
        with math1:
            st.markdown("**1. Kinematics (Hover Throttle)**")
            st.markdown(r"$$ Throttle_{hover} = \left( \frac{AUW}{Thrust_{max} \times N} \right) \times 100 $$")
            st.markdown(f"**Result:** ({auw_g:.1f}g / {total_max_thrust_g:.1f}g) × 100 = `{hover_throttle_pct:.1f}%`")
            
            st.markdown("**2. Aerodynamics (Disk Loading)**")
            st.markdown(r"$$ Disk\ Loading = \frac{AUW_{kg}}{N \times \pi \times r^2} $$")
            st.markdown(f"**Result:** {auw_kg:.3f}kg / {total_disk_area_m2:.4f}m² = `{disk_loading_kg_m2:.1f} kg/m²`")

        with math2:
            st.markdown("**3. Thermodynamics (Endurance)**")
            st.markdown(r"$$ T_{flight} = \frac{E_{batt} \times 0.85}{\frac{AUW}{\eta} + P_{elec}} \times 60 $$")
            st.markdown(f"**Result:** ({battery['wh']}Wh × 0.85 / {total_hover_power_w:.1f}W) × 60 = `{flight_time_minutes:.1f} min`")
            
            st.markdown("**4. Electrical Load (Peak Amps)**")
            st.markdown(r"$$ I_{peak} = \left( \frac{P_{mech}}{V} \times N \right) + I_{sys} $$")
            st.markdown(f"**Result:** Peak `{total_peak_system_amps:.1f}A` vs Max Safe `{batt_max_discharge_amps:.1f}A`")

        st.divider()
        
        st.markdown("### 🛡️ Comprehensive Safety Validation")
        # Validation checks
        checks_passed = True
        
        # Hard Errors (Physics & Electrical Failures)
        if total_peak_system_amps > batt_max_discharge_amps:
            st.error(f"❌ **C-Rating Hazard:** Peak draw ({total_peak_system_amps:.1f}A) exceeds battery limit ({batt_max_discharge_amps:.1f}A). Risk of voltage sag or fire.")
            checks_passed = False
        if battery["cells"] not in motor["cells"]:
            st.error(f"❌ **Voltage Incompatibility:** Motor expects {motor['cells']}S, but battery provides {battery['cells']}S.")
            checks_passed = False
        if total_payload_weight > frame["payload_limit_g"]:
            st.error(f"❌ **Structural Overweight:** Payload ({total_payload_weight:.1f}g) exceeds frame limit ({frame['payload_limit_g']}g).")
            checks_passed = False
        if twr < 1.8:
            st.error(f"❌ **Underpowered (TWR = {twr:.2f}):** Platform will struggle to stabilize during turbulent indoor downwash. Target ≥ 2.0.")
            checks_passed = False

        # Operational Warnings (Engineer Discretion)
        if hover_throttle_pct > 65.0:
            st.warning(f"⚠️ **High Hover Throttle ({hover_throttle_pct:.1f}%):** Motors will operate near their upper limit to maintain altitude, leaving minimal control authority.")
        elif hover_throttle_pct < 20.0:
            st.warning(f"⚠️ **Low Hover Throttle ({hover_throttle_pct:.1f}%):** Platform is highly overpowered. Pitch/roll commands may be hypersensitive.")
            
        if twr > 4.5:
            st.warning(f"⚠️ **Overpowered (TWR = {twr:.2f}):** Aggressive racing profile. Requires heavy PID tuning for smooth indoor flight.")
            
        if frame["wheelbase_mm"] > 400:
            st.warning(f"⚠️ **Spatial Footprint Caution:** Wheelbase ({frame['wheelbase_mm']}mm) exceeds typical 400mm indoor limits. Increases swarm collision risk.")
            
        if not frame["ducted"]:
            st.warning("⚠️ **Safety Hazard:** Open propellers selected. Wall strikes or mid-air node touches risk instant motor stalls.")

        # Success States
        if checks_passed:
            st.success("✅ **Electrical & Structural Check Passed:** Core physics constraints are nominal.")

    # ==========================================
    # FULL WIDTH: DYNAMIC BILL OF MATERIALS
    # ==========================================
    st.divider()
    st.markdown("### 🛒 Generated Bill of Materials (BoM)")
    bom_data = [
        {"Component": "Frame", "Model": selected_frame_name, "Weight (g)": frame["weight_g"], "Cost (EGP)": frame["price_egp"], "Buy": frame["buy_url"]},
        {"Component": f"Motors (x{num_motors})", "Model": motor_name, "Weight (g)": motor["weight"] * num_motors, "Cost (EGP)": motor["price_egp"] * num_motors, "Buy": motor["buy_url"]},
        {"Component": "ESC & Wiring", "Model": "4-in-1 40A ESC", "Weight (g)": esc_wiring_weight, "Cost (EGP)": 1500.0, "Buy": "https://makerselectronics.com"},
        {"Component": "Battery", "Model": battery_name, "Weight (g)": batt_weight, "Cost (EGP)": batt_price_egp, "Buy": battery["buy_url"]}
    ]
    if arch_choice == "Modular (Separate FC + SBC)":
        bom_data.extend([
            {"Component": "Flight Controller", "Model": fc_name, "Weight (g)": fc_weight, "Cost (EGP)": fc_price_egp, "Buy": fc["buy_url"]},
            {"Component": "SBC", "Model": sbc_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Buy": sbc["buy_url"]}
        ])
    else:
        bom_data.append({"Component": "Integrated Board", "Model": int_board_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Buy": int_board["buy_url"]})
        
    if esp32_sniffer:
        bom_data.append({"Component": "ESP32 Sensor", "Model": "SDR Sniffer", "Weight (g)": 25.0, "Cost (EGP)": 0.0, "Buy": ""})
    if "LiDAR" in lidar_cam:
        bom_data.append({"Component": "Perception", "Model": "2D LiDAR", "Weight (g)": 45.0, "Cost (EGP)": 0.0, "Buy": ""})
    elif "Stereo" in lidar_cam:
        bom_data.append({"Component": "Perception", "Model": "Stereo VIO Depth Camera", "Weight (g)": 75.0, "Cost (EGP)": 0.0, "Buy": ""})
        
    st.dataframe(pd.DataFrame(bom_data), column_config={"Buy": st.column_config.LinkColumn("Link ↗")}, use_container_width=True, hide_index=True)