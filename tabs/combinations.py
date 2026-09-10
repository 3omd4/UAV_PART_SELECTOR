import streamlit as st
import pandas as pd
import itertools
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

def render_combinations_tab():
    # Retrieve active database from session state
    FRAMES = st.session_state.get("FRAMES", {})
    MOTORS = st.session_state.get("MOTORS", {})
    BATTERIES = st.session_state.get("BATTERIES", {})
    FLIGHT_CONTROLLERS = st.session_state.get("FLIGHT_CONTROLLERS", {})
    SBCS = st.session_state.get("SBCS", {})
    INTEGRATED_BOARDS = st.session_state.get("INTEGRATED_BOARDS", {})
    
    st.subheader("Explore All Valid Component Combinations")
    st.caption("This tool computes every possible permutation of your hardware database. It guarantees zero Red Warning builds (structurally or electrically unsafe). You can optionally filter out Yellow Warning builds (operational edge cases).")
    
    col_payload, col_weights = st.columns([1, 1], gap="large")
    
    with col_payload:
        st.markdown("#### 1. Payload & Strict Filtering")
        combo_esp32 = st.checkbox("ESP32-S3 SDR Sniffer (+25g, 1.5W)", value=True, key="combo_esp32_key")
        combo_lidar = st.selectbox("Perception Sensor:", [
            "Lightweight 2D LiDAR (~45g, 1.5W)",
            "Stereo VIO Depth Camera (~75g, 2.5W)",
            "Optical Flow + Downward ToF (~15g, 0.5W)",
            "None (Pre-mapped / MoCap) (0g, 0W)"
        ], key="combo_lidar_key")
        
        st.markdown("---")
        strict_mode = st.checkbox(
            "🛡️ **Strict Operational Mode (Zero Warnings)**", 
            value=False, 
            help="Hides builds with Yellow operational warnings (e.g., TWR > 4.5, open propellers, wheelbase > 400mm, or throttle extremes)."
        )
        
    with col_weights:
        st.markdown("#### 2. Mission Profile Scoring")
        st.caption("Adjust weights to rank the generated builds.")
        w_time = st.slider("Endurance Priority (Hover Time)", 0.0, 1.0, 0.5, 0.1)
        w_cost = st.slider("Budget Priority (Lower Cost)", 0.0, 1.0, 0.3, 0.1)
        w_ai = st.slider("Compute Priority (AI TOPS)", 0.0, 1.0, 0.8, 0.1)
        w_twr = st.slider("Agility Priority (Thrust-to-Weight)", 0.0, 1.0, 0.2, 0.1)

    # Payload math mapping
    sensor_weight, sensor_power = 0.0, 0.0
    if combo_esp32:
        sensor_weight += 25.0
        sensor_power += 1.5
    if "LiDAR" in combo_lidar:
        sensor_weight += 45.0
        sensor_power += 1.5
    elif "Stereo" in combo_lidar:
        sensor_weight += 75.0
        sensor_power += 2.5
    elif "Optical" in combo_lidar:
        sensor_weight += 15.0
        sensor_power += 0.5
        
    def evaluate_combination(frame_name, motor_name, battery_name, fc_name, sbc_name, int_board_name):
        frame = FRAMES[frame_name]
        motor = MOTORS[motor_name]
        battery = BATTERIES[battery_name]
        
        fc_weight, fc_price_egp = 0.0, 0.0
        sbc_weight, sbc_price_egp, sbc_power_w = 0.0, 0.0, 0.0
        
        if int_board_name is None:
            fc = FLIGHT_CONTROLLERS[fc_name]
            sbc = SBCS[sbc_name]
            fc_weight, fc_price_egp = fc.get("weight", 0), fc.get("price_egp", 0)
            sbc_weight, sbc_price_egp, sbc_power_w = sbc.get("weight", 0), sbc.get("price_egp", 0), sbc.get("power_w", 0)
            ai_tops = sbc.get("ai_tops", 0.0)
        else:
            int_board = INTEGRATED_BOARDS[int_board_name]
            sbc_weight, sbc_price_egp, sbc_power_w = int_board.get("weight", 0), int_board.get("price_egp", 0), int_board.get("power_w", 0)
            ai_tops = 15.0 if "VOXL" in int_board_name else (40.0 if "Jetson" in int_board_name else 0.0)
            
        esc_wiring_weight = 40.0
        num_motors = frame.get("motor_count", 4)
        propulsion_weight = (motor.get("weight", 0) * num_motors) + esc_wiring_weight
        compute_and_fc_weight = fc_weight + sbc_weight
        total_payload_weight = compute_and_fc_weight + sensor_weight
        
        batt_weight = battery.get("weight_g", 0) or 0.0
        batt_price_egp = battery.get("price_egp", 0) or 0.0
        
        auw_g = frame.get("weight_g", 0) + propulsion_weight + batt_weight + total_payload_weight
        total_max_thrust_g = motor.get("thrust", 0) * num_motors
        twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
        
        motor_total_cost_egp = motor.get("price_egp", 0) * num_motors
        total_cost_egp = frame.get("price_egp", 0) + motor_total_cost_egp + 1500.0 + fc_price_egp + sbc_price_egp + batt_price_egp
        
        hover_mech_power_w = auw_g / motor.get("efficiency_hover_gw", 1.0)
        total_elec_power_w = sbc_power_w + sensor_power + 3.0
        total_hover_power_w = hover_mech_power_w + total_elec_power_w
        usable_wh = battery.get("wh", 0) * 0.85
        flight_time_minutes = (usable_wh / total_hover_power_w) * 60.0 if total_hover_power_w > 0 else 0.0
        
        batt_voltage = battery.get("voltage", 1.0) if battery.get("voltage", 1.0) > 0 else 1.0
        batt_max_discharge_amps = (battery.get("mah", 0) / 1000.0) * battery.get("c_rating", 1)
        total_peak_system_amps = ((motor.get("thrust", 0) / 3.0) / batt_voltage * num_motors) + (total_elec_power_w / batt_voltage)
        
        hover_throttle_pct = (auw_g / total_max_thrust_g) * 100 if total_max_thrust_g > 0 else 100.0

        # ------------------------------------------
        # HARD CONSTRAINTS (Zero Red Warnings Guarantee)
        # ------------------------------------------
        # Explicit rejection for any combination that would trigger a red error in Builder.py
        if battery.get("cells") not in motor.get("cells", []):
            return None
        if total_payload_weight > frame.get("payload_limit_g", 0):
            return None
        if twr < 1.8:
            return None
        if total_peak_system_amps > batt_max_discharge_amps:
            return None

        # ------------------------------------------
        # OPERATIONAL CONSTRAINTS (Yellow Warnings Filter)
        # ------------------------------------------
        if strict_mode:
            # Drops any build that triggers a yellow warning in Builder.py
            if hover_throttle_pct > 65.0 or hover_throttle_pct < 20.0:
                return None
            if twr > 4.5:
                return None
            if frame.get("wheelbase_mm", 0) > 400:
                return None
            if not frame.get("ducted", True):
                return None
        else:
            # Safety ceiling to drop fundamentally unflyable builds even in relaxed mode
            if hover_throttle_pct > 75.0:
                return None

        avionics_str = f"{fc_name} + {sbc_name}" if int_board_name is None else int_board_name
        
        return {
            "Frame": frame_name,
            "Motor": motor_name,
            "Battery": battery_name,
            "Avionics": avionics_str,
            "_FC": fc_name, 
            "_SBC": sbc_name,
            "_IntBoard": int_board_name,
            "Cost (EGP)": float(total_cost_egp),
            "Hover Time (min)": float(flight_time_minutes),
            "TWR": float(twr),
            "Hover Throttle (%)": float(hover_throttle_pct),
            "Peak Draw (A)": float(total_peak_system_amps),
            "AUW (g)": float(auw_g),
            "AI TOPS": float(ai_tops)
        }

    st.divider()
    
    if st.button("🚀 Execute Combinatorial Solver", type="primary", use_container_width=True):
        if not all([FRAMES, MOTORS, BATTERIES, FLIGHT_CONTROLLERS, SBCS]):
            st.error("Incomplete database. Ensure at least one component exists in Frames, Motors, Batteries, FCs, and SBCs before running the solver.")
            return

        with st.spinner("Iterating through physical permutations and applying safety constraints..."):
            valid_combos = []
            
            for f, m, b, fc, sbc in itertools.product(FRAMES.keys(), MOTORS.keys(), BATTERIES.keys(), FLIGHT_CONTROLLERS.keys(), SBCS.keys()):
                res = evaluate_combination(f, m, b, fc, sbc, None)
                if res: valid_combos.append(res)
                    
            for f, m, b, int_bd in itertools.product(FRAMES.keys(), MOTORS.keys(), BATTERIES.keys(), INTEGRATED_BOARDS.keys()):
                res = evaluate_combination(f, m, b, None, None, int_bd)
                if res: valid_combos.append(res)
            
            if not valid_combos:
                st.warning("No configurations satisfied the safety thresholds. Try relaxing the payload or unchecking 'Strict Operational Mode'.")
                if "solver_results" in st.session_state:
                    del st.session_state["solver_results"]
                return
                
            df_combos = pd.DataFrame(valid_combos)
            
            # ==========================================
            # DYNAMIC FITNESS SCORING
            # ==========================================
            def normalize(series, invert=False):
                if series.max() == series.min():
                    return 0.5
                if invert:
                    return (series.max() - series) / (series.max() - series.min())
                return (series - series.min()) / (series.max() - series.min())
            
            norm_time = normalize(df_combos["Hover Time (min)"])
            norm_cost = normalize(df_combos["Cost (EGP)"], invert=True)
            norm_ai = normalize(df_combos["AI TOPS"])
            norm_twr = normalize(df_combos["TWR"])
            
            total_weight = w_time + w_cost + w_ai + w_twr
            if total_weight == 0: total_weight = 1.0 
            
            df_combos["Fitness Score"] = (
                (norm_time * w_time) + 
                (norm_cost * w_cost) + 
                (norm_ai * w_ai) + 
                (norm_twr * w_twr)
            ) / total_weight
            
            df_combos["Fitness Score"] = (df_combos["Fitness Score"] * 100).round(1)
            
            df_combos = df_combos.sort_values(by="Fitness Score", ascending=False).reset_index(drop=True)
            df_combos.index = df_combos.index + 1
            df_combos.index.name = "Rank"
            df_combos = df_combos.reset_index()
            
            st.session_state["solver_results"] = df_combos

    # ==========================================
    # DISPLAY CACHED RESULTS & ROW-CLICK LOGIC
    # ==========================================
    if "solver_results" in st.session_state:
        df_combos = st.session_state["solver_results"]
        
        st.markdown("### 🏆 Top Configurations")
        st.caption("👇 **Click directly on any row below** to instantly load that specific architecture into the Drone Builder tab.")
        
        selection_event = st.dataframe(
            df_combos, 
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            column_config={
                "_FC": None, 
                "_SBC": None,
                "_IntBoard": None,
                "Rank": st.column_config.NumberColumn("Rank", format="#%d"),
                "Fitness Score": st.column_config.ProgressColumn("Fitness Score", format="%d%%", min_value=0, max_value=100),
                "Cost (EGP)": st.column_config.NumberColumn("Est. Cost", format="EGP %.0f"),
                "Hover Time (min)": st.column_config.NumberColumn("Hover Time", format="%.1f min"),
                "AUW (g)": st.column_config.NumberColumn("AUW", format="%.0f g"),
                "TWR": st.column_config.NumberColumn("TWR", format="%.2f"),
                "Hover Throttle (%)": st.column_config.NumberColumn("Throttle", format="%.1f%%"),
                "Peak Draw (A)": st.column_config.NumberColumn("Peak Draw", format="%.1f A"),
                "AI TOPS": st.column_config.NumberColumn("Compute", format="%.1f TOPS")
            }
        )
        
        selected_rows = selection_event.get("selection", {}).get("rows", [])
        
        if selected_rows:
            selected_idx = selected_rows[0]
            row = df_combos.iloc[selected_idx]
            
            st.session_state["builder_preset"] = {
                "frame": row["Frame"],
                "motor": row["Motor"],
                "battery": row["Battery"],
                "fc": row["_FC"],
                "sbc": row["_SBC"],
                "int_board": row["_IntBoard"]
            }
            
            st.success(f"✅ **Rank #{row['Rank']} Architecture locked in!** Switch to the 'Drone Builder' tab to review the Live Physics Engine.")