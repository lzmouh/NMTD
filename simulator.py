import streamlit as st
import json
from config import (
    fluid_impedance_db, default_densities,
    MATERIAL_DB, PIPE_DB, DEFAULT_CONFIG, INCH_TO_METER, DEFAULT_GAP_INCH
)

def show_simulator():
    st.title("🧪 NMTD Ultrasonic Response Simulator")

    # --- Load or initialize configuration ---
    if "config" not in st.session_state or not st.session_state.get("config"):
        st.session_state["config"] = DEFAULT_CONFIG.copy()

    config = st.session_state["config"]

    # --- FLUID SELECTION ---
    st.subheader("🌊 Borehole Fluid Properties")
    col1, col2 = st.columns(2)
    with col1:
        config["fluid"] = st.selectbox("Fluid Type", list(fluid_impedance_db.keys()), index=0)
        if config["fluid"] == "Other":
            config["fluid_density"] = st.number_input("Density (g/cc)", 0.5, 2.5, 1.0)
        else:
            config["fluid_density"] = default_densities[config["fluid"]]
            config["Z_fluid"] = fluid_impedance_db[config["fluid"]]
    
    with col2:
        Z = config["Z_fluid"] * 1e6  # Rayl
        rho = config["fluid_density"] * 1000  # kg/m³
        c_fluid = Z / rho
        config["fluid_velocity"] = c_fluid
        st.metric("Z_fluid", f"{config['Z_fluid']:.2f} MRayl")
        st.metric("Fluid Velocity", f"{c_fluid:.0f} m/s")

    # --- PIPE TYPE SELECTION ---
    st.subheader("🧱 Pipe Type and Layers")
    pipe_types = ["Custom"] + list(PIPE_DB.keys())
    config["pipe_type"] = st.selectbox("Pipe Type", pipe_types, index=pipe_types.index(config.get("pipe_type", "Custom")))

    if config["pipe_type"] != "Custom":
        config["layer_data"] = PIPE_DB[config["pipe_type"]].copy()
        config["num_layers"] = len(config["layer_data"])
    else:
        config["num_layers"] = st.slider("Number of Layers", 1, 10, config.get("num_layers", 3))

        # Truncate or pad layer list
        layers = config.get("layer_data", [])
        while len(layers) < config["num_layers"]:
            layers.append({
                "name": f"Layer {len(layers)+1}",
                "thickness": 0.2,
                "Z": 2.5,
                "material": "GRE (Glass-Reinforced Epoxy)",
                "v": 2500,
                "alpha0": 0.05,
                "n_exp": 1.2
            })
        config["layer_data"] = layers[:config["num_layers"]]

        st.markdown("### ✏️ Custom Layer Configuration")
        for i in range(config["num_layers"]):
            c1, c2, c3 = st.columns([1, 1, 2])
            layer = config["layer_data"][i]
            with c1:
                layer["thickness"] = st.number_input(f"Layer {i+1} Thickness (in)", 0.01, 1.0, layer["thickness"], key=f"thick_{i}")
            with c2:
                layer["Z"] = st.number_input(f"Layer {i+1} Z (MRayl)", 1.0, 10.0, layer["Z"], key=f"Z_{i}")
            with c3:
                mat = st.selectbox(f"Layer {i+1} Material", list(MATERIAL_DB.keys()), index=list(MATERIAL_DB.keys()).index(layer["material"]), key=f"mat_{i}")
                layer["material"] = mat
                if mat == "Custom":
                    layer["v"] = st.number_input(f"→ v (m/s)", 1000, 5000, layer.get("v", 2000), key=f"v_{i}")
                    layer["alpha0"] = st.number_input(f"→ α0 (dB/cm/MHz)", 0.0, 1.0, layer.get("alpha0", 0.05), key=f"a_{i}")
                    layer["n_exp"] = st.number_input(f"→ n exponent", 0.5, 3.0, layer.get("n_exp", 1.2), key=f"n_{i}")
                else:
                    props = MATERIAL_DB[mat]
                    layer["v"] = props["v"]
                    layer["alpha0"] = props["alpha0"]
                    layer["n_exp"] = props["n"]
                    st.markdown(f"→ v = {props['v']} m/s · α₀ = {props['alpha0']} · n = {props['n']}")

    config["total_thickness"] = sum(layer["thickness"] for layer in config["layer_data"])
    st.markdown(f"**📏 Total Pipe Thickness: `{config['total_thickness']:.2f}` inches**")

    # --- DEFECT SELECTION ---
    st.subheader("🧯 Defect Settings")
    if config["num_layers"] == 1:
        config["defect_type"] = "Crack"
        st.info("Only 1 layer — Defect type forced to **Crack**")
    else:
        config["defect_type"] = st.selectbox("Defect Type", ["None", "Delamination", "Crack"],
                                             index=["None", "Delamination", "Crack"].index(config.get("defect_type", "None")))

    config["defect_layer"] = st.slider("Defect Layer Index", 1, config["num_layers"], config.get("defect_layer", 1))

    # --- CHIRP CONFIGURATION ---
    st.subheader("📡 Chirp Transmitter Settings")
    col1, col2, col3 = st.columns(3)
    config["f_start_mhz"] = col1.number_input("Start Freq (MHz)", 0.1, 10.0, config.get("f_start_mhz", 0.5))
    config["f_end_mhz"]   = col2.number_input("End Freq (MHz)",   0.1, 10.0, config.get("f_end_mhz", 5.0))
    config["sweep_us"]    = col3.number_input("Duration (µs)",    1.0, 200.0, config.get("sweep_us", 50.0))
    config["sampling_rate"] = 100e6  # Fixed for now

    # --- Save config ---
    st.session_state["config"] = config

    # --- SAVE / LOAD / RESET ---
    st.subheader("💾 Save / Load Config")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📤 Export Config", json.dumps(config, indent=2), file_name="nmted_config.json", mime="application/json")
    with c2:
        uploaded = st.file_uploader("⬆️ Load Config", type="json")
        if uploaded:
            loaded = json.load(uploaded)
            if "layer_data" in loaded:
                st.session_state["config"] = loaded
                st.experimental_set_query_params(loaded="true")  # avoids endless rerun
                st.success("✅ Configuration loaded.")
                st.rerun()
    with c3:
        if st.button("🗑️ Reset to Default"):
            st.session_state["config"] = DEFAULT_CONFIG.copy()
            st.rerun()
