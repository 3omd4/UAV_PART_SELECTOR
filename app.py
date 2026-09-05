import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Indoor UAV Part list",
    page_icon="🛩️",
    layout="wide"
)

# ==========================================
# 1. COMPONENT DATABASE DEFINITIONS
# ==========================================

MOTORS = {
    "XXD A2212 (1000KV)": {
        "stator": "22 x 12 mm", "weight": 48.0, "kv": 1000, "cells": [3, 4],
        "prop": "8\"–10\"", "thrust": 900.0, "source": "Local (Makers/RAM)",
        "price_egp": 430.0, "price_usd": 8.5, "efficiency_hover_gw": 8.0,
        "notes": "Large open frames only; high downwash indoors.",
        "buy_url": "https://microohm-eg.com/a2212-6t-2200kv-brushless-motor-for-drone/"
    },
    "Holybro 2216 (920KV)": {
        "stator": "22 x 16 mm", "weight": 54.0, "kv": 920, "cells": [4],
        "prop": "9\"–10\"", "thrust": 1050.0, "source": "Global / Kit",
        "price_egp": 1182.83, "price_usd": 23.2, "efficiency_hover_gw": 8.5,
        "notes": "Standard X500 kit motor; too large for tight swarms.",
        "buy_url": "https://ar.aliexpress.com/item/1005004562567395.html"
    },
    "EMAX ECO II 2207 (1700KV)": {
        "stator": "22 x 7 mm", "weight": 33.0, "kv": 1700, "cells": [4, 5, 6],
        "prop": "5\"", "thrust": 1500.0, "source": "Global / FPV shops",
        "price_egp": 1199.00, "price_usd": 23.5, "efficiency_hover_gw": 6.8,
        "notes": "Top pick for 330mm custom ducted frame lifting SBC.",
        "buy_url": "https://www.fruugo.eg/emax-eco-ii-2207-1700kv-brushless-motor-drone-multirotor-cw-motor-3-6s-for-rc-fpv-racing-drone/p-463531857-975406632"
    },
    "T-Motor F2203.5 (1500KV)": {
        "stator": "22 x 3.5 mm", "weight": 19.7, "kv": 1500, "cells": [4, 5, 6],
        "prop": "4\"–5\"", "thrust": 875.0, "source": "Global (Specialized RC)",
        "price_egp": 936.95, "price_usd": 18.4, "efficiency_hover_gw": 7.5,
        "notes": "High efficiency pick for lightweight micro-heavy lifters.",
        "buy_url": "https://ar.aliexpress.com/item/1005007986142505.html"
    },
    "BrotherHobby Avenger 2004 (1700KV)": {
        "stator": "20 x 4 mm", "weight": 16.6, "kv": 1700, "cells": [4],
        "prop": "4\"", "thrust": 700.0, "source": "Global (Specialized FPV)",
        "price_egp": 1300.86, "price_usd": 25.5, "efficiency_hover_gw": 7.0,
        "notes": "Compact 4-inch frames; payload must stay under 250g.",
        "buy_url": "https://ar.aliexpress.com/item/1005010804220626.html"
    },
    "GEPRC SPEEDX2 2105.5 (2650KV)": {
        "stator": "21 x 5.5 mm", "weight": 21.0, "kv": 2650, "cells": [4, 6],
        "prop": "3.5\"", "thrust": 800.0, "source": "Global (GEPRC/Banggood)",
        "price_egp": 988.03, "price_usd": 19.4, "efficiency_hover_gw": 5.2,
        "notes": "Standard CineLog35 motor; high RPM draw cuts endurance.",
        "buy_url": "https://ar.aliexpress.com/item/1005009435278291.html"
    },
    "iFlight XING2 1404 (3800KV)": {
        "stator": "14 x 4 mm", "weight": 9.1, "kv": 3800, "cells": [3, 4],
        "prop": "2.5\"–3.5\"", "thrust": 385.0, "source": "Global (iFlight/AliExpress)",
        "price_egp": 631.83, "price_usd": 12.4, "efficiency_hover_gw": 5.0,
        "notes": "Too weak to lift an SBC or LiDAR payload.",
        "buy_url": "https://ar.aliexpress.com/item/1005002346308981.html"
    }
}

FLIGHT_CONTROLLERS = {
    "Holybro Pixhawk 6C Mini": {
        "mcu": "STM32H743", "weight": 39.0, "dim": "53.3 x 39 x 16.2 mm",
        "firmware": "PX4, ArduPilot", "price_egp": 11073.91, "price_usd": 150.0,
        "notes": "Full aluminum case, dual IMU redundancy.",
        "buy_url": "https://holybro.com/"
    },
    "Matek H743-SLIM V3": {
        "mcu": "STM32H743VIH6", "weight": 7.0, "dim": "36 x 36 x 5 mm",
        "firmware": "ArduPilot, BetaFlight", "price_egp": 3435.92, "price_usd": 115.0,
        "notes": "Ultra-lightweight bare-PCB, dual IMUs.",
        "buy_url": "https://ardupilot.org/"
    },
    "Holybro Kakute H7 Mini": {
        "mcu": "STM32H743", "weight": 5.1, "dim": "29 x 29 mm",
        "firmware": "ArduPilot, BetaFlight", "price_egp": 3293.61, "price_usd": 75.0,
        "notes": "Compact 20x20mm mounting for small whoops.",
        "buy_url": "https://holybro.com/"
    },
    "CUAV Nora+": {
        "mcu": "STM32H743", "weight": 48.0, "dim": "60 x 38.8 x 17.5 mm",
        "firmware": "PX4, ArduPilot", "price_egp": 30305.72, "price_usd": 260.0,
        "notes": "Triple redundant IMU; heavy and expensive.",
        "buy_url": "https://store.cuav.net/"
    }
}

SBCS = {
    "NVIDIA Jetson Orin Nano (SOM + Carrier)": {
        "cpu": "6-core ARM / 8GB", "ai_tops": 40.0, "weight": 75.0, "dim": "100 x 79 x 25 mm",
        "power_w": 12.0, "price_egp": 35000.0, "price_usd": 449.0,
        "best_for": "Heavy visual SLAM & deep learning.",
        "buy_url": "https://www.nvidia.com/"
    },
    "Khadas Edge2 (Maker Kit)": {
        "cpu": "8-core RK3588S / 8GB", "ai_tops": 6.0, "weight": 25.0, "dim": "82 x 57.5 x 5.7 mm",
        "power_w": 7.5, "price_egp": 21837.0, "price_usd": 199.0,
        "best_for": "Balanced edge AI & low-profile mounting.",
        "buy_url": "https://www.khadas.com/"
    },
    "Raspberry Pi 5 (8GB)": {
        "cpu": "Quad-core BCM2712", "ai_tops": 0.0, "weight": 46.0, "dim": "85 x 56 x 15 mm",
        "power_w": 8.0, "price_egp": 14000.0, "price_usd": 80.0,
        "best_for": "Ubiquitous ROS 2 nodes, 2D LiDAR SLAM.",
        "buy_url": "https://www.raspberrypi.com/"
    },
    "Radxa Zero 3W": {
        "cpu": "Quad-core RK3566", "ai_tops": 1.0, "weight": 9.0, "dim": "65 x 30 x 5 mm",
        "power_w": 3.0, "price_egp": 4240.0, "price_usd": 25.0,
        "best_for": "Minimalist weight budget; ESP32 mesh router.",
        "buy_url": "https://radxa.com/"
    }
}

INTEGRATED_BOARDS = {
    "ModalAI VOXL 2 Mini": {
        "arch": "True All-in-One (DSP PX4)", "compute": "Qualcomm QRB5165", "dim": "50 x 50 x 15 mm",
        "weight": 11.0, "power_w": 5.0, "price_egp": 63699.0, "price_usd": 1249.0,
        "best_for": "Extreme weight limits; professional edge AI.",
        "buy_url": "https://www.modalai.com/"
    },
    "ModalAI VOXL 2": {
        "arch": "True All-in-One (DSP PX4)", "compute": "Qualcomm QRB5165", "dim": "70 x 70 x 15 mm",
        "weight": 16.0, "power_w": 6.0, "price_egp": 66249.0, "price_usd": 1299.0,
        "best_for": "High-I/O swarms with multiple stereo sensors.",
        "buy_url": "https://www.modalai.com/"
    },
    "Holybro Pixhawk Jetson Baseboard": {
        "arch": "Unified Carrier", "compute": "Jetson Orin", "dim": "120 x 85 x 30 mm",
        "weight": 203.2, "power_w": 18.0, "price_egp": 24859.94, "price_usd": 487.0,
        "best_for": "Heavy AI on larger frames.",
        "buy_url": "https://holybro.com/"
    },
    "Holybro Pixhawk RPi CM4 Baseboard": {
        "arch": "Unified Carrier", "compute": "RPi CM4", "dim": "110 x 85 x 25 mm",
        "weight": 95.0, "power_w": 7.0, "price_egp": 25577.62, "price_usd": 350.0,
        "best_for": "Academic clean-wiring swarms.",
        "buy_url": "https://holybro.com/"
    },
    "BeagleBone Blue": {
        "arch": "Legacy All-in-One", "compute": "1GHz Cortex-A8", "dim": "86 x 54 x 15 mm",
        "weight": 35.0, "power_w": 2.0, "price_egp": 3500.0, "price_usd": 80.0,
        "best_for": "Ultra-budget 2D mapping without cameras.",
        "buy_url": "https://www.beagleboard.org/"
    }
}

FRAMES = {
    "Custom 330mm Ducted (Option C)": {
        "wheelbase_mm": 330, "weight_g": 180.0, "payload_limit_g": 450.0,
        "motor_count": 4, "max_prop": "5\"", "ducted": True,
        "price_egp": 3000.0, "price_usd": 58.8, "notes": "Optimized NACA ducts; optimal indoor swarm baseline.",
        "buy_url": "https://grabcad.com/"
    },
    "GEPRC CineLog35 V2 Frame": {
        "wheelbase_mm": 142, "weight_g": 133.7, "payload_limit_g": 250.0,
        "motor_count": 4, "max_prop": "3.5\"", "ducted": True,
        "price_egp": 3566.37, "price_usd": 70.0, "notes": "Heavy-duty injection guards; high drag.",
        "buy_url": "https://geprc.com/"
    },
    "BetaFPV Pavo35 Frame": {
        "wheelbase_mm": 148, "weight_g": 113.9, "payload_limit_g": 250.0,
        "motor_count": 4, "max_prop": "3.5\"", "ducted": True,
        "price_egp": 2547.41, "price_usd": 50.0, "notes": "Lightweight 3.5\" cinewhoop.",
        "buy_url": "https://betafpv.com/"
    },
    "iFlight Protek35 V1.4 Frame": {
        "wheelbase_mm": 151, "weight_g": 213.5, "payload_limit_g": 300.0,
        "motor_count": 4, "max_prop": "3.5\"", "ducted": True,
        "price_egp": 3311.63, "price_usd": 65.0, "notes": "Robust carbon with thick guards.",
        "buy_url": "https://www.getfpv.com/"
    },
    "Holybro X500 V2 Frame Kit": {
        "wheelbase_mm": 500, "weight_g": 365.0, "payload_limit_g": 1500.0,
        "motor_count": 4, "max_prop": "10\"", "ducted": False,
        "price_egp": 6063.95, "price_usd": 119.03, "notes": "410-500mm wheelbase is physically large for tight rooms.",
        "buy_url": "https://www.3dxr.co.uk/"
    }
}

BATTERIES = {
    "4S1P Molicel P45B 21700 Li-ion (Custom)": {
        "cells": 4,
        "mah": 4500,
        "weight_g": 280.0,
        "c_rating": 10,
        "voltage": 14.8,
        "wh": 66.6,
        "price_egp": 2500.0,
        "price_usd": 49.0,
        "dimensions": "N/A",
        "notes": "Highest energy density (238 Wh/kg); low IR prevents voltage sag.",
        "buy_url": "https://www.18650batterystore.com/products/molicel-p45b"
    },

    "LAVA 6S 1100mAh LiPo": {
        "cells": 6,
        "mah": 1100,
        "weight_g": 192.0,
        "c_rating": 100,
        "voltage": 22.2,
        "wh": 24.4,
        "price_egp": 1783.13,
        "price_usd": 35.0,
        "dimensions": "78 × 38 × 36 mm",
        "notes": "High burst C-rating, low capacity.",
        "buy_url": "https://betafpv.com/products/lava-6s-1100mah-lipo-battery"
    },

    "Tattu 6S 1550mAh LiPo R-Line": {
        "cells": 6,
        "mah": 1550,
        "weight_g": 254.0,
        "c_rating": 150,
        "voltage": 22.2,
        "wh": 34.4,
        "price_egp": 2037.87,
        "price_usd": 40.0,
        "dimensions": "78 × 37 × 52 mm",
        "notes": "Racing LiPo; extremely high discharge capability with modest endurance.",
        "buy_url": "https://genstattu.com/tattu-r-line-version-5-0-1550mah-6s-150c-22-2v-lipo-battery-pack-with-xt60-plug/"
    },

    "Lithium Polymer 3S 10400mAh 40C (170mm)": {
        "cells": 3,
        "mah": 10400,
        "weight_g": None,
        "c_rating": 40,
        "voltage": 11.1,
        "wh": 115.4,
        "price_egp": 5100.0,
        "price_usd": 100.10,
        "dimensions": "170 × 55 × 27 mm",
        "notes": "Very high-capacity 3S pack for long endurance; heavy and physically large.",
        "buy_url": "https://makerselectronics.com/product/lithium-polymer-battery-11-1v-3s-104/"
    },

    "Lithium Polymer 3S 10400mAh 40C (150mm)": {
        "cells": 3,
        "mah": 10400,
        "weight_g": None,
        "c_rating": 40,
        "voltage": 11.1,
        "wh": 115.4,
        "price_egp": 4500.0,
        "price_usd": 88.33,
        "dimensions": "150 × 70 × 22 mm",
        "notes": "High-capacity 3S endurance pack with a shorter but wider form factor.",
        "buy_url": "https://makerselectronics.com/product/lithium-polymer-battery-11-1-v-10-2/"
    },

    "Lithium Polymer 3S 3300mAh 40C": {
        "cells": 3,
        "mah": 3300,
        "weight_g": 250.0,
        "c_rating": 40,
        "voltage": 11.1,
        "wh": 36.6,
        "price_egp": 1950.0,
        "price_usd": 38.28,
        "dimensions": "140 × 45 × 21 mm",
        "notes": "Medium-capacity 3S pack; reasonable balance between endurance and weight.",
        "buy_url": "https://makerselectronics.com/product/polymer-battery-11-1v-3300mah-40c/"
    },

    "Lithium Polymer 3S 1500mAh 35C": {
        "cells": 3,
        "mah": 1500,
        "weight_g": 110.0,
        "c_rating": 35,
        "voltage": 11.1,
        "wh": 16.7,
        "price_egp": 1100.0,
        "price_usd": 21.59,
        "dimensions": "75 × 35 × 25 mm",
        "notes": "Lightweight 3S battery suitable for smaller drone platforms.",
        "buy_url": "https://makerselectronics.com/product/polymer-battery-11-1v-1500mah-35c/"
    },

    "Lithium Polymer 3S 22000mAh 35C": {
        "cells": 3,
        "mah": 22000,
        "weight_g": None,
        "c_rating": 35,
        "voltage": 11.1,
        "wh": 244.2,
        "price_egp": 12000.0,
        "price_usd": 235.54,
        "dimensions": "180 × 75 × 35 mm",
        "notes": "Extremely high-capacity endurance pack; very heavy and intended for large platforms.",
        "buy_url": "https://makerselectronics.com/product/lithium-polymer-batter-11-1v-3s-2200/"
    },

    "Lithium Polymer 3S 10400mAh 40C (160mm)": {
        "cells": 3,
        "mah": 10400,
        "weight_g": None,
        "c_rating": 40,
        "voltage": 11.1,
        "wh": 115.4,
        "price_egp": 5100.0,
        "price_usd": 100.10,
        "dimensions": "160 × 45 × 30 mm",
        "notes": "High-capacity 3S endurance pack with a relatively narrow form factor.",
        "buy_url": "https://makerselectronics.com/product/lithium-polymer-battery-11-1-v-3s-10/"
    },

    "Lithium Polymer 3S 5200mAh 40C": {
        "cells": 3,
        "mah": 5200,
        "weight_g": 350.0,
        "c_rating": 40,
        "voltage": 11.1,
        "wh": 57.7,
        "price_egp": 2750.0,
        "price_usd": 53.98,
        "dimensions": "145 × 50 × 28 mm",
        "notes": "Good capacity-to-weight balance for medium-size 3S systems.",
        "buy_url": "https://makerselectronics.com/product/polymer-battery-11-1v-5200mah-40c/"
    },

    "Lithium Polymer 3S 2200mAh 40C (UGE-One)": {
        "cells": 3,
        "mah": 2200,
        "weight_g": 120.0,
        "c_rating": 40,
        "voltage": 11.1,
        "wh": 24.4,
        "price_egp": None,
        "price_usd": None,
        "dimensions": "92 × 31 × 19 mm",
        "notes": "Compact 3S pack suitable for small drones and RC platforms.",
        "buy_url": "https://uge-one.com/product/lithium-polymer-lipo-rechargeable-battery-11-1v-2200mah-40c-for-drone-rc-helicopter/"
    },

    "SUPER NANO 3S 2200mAh LiPo": {
        "cells": 3,
        "mah": 2200,
        "weight_g": 185.0,
        "c_rating": 60,
        "voltage": 11.1,
        "wh": 24.4,
        "price_egp": 1850.0,
        "price_usd": 36.31,
        "dimensions": "108 × 36.5 × 25.5 mm",
        "notes": "Compact 3S pack with a relatively high discharge rating.",
        "buy_url": "https://circuits-elec.com/products/super-nano-lithium-polymer-battery-11-1-v-2200-mah-3s"
    },

    "SUPER NANO 3S 8000mAh 35C": {
        "cells": 3,
        "mah": 8000,
        "weight_g": 600.0,
        "c_rating": 35,
        "voltage": 11.1,
        "wh": 88.8,
        "price_egp": 3600.0,
        "price_usd": 70.66,
        "dimensions": "186 × 65 × 55 mm",
        "notes": "Heavy endurance pack for large platforms.",
        "buy_url": "https://circuits-elec.com/products/lithium-polymer-battery-11-1-v-10400-mah-40c-pre-ordered"
    }
}
# ==========================================
# 2. APPLICATION LAYOUT
# ==========================================

st.title("Autonomous Indoor Swarm UAV Trade Study & Builder")
st.caption("Systems engineering evaluator for localized decentralized SLAM & RF/RSSI mapping platforms.")

tab_catalogs, tab_builder = st.tabs(["Component Catalogs", "Drone Builder"])

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
    
    # All-Up Weight (AUW)
    auw_g = frame["weight_g"] + propulsion_weight + battery["weight_g"] + total_payload_weight
    auw_kg = auw_g / 1000.0
    
    # Thrust and TWR
    total_max_thrust_g = motor["thrust"] * num_motors
    twr = total_max_thrust_g / auw_g if auw_g > 0 else 0.0
    
    # Costs
    motor_total_cost_egp = motor["price_egp"] * num_motors
    motor_total_cost_usd = motor["price_usd"] * num_motors
    esc_cost_egp = 1500.0  # est 4-in-1 40A ESC
    esc_cost_usd = 30.0
    
    total_cost_egp = frame["price_egp"] + motor_total_cost_egp + esc_cost_egp + fc_price_egp + sbc_price_egp + battery["price_egp"]
    total_cost_usd = frame["price_usd"] + motor_total_cost_usd + esc_cost_usd + fc_price_usd + sbc_price_usd + battery["price_usd"]

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
            st.write(f"- Battery Pack: `{battery['weight_g']} g`")
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
            st.markdown(f"AUW = {frame['weight_g']}g + ({motor['weight']}g × {num_motors}) + {esc_wiring_weight}g + {battery['weight_g']}g + {compute_and_fc_weight}g + {sensor_weight}g = **{auw_g:.1f} g**")
            
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
    bom_data.append({"Component": "Battery", "Model": battery_name, "Weight (g)": battery["weight_g"], "Cost (EGP)": battery["price_egp"], "Where to Buy": battery["buy_url"]})
    
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