import streamlit as st
import pandas as pd

def render_catalogs_tab():
    st.subheader("Component Technical Specifications & Cost Tables")
    
    MOTORS = st.session_state.MOTORS
    FLIGHT_CONTROLLERS = st.session_state.FLIGHT_CONTROLLERS
    SBCS = st.session_state.SBCS
    INTEGRATED_BOARDS = st.session_state.INTEGRATED_BOARDS
    FRAMES = st.session_state.FRAMES
    BATTERIES = st.session_state.BATTERIES

    st.markdown("#### Single Board Computers (SBC)")
    st.dataframe(pd.DataFrame.from_dict(SBCS, orient="index"), 
    column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", 
    display_text="Link ↗")}, use_container_width=True)

    st.markdown("#### Integrated Autonomy Boards")
    st.dataframe(pd.DataFrame.from_dict(INTEGRATED_BOARDS, orient="index"), 
    column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", 
    display_text="Link ↗")}, use_container_width=True)

    st.markdown("#### Flight Controllers (FC)")
    st.dataframe(pd.DataFrame.from_dict(FLIGHT_CONTROLLERS, orient="index"), 
    column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", 
    display_text="Link ↗")}, use_container_width=True)

    st.markdown("#### Brushless DC Motors")
    st.dataframe(pd.DataFrame.from_dict(MOTORS, orient="index"), 
    column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", 
    display_text="Link ↗")}, use_container_width=True)

    st.markdown("#### Frame Kits")
    st.dataframe(pd.DataFrame.from_dict(FRAMES, orient="index"), 
    column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", 
    display_text="Link ↗")}, use_container_width=True)

    st.markdown("#### Battery Packs")
    st.dataframe(pd.DataFrame.from_dict(BATTERIES, orient="index"), 
    column_config={"buy_url": st.column_config.LinkColumn("Where to Buy", 
    display_text="Link ↗")}, use_container_width=True)
