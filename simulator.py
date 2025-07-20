import pandas as pd
import streamlit as st
import numpy as np
import json
import plotly.graph_objects as go
from config import (
    DEFAULT_CONFIG, FLUID_DB,
    PIPE_DB, LAYER_DB, INCH_TO_METER
)
from utils import generate_tx_chirp

def show_simulator():
    # --- INIT SESSION STATE ---
    if "config_loaded" not in st.session_state:
        st.session_state["config_loaded"] = False

    if "config" not in st.session_state or not st.session_state["config_loaded"]:
        st.session_state["config"] = DEFAULT_CONFIG.copy()

    config = st.session_state["config"]
    
    # --- SIDEBAR LAYOUT ---
    #st.sidebar.image("logo.png", use_container_width=True)
    st.sidebar.title("Simulation Setup")

    # FLUID SELECTION
    fluid_names = list(FLUID_DB.keys())
    config["fluid"] = st.sidebar.selectbox("Borehole Fluid", fluid_names, index=0)
    
    if config["fluid"] == "Other":
        config["fluid_density"] = st.sidebar.number_input("Fluid Density (g/cc)", 0.5, 2.5, 1.0)
        config["Z_fluid"] = st.sidebar.number_input("Z_fluid (MRayl)", 1.0, 3.0, 1.5)
    else:
        fluid_data = FLUID_DB[config["fluid"]]
        config["fluid_density"] = fluid_data["density"]
        config["Z_fluid"] = fluid_data["Z"]
    
    # Compute fluid velocity
    rho = config["fluid_density"] * 1000     # g/cc → kg/m³
    Z = config["Z_fluid"] * 1e6              # MRayl → Rayl
    config["fluid_velocity"] = Z / rho       # m/s

    # PIPE TYPE TOGGLE
    pipe_type = st.sidebar.radio("Pipe Configuration", ["Commercial Pipe", "Custom Pipe"], index=0)
    config["pipe_type"] = pipe_type

    # MAIN PAGE HEADER
    st.title("Non-metalic Tubualrs Defectoscope NMTD")
    st.subheader("Ultrasonic Simulation App")
    #st.markdown("Configure your test pipe and simulation parameters.")

    # DISPLAY FLUID BOXES
    df = pd.DataFrame([{
        "Fluid": config["fluid"],
        "Density (g/cc)": f"{config['fluid_density']:.2f}",
        "Z_fluid (MRayl)": f"{config['Z_fluid']:.2f}",
        "Velocity (m/s)": f"{config['fluid_velocity']:.0f}"
    }])
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # --- COMMERCIAL PIPE CONFIG ---
    if pipe_type == "Commercial Pipe":
        col1, col2, col3 = st.columns([1,3,1])
        with col2:
            pipe_name = st.selectbox("Select Pipe", list(PIPE_DB.keys()))
            pipe = PIPE_DB[pipe_name]
            config["layer_data"] = pipe["layers"]
            config["num_layers"] = len(pipe["layers"])
            config["total_thickness"] = pipe["total_thickness"]
            st.markdown(f"**{pipe['description']}**")
            
        st.markdown("### Layer Structure")
        df = [{**l} for l in config["layer_data"]]
        st.dataframe(df, use_container_width=True)
    
   # --- CUSTOM PIPE ---
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
                mat_name = st.selectbox(
                    f"Material {i+1}", ["New"] + mat_keys,
                    index=index,
                    key=f"mat_{i}"
                )
                            
            if mat_name != "New":
                props = LAYER_DB[mat_name]
                editable = True
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


    # --- TOTAL THICKNESS ---
    config["total_thickness"] = sum([l["thickness"] for l in config["layer_data"]])
    st.info(f"Total Pipe Thickness: **{config['total_thickness']:.2f}\"**")

    # Auto-estimate safe max_time
    D_total = sum([l["thickness"] for l in config["layers"]]) * 0.0254  # inches to meters
    c_min = min([l["velocity"] for l in config["layers"]])
    max_time_suggested = 2 * D_total / c_min  # Round-trip time
    config["max_time"] = st.sidebar.number_input(
        "Max Listening Time (µs)", 50.0, 1000.0, max_time_suggested * 1e6
    ) * 1e-6
    
    # --- DEFECT SETTINGS ---
    st.subheader("Defect Settings")
    if config["num_layers"] == 1:
        col1, col2 = st.columns(2)
        with col1:
            config["defect_type"] = st.selectbox("Defect Type", ["None", "Crack"])
        with col2:
            config["defect_layer"] = 1
            st.markdown(
                "<p style='font-size:14px;'>Defect Layer Index</p>",
                unsafe_allow_html=True
            )
            st.markdown("ℹ️ Only 1 layer: delamination not possible.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            config["defect_type"] = st.selectbox("Defect Type", ["None", "Delamination", "Crack"])
        with col2:
            config["defect_layer"] = st.slider("Defect Layer Index", 1, config["num_layers"], config.get("defect_layer", 1))

    # --- CHIRP SETTINGS ---
    st.subheader("Chirp Settings")
    c1, c2, c3 = st.columns(3)
    config["f_start_mhz"] = c1.number_input("Start Freq (MHz)", 0.1, 10.0, config.get("f_start_mhz", 0.5))
    config["f_end_mhz"] = c2.number_input("End Freq (MHz)", 0.1, 10.0, config.get("f_end_mhz", 5.0))
    config["sweep_us"] = c3.number_input("Duration (µs)", 10.0, 200.0, config.get("sweep_us", 50.0))
    config["sampling_rate"] = 100e6  # fixed 100 MHz

    # --- GENERATE CHIRP ---
    t_chirp, tx = generate_tx_chirp(
        fs=config["sampling_rate"],
        sweep_us=config["sweep_us"],
        f_start_mhz=config["f_start_mhz"],
        f_end_mhz=config["f_end_mhz"]
    )
    config["t_chirp"] = t_chirp.tolist()
    config["tx"] = tx.tolist()
    st.session_state["config"] = config
    st.session_state["config_loaded"] = True

    # --- CHIRP PLOTS ---
    with st.expander("Transmitted Chirp Preview", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=t_chirp * 1e6, y=tx, name="Tx Chirp"))
            fig1.update_layout(title="Chirp (Time)", xaxis_title="Time (µs)", height=300)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            TX_FFT = np.fft.fft(tx)
            freqs = np.fft.fftfreq(len(tx), d=1/config["sampling_rate"])
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=freqs[freqs > 0] / 1e6, y=np.abs(TX_FFT[freqs > 0]), name="Spectrum"))
            fig2.update_layout(title="Chirp (Freq)", xaxis_title="Frequency (MHz)", height=300)
            st.plotly_chart(fig2, use_container_width=True)

    
    # --- SAVE / LOAD ---
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
