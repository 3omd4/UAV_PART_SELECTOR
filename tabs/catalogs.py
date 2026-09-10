import streamlit as st
import pandas as pd

def process_catalog_df(db_dict, search_query):
    """Converts the session state dictionary to a DataFrame and applies global search."""
    if not db_dict:
        return pd.DataFrame()
        
    df = pd.DataFrame.from_dict(db_dict, orient="index").reset_index()
    df.rename(columns={"index": "Model"}, inplace=True)
    
    if search_query:
        mask = df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        df = df[mask]
        
    return df

def render_catalogs_tab():
    st.subheader("Component Technical Specifications & Cost Tables")
    
    MOTORS = st.session_state.get("MOTORS", {})
    FLIGHT_CONTROLLERS = st.session_state.get("FLIGHT_CONTROLLERS", {})
    SBCS = st.session_state.get("SBCS", {})
    INTEGRATED_BOARDS = st.session_state.get("INTEGRATED_BOARDS", {})
    FRAMES = st.session_state.get("FRAMES", {})
    BATTERIES = st.session_state.get("BATTERIES", {})
    
    total_parts = sum(len(x) for x in [MOTORS, FLIGHT_CONTROLLERS, SBCS, INTEGRATED_BOARDS, FRAMES, BATTERIES])
    
    col_metrics, col_search = st.columns([1, 2])
    with col_metrics:
        st.caption(f"**Database Status:** {total_parts} total components loaded.")
    with col_search:
        search_query = st.text_input("🔍 Global Search (e.g., 'Jetson', '1700KV', 'Holybro'):", "")

    cat_tabs = st.tabs([
        "🚀 Motors", "🧠 Companion Computers", "🕹️ Flight Controllers", 
        "⚡ Batteries", "🛸 Airframes", "🛠️ Integrated Boards"
    ])
    
    # Restored all truncated string configurations (Link ↗)
    with cat_tabs[0]:
        df_motors = process_catalog_df(MOTORS, search_query)
        if not df_motors.empty:
            st.dataframe(
                df_motors,
                column_config={
                    "Model": st.column_config.TextColumn("Motor Model", width="medium"),
                    "stator": st.column_config.TextColumn("Stator Size"),
                    "kv": st.column_config.NumberColumn("KV Rating", format="%d KV"),
                    "weight": st.column_config.NumberColumn("Weight", format="%.1f g"),
                    "thrust": st.column_config.NumberColumn("Max Thrust", format="%.1f g"),
                    "prop": st.column_config.TextColumn("Prop Size"),
                    "efficiency_hover_gw": st.column_config.NumberColumn("Hover Eff.", format="%.2f g/W"),
                    "cells": st.column_config.ListColumn("Cells (S)"),
                    "price_egp": st.column_config.NumberColumn("Cost (EGP)", format="EGP %.0f"),
                    "price_usd": st.column_config.NumberColumn("Cost (USD)", format="$%.2f"),
                    "buy_url": st.column_config.LinkColumn("Vendor", display_text="Link ↗"),
                    "notes": st.column_config.TextColumn("Engineering Notes", width="large"),
                    "source": None 
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No motors found matching your search.")

    with cat_tabs[1]:
        df_sbcs = process_catalog_df(SBCS, search_query)
        if not df_sbcs.empty:
            st.dataframe(
                df_sbcs,
                column_config={
                    "Model": st.column_config.TextColumn("SBC Model", width="medium"),
                    "cpu": st.column_config.TextColumn("Processor / RAM"),
                    "ai_tops": st.column_config.ProgressColumn("AI Compute (TOPS)", format="%.1f", min_value=0, max_value=50),
                    "weight": st.column_config.NumberColumn("Weight", format="%.1f g"),
                    "power_w": st.column_config.NumberColumn("Avg Power", format="%.1f W"),
                    "dim": st.column_config.TextColumn("Dimensions"),
                    "best_for": st.column_config.TextColumn("Primary Workload", width="large"),
                    "price_egp": st.column_config.NumberColumn("Cost (EGP)", format="EGP %.0f"),
                    "price_usd": st.column_config.NumberColumn("Cost (USD)", format="$%.2f"),
                    "buy_url": st.column_config.LinkColumn("Vendor", display_text="Link ↗")
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No SBCs found matching your search.")

    with cat_tabs[2]:
        df_fc = process_catalog_df(FLIGHT_CONTROLLERS, search_query)
        if not df_fc.empty:
            st.dataframe(
                df_fc,
                column_config={
                    "Model": st.column_config.TextColumn("FC Model", width="medium"),
                    "mcu": st.column_config.TextColumn("MCU Target"),
                    "weight": st.column_config.NumberColumn("Weight", format="%.1f g"),
                    "dim": st.column_config.TextColumn("Dimensions"),
                    "firmware": st.column_config.TextColumn("Firmware Support"),
                    "notes": st.column_config.TextColumn("Engineering Notes", width="large"),
                    "price_egp": st.column_config.NumberColumn("Cost (EGP)", format="EGP %.0f"),
                    "price_usd": st.column_config.NumberColumn("Cost (USD)", format="$%.2f"),
                    "buy_url": st.column_config.LinkColumn("Vendor", display_text="Link ↗")
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No Flight Controllers found matching your search.")

    with cat_tabs[3]:
        df_batt = process_catalog_df(BATTERIES, search_query)
        if not df_batt.empty:
            st.dataframe(
                df_batt,
                column_config={
                    "Model": st.column_config.TextColumn("Battery Model", width="medium"),
                    "cells": st.column_config.NumberColumn("Cells", format="%d S"),
                    "mah": st.column_config.NumberColumn("Capacity", format="%d mAh"),
                    "c_rating": st.column_config.NumberColumn("Discharge Rate", format="%d C"),
                    "wh": st.column_config.NumberColumn("Energy", format="%.1f Wh"),
                    "voltage": st.column_config.NumberColumn("Nominal Voltage", format="%.1f V"),
                    "weight_g": st.column_config.NumberColumn("Weight", format="%.1f g"),
                    "dimensions": st.column_config.TextColumn("Dimensions"),
                    "notes": st.column_config.TextColumn("Engineering Notes", width="large"),
                    "price_egp": st.column_config.NumberColumn("Cost (EGP)", format="EGP %.0f"),
                    "price_usd": st.column_config.NumberColumn("Cost (USD)", format="$%.2f"),
                    "buy_url": st.column_config.LinkColumn("Vendor", display_text="Link ↗")
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No Batteries found matching your search.")

    with cat_tabs[4]:
        df_frames = process_catalog_df(FRAMES, search_query)
        if not df_frames.empty:
            st.dataframe(
                df_frames,
                column_config={
                    "Model": st.column_config.TextColumn("Airframe Model", width="medium"),
                    "wheelbase_mm": st.column_config.NumberColumn("Wheelbase", format="%d mm"),
                    "weight_g": st.column_config.NumberColumn("Bare Weight", format="%.1f g"),
                    "payload_limit_g": st.column_config.NumberColumn("Max Structural Payload", format="%.1f g"),
                    "motor_count": st.column_config.NumberColumn("Motors", format="%d"),
                    "max_prop": st.column_config.TextColumn("Max Prop Size"),
                    "ducted": st.column_config.CheckboxColumn("Ducted Guards?"),
                    "notes": st.column_config.TextColumn("Engineering Notes", width="large"),
                    "price_egp": st.column_config.NumberColumn("Cost (EGP)", format="EGP %.0f"),
                    "price_usd": st.column_config.NumberColumn("Cost (USD)", format="$%.2f"),
                    "buy_url": st.column_config.LinkColumn("Vendor", display_text="Link ↗")
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No Airframes found matching your search.")

    with cat_tabs[5]:
        df_integrated = process_catalog_df(INTEGRATED_BOARDS, search_query)
        if not df_integrated.empty:
            st.dataframe(
                df_integrated,
                column_config={
                    "Model": st.column_config.TextColumn("Board Model", width="medium"),
                    "arch": st.column_config.TextColumn("Architecture"),
                    "compute": st.column_config.TextColumn("Compute Engine"),
                    "weight": st.column_config.NumberColumn("Weight", format="%.1f g"),
                    "power_w": st.column_config.NumberColumn("Avg Power", format="%.1f W"),
                    "dim": st.column_config.TextColumn("Dimensions"),
                    "best_for": st.column_config.TextColumn("Primary Workload", width="large"),
                    "price_egp": st.column_config.NumberColumn("Cost (EGP)", format="EGP %.0f"),
                    "price_usd": st.column_config.NumberColumn("Cost (USD)", format="$%.2f"),
                    "buy_url": st.column_config.LinkColumn("Vendor", display_text="Link ↗")
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No Integrated Boards found matching your search.")