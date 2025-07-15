import streamlit as st
import plotly.graph_objects as go
import numpy as np
from utils import simulate_multimode, calculate_group_delay, bandpass_filter, generate_tx_chirp 

def show_plots():
    st.title("Non-metalic Tubualrs Defectoscope NMTD")
    st.subheader("Ultrasonic Simulation App")

    if "config" not in st.session_state:
        st.warning("⚠️ Configuration not found. Please visit the **Simulator** page first.")
        st.stop()

    config = st.session_state["config"]

    # Settings
    st.sidebar.header("Signal Processing Options")
    align = st.sidebar.checkbox("Align to Group Delay", True)
    apply_filter = st.sidebar.checkbox("Apply Bandpass Filter", False)
    fmin = st.sidebar.number_input("Min Freq (MHz)", 0.1, 20.0, 0.5) * 1e6
    fmax = st.sidebar.number_input("Max Freq (MHz)", 0.1, 20.0, 5.0) * 1e6

    # Generate chirp
    fs = config["sampling_rate"]
    sweep_s = config.get("sweep_us", 50e-6)  # 50 µs default
    f_start = config.get("f_start_mhz", 0.5) * 1e6
    f_end   = config.get("f_end_mhz", 5.0) * 1e6
    
    t_chirp, tx = generate_tx_chirp(fs, sweep_s, f_start, f_end)
    config["t_chirp"] = t_chirp.tolist()
    config["tx"] = tx_chirp.tolist()

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
    
        # --- Frequency-Domain Plot ---
        with col2:
            fs = config["sampling_rate"]
            TX_FFT = np.fft.fft(tx)
            freqs = np.fft.fftfreq(len(tx), d=1/fs)
            mask = freqs > 0  # Keep only positive frequencies
    
            fig_fft = go.Figure()
            fig_fft.add_trace(go.Scatter(x=freqs[mask] / 1e6, y=np.abs(TX_FFT[mask]), name="Spectrum"))
            fig_fft.update_layout(
                title="Frequency Spectrum",
                xaxis_title="Frequency (MHz)",
                yaxis_title="Magnitude",
                height=300
            )
            st.plotly_chart(fig_fft, use_container_width=True)
        

