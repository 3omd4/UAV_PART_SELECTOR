import streamlit as st
import pandas as pd
import bisect
import hashlib
import json
from collections import defaultdict


# ======================================================================
# SAFETY CONSTANTS
# ----------------------------------------------------------------------
# Two independent caps, because the two failure modes are different:
#
#   MAX_TRIPLES  bounds RUNTIME. Every (frame, motor, battery) triple
#                costs at least one bisect call even if it produces zero
#                rows, so a huge F*M*B alone can hang the single Streamlit
#                session thread with nothing to show for it. We refuse to
#                even start the solver past this, and tell the user why.
#
#   MAX_ROWS     bounds MEMORY / PAYLOAD SIZE. A filter set that legitimately
#                produces a huge number of *valid* combos (e.g. barely any
#                constraints) can still blow up RAM building the list of
#                dicts, the DataFrame, the cache pickle, and then the
#                browser trying to render an AgGrid with millions of rows.
#                We stop appending once we hit this and tell the user the
#                result set was truncated.
# ======================================================================
MAX_TRIPLES = 20_000_000     # frame x motor x battery combinations scanned
MAX_ROWS = 200_000           # valid result rows kept

# Rough gate for the "you're about to nuke your browser tab" banner shown
# BEFORE the button is even pressed, computed from catalog sizes alone
# (no enumeration needed, so this is free to recompute on every rerun).
TRIPLE_WARN_THRESHOLD = 2_000_000


class _EnumerationTruncated(Exception):
    """Raised internally to unwind all three nested loops in one shot
    once a safety cap is hit. Caught once, at the top of the function."""
    def __init__(self, reason: str):
        self.reason = reason


# ======================================================================
# CACHED ENUMERATION
# ----------------------------------------------------------------------
# This is the expensive part (was the ~4.2*10^11-iteration brute force).
# It depends on the catalogs (now pre-filtered per Tier 1/Tier 2 below),
# the payload/strict-mode toggles, and the total budget cap -- NOT on the
# scoring sliders -- so we cache it independently of them. Repeated clicks
# with the same filters/payload/strict-mode/budget return instantly.
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
    budget_cap: float,
    _FRAMES: dict,
    _MOTORS: dict,
    _BATTERIES: dict,
    _FLIGHT_CONTROLLERS: dict,
    _SBCS: dict,
    _INTEGRATED_BOARDS: dict,
):
    esc_wiring_weight = 40.0
    have_budget = budget_cap is not None and budget_cap > 0

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
        ai_val = int_b.get("ai_compute_tops")
        if ai_val is None:
            # Fallback heuristic preserved from the original implementation
            # for boards whose ai_compute_tops field isn't populated yet.
            ai_val = 40.0 if "Jetson" in int_name else (15.0 if "VOXL" in int_name else 0.0)
        avionics_pool.append({
            "Avionics": int_name,
            "_FC": None,
            "_SBC": None,
            "_IntBoard": int_name,
            "weight": int_b.get("weight", 0),
            "price_egp": int_b.get("price_egp", 0),
            "power_w": int_b.get("power_w", 0),
            "ai_tops": float(ai_val),
        })

    if not avionics_pool:
        return pd.DataFrame(), False

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
    truncated = False
    triples_scanned = 0

    try:
        for f_name, frame in _FRAMES.items():
            f_wt = frame.get("weight_g") or frame.get("weight") or 0.0
            n_mot = frame.get("motor_count", 4)
            f_pl = frame.get("payload_limit_g", 500)
            f_wb = frame.get("wheelbase_mm", 300)

            # ---- Bug fix (Tier-1 audit finding) ----
            # frame.get("ducted", True) only applies the default when the
            # KEY is missing. In the real catalog the key is present with
            # value None for ~99% of frames, so f_ducted came out None and
            # `not f_ducted` evaluated True for almost every frame -- Strict
            # Mode was silently rejecting nearly the whole frame catalog on
            # a field that is actually *unset*, not actually non-ducted.
            # An unset/unknown value should not be treated as "fails the
            # ducted requirement"; only an explicit False should.
            f_ducted_raw = frame.get("ducted")
            f_ducted = True if f_ducted_raw is None else f_ducted_raw

            f_price = frame.get("price_egp", 0)

            for m_name, motor in _MOTORS.items():
                m_wt = motor.get("weight", 0)
                m_thr = motor.get("thrust", 0) * n_mot
                m_eff = motor.get("efficiency_hover_gw", 1.0)
                m_price = motor.get("price_egp", 0) * n_mot
                m_cells = motor.get("cells", [])
                m_max_a = motor.get("max_current_a", 0)

                for b_name, batt in _BATTERIES.items():
                    triples_scanned += 1
                    if triples_scanned > MAX_TRIPLES:
                        raise _EnumerationTruncated(
                            "search space too large (frame x motor x battery "
                            "triples exceeded the safety cap) -- narrow the "
                            "filters above and re-run"
                        )

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

                    candidate_sigs = sorted_sigs[:idx]

                    # ---- Tier-2 budget pruning ----
                    # Total cost is already fully known except for avionics
                    # price, and avionics price is part of the signature
                    # we're grouping on -- so once the weight-based bisect
                    # has narrowed candidates down to a small slice, a
                    # second cheap linear scan filters that slice by
                    # av_price <= budget - (frame+motor+battery+1500).
                    # This is a second pass over an already-small list, not
                    # a second full search dimension.
                    if have_budget:
                        remaining_budget = budget_cap - (f_price + m_price + 1500.0 + b_price)
                        if remaining_budget < 0:
                            continue
                        candidate_sigs = [s for s in candidate_sigs if s[1] <= remaining_budget]
                        if not candidate_sigs:
                            continue

                    for sig in candidate_sigs:
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
                            if len(valid_combos) >= MAX_ROWS:
                                raise _EnumerationTruncated(
                                    f"result set exceeded {MAX_ROWS:,} rows -- showing a "
                                    "partial (truncated) result. Narrow the filters above "
                                    "for a complete list."
                                )

    except _EnumerationTruncated as exc:
        truncated = True
        st.session_state["_combo_truncation_reason"] = exc.reason

    return pd.DataFrame(valid_combos), truncated


def _hash_catalogs(*dicts_and_scalars) -> str:
    """Cheap, correct cache key: full-content hash of the catalogs plus
    any scalar knobs (budget cap etc.) that affect enumeration. Only runs
    when the solver button is clicked, so the cost of hashing a few MB of
    JSON is negligible next to what it replaces."""
    payload = json.dumps(dicts_and_scalars, sort_keys=True, default=str).encode("utf-8")
    return hashlib.md5(payload).hexdigest()


# ======================================================================
# TIER 1 / TIER 2 HELPERS -- cheap, pre-loop, operate on plain dicts
# ======================================================================
def _field_values(catalogs, field):
    """Union of values for `field` across one or more catalog dicts.
    Handles list-valued fields (e.g. motor cell counts) and flags whether
    any record leaves the field unset, so callers can offer an explicit
    'Unknown' bucket instead of silently dropping those records."""
    values = set()
    has_unknown = False
    for catalog in catalogs:
        for item in catalog.values():
            v = item.get(field)
            if v is None or v == "":
                has_unknown = True
                continue
            if isinstance(v, list):
                if not v:
                    has_unknown = True
                for vv in v:
                    values.add(vv)
            else:
                values.add(v)
    return values, has_unknown


def _filter_by_values(catalog, field, selected):
    """Keep only entries whose `field` intersects `selected`. 'Unknown' in
    `selected` keeps entries missing the field. List-valued fields (e.g.
    motor cell counts) keep entries with ANY overlap, and an EMPTY list is
    treated as 'compatible with everything' (mirrors the existing
    b_cells/m_cells compatibility rule) so it only gets dropped if the
    caller explicitly excludes 'Unknown'."""
    if selected is None:
        return catalog
    selected = set(selected)
    keep_unknown = "Unknown" in selected
    out = {}
    for name, item in catalog.items():
        v = item.get(field)
        if isinstance(v, list) and not v:
            # An empty list means "no restriction stated" (e.g. a motor
            # with no cells[] entry supports any battery cell count, per
            # the `if b_cells not in m_cells and m_cells` compatibility
            # rule already used in the solver) -- always compatible,
            # regardless of which values the user has selected.
            out[name] = item
            continue
        if v is None or v == "":
            if keep_unknown:
                out[name] = item
            continue
        if isinstance(v, list):
            if selected.intersection(v):
                out[name] = item
        else:
            if v in selected:
                out[name] = item
    return out


def _filter_by_bool(catalog, field, require_true):
    if not require_true:
        return catalog
    return {k: v for k, v in catalog.items() if v.get(field) is True}


def _filter_by_min(catalog, field, min_val, include_unknown=True, name_hint=None):
    if min_val is None:
        return catalog
    out = {}
    for k, v in catalog.items():
        val = v.get(field)
        if name_hint == "int_board_ai" and val is None:
            val = 40.0 if "Jetson" in k else (15.0 if "VOXL" in k else 0.0)
        if val is None:
            if include_unknown:
                out[k] = v
            continue
        if val >= min_val:
            out[k] = v
    return out


def _filter_by_max_price(catalog, max_price):
    if max_price is None:
        return catalog
    return {k: v for k, v in catalog.items() if v.get("price_egp", 0) <= max_price}


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

    # ==================================================================
    # TIER 1 + TIER 2 -- narrow the catalogs BEFORE the loop ever runs.
    # These are cheap (they just shrink dicts) but they're the highest
    # leverage filters: cutting frames from 612 to 100 cuts total search
    # volume ~6x on its own, before any pruning inside the solver runs.
    # ==================================================================
    st.markdown("#### 3. Narrow The Search")
    st.caption(
        "These filters shrink the catalogs *before* the solver runs. "
        "Use them if the unfiltered search is too large to compute or "
        "too large for the browser to render."
    )

    with st.expander("🔎 Filters (size class, chemistry, compliance, budget, ...)", expanded=True):
        t1a, t1b, t1c = st.columns(3)

        with t1a:
            size_vals, size_unknown = _field_values([FRAMES, MOTORS], "size_class")
            size_options = sorted(size_vals, key=str) + (["Unknown"] if size_unknown else [])
            sel_size = st.multiselect("Prop / Frame Size Class", size_options, default=size_options)

            chem_vals, chem_unknown = _field_values([BATTERIES], "chemistry")
            chem_options = sorted(chem_vals, key=str) + (["Unknown"] if chem_unknown else [])
            sel_chem = st.multiselect("Battery Chemistry", chem_options, default=chem_options)

            conn_vals, conn_unknown = _field_values([BATTERIES], "battery_connector")
            conn_options = sorted(conn_vals, key=str) + (["Unknown"] if conn_unknown else [])
            sel_conn = st.multiselect("Battery Connector", conn_options, default=conn_options)

        with t1b:
            cell_vals, cell_unknown = _field_values([BATTERIES, MOTORS], "cells")
            cell_options = sorted(cell_vals) + (["Unknown"] if cell_unknown else [])
            sel_cells = st.multiselect(
                "Cell Count (S)", cell_options, default=cell_options,
                format_func=lambda v: f"{v}S" if v != "Unknown" else v,
            )

            subtype_vals, subtype_unknown = _field_values([FRAMES], "vehicle_subtype")
            subtype_options = sorted(subtype_vals, key=str) + (["Unknown"] if subtype_unknown else [])
            sel_subtype = st.multiselect("Vehicle Subtype", subtype_options, default=subtype_options)

            require_ndaa = st.checkbox("NDAA compliant only", value=False)
            require_blue_uas = st.checkbox("Blue UAS only", value=False)

        with t1c:
            mfr_vals, mfr_unknown = _field_values(
                [FRAMES, MOTORS, BATTERIES, FLIGHT_CONTROLLERS, SBCS, INTEGRATED_BOARDS], "manufacturer"
            )
            mfr_options = sorted(mfr_vals, key=str) + (["Unknown"] if mfr_unknown else [])
            sel_mfr = st.multiselect("Manufacturer", mfr_options, default=mfr_options)

            country_vals, country_unknown = _field_values(
                [FRAMES, MOTORS, BATTERIES, FLIGHT_CONTROLLERS, SBCS, INTEGRATED_BOARDS], "manufacturer_country"
            )
            country_options = sorted(country_vals, key=str) + (["Unknown"] if country_unknown else [])
            sel_country = st.multiselect("Manufacturer Country", country_options, default=country_options)

            min_ai = st.slider("Minimum AI Compute (TOPS)", 0.0, 40.0, 0.0, 1.0,
                                help="Applies to SBCs and integrated boards (e.g. set to 6 for a SLAM-capable-only search).")
            min_ram_active = st.checkbox("Require minimum SBC RAM", value=False)
            min_ram = st.slider("Minimum SBC RAM (GB)", 0, 32, 4, 1, disabled=not min_ram_active)

        st.markdown("##### Budget")
        t2a, t2b = st.columns(2)
        with t2a:
            budget_active = st.checkbox("Cap total build cost", value=False)
            budget_cap = st.number_input(
                "Max total cost (EGP)", min_value=0.0, value=100000.0, step=1000.0,
                disabled=not budget_active,
            ) if budget_active else None

        with t2b:
            per_cat_active = st.checkbox("Cap per-category price", value=False)
            max_frame_price = st.number_input("Max frame price (EGP)", min_value=0.0, value=10000.0, step=500.0, disabled=not per_cat_active)
            max_motor_price = st.number_input("Max motor price (EGP, each)", min_value=0.0, value=3000.0, step=100.0, disabled=not per_cat_active)
            max_batt_price = st.number_input("Max battery price (EGP)", min_value=0.0, value=8000.0, step=500.0, disabled=not per_cat_active)

    # ---- Apply Tier 1 + Tier 2 pre-filters to shrink the catalogs ----
    f_FRAMES = _filter_by_values(FRAMES, "size_class", sel_size)
    f_FRAMES = _filter_by_values(f_FRAMES, "vehicle_subtype", sel_subtype)
    f_FRAMES = _filter_by_bool(f_FRAMES, "ndaa_compliant", require_ndaa)
    f_FRAMES = _filter_by_bool(f_FRAMES, "blue_uas", require_blue_uas)
    f_FRAMES = _filter_by_values(f_FRAMES, "manufacturer", sel_mfr)
    f_FRAMES = _filter_by_values(f_FRAMES, "manufacturer_country", sel_country)
    if per_cat_active:
        f_FRAMES = _filter_by_max_price(f_FRAMES, max_frame_price)

    f_MOTORS = _filter_by_values(MOTORS, "size_class", sel_size)
    f_MOTORS = _filter_by_values(f_MOTORS, "cells", sel_cells)
    f_MOTORS = _filter_by_values(f_MOTORS, "manufacturer", sel_mfr)
    f_MOTORS = _filter_by_values(f_MOTORS, "manufacturer_country", sel_country)
    if per_cat_active:
        f_MOTORS = _filter_by_max_price(f_MOTORS, max_motor_price)

    f_BATTERIES = _filter_by_values(BATTERIES, "chemistry", sel_chem)
    f_BATTERIES = _filter_by_values(f_BATTERIES, "battery_connector", sel_conn)
    f_BATTERIES = _filter_by_values(f_BATTERIES, "cells", sel_cells)
    f_BATTERIES = _filter_by_values(f_BATTERIES, "manufacturer", sel_mfr)
    f_BATTERIES = _filter_by_values(f_BATTERIES, "manufacturer_country", sel_country)
    if per_cat_active:
        f_BATTERIES = _filter_by_max_price(f_BATTERIES, max_batt_price)

    f_FLIGHT_CONTROLLERS = _filter_by_bool(FLIGHT_CONTROLLERS, "ndaa_compliant", require_ndaa)
    f_FLIGHT_CONTROLLERS = _filter_by_bool(f_FLIGHT_CONTROLLERS, "blue_uas", require_blue_uas)
    f_FLIGHT_CONTROLLERS = _filter_by_values(f_FLIGHT_CONTROLLERS, "manufacturer", sel_mfr)
    f_FLIGHT_CONTROLLERS = _filter_by_values(f_FLIGHT_CONTROLLERS, "manufacturer_country", sel_country)

    f_SBCS = _filter_by_min(SBCS, "ai_tops", min_ai if min_ai > 0 else None)
    f_SBCS = _filter_by_min(f_SBCS, "ram_gb", min_ram if min_ram_active else None, include_unknown=True)
    f_SBCS = _filter_by_values(f_SBCS, "manufacturer", sel_mfr)
    f_SBCS = _filter_by_values(f_SBCS, "manufacturer_country", sel_country)

    f_INTEGRATED_BOARDS = _filter_by_min(
        INTEGRATED_BOARDS, "ai_compute_tops", min_ai if min_ai > 0 else None, name_hint="int_board_ai"
    )
    f_INTEGRATED_BOARDS = _filter_by_values(f_INTEGRATED_BOARDS, "manufacturer", sel_mfr)
    f_INTEGRATED_BOARDS = _filter_by_values(f_INTEGRATED_BOARDS, "manufacturer_country", sel_country)

    # ==================================================================
    # Pre-run size estimate -- free to compute (just dict lengths), shown
    # BEFORE the button so the user sees the effect of each filter live.
    # ==================================================================
    n_f, n_m, n_b = len(f_FRAMES), len(f_MOTORS), len(f_BATTERIES)
    n_avionics = (len(f_FLIGHT_CONTROLLERS) * len(f_SBCS)) + len(f_INTEGRATED_BOARDS)
    triples = n_f * n_m * n_b

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Frames", n_f)
    m2.metric("Motors", n_m)
    m3.metric("Batteries", n_b)
    m4.metric("Avionics options", n_avionics)
    st.caption(
        f"Frame x Motor x Battery triples to scan: **{triples:,}** "
        f"(worst-case raw space incl. avionics: ~{triples * max(n_avionics, 1):,})"
    )

    blocked = triples > MAX_TRIPLES
    if blocked:
        st.error(
            f"This filter combination would scan {triples:,} frame/motor/battery triples, "
            f"above the safety cap of {MAX_TRIPLES:,}. Narrow the filters above before running."
        )
    elif triples > TRIPLE_WARN_THRESHOLD:
        st.warning(
            f"{triples:,} triples is large -- the solver may take a while and the results "
            "table could be heavy to render. Consider narrowing further, especially size "
            "class, chemistry, or the budget cap."
        )

    st.divider()

    if st.button("🚀 Execute Combinatorial Solver", type="primary", width="stretch", disabled=blocked):
        if not all([f_FRAMES, f_MOTORS, f_BATTERIES]):
            st.error("No frames/motors/batteries survive the current filters. Loosen them and try again.")
            return

        with st.spinner("Computing valid configurations..."):
            catalog_hash = _hash_catalogs(
                f_FRAMES, f_MOTORS, f_BATTERIES, f_FLIGHT_CONTROLLERS, f_SBCS, f_INTEGRATED_BOARDS,
                budget_cap, strict_mode, sensor_weight, sensor_power,
            )

            df_combos, truncated = _enumerate_valid_combos(
                catalog_hash,
                sensor_weight,
                sensor_power,
                strict_mode,
                budget_cap,
                f_FRAMES,
                f_MOTORS,
                f_BATTERIES,
                f_FLIGHT_CONTROLLERS,
                f_SBCS,
                f_INTEGRATED_BOARDS,
            )

            if df_combos.empty:
                st.warning("No configurations satisfied safety thresholds. Try disabling strict mode or loosening filters.")
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
            st.session_state["solver_truncated"] = truncated
            if "builder_preset" in st.session_state:
                del st.session_state["builder_preset"]

    if "solver_results" in st.session_state:
        df_combos = st.session_state["solver_results"]

        if st.session_state.get("solver_truncated"):
            reason = st.session_state.get("_combo_truncation_reason", "the result set was truncated")
            st.warning(f"⚠️ Results are incomplete: {reason}")

        # ==============================================================
        # TIER 3 -- post-filters on the already-computed result table.
        # Zero solver cost: these are plain DataFrame range filters
        # applied to a table that's already in memory, so they can be
        # dragged freely without re-running anything.
        # ==============================================================
        with st.expander("🎚️ Refine Results (no re-computation)", expanded=False):
            r1, r2, r3 = st.columns(3)
            with r1:
                ht_min, ht_max = float(df_combos["Hover Time (min)"].min()), float(df_combos["Hover Time (min)"].max())
                sel_ht = st.slider("Hover Time (min)", ht_min, ht_max, (ht_min, ht_max))
                cost_min, cost_max = float(df_combos["Cost (EGP)"].min()), float(df_combos["Cost (EGP)"].max())
                sel_cost = st.slider("Cost (EGP)", cost_min, cost_max, (cost_min, cost_max))
            with r2:
                twr_min, twr_max = float(df_combos["TWR"].min()), float(df_combos["TWR"].max())
                sel_twr = st.slider("TWR", twr_min, twr_max, (twr_min, twr_max))
                ai_min, ai_max = float(df_combos["AI TOPS"].min()), float(df_combos["AI TOPS"].max())
                sel_ai = st.slider("AI TOPS", ai_min, ai_max, (ai_min, ai_max))
            with r3:
                auw_min, auw_max = float(df_combos["AUW (g)"].min()), float(df_combos["AUW (g)"].max())
                sel_auw = st.slider("AUW (g)", auw_min, auw_max, (auw_min, auw_max))

        df_display = df_combos[
            df_combos["Hover Time (min)"].between(*sel_ht)
            & df_combos["Cost (EGP)"].between(*sel_cost)
            & df_combos["TWR"].between(*sel_twr)
            & df_combos["AI TOPS"].between(*sel_ai)
            & df_combos["AUW (g)"].between(*sel_auw)
        ]

        st.markdown(f"### 🏆 Top Configurations ({len(df_display)} of {len(df_combos)} Valid Builds Shown)")
        st.caption("Select a row below to load it into the Drone Builder.")

        selection_event = st.dataframe(
            df_display,
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
            row = df_display.iloc[selected_rows[0]]
            st.markdown(f"**🎯 Targeted Configuration:** Rank `#{row['Rank']}` ({row['Frame']} + {row['Motor']})")

            if st.button(f"📥 Lock in Rank #{row['Rank']} & Load into Drone Builder", type="primary", width="stretch"):
                st.session_state["builder_preset"] = {
                    "frame": row["Frame"], "motor": row["Motor"], "battery": row["Battery"],
                    "fc": row["_FC"], "sbc": row["_SBC"], "int_board": row["_IntBoard"]
                }
                st.success("✅ **Architecture locked in!** Switch over to the 'Drone Builder' tab.")