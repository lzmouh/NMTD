from utils import simulate_multimode, calculate_group_delay, bandpass_filter
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from utils import simulate_multimode


def show_plots():
    st.title("Non-Metallic Tubulars Defectoscope (NMTD)")
    st.subheader("Ultrasonic Signal Processing & Visualization")

    if "config_loaded" not in st.session_state:
        st.session_state["config_loaded"] = False
    if "config" not in st.session_state or not st.session_state["config_loaded"]:
        st.warning("⚠️ Configuration not found. Please visit the **Simulator** page first.")
        st.stop()

    config = st.session_state["config"]

    # Sidebar settings
    st.sidebar.header("Signal Processing")
    align = st.sidebar.checkbox("Align to Group Delay", True)
    apply_filter = st.sidebar.checkbox("Apply Bandpass Filter", False)
    fmin = st.sidebar.number_input("Min Freq (MHz)", 0.1, 20.0, 0.5) * 1e6
    fmax = st.sidebar.number_input("Max Freq (MHz)", 0.1, 20.0, 5.0) * 1e6

    # Extract chirp
    fs = config["sampling_rate"]
    t_chirp = np.array(config["t_chirp"])
    tx = np.array(config["tx"])
    
    # Chirp Plots
    with st.expander("Transmitted Chirp Signal", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            fig_tx = go.Figure()
            fig_tx.add_trace(go.Scatter(x=t_chirp * 1e6, y=tx, name="Tx Chirp"))
            fig_tx.update_layout(title="Tx Chirp (Time)", xaxis_title="Time (µs)",
                                 yaxis_title="Amplitude", height=300)
            st.plotly_chart(fig_tx, use_container_width=True)

        with col2:
            fft_tx = np.fft.fft(tx)
            freqs = np.fft.fftfreq(len(tx), d=1/fs)
            mask = freqs > 0
            fig_fft = go.Figure()
            fig_fft.add_trace(go.Scatter(x=freqs[mask] / 1e6, y=np.abs(fft_tx[mask]), name="Spectrum"))
            fig_fft.update_layout(title="Tx Spectrum", xaxis_title="Frequency (MHz)",
                                  yaxis_title="Magnitude", height=300)
            st.plotly_chart(fig_fft, use_container_width=True)

        with col3:
            auto = np.correlate(tx, tx, mode='full')
            t_auto = (np.arange(len(auto)) - len(tx) + 1) / fs * 1e6
            fig_cor = go.Figure()
            fig_cor.add_trace(go.Scatter(x=t_auto, y=auto, name="Auto-corr"))
            fig_cor.update_layout(title="Tx Auto Corr", xaxis_title="Time (µs)", yaxis_title="Magnitude", height=300)
            st.plotly_chart(fig_cor, use_container_width=True)
    
    # --- Run simulation ---
    t, rx, df, rx_aligned, rx_compressed, rx_compressed_aligned = simulate_multimode(config)
    time_us = t * 1e6  # Time in µs

    st.subheader("📈 Ultrasonic Signal Outputs")
    col1, col2 = st.columns(2)

    # --- Plot 1: Raw Received Signal ---
    with col1:
        fig_raw = go.Figure()
        fig_raw.add_trace(go.Scatter(x=time_us, y=rx, name="Raw Rx", line=dict(color="royalblue")))
        fig_raw.update_layout(title="Raw Received Signal", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig_raw, use_container_width=True)

    # --- Plot 2: Aligned Signal ---
    with col2:
        fig_aligned = go.Figure()
        fig_aligned.add_trace(go.Scatter(x=time_us, y=rx_aligned, name="Aligned Rx", line=dict(color="seagreen")))
        fig_aligned.update_layout(title="Aligned Signal", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig_aligned, use_container_width=True)

    # --- Plot 3: Pulse Compressed Signal ---
    with col1:
        fig_compressed = go.Figure()
        fig_compressed.add_trace(go.Scatter(x=time_us, y=rx_compressed, name="Compressed Rx", line=dict(color="firebrick")))
        fig_compressed.update_layout(title="Pulse Compressed Signal", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig_compressed, use_container_width=True)

    # --- Plot 4: Aligned Pulse Compressed Signal ---
    with col2:
        fig_compressed_aligned = go.Figure()
        fig_compressed_aligned.add_trace(go.Scatter(x=time_us, y=rx_compressed_aligned, name="Aligned Compressed Rx", line=dict(color="darkorange")))
        fig_compressed_aligned.update_layout(title="Aligned Compressed Signal", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig_compressed_aligned, use_container_width=True)

    # --- Frequency Spectrum Plot ---
    st.markdown("### 📊 Frequency Spectrum")
    freqs = np.fft.fftfreq(len(rx), d=1/config["sampling_rate"])
    RX_FFT = np.fft.fft(rx)
    fig_fft = go.Figure()
    fig_fft.add_trace(go.Scatter(x=freqs[freqs > 0] / 1e6, y=np.abs(RX_FFT[freqs > 0]), name="FFT"))
    fig_fft.update_layout(title="FFT of Raw Signal", xaxis_title="Frequency (MHz)", yaxis_title="Magnitude", height=300)
    st.plotly_chart(fig_fft, use_container_width=True)

    # --- Direct Arrivals Table ---
    st.markdown("### 🧭 Direct Echoes at Layer Interfaces")
    if not df.empty and "IsDirect" in df.columns:
        df_direct = df[df["IsDirect"] == True].copy()
        df_direct["Time (µs)"] = (df_direct["time"] * 1e6).round(2)
        df_direct["Amplitude"] = df_direct["amplitude"].round(3)
        df_show = df_direct[["mode", "layer", "echo_type", "Time (µs)", "Amplitude"]]
        df_show = df_show.rename(columns={"mode": "Mode", "layer": "Layer", "echo_type": "Type"})
        st.dataframe(df_show, use_container_width=True, hide_index=True)
    else:
        st.info("No direct echoes were identified in this simulation.")
