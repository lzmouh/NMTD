import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from utils import generate_tx_chirp
from config import (
    fluid_impedance_db, default_densities, INCH_TO_METER,
    DEFAULT_CONFIG, LAYER_DB, PIPE_DB
)

def show_simulator():
    st.set_page_config(page_title="NMTD Simulator", layout="wide")

    # Initialize session
    if "config" not in st.session_state:
        st.session_state["config"] = DEFAULT_CONFIG.copy()
    if "config_loaded" not in st.session_state:
        st.session_state["config_loaded"] = False

    config = st.session_state["config"]

    # --- Sidebar with Logo and Controls ---
    with st.sidebar:
        #st.image("company_logo.png", use_container_width=True)  # Add your logo here

        st.markdown("## Configuration")

        # Fluid Control
        fluid = st.selectbox("Fluid Type", list(fluid_impedance_db.keys()), index=list(fluid_impedance_db.keys()).index(config["fluid"]))
        config["fluid"] = fluid
        if fluid == "Other":
            config["fluid_density"] = st.number_input("Density (g/cc)", 0.5, 2.5, config.get("fluid_density",1.0))
            config["Z_fluid"] = st.number_input("Z (MRayl)", 1.0, 5.0, config.get("Z_fluid",1.5))
        else:
            config["fluid_density"] = default_densities[fluid]
            config["Z_fluid"] = fluid_impedance_db[fluid]

        # Pipe Type and Layers
        st.markdown("---")
        config["pipe_type"] = st.radio("Pipe Type", ["Commercial", "Custom"])
        if config["pipe_type"] == "Custom":
            config["num_layers"] = st.slider("Number of Layers", 1, 10, config.get("num_layers", 3))

        # Chirp Inputs
        st.markdown("---")
        st.markdown("### 📡 Chirp Settings")
        config["f_start_mhz"] = st.number_input("Start Freq (MHz)",0.1,10.0,config.get("f_start_mhz",0.5))
        config["f_end_mhz"] = st.number_input("End Freq (MHz)",0.1,10.0,config.get("f_end_mhz",5.0))
        config["sweep_us"] = st.number_input("Sweep Duration (µs)",10.0,200.0,config.get("sweep_us",50.0))
        config["sampling_rate"] = 100e6

    st.session_state["config"] = config  # ensure config is updated

    # --- Main Page Content ---

    st.title("NMTD Ultrasonic Response Simulator")

    # Fluid summary
    Z = config["Z_fluid"] * 1e6
    rho = config["fluid_density"] * 1000
    c_fluid = Z / rho
    config["fluid_velocity"] = c_fluid

    col1, col2, col3 = st.columns(3)
    col1.metric("Z_fluid (MRayl)", f"{config['Z_fluid']:.2f}")
    col2.metric("Fluid Density", f"{config['fluid_density']:.2f} g/cc")
    col3.metric("Fluid Velocity", f"{c_fluid:.0f} m/s")

    # Layer table preparation
    if pipe_type=="Commercial":
        pipe = PIPE_DB[st.session_state["pipe_selection"]] if "pipe_selection" in st.session_state else None
        pipe = pipe or PIPE_DB[list(PIPE_DB.keys())[0]]
        st.session_state["pipe_selection"] = pipe
        config["layer_data"] = pipe["layers"]
        config["num_layers"] = len(pipe["layers"])
        config["total_thickness"] = pipe["total_thickness"]
    else:
        # Initialize blank rows
        layers = config.get("layer_data", [])
        if len(layers) < config["num_layers"]:
            for _ in range(config["num_layers"] - len(layers)):
                layers.append({"name":"", "thickness":0.2, "Z":2.5, "v":2000,"alpha0":0.05,"n_exp":1.2})
        config["layer_data"] = layers

    df = pd.DataFrame(config["layer_data"])
    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
    config["layer_data"] = edited.to_dict("records")
    config["total_thickness"] = edited["thickness"].sum()
    st.write(f"### Total Thickness: **{config['total_thickness']:.2f} in**")

    # Defect handling
    st.markdown("---")
    st.subheader("🩻 Defect Settings")
    if config["num_layers"] == 1:
        config["defect_type"] = st.selectbox("Defect Type", ["None", "Crack"], index=["None","Crack"].index(config.get("defect_type","None")))
        st.markdown("> *Only one layer ⇒ delamination disabled*")
        config["defect_layer"] = 1
    else:
        config["defect_type"] = st.selectbox("Defect Type", ["None","Delamination","Crack"], index=["None","Delamination","Crack"].index(config.get("defect_type","None")))
        config["defect_layer"] = st.selectbox("Defect Layer", list(range(1,config["num_layers"]+1)), index=config.get("defect_layer",1)-1)

    st.session_state["config"] = config

    # Chirp Generation
    fs = config["sampling_rate"]
    t_chirp, tx = generate_tx_chirp(fs, config["sweep_us"]*1e-6, config["f_start_mhz"]*1e6, config["f_end_mhz"]*1e6)
    config["tx_chirp_t"] = t_chirp.tolist()
    config["tx_chirp_waveform"] = tx.tolist()
    st.session_state["config"] = config

    # Plot Chirp
    with st.expander("📈 Transmitted Chirp Signals", expanded=True):
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=t_chirp*1e6, y=tx, name="Time-Domain", line=dict(color='black')))
        fig1.update_layout(height=300, xaxis_title="Time (µs)", yaxis_title="Amplitude")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = go.Figure()
        fft_vals = np.abs(np.fft.fft(tx))
        freqs = np.fft.fftfreq(len(tx), d=1/fs)
        fig2.add_trace(go.Scatter(x=freqs[freqs>0]/1e6, y=fft_vals[freqs>0], name="Spectrum", line=dict(color='violet')))
        fig2.update_layout(height=300, xaxis_title="Freq (MHz)", yaxis_title="Magnitude")
        st.plotly_chart(fig2, use_container_width=True)

    # Save / Load / Reset
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("📤 Export Config", json.dumps(config, indent=2), "config.json", "application/json")
    with col2:
        up = st.file_uploader("⬆️ Load Config", type="json")
        if up and not st.session_state["config_loaded"]:
            loaded = json.load(up)
            if "layer_data" in loaded:
                st.session_state["config"] = loaded
                st.session_state["config_loaded"] = True
                st.success("Loaded – please refresh or switch tab")
    with col3:
        if st.button("🔄 Reset to Default"):
            st.session_state["config"] = DEFAULT_CONFIG.copy()
            st.session_state["config_loaded"] = False
            st.experimental_rerun()
