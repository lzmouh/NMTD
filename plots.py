import streamlit as st
import numpy as np
import pandas as pd
from scipy.signal import chirp, fftconvolve, butter, sosfilt
from scipy.signal.windows import tukey
from scipy.fft import fft, fftfreq
import plotly.graph_objects as go
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def generate_tx_chirp(fs, sweep_s, f_start, f_end):
    n = int(fs * sweep_s)
    t = np.linspace(0, sweep_s, n, endpoint=False)
    tx = chirp(t, f0=f_start, f1=f_end, t1=sweep_s, method='linear')
    tx *= tukey(n, alpha=0.1)
    return t, tx

def calculate_group_delay(tx, fs):
    spectrum = fft(tx)
    freqs = fftfreq(len(tx), d=1/fs)
    phase = np.unwrap(np.angle(spectrum))
    dphi_df = np.gradient(phase, freqs)
    group_delay = np.mean(dphi_df[(freqs > 1e6) & (freqs < 5e6)])
    return group_delay  # in seconds

def bandpass_filter(signal, fs, fmin, fmax):
    sos = butter(4, [fmin, fmax], btype='bandpass', fs=fs, output='sos')
    return sosfilt(sos, signal)

def simulate_multimode(config):
    fs = config["sampling_rate"]
    t_chirp = np.array(config["tx_chirp_t"])
    tx = np.array(config["tx_chirp_waveform"])
    fluid_vel = config["fluid_velocity"]
    defect = config["defect_type"]
    defect_i = config["defect_layer"] - 1
    layers = config["layer_data"]

    f0_mhz = (config["chirp_start_mhz"] + config["chirp_end_mhz"]) / 2

    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for lyr in layers:
        depths.append(depths[-1] + lyr["thickness"] * INCH_TO_METER)

    R_list, T_list = [], []
    Z_prev = config["Z_fluid"]
    for lyr in layers:
        Z_curr = lyr["Z"]
        R = (Z_curr - Z_prev) / (Z_curr + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_curr

    modes = [(fluid_vel, 0.0, 0.0)] + [(lyr["v"], lyr["alpha0"], lyr["n_exp"]) for lyr in layers]

    max_delay = 2 * depths[-1] / min([v for v,_,_ in modes])
    n_rx = int(fs * (max_delay + len(t_chirp)/fs + 10e-6))
    rx = np.zeros(n_rx)
    t_rx = np.arange(n_rx) / fs

    records = []
    freqs = fftfreq(len(tx), d=1/fs)
    P = fft(tx)

    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        beta = 0.05  # dispersion coefficient

        for i, depth in enumerate(depths):
            tau_s = 2 * depth / v
            alpha_f = alpha0 * (np.abs(freqs)/1e6)**n_exp * 100
            H = 10 ** (-alpha_f * depth / 20)
            c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D = np.exp(-1j * 2 * np.pi * freqs * (2 * depth / c_f))
            P_i = P * H * D
            p_i = np.real(np.fft.ifft(P_i))

            if i == 0:
                R = -1.0
                T = 1.0
            else:
                R = R_list[i-1]
                T = T_list[i-1]

            if defect == "Delamination" and (i-1) == defect_i:
                R *= 0.7; T *= 0.7
            if defect == "Crack" and (i-1) == defect_i:
                R *= 0.5; T *= 0.5

            amp = abs(R)
            idx = int(round(tau_s * fs))
            rx[idx:idx+len(p_i)] += amp * p_i

            if i == 0:
                tt_fluid = 2 * gap_m / fluid_vel * 1e6
                records.append({
                    "Mode": m_idx + 1, "Layer": "Fluid Gap", "Thickness (in)": round(DEFAULT_GAP_INCH,3),
                    "Z (MRayl)": round(config["Z_fluid"],3), "α0": 0, "n exp": 0,
                    "R": -1.0, "T": 1.0, "Time (µs)": round(tt_fluid,2), "Amp": round(amp,3)
                })
            elif i > 0:
                records.append({
                    "Mode": m_idx + 1,
                    "Layer": layers[i-1]["name"],
                    "Thickness (in)": round(layers[i-1]["thickness"], 3),
                    "Z (MRayl)": round(layers[i-1]["Z"], 3),
                    "α0": round(alpha0, 3), "n exp": round(n_exp, 3),
                    "R": round(R, 3), "T": round(T, 3),
                    "Time (µs)": round(tau_s * 1e6, 2),
                    "Amp": round(amp, 3)
                })

    compressed = fftconvolve(rx, tx[::-1], mode='same')
    df = pd.DataFrame.from_records(records)
    return t_rx, rx, compressed, freqs, df

def show_plots():
    st.title("Non-Metalic Tubulars Defectoscope NMTD")
    st.subheader("Ultrasonic Simulation")

    if "config" not in st.session_state:
        st.warning("⚠️ Configuration not found. Please visit the **Simulator** page first to define the layer structure and settings.")
        st.stop()
    
    config = st.session_state["config"]
    fs = config["sampling_rate"]

    t_chirp = np.array(config["tx_chirp_t"])
    tx_chirp = np.array(config["tx_chirp_waveform"])
 
    # 1) Display chirp signal
    col1, col2 = st.columns(2)
    with col1:
        # Time‐domain plot
        st.subheader("Transmitted Chirp Waveform")
        figtx = go.Figure()
        figtx.add_trace(go.Scatter(x=t_chirp*1e6, y=tx_chirp, name="Tx chirp", line=dict(color='black')))
        figtx.update_layout(title="Transmitter Chirp Signal", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=500)
        
    with col2:
        # Frequency‐domain plot
        st.subheader("Chirp Frequency Spectrum")
        TX_FFT = np.fft.fft(tx_chirp)
        freqs = np.fft.fftfreq(len(tx_chirp), d=1/fs)
        mask = freqs >= 0
        figtxf = go.Figure()
        figtxf.add_trace(go.Scatter(x=freqs[mask] / 1e6, y=np.abs(TX_FFT[mask]), name="Tx chirp", line=dict(color='black')))
        figtxf.update_layout(title="Tx Chirp Frequency Spectrum", xaxis_title="Frequency (MHz)", yaxis_title="Magnitude", height=500)

    
    # 2) Band-pass filter settings
    st.sidebar.markdown("###Band-Pass Filter")
    filter_enabled = st.sidebar.checkbox("Apply Bandpass filter", False)
    fmin  = st.sidebar.number_input("Low cut (MHz)",  0.1, 10.0, 0.5, step=0.1) * 1e6
    fmax = st.sidebar.number_input("High cut (MHz)", 0.1, 20.0, 5.0, step=0.1) * 1e6
    order   = st.sidebar.slider("Filter order", 2, 8, 4)

    # 3) Align toggle
    align = st.sidebar.checkbox("Align to Group Delay", True)
    
    t_rx, rx_raw, compressed_raw, freqs, df = simulate_multimode(config)
    gd_s = calculate_group_delay(tx, fs) if align else 0.0
    shift_samples = int(gd_s * fs)

    rx_aligned = np.roll(rx_raw, -shift_samples)
    compressed_aligned = np.roll(compressed_raw, -shift_samples)

    if filter_enabled:
        rx_aligned = bandpass_filter(rx_aligned, fs, fmin, fmax)
        compressed_aligned = bandpass_filter(compressed_aligned, fs, fmin, fmax)

    df_mode1 = df[df["Mode"] == 1]

    st.subheader("🖼 Signal Plots (2×2)")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=t_rx*1e6, y=rx_raw, name="Raw", line=dict(color='gray')))
    fig1.update_layout(title="Raw Signal", xaxis_title="Time (µs)", height=250)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t_rx*1e6, y=rx_aligned, name="Aligned", line=dict(color='blue')))
    for _, row in df_mode1.iterrows():
        fig2.add_vline(x=row["Time (µs)"], line_color="red", line_dash="dot",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig2.update_layout(title="Aligned Raw Signal", xaxis_title="Time (µs)", height=250)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=t_rx*1e6, y=compressed_raw, name="Compressed", line=dict(color='black')))
    fig3.update_layout(title="Raw Compressed", xaxis_title="Time (µs)", height=250)

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=t_rx*1e6, y=compressed_aligned, name="Compressed Aligned", line=dict(color='green')))
    for _, row in df_mode1.iterrows():
        fig4.add_vline(x=row["Time (µs)"], line_color="red", line_dash="dot",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig4.update_layout(title="Aligned Compressed Signal", xaxis_title="Time (µs)", height=250)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig3, use_container_width=True)
    with col2:
        st.plotly_chart(fig2, use_container_width=True)
        st.plotly_chart(fig4, use_container_width=True)

    # Frequency Spectrum
    st.subheader("🔍 Frequency Spectrum of Received Signal")
    spectrum = np.abs(fft(rx_aligned))
    freqs_mhz = freqs[:len(freqs)//2]/1e6
    spec_mag = spectrum[:len(freqs)//2]
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(x=freqs_mhz, y=spec_mag, name="Spectrum", line=dict(color='purple')))
    fig5.update_layout(xaxis_title="Frequency (MHz)", yaxis_title="Magnitude", height=300)
    st.plotly_chart(fig5, use_container_width=True)

    # Parameter Table
    st.subheader("📋 Direct Echo Parameters (Mode 1 Only)")
    st.dataframe(df_mode1)
