import streamlit as st
import json
from config import (
    fluid_impedance_db, default_densities, INCH_TO_METER,
    DEFAULT_GAP_INCH, MATERIAL_DB, DEFAULT_CONFIG
)
from utils import generate_tx_chirp

def show_simulator():
    st.title("🔍 NMTD Ultrasonic Response Simulator")

    # 1) Initialize session config
    if "config" not in st.session_state:
        st.session_state["config"] = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy

    config = st.session_state["config"]

    # 2) Fluid selection
    col1, col2 = st.columns(2)
    with col1:
        config["fluid"] = st.selectbox("Select Borehole Fluid", list(fluid_impedance_db.keys()),
                                       index=list(fluid_impedance_db.keys()).index(config.get("fluid", "Water")))
        if config["fluid"] == "Other":
            config["fluid_density"] = st.number_input("Fluid Density (g/cc)", 0.5, 2.5, 1.0)
        else:
            config["fluid_density"] = default_densities[config["fluid"]]

        config["Z_fluid"] = fluid_impedance_db[config["fluid"]] if config["fluid"] != "Other" else config.get("Z_fluid", 1.48)

        # Velocity = Z / rho
        Z = config["Z_fluid"] * 1e6
        rho = config["fluid_density"] * 1000
        c_fluid = Z / rho
        config["fluid_velocity"] = c_fluid

        st.write(f"**Z_fluid = {config['Z_fluid']:.2f} MRayl**")
        st.write(f"**Fluid velocity = {c_fluid:.0f} m/s**")

    # 3) Layer structure
    with col2:
        config["num_layers"] = st.slider("Number of Layers", 1, 10, config.get("num_layers", 3))

    # Normalize layer format
    for i in range(len(config["layer_data"])):
        if isinstance(config["layer_data"][i], list):
            name, t, z = config["layer_data"][i]
            config["layer_data"][i] = {
                "name": name,
                "thickness": t,
                "Z": z,
                "material": "Custom",
                "v": 2000,
                "alpha0": 0.1,
                "n_exp": 1.2
            }

    # Resize list
    config["layer_data"] = config["layer_data"][:config["num_layers"]]
    while len(config["layer_data"]) < config["num_layers"]:
        config["layer_data"].append({
            "name": f"Layer {len(config['layer_data'])+1}",
            "thickness": 0.2,
            "Z": 2.5,
            "material": "GRE (Glass-Reinforced Epoxy)",
            "v": 2000,
            "alpha0": 0.1,
            "n_exp": 1.2
        })

    st.markdown("### 📦 Layers Configuration")
    new_layers = []
    for i, layer in enumerate(config["layer_data"]):
        c1, c2, c3 = st.columns([1,1,2])
        with c1:
            t = st.number_input(f"Layer {i+1} Thickness (in)", 0.01, 1.0, value=layer.get("thickness", 0.2), key=f"t_{i}")
        with c2:
            z = st.number_input(f"Layer {i+1} Z (MRayl)", 1.0, 10.0, value=layer.get("Z", 2.5), key=f"z_{i}")
        with c3:
            mat = st.selectbox(
                f"Layer {i+1} Material", list(MATERIAL_DB.keys()),
                index=list(MATERIAL_DB.keys()).index(layer.get("material", "GRE (Glass-Reinforced Epoxy)")),
                key=f"mat_{i}"
            )
            props = MATERIAL_DB[mat]
            if mat == "Custom":
                v     = st.number_input(f"  → v (m/s)", 500, 5000, layer.get("v", 2000), key=f"v_{i}")
                alpha = st.number_input(f"  → α0 (dB/cm/MHz)", 0.0, 1.0, layer.get("alpha0", 0.05), key=f"a_{i}")
                n_exp = st.number_input(f"  → n exponent", 0.1, 3.0, layer.get("n_exp", 1.2), key=f"n_{i}")
            else:
                v, alpha, n_exp = props["v"], props["alpha0"], props["n"]
                st.markdown(f"  • v = {v} m/s · α₀ = {alpha} dB/cm/MHz · n = {n_exp}")

        new_layers.append({
            "name": f"Layer {i+1}",
            "thickness": t,
            "Z": z,
            "material": mat,
            "v": v,
            "alpha0": alpha,
            "n_exp": n_exp
        })

    config["layer_data"] = new_layers
    config["total_thickness"] = sum(l["thickness"] for l in new_layers)
    st.markdown(f"**📏 Total Thickness: {config['total_thickness']:.2f} inches**")

    # 4) Defect Settings (disable if 1 layer)
    st.subheader("📌 Defect Settings")
    c1, c2 = st.columns(2)
    with c1:
        config["defect_type"] = st.selectbox("Defect Type", ["None", "Delamination", "Crack"],
                                             index=["None", "Delamination", "Crack"].index(config.get("defect_type", "None")))
    with c2:
        if config["num_layers"] == 1:
            st.markdown("🧯 Only one layer — no defect layer to select.")
            config["defect_layer"] = 1
        else:
            config["defect_layer"] = st.slider("Defect Layer Index", 1, config["num_layers"], config.get("defect_layer", 1))

    # 5) Chirp Settings
    st.subheader("📡 Chirp Excitation Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        f_start = st.number_input("Start Frequency (MHz)", 0.1, 10.0, config.get("f_start_mhz", 0.5), step=0.1)
    with col2:
        f_end = st.number_input("End Frequency (MHz)", f_start + 0.1, 20.0, config.get("f_end_mhz", 5.0), step=0.1)
    with col3:
        sweep_us = st.number_input("Sweep Duration (µs)", 1.0, 200.0, config.get("sweep_us", 50.0))

    # Compute chirp signal
    fs = 100e6  # sampling rate
    t_chirp, tx_chirp = generate_tx_chirp(fs, sweep_us * 1e-6, f_start * 1e6, f_end * 1e6)

    config.update({
        "chirp_start_mhz": f_start,
        "chirp_end_mhz": f_end,
        "sweep_us": sweep_us,
        "sampling_rate": fs,
        "tx_chirp_t": t_chirp.tolist(),
        "tx_chirp_waveform": tx_chirp.tolist()
    })

    # 6) Export / Import / Reset
    st.markdown("### 💾 Save / Load / Reset")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "📤 Export Config",
            data=json.dumps(config, indent=2),
            file_name="nmted_config.json",
            mime="application/json"
        )
    with col2:
        uploaded = st.file_uploader("⬆️ Load Config", type="json")
        if uploaded:
            try:
                loaded = json.load(uploaded)
                if "layer_data" in loaded:
                    # sanitize if layer_data is list of lists
                    for i in range(len(loaded["layer_data"])):
                        if isinstance(loaded["layer_data"][i], list):
                            name, t, z = loaded["layer_data"][i]
                            loaded["layer_data"][i] = {
                                "name": name,
                                "thickness": t,
                                "Z": z,
                                "material": "Custom",
                                "v": 2000,
                                "alpha0": 0.1,
                                "n_exp": 1.2
                            }
                    st.session_state["config"] = loaded
                    st.success("✅ Configuration loaded")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to load config: {e}")
    with col3:
        if st.button("🗑️ Reset to Default"):
            st.session_state["config"] = json.loads(json.dumps(DEFAULT_CONFIG))
            st.rerun()
