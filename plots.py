import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from utils import (
    simulate_multilayer_propagation,
    calculate_group_delay,
    bandpass_filter,
    matched_filter_compress
)

# Ensure session config exists
if "config" not in st.session_state:
    st.session_state["config"] = {}
if "config_loaded" not in st.session_state:
    st.session_state["config_loaded"] = False

def show_plots():
    st.title("Non-Metallic Tubulars Defectoscope (NMTD)")
    st.subheader("Ultrasonic Signal Processing & Visualization")
    
    # Check for config
    if "config" not in st.session_state or not st.session_state["config_loaded"]:
        st.warning("⚠️ Configuration not found. Please visit the **Simulator** page first.")
        st.stop()

    config = st.session_state["config"]

    # Sidebar: signal processing options
    st.sidebar.header("Signal Processing")
    align = st.sidebar.checkbox("Align to Group Delay", False)
    apply_filter = st.sidebar.checkbox("Apply Bandpass Filter", False)
    fmin = st.sidebar.number_input("Min Frequency (MHz)", 0.1, 20.0, 0.5) * 1e6
    fmax = st.sidebar.number_input("Max Frequency (MHz)", 0.1, 20.0, 5.0) * 1e6

    # Extract config
    fs = config["sampling_rate"]
    t_chirp = np.array(config["t_chirp"])
    tx = np.array(config["tx"])

    # Chirp diagnostics
    with st.expander("Transmitted Chirp Diagnostics", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            fig_tx = go.Figure()
            fig_tx.add_trace(go.Scatter(x=t_chirp * 1e6, y=tx))
            fig_tx.update_layout(title="Tx Chirp (Time)", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
            st.plotly_chart(fig_tx, use_container_width=True)

        with col2:
            fft_tx = np.fft.fft(tx)
            freqs = np.fft.fftfreq(len(tx), d=1/fs)
            fig_fft = go.Figure()
            fig_fft.add_trace(go.Scatter(x=freqs[freqs > 0] / 1e6, y=np.abs(fft_tx[freqs > 0])))
            fig_fft.update_layout(title="Tx Spectrum", xaxis_title="Freq (MHz)", yaxis_title="Magnitude", height=300)
            st.plotly_chart(fig_fft, use_container_width=True)

        with col3:
            auto = np.correlate(tx, tx, mode='full')
            t_auto = (np.arange(len(auto)) - len(tx) + 1) / fs * 1e6
            fig_cor = go.Figure()
            fig_cor.add_trace(go.Scatter(x=t_auto, y=auto))
            fig_cor.update_layout(title="Autocorrelation", xaxis_title="Time (µs)", yaxis_title="Magnitude", height=300)
            st.plotly_chart(fig_cor, use_container_width=True)

    # Prepare layer properties
    layers = []
    for layer in config["layer_data"]:
        layers.append({
            "thickness": layer["thickness"] * 0.0254,
            "c": layer["v"],
            "rho": layer["Z"] / layer["v"],
            "alpha0": layer["alpha0"],
            "n": layer["n_exp"],
            "beta": layer.get("beta", 0.0),
        })

    fluid_props = {
        "c": config["fluid_velocity"],
        "rho": config["fluid_density"] * 1000,
        "Z": config["Z_fluid"], 
    }

    # Claculate group delay
    gd = calculate_group_delay(tx, fs)
    st.metric(label="Estimated Group Delay", value=f"{gd*1e6:.2f} µs")

    # Run simulation
    rx, t, metadata = simulate_multilayer_propagation(
        chirp_signal=tx,
        chirp_t=t_chirp,
        fluid_props=fluid_props,
        layers=layers,
        gap_thickness=2.54e-3,
        fs=fs
    )

    # Bandpass filter
    if apply_filter:
        rx = bandpass_filter(rx, fs, fmin, fmax)

    # Group delay alignment
    rx_aligned = rx
    gd = 0.0
    if align:
        shift_samples = int(np.round(gd * fs))
        rx_aligned = np.roll(rx, -shift_samples)

    # Pulse compression
    rx_compressed = matched_filter_compress(rx, tx)
    rx_compressed_aligned = rx_compressed
    if align:
        rx_compressed_aligned = np.roll(rx_compressed, -shift_samples)

    # Time axis
    t = np.arange(len(rx)) / fs  # in seconds

    st.subheader("📈 Ultrasonic Signal Outputs")
    col1, col2 = st.columns(2)

    # ---------- RAW SIGNAL ----------
    with col1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=t * 1e6, y=rx, name="Raw"))

        # Annotations from metadata (raw time)
        for echo in metadata:
            if "Entry" in echo["interface"] or echo["interface"] == "Back Wall":
                t_us = echo["time"] * 1e6
                fig1.add_shape(type="line", x0=t_us, x1=t_us, y0=0, y1=1,
                               line=dict(color="blue", dash="dash"), xref="x", yref="paper")
                fig1.add_annotation(x=t_us, y=1.02, text=echo["interface"],
                                    showarrow=False, xref="x", yref="paper", font=dict(size=10, color="blue"))

        fig1.update_layout(title="Raw Received Signal",
                           xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig1, use_container_width=True)

    # ---------- ALIGNED SIGNAL ----------
    with col2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=t * 1e6, y=rx_aligned, name="Aligned"))

        for echo in metadata:
            if "Entry" in echo["interface"] or echo["interface"] == "Back Wall":
                t_us = echo["time_aligned"] * 1e6
                fig2.add_shape(type="line", x0=t_us, x1=t_us, y0=0, y1=1,
                               line=dict(color="green", dash="dash"), xref="x", yref="paper")
                fig2.add_annotation(x=t_us, y=1.02, text=echo["interface"],
                                    showarrow=False, xref="x", yref="paper", font=dict(size=10, color="green"))

        fig2.update_layout(title="Aligned Signal",
                           xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig2, use_container_width=True)

    # ---------- COMPRESSED SIGNAL ----------
    with col1:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=t * 1e6, y=rx_compressed, name="Compressed"))

        for echo in metadata:
            if "Entry" in echo["interface"] or echo["interface"] == "Back Wall":
                t_us = echo["time"] * 1e6
                fig3.add_shape(type="line", x0=t_us, x1=t_us, y0=0, y1=1,
                               line=dict(color="purple", dash="dash"), xref="x", yref="paper")
                fig3.add_annotation(x=t_us, y=1.02, text=echo["interface"],
                                    showarrow=False, xref="x", yref="paper", font=dict(size=10, color="purple"))

        fig3.update_layout(title="Pulse Compressed Signal",
                           xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig3, use_container_width=True)

    # ---------- ALIGNED + COMPRESSED ----------
    with col2:
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=t * 1e6, y=rx_compressed_aligned, name="Aligned Compressed"))

        for echo in metadata:
            if "Entry" in echo["interface"] or echo["interface"] == "Back Wall":
                t_us = echo["time_aligned"] * 1e6
                fig4.add_shape(type="line", x0=t_us, x1=t_us, y0=0, y1=1,
                               line=dict(color="red", dash="dash"), xref="x", yref="paper")
                fig4.add_annotation(x=t_us, y=1.02, text=echo["interface"],
                                    showarrow=False, xref="x", yref="paper", font=dict(size=10, color="red"))

        fig4.update_layout(title="Aligned Pulse Compressed",
                           xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig4, use_container_width=True)

    # FFT
    st.markdown("### 📊 Frequency Spectrum")
    RX_FFT = np.fft.fft(rx)
    freqs = np.fft.fftfreq(len(rx), d=1/fs)
    fig_fft_rx = go.Figure()
    fig_fft_rx.add_trace(go.Scatter(x=freqs[freqs > 0] / 1e6, y=np.abs(RX_FFT[freqs > 0])))
    fig_fft_rx.update_layout(title="FFT of Raw Signal", xaxis_title="Freq (MHz)", yaxis_title="Magnitude", height=300)
    st.plotly_chart(fig_fft_rx, use_container_width=True)

    # Metadata Table
    st.markdown("### 🧾 Echo Metadata")
    if metadata:
        df = pd.DataFrame(metadata)
        # Format time columns for clarity
        df["Raw Time (µs)"] = (df["time"] * 1e6).round(2)
        df["Aligned Time (µs)"] = (df["time_aligned"] * 1e6).round(2)
        df["Amplitude"] = df["amplitude"].round(3)
        # Display useful columns only
        st.dataframe(df[[
            "interface",
            "Raw Time (µs)",
            "Aligned Time (µs)",
            "amplitude",
            "Z1 (MRayl)",
            "Z2 (MRayl)",
            "thickness (mm)",
            "R",
            "T"
        ]])
    else:
        st.info("No echoes found in this simulation.")
    
    # Save to session state
    st.session_state["config"] = config
    st.session_state["config_loaded"] = True
