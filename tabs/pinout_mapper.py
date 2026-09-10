import streamlit as st
import pandas as pd

def render_pinout_mapper_tab():
    st.subheader("Avionics I/O & Pinout Mapper")
    st.caption("Virtually wire your payload to ensure the selected Companion Computer and Flight Controller have sufficient bandwidth and physical ports.")

    if "builder_preset" not in st.session_state or not st.session_state["builder_preset"]:
        st.warning("⚠️ **No Active Architecture:** Please load a configuration from the 'Valid Combinations' or 'Drone Builder' tab first.")
        return

    preset = st.session_state["builder_preset"]
    FLIGHT_CONTROLLERS = st.session_state.get("FLIGHT_CONTROLLERS", {})
    SBCS = st.session_state.get("SBCS", {})
    INTEGRATED_BOARDS = st.session_state.get("INTEGRATED_BOARDS", {})

    is_integrated = preset.get("int_board") is not None
    fc_name = preset.get("fc")
    sbc_name = preset.get("sbc")
    int_board_name = preset.get("int_board")

    col_config, col_routing = st.columns([1, 1.5], gap="large")

    with col_config:
        st.markdown("### 🔌 Active Peripherals")
        st.caption("Toggle payload sensors to observe real-time port allocation.")
        
        req_telem = not is_integrated  # If modular, we MUST have a MAVLink UART connection
        has_depth_cam = st.checkbox("Stereo VIO Depth Camera (RealSense D435i)", value=True)
        has_lidar = st.checkbox("2D LiDAR (RPLidar/LD06)", value=True)
        has_esp32 = st.checkbox("ESP32-S3 SDR Sniffer", value=True)
        has_optical = st.checkbox("Optical Flow + ToF", value=False)
        has_gps = st.checkbox("RTK GPS + Compass Node", value=True)
        has_rc = st.checkbox("RC Receiver (SBUS/CRSF)", value=True)

        st.divider()

        # Simulated I/O capacities based on standard aerospace hardware classes
        sys_io = {"USB_3": 0, "USB_2": 0, "UART": 0, "I2C": 0}
        
        if is_integrated:
            st.markdown(f"**Target:** {int_board_name}")
            # Integrated boards generally have high I/O exposed
            sys_io = {"USB_3": 2, "USB_2": 2, "UART": 4, "I2C": 2}
        else:
            st.markdown(f"**Target SBC:** {sbc_name}")
            st.markdown(f"**Target FC:** {fc_name}")
            # Baseline modular capacities
            sys_io["USB_3"] = 2 if "Orin" in sbc_name or "Pi 5" in sbc_name else 0
            sys_io["USB_2"] = 2 if "Zero" not in sbc_name else 1
            sys_io["UART"] = 6 # Sum of typical FC + SBC UARTs
            sys_io["I2C"] = 2

        st.markdown("#### Total System Capacity")
        st.write(f"- **USB 3.0 Ports:** {sys_io['USB_3']}")
        st.write(f"- **USB 2.0 Ports:** {sys_io['USB_2']}")
        st.write(f"- **UART (Serial):** {sys_io['UART']}")
        st.write(f"- **I2C Buses:** {sys_io['I2C']}")

    with col_routing:
        st.markdown("### 🗺️ Connection Topology")
        
        routing_table = []
        used_usb3, used_usb2, used_uart, used_i2c = 0, 0, 0, 0
        
        # MAVLink Bridge
        if req_telem:
            routing_table.append({"Device": "SBC ↔ FC Bridge", "Protocol": "UART", "Bandwidth": "High (921600 baud)", "Status": "✅ Mapped"})
            used_uart += 1
            
        # RC Receiver
        if has_rc:
            routing_table.append({"Device": "RC Receiver", "Protocol": "UART (RX only)", "Bandwidth": "Low", "Status": "✅ Mapped"})
            used_uart += 1
            
        # GPS/Compass
        if has_gps:
            routing_table.append({"Device": "RTK GPS", "Protocol": "UART", "Bandwidth": "Medium (115200 baud)", "Status": "✅ Mapped"})
            routing_table.append({"Device": "Magnetometer", "Protocol": "I2C", "Bandwidth": "Low", "Status": "✅ Mapped"})
            used_uart += 1
            used_i2c += 1
            
        # Depth Camera
        if has_depth_cam:
            if used_usb3 < sys_io["USB_3"]:
                routing_table.append({"Device": "Stereo Depth Camera", "Protocol": "USB 3.0", "Bandwidth": "Extreme (5 Gbps)", "Status": "✅ Mapped"})
                used_usb3 += 1
            else:
                routing_table.append({"Device": "Stereo Depth Camera", "Protocol": "USB 3.0", "Bandwidth": "Extreme (5 Gbps)", "Status": "❌ Port Unavailable"})
                used_usb3 += 1 # Intentionally increment to trigger the error check later
                
        # LiDAR
        if has_lidar:
            if used_usb2 < sys_io["USB_2"]:
                routing_table.append({"Device": "2D LiDAR", "Protocol": "USB 2.0 (CP2102)", "Bandwidth": "Medium", "Status": "✅ Mapped"})
                used_usb2 += 1
            elif used_uart < sys_io["UART"]:
                routing_table.append({"Device": "2D LiDAR", "Protocol": "UART", "Bandwidth": "Medium", "Status": "✅ Mapped"})
                used_uart += 1
            else:
                routing_table.append({"Device": "2D LiDAR", "Protocol": "UART / USB 2.0", "Bandwidth": "Medium", "Status": "❌ Port Unavailable"})
                used_uart += 1
                
        # ESP32
        if has_esp32:
            if used_uart < sys_io["UART"]:
                routing_table.append({"Device": "ESP32 SDR Sniffer", "Protocol": "UART", "Bandwidth": "Medium", "Status": "✅ Mapped"})
                used_uart += 1
            else:
                routing_table.append({"Device": "ESP32 SDR Sniffer", "Protocol": "UART", "Bandwidth": "Medium", "Status": "❌ Port Unavailable"})
                used_uart += 1
                
        # Optical Flow
        if has_optical:
            if used_i2c < sys_io["I2C"]:
                routing_table.append({"Device": "Optical Flow + ToF", "Protocol": "I2C", "Bandwidth": "Low", "Status": "✅ Mapped"})
                used_i2c += 1
            else:
                routing_table.append({"Device": "Optical Flow + ToF", "Protocol": "I2C", "Bandwidth": "Low", "Status": "❌ Port Unavailable"})
                used_i2c += 1

        df_routing = pd.DataFrame(routing_table)
        
        if not df_routing.empty:
            st.dataframe(
                df_routing, 
                use_container_width=True, 
                hide_index=True,
                column_config={"Status": st.column_config.TextColumn("Status", width="medium")}
            )
        else:
            st.info("No payload peripherals selected.")

        st.divider()
        st.markdown("### 🛡️ I/O Integrity Verification")
        
        checks_passed = True
        
        if used_usb3 > sys_io["USB_3"]:
            st.error(f"❌ **USB 3.0 Bottleneck:** Payload requires {used_usb3} USB 3.0 ports, but the compute board only supplies {sys_io['USB_3']}. High-bandwidth vision data will crash.")
            checks_passed = False
            
        if used_usb2 > sys_io["USB_2"]:
            st.error(f"❌ **USB 2.0 Saturation:** Out of standard USB ports. Consider routing peripherals directly to open UART pads.")
            checks_passed = False
            
        if used_uart > sys_io["UART"]:
            st.error(f"❌ **UART Exhaustion:** System requires {used_uart} serial ports but only {sys_io['UART']} are physically available. You must upgrade the Flight Controller or drop a sensor.")
            checks_passed = False
            
        if used_i2c > sys_io["I2C"]:
            st.error(f"❌ **I2C Address Conflict / Saturation:** I2C bus limits exceeded.")
            checks_passed = False
            
        if checks_passed:
            st.success("✅ **I/O Routing Validated:** The selected processing architecture possesses adequate bandwidth and physical headers for the entire perception and control payload.")