import streamlit as st
import json
from config import fluid_impedance_db, default_densities, DEFAULT_CONFIG

def show_simulator():
    st.title("🔍 NMTD Ultrasonic Response Simulator")

    # --- Initialize default config if missing ---
    if "config" not in st.session_state or not st.session_state.get("config"):
        st.session_state["config"] = DEFAULT_CONFIG.copy()

    config = st.session_state["config"]

    col1, col2 = st.columns(2)

    # --- FLUID SETTINGS ---
    with col1:
        config["fluid"] = st.selectbox(
            "Select Borehole Fluid", list(fluid_impedance_db.keys()),
            index=list(fluid_impedance_db.keys()).index(config["fluid"])
        )
        if config["fluid"] == "Other":
            config["fluid_density"] = st.number_input("Fluid Density (g/cc)", 0.5, 2.5, 1.0)
        else:
            config["fluid_density"] = default_densities[config["fluid"]]

        config["Z_fluid"] = fluid_impedance_db[config["fluid"]] if config["fluid"] != "Other" else config["Z_fluid"]

        # Compute fluid velocity
        Z = config["Z_fluid"] * 1e6  # Rayl
        rho = config["fluid_density"] * 1000  # kg/m³
        c_fluid = Z / rho  # m/s
        config["fluid_velocity"] = c_fluid

        st.write(f"**Z_fluid = {config['Z_fluid']:.2f} MRayl**")
        st.write(f"**Fluid velocity = {c_fluid:.0f} m/s**")

    # --- LAYER SETTINGS ---
    with col2:
        config["num_layers"] = st.slider("Number of Layers", 1, 10, config["num_layers"])
        config["layer_data"] = config["layer_data"][:config["num_layers"]]
        while len(config["layer_data"]) < config["num_layers"]:
            config["layer_data"].append([f"Layer {len(config['layer_data'])+1}", 0.2, 2.5])

    st.markdown("### 📦 Layers Configuration")

    for i in range(config["num_layers"]):
        c1, c2 = st.columns(2)
        with c1:
            config["layer_data"][i][1] = st.number_input(
                f"Layer {i+1} Thickness (in)", min_value=0.01, max_value=1.0,
                value=config["layer_data"][i][1], key=f"t_{i}"
            )
        with c2:
            config["layer_data"][i][2] = st.number_input(
                f"Layer {i+1} Z (MRayl)", min_value=1.0, max_value=10.0,
                value=config["layer_data"][i][2], key=f"z_{i}"
            )

    # Calculate and display total thickness
    config["total_thickness"] = sum([layer[1] for layer in config["layer_data"]])
    st.markdown(f"**📏 Total Pipe Thickness: `{config['total_thickness']:.2f}` inches**")

    # --- DEFECT SETTINGS ---
    st.subheader("📌 Defect Settings")
    c1, c2 = st.columns(2)
    with c1:
        config["defect_type"] = st.selectbox(
            "Defect Type", ["None", "Delamination", "Crack"],
            index=["None", "Delamination", "Crack"].index(config["defect_type"])
        )
    with c2:
        config["defect_layer"] = st.slider(
            "Defect Layer Index", 1, config["num_layers"], config["defect_layer"]
        )

    # --- CONFIG SAVE/LOAD ---
    st.markdown("### 💾 Save / Load / Export")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "📤 Export Config (.json)",
            data=json.dumps(config, indent=2),
            file_name="nmted_config.json",
            mime="application/json"
        )

    with c2:
        uploaded = st.file_uploader("⬆️ Load Config (.json)", type="json")
        if uploaded:
            loaded = json.load(uploaded)
            if "layer_data" in loaded:
                st.session_state["config"] = loaded
                st.success("Configuration loaded.")
                st.rerun()

    with c3:
        if st.button("🗑️ Reset to Default"):
            st.session_state["config"] = json.loads(json.dumps(DEFAULT_CONFIG))
            st.rerun()
