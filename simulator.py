import numpy as np
import streamlit as st
import plotly.graph_objects as go
import json
from utils import generate_tx_chirp
from config import (
    fluid_impedance_db, default_densities, INCH_TO_METER,
    DEFAULT_GAP_INCH, LAYER_DB, DEFAULT_CONFIG, PIPE_DB
)

def show_simulator():
    st.title("NMTD Ultrasonic Response Simulator")

    # --- Initialize default config if missing ---
    if "config" not in st.session_state:
        st.session_state["config"] = DEFAULT_CONFIG.copy()
    if "config_loaded" not in st.session_state:
        st.session_state["config_loaded"] = False

    config = st.session_state["config"]

     # --- Sidebar ---
    with st.sidebar:
        st.header("🔧 Settings")

        # --- Fluid Selection ---
        config["fluid"] = st.selectbox("Fluid Type", list(fluid_impedance_db.keys()), index=0)
        if config["fluid"] == "Other":
            config["fluid_density"] = st.number_input("Density (g/cc)", 0.5, 2.5, 1.0)
            config["Z_fluid"] = st.number_input("Z (MRayl)", 1.0, 5.0, 1.5)
        else:
            config["fluid_density"] = default_densities[config["fluid"]]
            config["Z_fluid"] = fluid_impedance_db[config["fluid"]]

        Z_rayl = config["Z_fluid"] * 1e6
        rho = config["fluid_density"] * 1000
        config["fluid_velocity"] = Z_rayl / rho

        st.markdown("---")
        config["pipe_type"] = st.radio("Pipe Type", ["Commercial", "Custom"])
        if config["pipe_type"] == "Custom":
            config["num_layers"] = st.slider("Number of Layers", 1, 10, config.get("num_layers", 3))

    # --- Fluid Info Display ---
    st.subheader("🌊 Fluid Properties")
    col1, col2, col3 = st.columns(3)
    col1.metric("Z_fluid", f"{config['Z_fluid']:.2f} MRayl")
    col2.metric("Density", f"{config['fluid_density']:.2f} g/cc")
    col3.metric("Velocity", f"{config['fluid_velocity']:.0f} m/s")

    # --- Pipe Configuration ---
    if config["pipe_type"] == "Commercial":
        pipe_name = st.selectbox("Select Pipe", list(PIPE_DB.keys()))
        pipe = PIPE_DB[pipe_name]
        st.markdown(f"**📦 {pipe_name}** — {pipe['description']}")
        config["layer_data"] = pipe["layers"]
        config["num_layers"] = len(pipe["layers"])
        config["total_thickness"] = pipe["total_thickness"]

        # Show each layer
        st.markdown("### 🧱 Pipe Layers")
        for i, layer in enumerate(config["layer_data"]):
            st.markdown(
                f"**Layer {i+1}: {layer['name']}**  \n"
                f"`Material`: {layer['material']} · `Z`: {layer['Z']} MRayl · `v`: {layer['v']} m/s · "
                f"`α₀`: {layer['alpha0']} dB/cm/MHz · `n`: {layer['n_exp']} · `Thickness`: {layer['thickness']} in"
            )

    else:
        # --- Custom Pipe Input ---
        config["layer_data"] = config.get("layer_data", [])
        config["layer_data"] = config["layer_data"][:config["num_layers"]]

        while len(config["layer_data"]) < config["num_layers"]:
            config["layer_data"].append({})

        st.subheader("🧱 Custom Layer Configuration")
        for i in range(config["num_layers"]):
            st.markdown(f"#### Layer {i+1}")
            layer_type = st.selectbox(f"Layer Source", ["Select from DB", "Custom"], key=f"layer_src_{i}")

            if layer_type == "Select from DB":
                selected = st.selectbox("Choose Layer", list(LAYER_DB.keys()), key=f"sel_{i}")
                props = LAYER_DB[selected]
                config["layer_data"][i] = {
                    "name": selected, "material": selected, **props
                }
                st.markdown(
                    f"`Z`: {props['Z']} MRayl · `v`: {props['v']} m/s · α₀ = {props['alpha0']} dB/cm/MHz · "
                    f"n = {props['n_exp']} · Thickness = {props['thickness']} in"
                )
            else:
                name = st.text_input("Name", f"Layer {i+1}", key=f"name_{i}")
                thick = st.number_input("Thickness (in)", 0.01, 1.0, 0.2, 0.01, key=f"t_{i}")
                Z = st.number_input("Z (MRayl)", 1.0, 5.0, 2.5, key=f"Z_{i}")
                v = st.number_input("Velocity (m/s)", 1000, 5000, 2000, step=10, key=f"v_{i}")
                alpha = st.number_input("α₀ (dB/cm/MHz)", 0.01, 2.0, 0.05, key=f"a_{i}")
                n = st.number_input("n exponent", 0.5, 3.0, 1.2, key=f"n_{i}")
                config["layer_data"][i] = {
                    "name": name, "material": "Custom", "thickness": thick,
                    "Z": Z, "v": v, "alpha0": alpha, "n_exp": n
                }

 
    # --- Total Thickness ---
    config["total_thickness"] = sum(l["thickness"] for l in config["layer_data"])
    st.markdown(f"**Total Pipe Thickness: {config['total_thickness']:.2f} inches**")

    # --- Defect Settings ---
    st.markdown("###Defect Settings")
    if config["num_layers"] == 1:
        # Force defect type to Crack or None
        config["defect_type"] = st.selectbox(
            "Defect Type", ["None", "Crack"], index=["None", "Crack"].index(config["defect_type"])
        )
        # Disable defect layer index; only one layer
        st.markdown("Defect Layer Index: **1** (only one layer)")
        config["defect_layer"] = 1
    else:
        config["defect_type"] = st.selectbox(
            "Defect Type", ["None", "Delamination", "Crack"],
            index=["None", "Delamination", "Crack"].index(config["defect_type"])
        )
        config["defect_layer"] = st.slider(
            "Defect Layer Index", min_value=1, max_value=config["num_layers"], value=config["defect_layer"]
        )
 
    # --- Chirp Settings UI ---
    st.subheader("Chirp Settings")
    c1, c2, c3 = st.columns(3)
    config["f_start_mhz"] = c1.number_input("Start Freq (MHz)", 0.1, 10.0, config["f_start_mhz"])
    config["f_end_mhz"]   = c2.number_input("End Freq (MHz)",   0.1, 10.0, config["f_end_mhz"])
    config["sweep_us"]    = c3.number_input("Sweep Duration (µs)", 10.0, 100.0, config["sweep_us"])
    config["sampling_rate"] = 100e6  # or make this configurable later
    
    # --- Chirp Generation ---
    fs = config["sampling_rate"]
    t_chirp, tx = generate_tx_chirp(
        fs,
        sweep_us=config["sweep_us"],
        f_start_mhz=config["f_start_mhz"],
        f_end_mhz=config["f_end_mhz"]
    )
    
    # --- Save to session ---
    config["t_chirp"] = t_chirp.tolist()
    config["tx"] = tx.tolist()
    st.session_state["config"] = config
        
    # Chirp plots
    with st.expander("Transmitted Chirp Signal"):
        col1, col2 = st.columns(2)
    
        # --- Time-Domain Plot ---
        with col1:
            fig_tx = go.Figure()
            fig_tx.add_trace(go.Scatter(x=t_chirp * 1e6, y=tx, name="Tx Chirp"))
            fig_tx.update_layout(
                title="Chirp Signal",
                xaxis_title="Time (µs)",
                yaxis_title="Amplitude",
                height=300
            )
            st.plotly_chart(fig_tx, use_container_width=True)

        with col2:
            # --- Frequency-Domain Plot ---
            TX_FFT = np.fft.fft(tx)
            freqs = np.fft.fftfreq(len(tx), d=1/fs)
            mask = freqs > 0
        
            fig_fft = go.Figure()
            fig_fft.add_trace(go.Scatter(x=freqs[mask] / 1e6, y=np.abs(TX_FFT[mask]), name="Spectrum"))
            fig_fft.update_layout(
                title="Frequency Spectrum",
                xaxis_title="Frequency (MHz)",
                yaxis_title="Magnitude",
                height=300
            )
            st.plotly_chart(fig_fft, use_container_width=True)


    
    # --- Save/Load/Reset ---
    st.markdown("### 💾 Save / Load Config")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "📤 Export JSON",
            data=json.dumps(config, indent=2),
            file_name="nmted_config.json",
            mime="application/json"
        )
    with col2:
        uploaded = st.file_uploader("⬆️ Load Config", type="json")
        if uploaded and not st.session_state["config_loaded"]:
            loaded = json.load(uploaded)
            if "layer_data" in loaded:
                st.session_state["config"] = loaded
                st.session_state["config_loaded"] = True
                st.success("Configuration loaded. Please refresh or navigate to another tab.")
    with col3:
        if st.button("🗑️ Reset"):
            st.session_state["config"] = DEFAULT_CONFIG.copy()
            st.session_state["config_loaded"] = False
            st.rerun()
