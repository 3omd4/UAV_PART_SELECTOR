import streamlit as st
import pandas as pd
import numpy as np
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

def render_flight_envelope_tab():
    st.subheader("Flight Envelope & Kinematic Simulator")
    st.caption("Model theoretical forward speeds, tilt-angle constraints, and wind resistance thresholds for autonomous path-planning algorithm bounds.")

    if "builder_preset" not in st.session_state or not st.session_state["builder_preset"]:
        st.warning("⚠️ **No Active Architecture:** Please load a configuration from the 'Valid Combinations' or 'Drone Builder' tab first.")
        return

    preset = st.session_state["builder_preset"]
    FRAMES = st.session_state.get("FRAMES", {})
    MOTORS = st.session_state.get("MOTORS", {})
    BATTERIES = st.session_state.get("BATTERIES", {})

    frame = FRAMES.get(preset.get("frame"), {})
    motor = MOTORS.get(preset.get("motor"), {})
    battery = BATTERIES.get(preset.get("battery"), {})

    if not frame or not motor or not battery:
        st.error("❌ Corrupted hardware preset. Please re-load your configuration.")
        return

    col_controls, col_plot = st.columns([1, 2], gap="large")

    # ==========================================
    # KINEMATIC MATH ENGINE
    # ==========================================
    # 1. Propeller Pitch Extraction
    # Standard assumption: if prop string is '5"', pitch is usually ~0.6 to 0.8 times the diameter for standard multirotors.
    # We will estimate pitch as 0.7 * diameter if exact pitch isn't specified in standard format (e.g., 5040).
    prop_dia_in = extract_inches(frame.get("max_prop", "")) or extract_inches(motor.get("prop", ""))
    estimated_pitch_in = prop_dia_in * 0.7 

    # 2. RPM & Pitch Speed Calculations
    batt_voltage = battery.get("voltage", 14.8)
    motor_kv = motor.get("kv", 1000)
    
    # Motor efficiency under load is typically ~80-85% of its free-spinning RPM
    load_efficiency = 0.85 
    max_rpm = batt_voltage * motor_kv * load_efficiency
    
    # Pitch speed = RPM * Pitch (inches) * (conversion to meters) / 60 seconds
    max_pitch_speed_ms = (max_rpm * estimated_pitch_in * 0.0254) / 60.0
    max_pitch_speed_kmh = max_pitch_speed_ms * 3.6

    with col_controls:
        st.markdown("### 🎛️ Flight Controller Limits")
        
        max_tilt_deg = st.slider("Max Allowed Tilt Angle (°)", min_value=10, max_value=60, value=35, step=5, help="The maximum pitch/roll angle permitted by your flight controller's attitude limits.")
        system_efficiency = st.slider("Aerodynamic Efficiency (%)", min_value=50, max_value=100, value=70, step=5, help="Accounts for parasitic drag from the frame and sensors.") / 100.0

        st.divider()
        
        st.markdown("### 📊 Hardware Boundaries")
        st.write(f"- **Operating Voltage:** `{batt_voltage} V`")
        st.write(f"- **Motor KV:** `{motor_kv} KV`")
        st.write(f"- **Est. Loaded RPM:** `{max_rpm:,.0f} RPM`")
        st.write(f"- **Theoretical V-Max:** `{max_pitch_speed_kmh:.1f} km/h`")

    # ==========================================
    # DATA GENERATION & PLOTTING
    # ==========================================
    with col_plot:
        st.markdown("### 📈 Forward Velocity vs. Tilt Angle")
        
        # Generate data for the curve (0 degrees to user's max tilt)
        angles_deg = np.arange(0, max_tilt_deg + 1, 1)
        angles_rad = np.radians(angles_deg)
        
        # Calculate horizontal speed component
        # V_horizontal = V_pitch * sin(tilt_angle) * efficiency_loss_due_to_drag
        horizontal_speeds_ms = max_pitch_speed_ms * np.sin(angles_rad) * system_efficiency
        horizontal_speeds_kmh = horizontal_speeds_ms * 3.6
        
        df_plot = pd.DataFrame({
            "Tilt Angle (°)": angles_deg,
            "Forward Speed (km/h)": horizontal_speeds_kmh
        }).set_index("Tilt Angle (°)")

        st.line_chart(df_plot, y="Forward Speed (km/h)", color="#ff4b4b")

        # Key Takeaways
        max_achievable_speed_kmh = horizontal_speeds_kmh[-1]
        max_achievable_speed_ms = horizontal_speeds_ms[-1]
        safe_wind_limit_ms = max_achievable_speed_ms * 0.5 # 50% rule of thumb for safe wind rejection
        
        st.markdown("#### 🌪️ Environmental & Planning Constraints")
        c1, c2, c3 = st.columns(3)
        c1.metric("Target Top Speed", f"{max_achievable_speed_kmh:.1f} km/h", help=f"At {max_tilt_deg}° tilt")
        c2.metric("Max Waypoint Velocity", f"{max_achievable_speed_ms:.1f} m/s", help="Use this as the hard limit in your trajectory generation algorithms.")
        c3.metric("Safe Wind Rejection", f"{safe_wind_limit_ms:.1f} m/s", help="Max ambient wind speed before the drone loses the ability to hold a stationary GPS coordinate reliably.")

    # ==========================================
    # MATHEMATICAL DERIVATIONS
    # ==========================================
    st.divider()
    with st.expander("View Kinematic Equations"):
        math1, math2 = st.columns(2)
        with math1:
            st.markdown("**1. Loaded Motor RPM**")
            st.latex(r"RPM_{max} = V_{batt} \times KV \times \eta_{motor}")
            st.markdown(f"**Result:** {batt_voltage}V × {motor_kv} × 0.85 = `{max_rpm:,.0f} RPM`")
            
            st.markdown("**2. Absolute Pitch Velocity ($V_{pitch}$)**")
            st.latex(r"V_{pitch} = \frac{RPM_{max} \times Pitch_{in} \times 0.0254}{60}")
            st.markdown(f"**Result:** `{max_pitch_speed_ms:.1f} m/s`")
            
        with math2:
            st.markdown("**3. Practical Forward Velocity ($V_{forward}$)**")
            st.latex(r"V_{forward} = V_{pitch} \times \sin(\theta_{tilt}) \times \eta_{aero}")
            st.markdown(f"**Result:** {max_pitch_speed_ms:.1f} m/s × $\sin({max_tilt_deg}^\circ)$ × {system_efficiency} = `{max_achievable_speed_ms:.1f} m/s`")