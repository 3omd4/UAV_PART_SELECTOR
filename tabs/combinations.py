import streamlit as st
import pandas as pd
import bisect
import hashlib
import json
from collections import defaultdict


# ======================================================================
# CACHED ENUMERATION
# ----------------------------------------------------------------------
# This is the expensive part (was the ~4.2*10^11-iteration brute force).
# It depends only on the catalogs + the payload/strict-mode toggles, NOT
# on the scoring sliders, so we cache it independently of them. Repeated
# clicks with the same payload/strict-mode settings return instantly.
#
# Leading-underscore params are excluded from Streamlit's hash check
# (dicts of this size are too expensive to hash on every call); we hash
# them ourselves once into `catalog_hash` and pass that in as the real
# cache key.
#
# NOTE: this returns a pandas DataFrame, not a list of dicts. st.cache_data
# deep-copies (pickles) whatever it returns on every cache hit so the caller
# can't mutate the cached object. For a result set in the hundreds of
# thousands of rows, pickling a list of plain Python dicts measurably ate
# into the caching win (~7s for ~1.4M dicts in testing); a DataFrame's
# columnar/numpy storage pickles roughly an order of magnitude faster.
# ======================================================================
@st.cache_data(show_spinner=False)
def _enumerate_valid_combos(
    catalog_hash: str,
    sensor_weight: float,
    sensor_power: float,
    strict_mode: bool,
    _FRAMES: dict,
    _MOTORS: dict,
    _BATTERIES: dict,
    _FLIGHT_CONTROLLERS: dict,
    _SBCS: dict,
    _INTEGRATED_BOARDS: dict,
):
    esc_wiring_weight = 40.0

    # ---- Build avionics pool (same content as before) ----
    avionics_pool = []
    for fc_name, fc in _FLIGHT_CONTROLLERS.items():
        for sbc_name, sbc in _SBCS.items():
            avionics_pool.append({
                "Avionics": f"{fc_name} + {sbc_name}",
                "_FC": fc_name,
                "_SBC": sbc_name,
                "_IntBoard": None,
                "weight": fc.get("weight", 0) + sbc.get("weight", 0),
                "price_egp": fc.get("price_egp", 0) + sbc.get("price_egp", 0),
                "power_w": sbc.get("power_w", 0),
                "ai_tops": sbc.get("ai_tops", 0.0),
            })
    for int_name, int_b in _INTEGRATED_BOARDS.items():
        ai_val = 40.0 if "Jetson" in int_name else (15.0 if "VOXL" in int_name else 0.0)
        avionics_pool.append({
            "Avionics": int_name,
            "_FC": None,
            "_SBC": None,
            "_IntBoard": int_name,
            "weight": int_b.get("weight", 0),
            "price_egp": int_b.get("price_egp", 0),
            "power_w": int_b.get("power_w", 0),
            "ai_tops": ai_val,
        })

    if not avionics_pool:
        return pd.DataFrame()

    # ---- Fix #2: collapse avionics options that are numerically
    # identical (same weight/price/power/ai_tops) into one group.
    # Every filter and computed metric depends only on these four
    # numbers, so equivalent entries only need to be evaluated once;
    # we fan the result back out to every member's display name after.
    groups = defaultdict(list)
    for av in avionics_pool:
        sig = (av["weight"], av["price_egp"], av["power_w"], av["ai_tops"])
        groups[sig].append((av["Avionics"], av["_FC"], av["_SBC"], av["_IntBoard"]))

    sorted_sigs = sorted(groups.keys(), key=lambda s: s[0])   # sort by weight
    weights_sorted = [s[0] for s in sorted_sigs]

    valid_combos = []

    for f_name, frame in _FRAMES.items():
        f_wt = frame.get("weight_g") or frame.get("weight") or 0.0
        n_mot = frame.get("motor_count", 4)
        f_pl = frame.get("payload_limit_g", 500)
        f_wb = frame.get("wheelbase_mm", 300)
        f_ducted = frame.get("ducted", True)
        f_price = frame.get("price_egp", 0)

        for m_name, motor in _MOTORS.items():
            m_wt = motor.get("weight", 0)
            m_thr = motor.get("thrust", 0) * n_mot
            m_eff = motor.get("efficiency_hover_gw", 1.0)
            m_price = motor.get("price_egp", 0) * n_mot
            m_cells = motor.get("cells", [])
            m_max_a = motor.get("max_current_a", 0)

            for b_name, batt in _BATTERIES.items():
                b_cells = batt.get("cells", 3)
                if b_cells not in m_cells and m_cells:
                    continue

                b_wt = batt.get("weight_g") or batt.get("weight") or 0.0
                b_mah = batt.get("mah", 0)
                b_c = batt.get("c_rating", 1)
                b_volt = batt.get("voltage", 11.1)
                b_wh = batt.get("wh", 0)
                b_price = batt.get("price_egp", 0)

                max_disc_amps = (b_mah / 1000.0) * b_c
                prop_wt = (m_wt * n_mot) + esc_wiring_weight

                # ---- Fix #1: algebraic pruning of the avionics dimension ----
                # Payload check:  av_weight + sensor_weight <= f_pl
                #              => av_weight <= f_pl - sensor_weight
                # TWR >= 1.8:     m_thr / auw >= 1.8, auw includes av_weight
                #              => av_weight <= m_thr/1.8 - f_wt - prop_wt - b_wt - sensor_weight
                # Both are simple upper bounds on av_weight, so instead of
                # scanning every avionics option we binary-search the
                # weight-sorted list for the cutoff and only touch the
                # (usually tiny) subset that can possibly pass.
                max_av_weight_payload = f_pl - sensor_weight
                max_av_weight_twr = (m_thr / 1.8) - f_wt - prop_wt - b_wt - sensor_weight
                max_av_weight = min(max_av_weight_payload, max_av_weight_twr)

                if max_av_weight < 0:
                    continue  # no avionics option, however light, can pass here

                idx = bisect.bisect_right(weights_sorted, max_av_weight)
                if idx == 0:
                    continue

                for sig in sorted_sigs[:idx]:
                    av_weight, av_price, av_power, av_ai = sig

                    tot_payload = av_weight + sensor_weight
                    auw = f_wt + prop_wt + b_wt + tot_payload
                    if auw <= 0:
                        continue

                    twr = m_thr / auw
                    if twr < 1.8:
                        continue  # defensive: float-precision guard at the boundary

                    tot_elec_p = av_power + sensor_power + 3.0
                    if m_max_a > 0:
                        peak_amps = (m_max_a * n_mot) + (tot_elec_p / b_volt if b_volt > 0 else 1)
                    else:
                        peak_amps = ((m_thr / 3.0) / b_volt * n_mot) + (tot_elec_p / b_volt)

                    if peak_amps > max_disc_amps:
                        continue

                    hover_throttle = (auw / m_thr) * 100 if m_thr > 0 else 100.0

                    if strict_mode:
                        if (hover_throttle > 65.0 or hover_throttle < 20.0
                                or twr > 4.5 or f_wb > 400 or not f_ducted):
                            continue
                    else:
                        if hover_throttle > 75.0:
                            continue

                    hover_mech_p = auw / (m_eff if m_eff > 0 else 1.0)
                    tot_hover_p = hover_mech_p + tot_elec_p
                    flight_time = ((b_wh * 0.85) / tot_hover_p) * 60.0 if tot_hover_p > 0 else 0.0
                    tot_cost_base = f_price + m_price + 1500.0 + b_price

                    # Fan back out: emit one row per original avionics
                    # label in this equivalence class, exactly as the
                    # unoptimized version would have.
                    for (av_name, fc_name, sbc_name, int_board_name) in groups[sig]:
                        valid_combos.append({
                            "Frame": f_name,
                            "Motor": m_name,
                            "Battery": b_name,
                            "Avionics": av_name,
                            "_FC": fc_name,
                            "_SBC": sbc_name,
                            "_IntBoard": int_board_name,
                            "Cost (EGP)": float(tot_cost_base + av_price),
                            "Hover Time (min)": float(flight_time),
                            "TWR": float(twr),
                            "Hover Throttle (%)": float(hover_throttle),
                            "Peak Draw (A)": float(peak_amps),
                            "AUW (g)": float(auw),
                            "AI TOPS": float(av_ai),
                        })

    return pd.DataFrame(valid_combos)


def _hash_catalogs(*dicts) -> str:
    """Cheap, correct cache key: full-content hash of the catalogs.
    Only runs when the solver button is clicked, so the cost of hashing
    a few MB of JSON is negligible next to what it replaces."""
    payload = json.dumps(dicts, sort_keys=True, default=str).encode("utf-8")
    return hashlib.md5(payload).hexdigest()


def render_combinations_tab():
    FRAMES = st.session_state.get("FRAMES", {})
    MOTORS = st.session_state.get("MOTORS", {})
    BATTERIES = st.session_state.get("BATTERIES", {})
    FLIGHT_CONTROLLERS = st.session_state.get("FLIGHT_CONTROLLERS", {})
    SBCS = st.session_state.get("SBCS", {})
    INTEGRATED_BOARDS = st.session_state.get("INTEGRATED_BOARDS", {})

    st.subheader("Explore All Valid Component Combinations")
    st.caption(
        "Combinatorial matrix solver with algebraic pruning and result caching. "
        "Evaluates the full frame x motor x battery x avionics search space efficiently."
    )

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
            help="Hides builds with Yellow operational warnings."
        )

    with col_weights:
        st.markdown("#### 2. Mission Profile Scoring")
        w_time = st.slider("Endurance Priority (Hover Time)", 0.0, 1.0, 0.5, 0.1)
        w_cost = st.slider("Budget Priority (Lower Cost)", 0.0, 1.0, 0.3, 0.1)
        w_ai = st.slider("Compute Priority (AI TOPS)", 0.0, 1.0, 0.8, 0.1)
        w_twr = st.slider("Agility Priority (Thrust-to-Weight)", 0.0, 1.0, 0.2, 0.1)

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

    st.divider()

    if st.button("🚀 Execute Combinatorial Solver", type="primary", use_container_width=True):
        if not all([FRAMES, MOTORS, BATTERIES]):
            st.error("Incomplete database. Ensure Frames, Motors, and Batteries exist.")
            return

        with st.spinner("Computing valid configurations..."):
            catalog_hash = _hash_catalogs(
                FRAMES, MOTORS, BATTERIES, FLIGHT_CONTROLLERS, SBCS, INTEGRATED_BOARDS
            )

            df_combos = _enumerate_valid_combos(
                catalog_hash,
                sensor_weight,
                sensor_power,
                strict_mode,
                FRAMES,
                MOTORS,
                BATTERIES,
                FLIGHT_CONTROLLERS,
                SBCS,
                INTEGRATED_BOARDS,
            )

            if df_combos.empty:
                st.warning("No configurations satisfied safety thresholds. Try disabling strict mode.")
                if "solver_results" in st.session_state:
                    del st.session_state["solver_results"]
                return

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

            tot_w = w_time + w_cost + w_ai + w_twr
            if tot_w == 0:
                tot_w = 1.0

            df_combos["Fitness Score"] = (
                (norm_time * w_time) + (norm_cost * w_cost) + (norm_ai * w_ai) + (norm_twr * w_twr)
            ) / tot_w
            df_combos["Fitness Score"] = (df_combos["Fitness Score"] * 100).round(1)
            df_combos = df_combos.sort_values(by="Fitness Score", ascending=False).reset_index(drop=True)
            df_combos.index = df_combos.index + 1
            df_combos.index.name = "Rank"
            df_combos = df_combos.reset_index()

            st.session_state["solver_results"] = df_combos
            if "builder_preset" in st.session_state:
                del st.session_state["builder_preset"]

    if "solver_results" in st.session_state:
        df_combos = st.session_state["solver_results"]
        st.markdown(f"### 🏆 Top Configurations ({len(df_combos)} Valid Builds Found)")
        st.caption("Select a row below to load it into the Drone Builder.")

        selection_event = st.dataframe(
            df_combos,
            key="combo_ranking_table",
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            column_config={
                "_FC": None, "_SBC": None, "_IntBoard": None,
                "Rank": st.column_config.NumberColumn("Rank", format="#%d"),
                "Fitness Score": st.column_config.ProgressColumn("Fitness Score", format="%d%%", min_value=0, max_value=100),
                "Cost (EGP)": st.column_config.NumberColumn("Est. Cost", format="EGP %.0f"),
                "Hover Time (min)": st.column_config.NumberColumn("Hover Time", format="%.1f min"),
                "AUW (g)": st.column_config.NumberColumn("AUW", format="%.0f g"),
                "TWR": st.column_config.NumberColumn("TWR", format="%.2f"),
                "Hover Throttle (%)": st.column_config.NumberColumn("Throttle", format="%.1f%%"),
                "Peak Draw (A)": st.column_config.NumberColumn("Peak Draw", format="%.1f A"),
                "AI TOPS": st.column_config.NumberColumn("Compute", format="%.1f TOPS"),
            }
        )

        selected_rows = selection_event.selection.rows
        if selected_rows:
            row = df_combos.iloc[selected_rows[0]]
            st.markdown(f"**🎯 Targeted Configuration:** Rank `#{row['Rank']}` ({row['Frame']} + {row['Motor']})")

            if st.button(f"📥 Lock in Rank #{row['Rank']} & Load into Drone Builder", type="primary", width="stretch"):
                st.session_state["builder_preset"] = {
                    "frame": row["Frame"], "motor": row["Motor"], "battery": row["Battery"],
                    "fc": row["_FC"], "sbc": row["_SBC"], "int_board": row["_IntBoard"]
                }
                st.success("✅ **Architecture locked in!** Switch over to the 'Drone Builder' tab.")