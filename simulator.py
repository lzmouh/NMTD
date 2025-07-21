import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json

from config import (
    DEFAULT_CONFIG, FLUID_DB, PIPE_DB, LAYER_DB, INCH_TO_METER
)
from utils import generate_tx_chirp, simulate_multilayer_propagation

def show_simulator():
    # --- SESSION INIT ---
    if "config_loaded" not in st.session_state:
        st.session_state["config_loaded"] = False
    if "config" not in st.session_state or not st.session_state["config_loaded"]:
        st.session_state["config"] = DEFAULT_CONFIG.copy()

    config = st.session_state["config"]

    # --- SIDEBAR SETUP ---
    st.sidebar.title("Simulation Setup")

    fluid_names = list(FLUID_DB.keys())
    config["fluid"] = st.sidebar.selectbox("Borehole Fluid", fluid_names, index=0)

    fluid_name = config["fluid"]
    if fluid_name == "Other":
        config["fluid_density"] = st.sidebar.number_input("Fluid Density (g/cc)", 0.5, 2.5, 1.0)
        config["Z_fluid"] = st.sidebar.number_input("Z_fluid (MRayl)", 1.0, 3.0, 1.5)
        rho = config["fluid_density"] * 1000
        Z = config["Z_fluid"] * 1e6
        config["fluid_velocity"] = Z / rho
        config["fluid"] = {
            "name": "Custom",
            "density": rho,
            "velocity": config["fluid_velocity"],
            "Z": Z,
        }
    else:
        fluid_data = FLUID_DB[fluid_name]
        config["fluid"] = fluid_data
        config["fluid_density"] = fluid_data["density"] / 1000  # kg/m³ → g/cc
        config["Z_fluid"] = fluid_data["Z"] / 1e6
        config["fluid_velocity"] = fluid_data["velocity"]

    pipe_type = st.sidebar.radio("Pipe Configuration", ["Commercial Pipe", "Custom Pipe"], index=0)
    config["pipe_type"] = pipe_type

    # --- PAGE HEADER ---
    st.title("Non-Metallic Tubulars Defectoscope (NMTD)")
    st.subheader("Ultrasonic Simulation App")

    # --- FLUID PROPERTIES TABLE ---
    st.markdown("### Fluid Properties")
    fluid_df = pd.DataFrame([{
        "Fluid": fluid_name,
        "Density (g/cc)": f"{config['fluid_density']:.2f}",
        "Z_fluid (MRayl)": f"{config['Z_fluid']:.2f}",
        "Velocity (m/s)": f"{config['fluid_velocity']:.0f}"
    }])
    st.dataframe(fluid_df, use_container_width=True, hide_index=True)

    # --- COMMERCIAL PIPE CONFIG ---
    if pipe_type == "Commercial Pipe":
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            pipe_name = st.selectbox("Select Pipe", list(PIPE_DB.keys()))
            pipe = PIPE_DB[pipe_name]
            config["layer_data"] = pipe["layers"]
            config["num_layers"] = len(pipe["layers"])
            config["total_thickness"] = pipe["total_thickness"]
            st.markdown(f"**{pipe['description']}**")
        st.markdown("### Layer Structure")
        st.dataframe(config["layer_data"], use_container_width=True)

    # --- CUSTOM PIPE CONFIG ---
    elif pipe_type == "Custom Pipe":
        st.sidebar.markdown("---")
        config["num_layers"] = st.sidebar.slider("Number of Layers", 1, 10, config.get("num_layers", 3))
        config["layer_data"] = config.get("layer_data", [])[:config["num_layers"]]
        while len(config["layer_data"]) < config["num_layers"]:
            config["layer_data"].append({})

        st.markdown("### Custom Layer Configuration")
        layer_cols = st.columns(7)
        for i in range(config["num_layers"]):
            layer = config["layer_data"][i]
            with layer_cols[0]:
                mat_keys = list(LAYER_DB.keys())
                mat_value = layer.get("material", "New")
                index = 0 if mat_value == "Custom" or mat_value not in mat_keys else mat_keys.index(mat_value) + 1
                mat_name = st.selectbox(f"Material {i+1}", ["New"] + mat_keys, index=index, key=f"mat_{i}")
            if mat_name != "New":
                props = LAYER_DB[mat_name]
                row = {
                    "name": mat_name,
                    "material": mat_name,
                    "thickness": props["thickness"],
                    "Z": props["Z"],
                    "v": props["v"],
                    "alpha0": props["alpha0"],
                    "n_exp": props["n_exp"],
                }
            else:
                row = config["layer_data"][i] if isinstance(config["layer_data"][i], dict) else {}

            with layer_cols[1]: row["name"] = st.text_input(f"Name {i+1}", row.get("name", f"Layer {i+1}"), key=f"name_{i}")
            with layer_cols[2]: row["thickness"] = st.number_input(f"Thk {i+1}", 0.01, 1.0, row.get("thickness", 0.2), key=f"t_{i}")
            with layer_cols[3]: row["Z"] = st.number_input(f"Z {i+1}", 1.0, 10.0, row.get("Z", 2.5), key=f"Z_{i}")
            with layer_cols[4]: row["v"] = st.number_input(f"v {i+1}", 500, 5000, row.get("v", 2500), step=50, key=f"v_{i}")
            with layer_cols[5]: row["alpha0"] = st.number_input(f"α₀ {i+1}", 0.0, 1.0, row.get("alpha0", 0.05), step=0.01, key=f"a_{i}")
            with layer_cols[6]: row["n_exp"] = st.number_input(f"n {i+1}", 0.5, 3.0, row.get("n_exp", 1.2), step=0.1, key=f"n_{i}")
            row["material"] = mat_name if mat_name != "New" else "Custom"
            config["layer_data"][i] = row

    config["total_thickness"] = sum(layer["thickness"] for layer in config["layer_data"])
    st.info(f"Total Pipe Thickness: **{config['total_thickness']:.2f}\"**")

    # --- MAX LISTENING TIME ---
    D_total = config["total_thickness"] * INCH_TO_METER
    c_min = min([l["v"] for l in config["layer_data"]])
    max_time_suggested = 2 * D_total / c_min
    default_us = max(50.0, max_time_suggested * 1e6)
    config["max_time"] = st.sidebar.number_input("Max Listening Time (µs)", 50.0, 1000.0, default_us) * 1e-6

    # --- DEFECT SETTINGS ---
    st.subheader("Defect Settings")
    if config["num_layers"] == 1:
        config["defect_type"] = st.selectbox("Defect Type", ["None", "Crack"])
        config["defect_layer"] = 1
        st.markdown("ℹ️ Only 1 layer: delamination not possible.")
    else:
        config["defect_type"] = st.selectbox("Defect Type", ["None", "Delamination", "Crack"])
        config["defect_layer"] = st.slider("Defect Layer Index", 1, config["num_layers"], config.get("defect_layer", 1))

    # --- CHIRP SETTINGS ---
    st.subheader("Chirp Settings")
    c1, c2, c3 = st.columns(3)
    config["f_start_mhz"] = c1.number_input("Start Freq (MHz)", 0.1, 10.0, config.get("f_start_mhz", 0.5))
    config["f_end_mhz"] = c2.number_input("End Freq (MHz)", 0.1, 10.0, config.get("f_end_mhz", 5.0))
    config["sweep_us"] = c3.number_input("Duration (µs)", 10.0, 200.0, config.get("sweep_us", 50.0))
    config["sampling_rate"] = 100e6  # fixed

    # --- CHIRP GENERATION ---
    t_chirp, tx = generate_tx_chirp(
        fs=config["sampling_rate"],
        sweep_us=config["sweep_us"],
        f_start_mhz=config["f_start_mhz"],
        f_end_mhz=config["f_end_mhz"]
    )
    config["t_chirp"] = t_chirp.tolist()
    config["tx"] = tx.tolist()

    # --- CHIRP PREVIEW ---
    with st.expander("Transmitted Chirp Preview", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=t_chirp * 1e6, y=tx, name="Tx Chirp"))
            fig1.update_layout(title="Chirp (Time)", xaxis_title="Time (µs)", height=300)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            TX_FFT = np.fft.fft(tx)
            freqs = np.fft.fftfreq(len(tx), d=1 / config["sampling_rate"])
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=freqs[freqs > 0] / 1e6, y=np.abs(TX_FFT[freqs > 0]), name="Spectrum"))
            fig2.update_layout(title="Chirp (Freq)", xaxis_title="Frequency (MHz)", height=300)
            st.plotly_chart(fig2, use_container_width=True)

    # --- SIMULATE MULTILAYER RESPONSE ---
    st.subheader("📡 Simulated Ultrasonic Response")
    layers = [{
        "thickness": l["thickness"] * INCH_TO_METER,
        "c": l["v"],
        "rho": l["Z"] / l["v"],
        "alpha0": l["alpha0"],
        "n": l["n_exp"],
        "beta": l.get("beta", 0.0),
    } for l in config["layer_data"]]

    fluid_props = {
        "c": config["fluid_velocity"],
        "rho": config["fluid_density"] * 1000
    }

    received_signal, time_axis, echo_metadata = simulate_multilayer_propagation(
        chirp_signal=np.array(tx),
        chirp_t=np.array(t_chirp),
        fluid_props=fluid_props,
        layers=layers,
        gap_thickness=2.54e-3,
        fs=config["sampling_rate"]
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time_axis * 1e6, y=received_signal, name="Received Signal"))
    for echo in echo_metadata:
        fig.add_vline(x=echo["time"] * 1e6, line=dict(color="red", dash="dot"),
                      annotation_text=echo["interface"], annotation_position="top right")
    fig.update_layout(title="Simulated A-scan", xaxis_title="Time (µs)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # --- METADATA TABLE ---
    st.subheader("🧾 Echo Metadata")
    st.dataframe(pd.DataFrame(echo_metadata), use_container_width=True)

    # --- SAVE / LOAD CONFIG ---
    st.subheader("💾 Save / Load Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📤 Export JSON", data=json.dumps(config, indent=2), file_name="nmted_config.json")
    with c2:
        uploaded = st.file_uploader("⬆️ Load Config", type="json")
        if uploaded and not st.session_state["config_loaded"]:
            st.session_state["config"] = json.load(uploaded)
            st.session_state["config_loaded"] = True
            st.success("Configuration loaded.")
            st.rerun()
    with c3:
        if st.button("🗑️ Reset"):
            st.session_state["config"] = DEFAULT_CONFIG.copy()
            st.session_state["config_loaded"] = False
            st.rerun()
