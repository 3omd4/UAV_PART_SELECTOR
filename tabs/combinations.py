import streamlit as st
import pandas as pd
import itertools

def render_combinations_tab():
    # Retrieve active database from session state
    FRAMES = st.session_state.FRAMES
    MOTORS = st.session_state.MOTORS
    BATTERIES = st.session_state.BATTERIES
    FLIGHT_CONTROLLERS = st.session_state.FLIGHT_CONTROLLERS
    SBCS = st.session_state.SBCS
    INTEGRATED_BOARDS = st.session_state.INTEGRATED_BOARDS

    st.subheader("Explore All Valid Component Combinations")
    st.caption("This tool computes every possible combination of frames, motors, batteries, and avionics based on your database, but only lists builds that strictly pass the core safety checks: Voltage Compatibility, Maximum Structural Payload, and Minimum Thrust-to-Weight Ratio (TWR ≥ 1.8).")

    st.markdown("#### Select Standard Payload for Analysis")
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

    # Sensor payload math for combinations tab
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
        """Helper function to calculate stats and evaluate validity."""
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
        
        batt_weight = battery["weight_g"] if battery["weight_g"] is not None else 0.0
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

        # Strict Safety Checks
        is_valid = True
        if battery["cells"] not in motor["cells"]:
            is_valid = False
        if total_payload_weight > frame["payload_limit_g"]:
            is_valid = False
        if twr < 1.8:
            is_valid = False
            
        if not is_valid:
            return None
            
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
            
            # 1. Evaluate all modular configurations
            for f, m, b, fc, sbc in itertools.product(FRAMES.keys(), MOTORS.keys(), BATTERIES.keys(), FLIGHT_CONTROLLERS.keys(), SBCS.keys()):
                res = evaluate_combination(f, m, b, fc, sbc, None, combo_sensor_weight, combo_sensor_power)
                if res:
                    valid_combos.append(res)
                    
            # 2. Evaluate all integrated configurations
            for f, m, b, int_bd in itertools.product(FRAMES.keys(), MOTORS.keys(), BATTERIES.keys(), INTEGRATED_BOARDS.keys()):
                res = evaluate_combination(f, m, b, None, None, int_bd, combo_sensor_weight, combo_sensor_power)
                if res:
                    valid_combos.append(res)
            
            if valid_combos:
                df_combos = pd.DataFrame(valid_combos)
                st.success(f"Successfully discovered {len(df_combos)} valid drone configurations out of all possible permutations.")
                st.caption("Click on any column header to sort by Cost, Hover Time, AUW, etc.")
                st.dataframe(
                    df_combos, 
                    use_container_width=True,
                    column_config={
                        "Cost (EGP)": st.column_config.NumberColumn(format="EGP %.0f"),
                        "Hover Time (min)": st.column_config.NumberColumn(format="%.1f min"),
                        "AUW (g)": st.column_config.NumberColumn(format="%.1f g")
                    }
                )
            else:
                st.warning("No combinations currently satisfy all engineering and safety rules. Try adjusting the target payload or adding stronger components to the database.")