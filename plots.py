import streamlit as st
import plotly.graph_objects as go
import numpy as np
from utils import simulate_multimode, calculate_group_delay, bandpass_filter

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

    # --- Simulation ---
    t_rx, rx_raw, compressed_raw, freqs, df = simulate_multimode(config)

    # Calculate group delay
    gd = calculate_group_delay(tx, fs)
    st.info(f"🔧 Computed group delay: **{gd*1e6:.2f} µs**")

    shift = int(round(gd * fs)) if align else 0
    rx_aligned = np.roll(rx_raw, -shift)
    compressed_aligned = np.roll(compressed_raw, -shift)

    if apply_filter:
        rx_aligned = bandpass_filter(rx_aligned, fs, fmin, fmax)
        compressed_aligned = bandpass_filter(compressed_aligned, fs, fmin, fmax)

    df_direct = df[df["IsDirect"] == True]

    # --- Plot Signals ---
    st.subheader("📊 Signal Plots")
    col1, col2 = st.columns(2)

    # Raw
    with col1:
        st.markdown("**Raw Signal**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=rx_raw, name="Raw Rx"))
        fig.update_layout(xaxis_title="Time (µs)", height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Aligned Raw
    with col2:
        st.markdown("**Aligned Raw Signal**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=rx_aligned, name="Aligned Rx"))
        fig.update_layout(xaxis_title="Time (µs)", height=350)
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)

    # Raw Compressed
    with col3:
        st.markdown("**Raw Compressed Signal**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=compressed_raw, name="Raw Compressed"))
        fig.update_layout(xaxis_title="Time (µs)", height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Aligned Compressed with annotations
    with col4:
        st.markdown("**Aligned Compressed Signal with Direct Echoes**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_rx * 1e6, y=compressed_aligned, name="Aligned Compressed"))
        for _, row in df_direct.iterrows():
            fig.add_vline(
                x=row["Time (µs)"],
                line_dash="dot",
                line_color="blue",
                annotation_text=row["Interface"],
                annotation_position="top right"
            )
        fig.update_layout(xaxis_title="Time (µs)", height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Spectrum
    st.subheader("📈 Received Signal Spectrum")
    fft_rx = np.fft.fft(rx_raw)
    freqs_rx = np.fft.fftfreq(len(rx_raw), d=1/fs)
    mask_rx = freqs_rx > 0
    fig_spec = go.Figure()
    fig_spec.add_trace(go.Scatter(x=freqs_rx[mask_rx]/1e6, y=np.abs(fft_rx[mask_rx]), name="Rx Spectrum"))
    fig_spec.update_layout(xaxis_title="Frequency (MHz)", yaxis_title="Magnitude", height=350)
    st.plotly_chart(fig_spec, use_container_width=True)

    # Direct Echo Table (Thickness)
    st.subheader("📏 Layer Thickness Estimation from Direct Arrivals")
    if not df_direct.empty:
        st.dataframe(df_direct[[
            "Interface", "Time (µs)", "TOF (µs)", "Calc Thickness (in)", "Thickness (in)",
            "Z (MRayl)", "α₀", "n_exp"
        ]].style.format({
            "Time (µs)": "{:.2f}",
            "TOF (µs)": "{:.2f}",
            "Calc Thickness (in)": "{:.3f}",
            "Thickness (in)": "{:.3f}",
            "Z (MRayl)": "{:.2f}",
            "α₀": "{:.2f}",
            "n_exp": "{:.2f}",
        }), height=350)

        total_est_thk = df_direct["Calc Thickness (in)"].sum()
        total_actual_thk = df_direct["Thickness (in)"].sum()
        st.success(f"🔢 **Estimated Total Thickness:** {total_est_thk:.3f} in (Actual: {total_actual_thk:.3f} in)")
    else:
        st.warning("⚠️ No direct arrivals detected.")

    # All Echoes
    with st.expander("All Echoes (All Modes)", expanded=False):
        df_display = df.copy()
        df_display.index += 1
        st.dataframe(df_display.style.format({
            "Time (µs)": "{:.2f}",
            "TOF (µs)": "{:.2f}",
            "Thickness (in)": "{:.3f}",
            "Calc Thickness (in)": "{:.3f}",
            "Z (MRayl)": "{:.2f}",
            "α₀": "{:.2f}",
            "n_exp": "{:.2f}",
            "R": "{:.2f}",
            "T": "{:.2f}"
        }), height=400)

    # Debug Info
    with st.expander("🔍 Debug Info"):
        st.write("TX max amplitude:", np.max(np.abs(tx)))
        st.write("RX raw max amplitude:", np.max(np.abs(rx_raw)))
        st.write("Compressed max:", np.max(np.abs(compressed_raw)))
        st.write("fs:", fs, "Hz")
        st.write("Group delay shift (samples):", shift)
