import streamlit as st
import json
from config import (
    fluid_impedance_db, default_densities, INCH_TO_METER,
    DEFAULT_GAP_INCH, MATERIAL_DB, DEFAULT_CONFIG, COMMERCIAL_PIPES
)

def show_simulator():
    st.title("NMTD Ultrasonic Response Simulator")

    # --- Initialize default config if missing ---
    if "config" not in st.session_state:
        st.session_state["config"] = DEFAULT_CONFIG.copy()
    if "config_loaded" not in st.session_state:
        st.session_state["config_loaded"] = False

    config = st.session_state["config"]

    # --- Fluid Selection ---
    col1, col2 = st.columns(2)
    with col1:
        config["fluid"] = st.selectbox("Select Borehole Fluid", list(fluid_impedance_db.keys()), index=0)
        if config["fluid"] == "Other":
            config["fluid_density"] = st.number_input("Fluid Density (g/cc)", 0.5, 2.5, 1.0)
        else:
            config["fluid_density"] = default_densities[config["fluid"]]
        config["Z_fluid"] = fluid_impedance_db[config["fluid"]] or config["Z_fluid"]

        Z = config["Z_fluid"] * 1e6
        rho = config["fluid_density"] * 1000
        c_fluid = Z / rho
        config["fluid_velocity"] = c_fluid

        st.markdown(f"**Z_fluid = {config['Z_fluid']:.2f} MRayl**")
        st.markdown(f"**Fluid velocity = {c_fluid:.0f} m/s**")

    # --- Pipe Selection ---
    with col2:
        config["pipe_type"] = st.selectbox("Select Pipe Type", ["Custom"] + list(COMMERCIAL_PIPES.keys()))
        if config["pipe_type"] != "Custom":
            config["layer_data"] = COMMERCIAL_PIPES[config["pipe_type"]]
            config["num_layers"] = len(config["layer_data"])
        else:
            config["num_layers"] = st.slider("Number of Layers", 1, 10, config.get("num_layers", 3))

    # --- Layer Configuration ---
    st.markdown("### 📦 Layer Configuration")
    layer_data = config["layer_data"][:config["num_layers"]]
    while len(layer_data) < config["num_layers"]:
        layer_data.append({
            "name": f"Layer {len(layer_data)+1}",
            "thickness": 0.2,
            "Z": 2.5,
            "material": "GRE (Glass-Reinforced Epoxy)",
            "v": 2000,
            "alpha0": 0.05,
            "n_exp": 1.2,
        })

    updated_layers = []
    for i in range(config["num_layers"]):
        st.markdown(f"#### Layer {i+1}")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            thickness = st.number_input("Thickness (in)", 0.01, 1.0, layer_data[i]["thickness"], key=f"t_{i}")
        with c2:
            Z = st.number_input("Z (MRayl)", 1.0, 10.0, layer_data[i]["Z"], key=f"z_{i}")
        with c3:
            material = st.selectbox(
                "Material", list(MATERIAL_DB.keys()),
                index=list(MATERIAL_DB.keys()).index(layer_data[i].get("material", "GRE (Glass-Reinforced Epoxy)")),
                key=f"mat_{i}"
            )
            props = MATERIAL_DB[material]
            if material == "Custom":
                v     = st.number_input("  → v (m/s)", 500, 10000, layer_data[i].get("v", 2000), key=f"v_{i}")
                alpha = st.number_input("  → α0 (dB/cm/MHz)", 0.01, 1.0, layer_data[i].get("alpha0", 0.05), key=f"a_{i}")
                n_exp = st.number_input("  → n exponent", 0.1, 3.0, layer_data[i].get("n_exp", 1.2), key=f"n_{i}")
            else:
                v, alpha, n_exp = props["v"], props["alpha0"], props["n"]

        updated_layers.append({
            "name":      f"Layer {i+1}",
            "thickness": thickness,
            "Z":         Z,
            "material":  material,
            "v":         v,
            "alpha0":    alpha,
            "n_exp":     n_exp
        })

    config["layer_data"] = updated_layers

    # --- Total Thickness ---
    config["total_thickness"] = sum(l["thickness"] for l in config["layer_data"])
    st.markdown(f"**📏 Total Pipe Thickness: {config['total_thickness']:.2f} inches**")

    # --- Defect Settings ---
    st.subheader("📌 Defect Settings")
    c1, c2 = st.columns(2)
    with c1:
        if config["num_layers"] == 1:
            config["defect_type"] = "Crack"
            st.markdown("Only **Crack** allowed for 1-layer pipe.")
        else:
            config["defect_type"] = st.selectbox(
                "Defect Type", ["None", "Delamination", "Crack"],
                index=["None", "Delamination", "Crack"].index(config["defect_type"])
            )
    with c2:
        config["defect_layer"] = st.slider(
            "Defect Layer Index", 1, config["num_layers"], config.get("defect_layer", 1)
        )

    # --- Chirp Settings ---
    st.subheader("🔊 Chirp Settings")
    c1, c2, c3 = st.columns(3)
    config["f_start_mhz"] = c1.number_input("Start Freq (MHz)", 0.1, 10.0, 0.5)
    config["f_end_mhz"]   = c2.number_input("End Freq (MHz)",   0.1, 10.0, 5.0)
    config["sweep_us"]    = c3.number_input("Sweep Duration (µs)", 10.0, 100.0, 50.0)
    config["sampling_rate"] = 100e6  # 100 MHz

    # --- Save to session ---
    st.session_state["config"] = config

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
