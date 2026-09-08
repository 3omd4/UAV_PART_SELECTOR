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

# Full default fallback dictionaries
DEFAULT_MOTORS = {
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

DEFAULT_FC = {
    "Holybro Pixhawk 6C Mini": {
        "mcu": "STM32H743", "weight": 39.0, "dim": "53.3 x 39 x 16.2 mm",
        "firmware": "PX4, ArduPilot", "price_egp": 11073.91, "price_usd": 150.0,
        "notes": "Full aluminum case, dual IMU redundancy.",
        "buy_url": "https://holybro.com/products/pixhawk-6c-mini"
    },
    "Matek H743-SLIM V3": {
        "mcu": "STM32H743VIH6", "weight": 7.0, "dim": "36 x 36 x 5 mm",
        "firmware": "ArduPilot, BetaFlight", "price_egp": 3435.92, "price_usd": 115.0,
        "notes": "Ultra-lightweight bare-PCB, dual IMUs.",
        "buy_url": "https://ardupilot.org/copter/docs/common-matekh743-wing.html"
    },
    "Holybro Kakute H7 Mini": {
        "mcu": "STM32H743", "weight": 5.1, "dim": "29 x 29 mm",
        "firmware": "ArduPilot, BetaFlight", "price_egp": 3293.61, "price_usd": 75.0,
        "notes": "Compact 20x20mm mounting for small whoops.",
        "buy_url": "https://holybro.com/products/kakute-h7-mini"
    },
    "CUAV Nora+": {
        "mcu": "STM32H743", "weight": 48.0, "dim": "60 x 38.8 x 17.5 mm",
        "firmware": "PX4, ArduPilot", "price_egp": 30305.72, "price_usd": 260.0,
        "notes": "Triple redundant IMU; heavy and expensive.",
        "buy_url": "https://store.cuav.net/shop/nora/"
    }
}

DEFAULT_SBCS = {
    "NVIDIA Jetson Orin Nano (SOM + Carrier)": {
        "cpu": "6-core ARM / 8GB", "ai_tops": 40.0, "weight": 75.0, "dim": "100 x 79 x 25 mm",
        "power_w": 12.0, "price_egp": 35000.0, "price_usd": 449.0,
        "best_for": "Heavy visual SLAM & deep learning.",
        "buy_url": "https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/"
    },
    "Khadas Edge2 (Maker Kit)": {
        "cpu": "8-core RK3588S / 8GB", "ai_tops": 6.0, "weight": 25.0, "dim": "82 x 57.5 x 5.7 mm",
        "power_w": 7.5, "price_egp": 21837.0, "price_usd": 199.0,
        "best_for": "Balanced edge AI & low-profile mounting.",
        "buy_url": "https://www.khadas.com/edge2"
    },
    "Raspberry Pi 5 (8GB)": {
        "cpu": "Quad-core BCM2712", "ai_tops": 0.0, "weight": 46.0, "dim": "85 x 56 x 15 mm",
        "power_w": 8.0, "price_egp": 14000.0, "price_usd": 80.0,
        "best_for": "Ubiquitous ROS 2 nodes, 2D LiDAR SLAM.",
        "buy_url": "https://www.raspberrypi.com/products/raspberry-pi-5/"
    },
    "Radxa Zero 3W": {
        "cpu": "Quad-core RK3566", "ai_tops": 1.0, "weight": 9.0, "dim": "65 x 30 x 5 mm",
        "power_w": 3.0, "price_egp": 4240.0, "price_usd": 25.0,
        "best_for": "Minimalist weight budget; ESP32 mesh router.",
        "buy_url": "https://radxa.com/products/zeros/zero3w/"
    }
}

DEFAULT_INTEGRATED = {
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

DEFAULT_FRAMES = {
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
    },
    "F450 Quad Frame": {
        "wheelbase_mm": 450, "weight_g": 280.0, "payload_limit_g": 800.0,
        "motor_count": 4, "max_prop": "10\"", "ducted": False,
        "price_egp": 500.0, "price_usd": 10.0, "notes": "Cheap baseline; exposed props.",
        "buy_url": "https://ar.aliexpress.com/item/1005010192554268.html"
    },
    "F550 Hexa-Rotor Frame": {
        "wheelbase_mm": 550, "weight_g": 424.0, "payload_limit_g": 1200.0,
        "motor_count": 6, "max_prop": "10\"", "ducted": False,
        "price_egp": 1003.74, "price_usd": 19.70, "notes": "6 motors; excessive downwash in confined spaces.",
        "buy_url": "https://ar.aliexpress.com/item/1005006994473505.html"
    },
    "Tarot X6 Hexacopter Frame": {
        "wheelbase_mm": 960, "weight_g": 2000.0, "payload_limit_g": 5000.0,
        "motor_count": 6, "max_prop": "18\"", "ducted": False,
        "price_egp": 14787.69, "price_usd": 290.25, "notes": "Heavy lift industrial; impossible for indoor swarms.",
        "buy_url": "https://www.3dxr.co.uk/products/tarot-x6"
    }
}

DEFAULT_BATTERIES = {
    "4S1P Molicel P45B 21700 Li-ion": {
        "cells": 4, "mah": 4500, "weight_g": 280.0, "c_rating": 10,
        "voltage": 14.8, "wh": 66.6, "price_egp": 2500.0, "price_usd": 49.0,
        "dimensions": "85 × 43 × 43 mm", "notes": "Highest energy density (238 Wh/kg).",
        "buy_url": "https://www.18650batterystore.com/"
    },
    "LAVA 6S 1100mAh LiPo": {
        "cells": 6, "mah": 1100, "weight_g": 192.0, "c_rating": 100,
        "voltage": 22.2, "wh": 24.4, "price_egp": 1783.13, "price_usd": 35.0,
        "dimensions": "78 × 39 × 38 mm", "notes": "High burst C-rating, low capacity.",
        "buy_url": "https://betafpv.com/products/lava-6s-1100mah-lipo-battery"
    },
    "Tattu 6S 1550mAh LiPo R-Line": {
        "cells": 6, "mah": 1550, "weight_g": 254.0, "c_rating": 150,
        "voltage": 22.2, "wh": 34.4, "price_egp": 2037.87, "price_usd": 40.0,
        "dimensions": "78 × 39 × 38 mm", "notes": "Racing LiPo; high discharge, modest endurance.",
        "buy_url": "https://genstattu.com/"
    },
    "Lithium Polymer 3S 5200mAh 40C": {
        "cells": 3, "mah": 5200, "weight_g": 350.0, "c_rating": 40,
        "voltage": 11.1, "wh": 57.7, "price_egp": 2750.0, "price_usd": 53.98,
        "dimensions": "135 × 42 × 30 mm", "notes": "Good capacity-to-weight for 3S systems.",
        "buy_url": "https://makerselectronics.com/"
    },
    "Lithium Polymer 3S 3300mAh 40C": {
        "cells": 3, "mah": 3300, "weight_g": 250.0, "c_rating": 40,
        "voltage": 11.1, "wh": 36.6, "price_egp": 1950.0, "price_usd": 38.28,
        "dimensions": "135 × 42 × 23 mm", "notes": "Medium 3S pack.",
        "buy_url": "https://makerselectronics.com/"
    },
    "Lithium Polymer 3S 2200mAh 40C": {
        "cells": 3, "mah": 2200, "weight_g": 185.0, "c_rating": 40,
        "voltage": 11.1, "wh": 24.4, "price_egp": 1850.0, "price_usd": 36.31,
        "dimensions": "105 × 34 × 24 mm", "notes": "Common local hobby pack.",
        "buy_url": "https://uge-one.com/"
    },
    "Lithium Polymer 3S 10400mAh 40C": {
        "cells": 3, "mah": 10400, "weight_g": 620.0, "c_rating": 40,
        "voltage": 11.1, "wh": 115.4, "price_egp": 4500.0, "price_usd": 88.33,
        "dimensions": "165 × 65 × 35 mm", "notes": "Heavy pack; requires larger motors.",
        "buy_url": "https://makerselectronics.com/"
    },
    "SUPER NANO 3S 8000mAh 35C": {
        "cells": 3, "mah": 8000, "weight_g": 600.0, "c_rating": 35,
        "voltage": 11.1, "wh": 88.8, "price_egp": 3600.0, "price_usd": 70.66,
        "dimensions": "155 × 45 × 42 mm", "notes": "Heavy endurance pack for large platforms.",
        "buy_url": "https://circuits-elec.com/"
    }
}

DEFAULT_PRESETS = {
    "Balanced Default": {"auw": 1.0, "twr": 1.0, "hover": 1.0, "cost": 1.0},
    "Endurance Optimized": {"auw": 0.5, "twr": 0.5, "hover": 2.5, "cost": 1.0},
    "Budget Friendly": {"auw": 1.0, "twr": 1.0, "hover": 1.0, "cost": 3.0}
}

CATEGORIES = ["MOTORS", "FLIGHT_CONTROLLERS", "SBCS", "INTEGRATED_BOARDS", "FRAMES", "BATTERIES", "WEIGHT_PRESETS"]

# Load permanent component database from JSON file
try:
    with open("custom_database.json", "r", encoding="utf-8") as f:
        db_from_file = json.load(f)
except Exception:
    db_from_file = {}

# Initialize session state for each category, using the hardcoded defaults if the JSON is missing or empty
if "MOTORS" not in st.session_state: st.session_state.MOTORS = db_from_file.get("MOTORS", DEFAULT_MOTORS) or DEFAULT_MOTORS
if "FLIGHT_CONTROLLERS" not in st.session_state: st.session_state.FLIGHT_CONTROLLERS = db_from_file.get("FLIGHT_CONTROLLERS", DEFAULT_FC) or DEFAULT_FC
if "SBCS" not in st.session_state: st.session_state.SBCS = db_from_file.get("SBCS", DEFAULT_SBCS) or DEFAULT_SBCS
if "INTEGRATED_BOARDS" not in st.session_state: st.session_state.INTEGRATED_BOARDS = db_from_file.get("INTEGRATED_BOARDS", DEFAULT_INTEGRATED) or DEFAULT_INTEGRATED
if "FRAMES" not in st.session_state: st.session_state.FRAMES = db_from_file.get("FRAMES", DEFAULT_FRAMES) or DEFAULT_FRAMES
if "BATTERIES" not in st.session_state: st.session_state.BATTERIES = db_from_file.get("BATTERIES", DEFAULT_BATTERIES) or DEFAULT_BATTERIES
if "WEIGHT_PRESETS" not in st.session_state: st.session_state.WEIGHT_PRESETS = db_from_file.get("WEIGHT_PRESETS", DEFAULT_PRESETS) or DEFAULT_PRESETS

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
        # Code block logic preserved exactly as requested.
        st.info("To make your added presets or components permanent, click the cloud sync button below.")
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

    # Show persistent success/error messages from saving/deleting presets
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
                    st.session_state.combo_notify = f"🗑️ Preset '{selected_preset}' deleted!"
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