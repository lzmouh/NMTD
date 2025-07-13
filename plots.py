import streamlit as st
import plotly.graph_objects as go
import numpy as np
from utils import simulate_multimode, calculate_group_delay, bandpass_filter

def show_plots():
    st.title("Non-metalic Tubualrs Defectoscope NMTD")
    st.subheader("Ultrasonic Simulation App")

    if "config" not in st.session_state:
        st.warning("⚠️ Configuration not found. Please visit the **Simulator** page first.")
        st.stop()

    config = st.session_state["config"]
    fs = config["sampling_rate"]
    t_chirp = np.array(config["tx_chirp_t"])
    tx = np.array(config["tx_chirp_waveform"])

    # Chirp plots
    with st.expander("Transmitted Chirp"):
        fig_tx = go.Figure()
        fig_tx.add_trace(go.Scatter(x=t_chirp * 1e6, y=tx))
        fig_tx.update_layout(title="Tx Chirp (Time Domain)", xaxis_title="Time (µs)", height=300)
        st.plotly_chart(fig_tx, use_container_width=True)

    # Settings
    st.sidebar.header("Signal Processing Options")
    align = st.sidebar.checkbox("Align to Group Delay", True)
    apply_filter = st.sidebar.checkbox("Apply Bandpass Filter", False)
    fmin = st.sidebar.number_input("Min Freq (MHz)", 0.1, 20.0, 0.5) * 1e6
    fmax = st.sidebar.number_input("Max Freq (MHz)", 0.1, 20.0, 5.0) * 1e6

    # Run Simulation
    t_rx, rx_raw, compressed_raw, freqs, df = simulate_multimode(config)

    # Group delay alignment
    shift = int(calculate_group_delay(tx, fs) * fs) if align else 0
    rx = np.roll(rx_raw, -shift)
    compressed = np.roll(compressed_raw, -shift)

    if apply_filter:
        rx = bandpass_filter(rx, fs, fmin, fmax)
        compressed = bandpass_filter(compressed, fs, fmin, fmax)

    df_mode1 = df[df["Mode"] == 1]

    # 2×2 Plots
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Raw Signal")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=rx_raw))
        fig.update_layout(height=500, xaxis_title="Time (µs)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Aligned Raw Signal")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=rx))
        for _, row in df_mode1.iterrows():
            fig.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="red",
                          annotation_text=row["Layer"], annotation_position="top right")
        fig.update_layout(height=500, xaxis_title="Time (µs)")
        st.plotly_chart(fig, use_container_width=True)


    with col2:
        st.subheader("Compressed Signal")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=compressed_raw))
        fig.update_layout(height=500, xaxis_title="Time (µs)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Aligned Compressed Signal")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=compressed))
        for _, row in df_mode1.iterrows():
            fig.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="blue",
                          annotation_text=row["Layer"], annotation_position="top right")
        fig.update_layout(height=500, xaxis_title="Time (µs)")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Direct Mode Echos")
    st.dataframe(df_mode1)
