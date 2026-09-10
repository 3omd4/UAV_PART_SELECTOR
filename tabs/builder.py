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
    # Retrieve active database and presets from session state
    FRAMES = st.session_state.get("FRAMES", {})
    MOTORS = st.session_state.get("MOTORS", {})
    BATTERIES = st.session_state.get("BATTERIES", {})
    FLIGHT_CONTROLLERS = st.session_state.get("FLIGHT_CONTROLLERS", {})
    SBCS = st.session_state.get("SBCS", {})
    INTEGRATED_BOARDS = st.session_state.get("INTEGRATED_BOARDS", {})
    
    preset = st.session_state.get("builder_preset", {})
    
    st.subheader("Configure Platform & Evaluate Compatibility")
    
    col_inputs, col_physics = st.columns([1.1, 1.5], gap="large")
    
    # ==========================================
    # LEFT COLUMN: USER INPUTS (Preset Aware)
    # ==========================================
    with col_inputs:
        st.markdown("### ⚙️ Hardware Configuration")
        
        f_idx = list(FRAMES.keys()).index(preset["frame"]) if preset.get("frame") in FRAMES else 0
        selected_frame_name = st.selectbox("1. Airframe Architecture:", list(FRAMES.keys()), index=f_idx)
        frame = FRAMES[selected_frame_name]
        
        arch_idx = 1 if preset.get("int_board") else 0
        arch_choice = st.radio("2. Avionics Stack:", ["Modular (Separate FC + SBC)", "Integrated Board (All-in-One)"], index=arch_idx)
        
        fc_weight, fc_price_egp, fc_price_usd = 0.0, 0.0, 0.0
        sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = 0.0, 0.0, 0.0, 0.0
        int_board_name, fc_name, sbc_name = None, None, None
        
        if arch_choice == "Modular (Separate FC + SBC)":
            fc_idx = list(FLIGHT_CONTROLLERS.keys()).index(preset["fc"]) if preset.get("fc") in FLIGHT_CONTROLLERS else 1
            sbc_idx = list(SBCS.keys()).index(preset["sbc"]) if preset.get("sbc") in SBCS else 1
            
            fc_name = st.selectbox("Flight Controller:", list(FLIGHT_CONTROLLERS.keys()), index=fc_idx)
            sbc_name = st.selectbox("Companion Computer (SBC):", list(SBCS.keys()), index=sbc_idx)
            fc, sbc = FLIGHT_CONTROLLERS[fc_name], SBCS[sbc_name]
            fc_weight, fc_price_egp, fc_price_usd = fc.get("weight", 0), fc.get("price_egp", 0), fc.get("price_usd", 0)
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = sbc.get("weight", 0), sbc.get("price_egp", 0), sbc.get("price_usd", 0), sbc.get("power_w", 0)
            ai_tops = sbc.get("ai_tops", 0)
        else:
            int_idx = list(INTEGRATED_BOARDS.keys()).index(preset["int_board"]) if preset.get("int_board") in INTEGRATED_BOARDS else 0
            int_board_name = st.selectbox("Integrated Autonomy Board:", list(INTEGRATED_BOARDS.keys()), index=int_idx)
            int_board = INTEGRATED_BOARDS[int_board_name]
            sbc_weight, sbc_price_egp, sbc_price_usd, sbc_power_w = int_board.get("weight", 0), int_board.get("price_egp", 0), int_board.get("price_usd", 0), int_board.get("power_w", 0)
            ai_tops = 15.0 if "VOXL" in int_board_name else (40.0 if "Jetson" in int_board_name else 0.0)
            
        m_idx = list(MOTORS.keys()).index(preset["motor"]) if preset.get("motor") in MOTORS else 2
        motor_name = st.selectbox("3. Brushless Motors:", list(MOTORS.keys()), index=m_idx)
        motor = MOTORS[motor_name]
        
        b_idx = list(BATTERIES.keys()).index(preset["battery"]) if preset.get("battery") in BATTERIES else 0
        battery_name = st.selectbox("4. Energy Storage:", list(BATTERIES.keys()), index=b_idx)
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
    num_motors = frame.get("motor_count", 4)
    propulsion_weight = (motor.get("weight", 0) * num_motors) + esc_wiring_weight
    compute_and_fc_weight = fc_weight + sbc_weight
    total_payload_weight = compute_and_fc_weight + sensor_weight
    
    batt_weight = battery["weight_g"] if battery["weight_g"] is not None else 0.0
    batt_weight = battery["weight_g"] if battery["weight_g"] is not None else 0.0
    batt_price_egp = battery["price_egp"] or 0.0
    batt_price_usd = battery["price_usd"] or 0.0
    auw_g = frame["weight_g"] + propulsion_weight + batt_weight + total_payload_weight
    auw_kg = auw_g / 1000.0
    
    total_max_thrust_g = motor.get("thrust", 0) * num_motors
    twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
    hover_throttle_pct = (auw_g / total_max_thrust_g) * 100 if total_max_thrust_g > 0 else 100.0
    
    prop_size_in = extract_inches(frame.get("max_prop", "")) or extract_inches(motor.get("prop", ""))
    if prop_size_in > 0:
        total_disk_area_m2 = (math.pi * (((prop_size_in * 0.0254) / 2.0) ** 2)) * num_motors
        disk_loading_kg_m2 = auw_kg / total_disk_area_m2 if total_disk_area_m2 > 0 else 0.0
    else:
        total_disk_area_m2, disk_loading_kg_m2 = 0.0, 0.0
        
    batt_max_discharge_amps = (battery.get("mah", 0) / 1000.0) * battery.get("c_rating", 1)
    total_elec_power_w = sbc_power_w + sensor_power + 3.0
    
    batt_voltage = battery.get("voltage", 1.0) if battery.get("voltage", 1.0) > 0 else 1.0
    total_peak_system_amps = ((motor.get("thrust", 0) / 3.0) / batt_voltage * num_motors) + (total_elec_power_w / batt_voltage)

    hover_mech_power_w = auw_g / motor.get("efficiency_hover_gw", 1.0)
    total_hover_power_w = hover_mech_power_w + total_elec_power_w
    flight_time_minutes = ((battery.get("wh", 0) * 0.85) / total_hover_power_w) * 60.0 if total_hover_power_w > 0 else 0.0

    total_cost_egp = frame.get("price_egp", 0) + (motor.get("price_egp", 0) * num_motors) + 1500.0 + fc_price_egp + sbc_price_egp + (battery.get("price_egp", 0) or 0)
    total_cost_usd = frame.get("price_usd", 0) + (motor.get("price_usd", 0) * num_motors) + 30.0 + fc_price_usd + sbc_price_usd + (battery.get("price_usd", 0) or 0)

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
            st.write(f"- **Frame:** {frame.get('weight_g', 0)}")
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
            st.write(f"- **Wheelbase:** {frame.get('wheelbase_mm', 'N/A')} mm")
            st.write(f"- **Max Prop:** {frame.get('max_prop', 'N/A')}")
            st.write(f"- **Stator:** {motor.get('stator', 'N/A')}")
            st.write(f"- **Avionics:** {int_board.get('dim', 'N/A') if int_board_name else sbc.get('dim', 'N/A')}")
            
        st.markdown("**Payload Limits**")
        frame_payload_limit = frame.get("payload_limit_g", 1) if frame.get("payload_limit_g", 0) > 0 else 1.0
        payload_pct = min((total_payload_weight / frame_payload_limit), 1.0)
        st.progress(payload_pct, text=f"Structural Payload Used: {total_payload_weight:.1f}g / {frame.get('payload_limit_g', 0)}g")

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
            st.markdown(f"**Result:** ({battery.get('wh', 0)}Wh × 0.85 / {total_hover_power_w:.1f}W) × 60 = `{flight_time_minutes:.1f} min`")
            
            st.markdown("**4. Electrical Load (Peak Amps)**")
            st.markdown(r"$$ I_{peak} = \left( \frac{P_{mech}}{V} \times N \right) + I_{sys} $$")
            st.markdown(f"**Result:** Peak `{total_peak_system_amps:.1f}A` vs Max Safe `{batt_max_discharge_amps:.1f}A`")

        st.divider()
        
        st.markdown("### 🛡️ Comprehensive Safety Validation")
        checks_passed = True
        
        if total_peak_system_amps > batt_max_discharge_amps:
            st.error(f"❌ **C-Rating Hazard:** Peak draw ({total_peak_system_amps:.1f}A) exceeds battery limit ({batt_max_discharge_amps:.1f}A). Risk of voltage sag or fire.")
            checks_passed = False
        if battery.get("cells") not in motor.get("cells", []):
            st.error(f"❌ **Voltage Incompatibility:** Motor expects {motor.get('cells', 'N/A')}S, but battery provides {battery.get('cells', 'N/A')}S.")
            checks_passed = False
        if total_payload_weight > frame.get("payload_limit_g", 0):
            st.error(f"❌ **Structural Overweight:** Payload ({total_payload_weight:.1f}g) exceeds frame limit ({frame.get('payload_limit_g', 0)}g).")
            checks_passed = False
        if twr < 1.8:
            st.error(f"❌ **Underpowered (TWR = {twr:.2f}):** Platform will struggle to stabilize during turbulent indoor downwash. Target ≥ 2.0.")
            checks_passed = False

        if hover_throttle_pct > 65.0:
            st.warning(f"⚠️ **High Hover Throttle ({hover_throttle_pct:.1f}%):** Motors will operate near their upper limit to maintain altitude, leaving minimal control authority.")
        elif hover_throttle_pct < 20.0:
            st.warning(f"⚠️ **Low Hover Throttle ({hover_throttle_pct:.1f}%):** Platform is highly overpowered. Pitch/roll commands may be hypersensitive.")
            
        if twr > 4.5:
            st.warning(f"⚠️ **Overpowered (TWR = {twr:.2f}):** Aggressive racing profile. Requires heavy PID tuning for smooth indoor flight.")
            
        if frame.get("wheelbase_mm", 0) > 400:
            st.warning(f"⚠️ **Spatial Footprint Caution:** Wheelbase ({frame.get('wheelbase_mm')}mm) exceeds typical 400mm indoor limits. Increases swarm collision risk.")
            
        if not frame.get("ducted", True):
            st.warning("⚠️ **Safety Hazard:** Open propellers selected. Wall strikes or mid-air node touches risk instant motor stalls.")

        if checks_passed:
            st.success("✅ **Electrical & Structural Check Passed:** Core physics constraints are nominal.")

    # ==========================================
    # FULL WIDTH: DYNAMIC BILL OF MATERIALS
    # ==========================================
    st.divider()
    st.markdown("### 🛒 Generated Bill of Materials (BoM)")
    bom_data = [
        {"Component": "Frame", "Model": selected_frame_name, "Weight (g)": frame.get("weight_g", 0), "Cost (EGP)": frame.get("price_egp", 0), "Buy": frame.get("buy_url", "")},
        {"Component": f"Motors (x{num_motors})", "Model": motor_name, "Weight (g)": motor.get("weight", 0) * num_motors, "Cost (EGP)": motor.get("price_egp", 0) * num_motors, "Buy": motor.get("buy_url", "")},
        {"Component": "ESC & Wiring", "Model": "4-in-1 40A ESC", "Weight (g)": esc_wiring_weight, "Cost (EGP)": 1500.0, "Buy": "https://makerselectronics.com"},
        {"Component": "Battery", "Model": battery_name, "Weight (g)": batt_weight, "Cost (EGP)": batt_price_egp, "Buy": battery.get("buy_url", "")}
    ]
    if arch_choice == "Modular (Separate FC + SBC)":
        bom_data.extend([
            {"Component": "Flight Controller", "Model": fc_name, "Weight (g)": fc_weight, "Cost (EGP)": fc_price_egp, "Buy": fc.get("buy_url", "")},
            {"Component": "SBC", "Model": sbc_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Buy": sbc.get("buy_url", "")}
        ])
    else:
        bom_data.append({"Component": "Integrated Board", "Model": int_board_name, "Weight (g)": sbc_weight, "Cost (EGP)": sbc_price_egp, "Buy": int_board.get("buy_url", "")})
        
    if esp32_sniffer:
        bom_data.append({"Component": "ESP32 Sensor", "Model": "SDR Sniffer", "Weight (g)": 25.0, "Cost (EGP)": 0.0, "Buy": ""})
    if "LiDAR" in lidar_cam:
        bom_data.append({"Component": "Perception", "Model": "2D LiDAR", "Weight (g)": 45.0, "Cost (EGP)": 0.0, "Buy": ""})
    elif "Stereo" in lidar_cam:
        bom_data.append({"Component": "Perception", "Model": "Stereo VIO Depth Camera", "Weight (g)": 75.0, "Cost (EGP)": 0.0, "Buy": ""})
        
    st.dataframe(pd.DataFrame(bom_data), column_config={"Buy": st.column_config.LinkColumn("Link ↗")}, use_container_width=True, hide_index=True)