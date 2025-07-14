# simulator.py

import streamlit as st
import json
from config import DEFAULT_CONFIG, PIPE_DB

def show_simulator():
    # Ensure we have a session config
    if "config" not in st.session_state:
        st.session_state["config"] = json.loads(json.dumps(DEFAULT_CONFIG))
    
    config = st.session_state["config"]
    
    st.set_page_config(page_title="NMTD Simulator", layout="wide")
    st.sidebar.title("📁 Menu")
    page = st.sidebar.radio("Navigation", ["Simulator", "Plots", "Visualization", "About"])
    
    if page == "Simulator":
        st.title("🔍 NMTD Ultrasonic Response Simulator")
    
        # --- 1) Pipe Preset Selection ---
        preset = st.selectbox(
            "Choose Commercial Pipe or Custom",
            ["Custom"] + list(PIPE_DB.keys())
        )
    
        if preset != "Custom":
            # Load preset data into config
            entry = PIPE_DB[preset]
            layers = []
            for lyr in entry["layers"]:
                layers.append({
                    "name": lyr["name"],
                    "thickness": lyr["thickness"],
                    "Z": lyr["Z"],
                    "v": lyr["v"],
                    "alpha0": lyr["alpha0"],
                    "n_exp": lyr["n_exp"]
                })
            config["layer_data"]     = layers
            config["num_layers"]     = len(layers)
            config["total_thickness"]= entry["total_thickness"]
            st.markdown(f"**Preset Description:** {entry['description']}")
        # else: keep existing config["layer_data"] / num_layers
    
        # --- 2) Fluid Configuration ---
        col1, col2 = st.columns(2)
        with col1:
            config["fluid"] = st.selectbox(
                "Select Borehole Fluid",
                list(config.get("fluid_impedance_db", {}).keys()) if False else list(config.get("fluid_impedance_db", {}))  # assume fluid list in config or elsewhere
            )
            # For brevity, assume fluid velocity/Z already in config
    
        # --- 3) Layer Inputs ---
        st.markdown("### 📦 Layers Configuration")
        config["layer_data"] = config["layer_data"][: config["num_layers"]]
        while len(config["layer_data"]) < config["num_layers"]:
            # append default blank layers
            config["layer_data"].append({
                "name": f"Layer {len(config['layer_data'])+1}",
                "thickness": 0.2,
                "Z": 2.5,
                "v": 2000,
                "alpha0": 0.5,
                "n_exp": 1.2
            })
    
        for i in range(config["num_layers"]):
            lyr = config["layer_data"][i]
            c1, c2, c3 = st.columns([1,1,2])
            with c1:
                lyr["thickness"] = st.number_input(
                    f"{lyr['name']} Thickness (in)", 0.01, 2.0,
                    value=lyr["thickness"], key=f"th_{i}"
                )
            with c2:
                lyr["Z"] = st.number_input(
                    f"{lyr['name']} Impedance (MRayl)", 1.0, 5.0,
                    value=lyr["Z"], key=f"Z_{i}"
                )
            with c3:
                # allow renaming
                lyr["name"] = st.text_input(
                    f"Layer {i+1} Name", value=lyr["name"], key=f"name_{i}"
                )
    
        # Recompute total thickness
        config["num_layers"]      = len(config["layer_data"])
        config["total_thickness"] = sum(lyr["thickness"] for lyr in config["layer_data"])
        st.markdown(f"**📏 Total Pipe Thickness: {config['total_thickness']:.2f} inches**")
    
        # --- 4) Defect Settings ---
        st.subheader("📌 Defect Settings")
        config["defect_type"]  = st.selectbox(
            "Defect Type", ["None", "Delamination", "Crack"],
            index=["None","Delamination","Crack"].index(config["defect_type"])
        )
        config["defect_layer"] = st.slider(
            "Defect Layer Index",
            1, config["num_layers"], config["defect_layer"]
        )
    
        # --- 5) Save / Load / Reset ---
        st.markdown("### 💾 Save / Load / Reset")
        col1, col2, col3 = st.columns(3)
    
        with col1:
            st.download_button(
                "📤 Export Config (.json)",
                data=json.dumps(config, indent=2),
                file_name="nmted_config.json",
                mime="application/json"
            )
    
        with col2:
            uploaded = st.file_uploader("⬆️ Load Config (.json)", type="json")
            if uploaded:
                loaded = json.load(uploaded)
                if "layer_data" in loaded:
                    st.session_state["config"] = loaded
                    st.success("✅ Configuration loaded. Please review settings above.")
                    st.experimental_rerun()
    
        with col3:
            if st.button("🗑️ Reset to Default"):
                st.session_state["config"] = json.loads(json.dumps(DEFAULT_CONFIG))
                st.experimental_rerun()
