import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import json
from config import fluid_impedance_db, default_densities, INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_CONFIG
from scipy.signal import chirp
from scipy.signal.windows import tukey

def generate_tx_chirp(fs, sweep_s, f_start, f_end):
    n = int(fs * sweep_s)
    t = np.linspace(0, sweep_s, n, endpoint=False)
    # Linear FM chirp
    tx = chirp(t, f0=f_start, f1=f_end, t1=sweep_s, method='linear')
    # Apply Tukey window (alpha=0.1) to ramp in/out
    win = tukey(n, alpha=0.1)
    tx *= win
    return t, tx

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
    new_layers = []
    for i in range(config["num_layers"]):
        # two columns: thickness & impedance
        c1, c2, c3 = st.columns([1,1,2])
        with c1:
            thickness = st.number_input(
                f"Layer {i+1} Thickness (in)",
                min_value=0.01, max_value=1.0,
                value=config["layer_data"][i].get("thickness",0.2),
                key=f"thick_{i}"
            )
        with c2:
            impedance = st.number_input(
                f"Layer {i+1} Z (MRayl)",
                min_value=1.0, max_value=10.0,
                value=config["layer_data"][i].get("Z",2.5),
                key=f"Z_{i}"
            )
        with c3:
            mat = st.selectbox(
                f"Layer {i+1} Material",
                options=list(MATERIAL_DB.keys()),
                index=list(MATERIAL_DB.keys()).index(
                    config["layer_data"][i].get("material","GRE (Glass-Reinforced Epoxy)")
                ),
                key=f"mat_{i}"
            )
            props = MATERIAL_DB[mat]
            # if custom, let user fill in
            if mat == "Custom":
                v     = st.number_input(f"  → v (m/s)", 500, 5000, 2000, key=f"v_{i}")
                alpha = st.number_input(f"  → α0 (dB/cm/MHz)", 0.0, 1.0, 0.05, key=f"a_{i}")
                n_exp = st.number_input(f"  → n exponent", 0.1, 3.0, 1.2, key=f"n_{i}")
            else:
                v, alpha, n_exp = props["v"], props["alpha0"], props["n"]
                st.markdown(f"  • v = {v} m/s · α₀ = {alpha} dB/cm/MHz · n = {n_exp}")
        # pack into dict
        new_layers.append({
            "name":       f"Layer {i+1}",
            "thickness":  thickness,
            "Z":          impedance,
            "material":   mat,
            "v":          v,
            "alpha0":     alpha,
            "n_exp":      n_exp
        })
    
    config["layer_data"] = new_layers
    st.session_state["config"] = config

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

    # --- Chirp settings ---
    st.subheader("📡 Transmitter Chirp Settings")
    col1, col2, col3 = st.columns(3)
    with col1:
        # in MHz
        f_start_mhz = st.number_input("Start Frequency (MHz)", min_value=0.1, max_value=10.0,
                                      value=0.5, step=0.1, key="f_start_mhz")
    with col2:
        f_end_mhz   = st.number_input("End Frequency (MHz)",   min_value=0.1, max_value=10.0,
                                      value=5.0, step=0.1, key="f_end_mhz")
    with col3:
        sweep_us    = st.number_input("Sweep Duration (µs)",    min_value=1.0, max_value=200.0,
                                      value=50.0, step=1.0, key="sweep_us")

    # Convert units
    fs = 100e6  # 100 MHz sampling
    f0 = f_start_mhz * 1e6
    f1 = f_end_mhz   * 1e6
    sweep_s = sweep_us * 1e-6

    # Generate windowed chirp
    t_chirp, tx_chirp = generate_tx_chirp(fs, sweep_s, f0, f1)

    # Time‐domain plot
    st.subheader("🟡 Transmitted Chirp Waveform")
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.plot(t_chirp * 1e6, tx_chirp)
    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Amplitude")
    ax.set_title(f"{f_start_mhz:.1f}→{f_end_mhz:.1f} MHz over {sweep_us:.0f} µs")
    ax.grid(True)
    st.pyplot(fig)

    # Frequency‐domain plot
    st.subheader("🔊 Chirp Frequency Spectrum")
    TX_FFT = np.fft.fft(tx_chirp)
    freqs = np.fft.fftfreq(len(tx_chirp), d=1/fs)
    fig2, ax2 = plt.subplots(figsize=(6, 2))
    mask = freqs >= 0
    ax2.plot(freqs[mask] / 1e6, np.abs(TX_FFT[mask]))
    ax2.set_xlabel("Frequency (MHz)")
    ax2.set_ylabel("Magnitude")
    ax2.set_title("Spectrum of Windowed Chirp")
    ax2.grid(True)
    st.pyplot(fig2)

    # Save to config for downstream use
    config.update({
        "chirp_start_mhz":  f_start_mhz,
        "chirp_end_mhz":    f_end_mhz,
        "chirp_sweep_us":   sweep_us,
        "sampling_rate":    fs,
        "tx_chirp_t":       t_chirp.tolist(),
        "tx_chirp_waveform":tx_chirp.tolist()
    })
    st.session_state["config"] = config
    
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
            st.session_state["config"] = DEFAULT_CONFIG.copy()
            st.rerun()

