# plots.py

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import fftconvolve
from scipy.fft import fft, fftfreq
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def simulate_multimode(config):
    """
    Simulate raw & compressed A-scan with multiple modes and per-layer physics.
    Returns:
      t_rx       : time axis (s)
      rx         : raw A-scan
      compressed : pulse-compressed A-scan
      df_params  : DataFrame of echo parameters for each layer & mode
    """
    # Unpack config
    fs         = config["sampling_rate"]
    t_chirp    = np.array(config["tx_chirp_t"])
    tx         = np.array(config["tx_chirp_waveform"])
    layers     = config["layer_data"]
    defect     = config["defect_type"]
    defect_idx = config["defect_layer"] - 1

    # Define modes: velocity (m/s), α0 (dB/cm/MHz), exponent n
    # Example set; you can make this user-configurable
    modes = [
        (2000, 0.02, 1.0),
        (1800, 0.05, 1.2),
        (1600, 0.08, 1.5)
    ]
    freq0 = (config["chirp_start_mhz"] + config["chirp_end_mhz"])/2  # MHz

    # Compute depths for fluid gap + each interface
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for _, thick_in, _ in layers:
        depths.append(depths[-1] + thick_in * INCH_TO_METER)

    # Reflection & transmission per interface
    Z_prev = config["Z_fluid"]
    R_list, T_list = [], []
    for name, thick, Z in layers:
        R = (Z - Z_prev)/(Z + Z_prev)
        T = 1 - R**2
        R_list.append(R); T_list.append(T)
        Z_prev = Z

    # Allocate raw rx
    max_delay_s = max(2*d/DEFAULT_VELOCITY for d in depths) + len(t_chirp)/fs
    n_rx = int(max_delay_s * fs) + len(t_chirp)
    rx = np.zeros(n_rx)
    t_rx = np.arange(n_rx)/fs

    # Collect parameters
    records = []

    # Simulate each mode and each interface echo
    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        # frequency domain chirp
        P = fft(tx)
        freqs = fftfreq(len(tx), 1/fs)

        # attenuation filter H(f) and dispersion D(f)
        # we'll apply same for all interfaces, then time-shift
        alpha_f = alpha0 * (np.abs(freqs)/1e6)**n_exp * 100  # dB/m
        H = 10**(-alpha_f * (depths[-1]) / 20)  # worst-case path
        beta = 0.05  # dispersion coefficient
        c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
        # we'll apply per depth inside loop

        for i, depth in enumerate(depths):
            # two-way travel
            tau_s = 2 * depth / v
            # phase shift for dispersion
            D = np.exp(-1j * 2*np.pi*freqs * (2*depth/c_f))
            # attenuation at this depth
            path_cm = depth * 100
            H_i = 10**(-alpha0 * (np.abs(freqs)/1e6)**n_exp * path_cm / 20)
            # combined filter
            P_i = P * H_i * D
            p_i = np.real(np.fft.ifft(P_i))

            # reflection or full for fluid gap
            if i == 0:
                R = -1.0
                T = 1.0
            else:
                R = R_list[i-1]
                T = T_list[i-1]

            # defect override
            if defect=="Delamination" and (i-1)==defect_idx:
                R *= 0.7; T *= 0.7
            if defect=="Crack" and (i-1)==defect_idx:
                R *= 0.5; T *= 0.5

            amp = abs(R)
            idx = int(tau_s * fs)
            rx[idx:idx+len(p_i)] += amp * p_i

            # record params
            if i>0:  # skip fluid in table
                records.append({
                    "Mode": m_idx+1,
                    "Layer": layers[i-1][0],
                    "Thickness (in)": layers[i-1][1],
                    "Z (MRayl)": layers[i-1][2],
                    "α0 (dB/cm/MHz)": round(alpha0,2),
                    "n exp": round(n_exp,2),
                    "R": round(R,3),
                    "T": round(T,3),
                    "Time (µs)": round(tau_s*1e6,2),
                    "Amp": round(amp,3)
                })

    # Matched‐filter compression
    compressed = fftconvolve(rx, tx[::-1], mode='same')

    df = pd.DataFrame.from_records(records)

    return t_rx, rx, compressed, freqs, df

def show_plots():
    st.title("📊 Multimode A-Scan Simulation")

    # Run sim
    config = st.session_state["config"]
    t_rx, rx, compressed, freqs, df = simulate_multimode(config)

    # Table of parameters
    
    # select only Mode 1 rows
    df_mode1 = df[df["Mode"] == 1]
    st.subheader("📋 Direct Mode Echo Parameters")
    st.dataframe(df_mode1, use_container_width=True)

    # Raw A-scan
    st.subheader("🟢 Raw Received A-Scan")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=t_rx*1e6, y=rx, line=dict(color="green"), name="Raw"))
    for _, row in df.iterrows():
        fig1.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig1.update_layout(xaxis_title="Time (µs)", yaxis_title="Amp",
                       hovermode="x unified", height=350)
    st.plotly_chart(fig1, use_container_width=True)

    # Compressed A-scan
    st.subheader("🔴 Pulse-Compressed A-Scan")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t_rx*1e6, y=compressed, line=dict(color="firebrick"), name="Compressed"))
    for _, row in df_mode1.iterrows():
        fig2.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig2.update_layout(xaxis_title="Time (µs)", yaxis_title="Amp",
                       hovermode="x unified", height=350)
    st.plotly_chart(fig2, use_container_width=True)

    # 3) Frequency-domain of compressed signal
    st.subheader("📈 Frequency Spectrum (Compressed A-Scan)")
    fft_vals = np.abs(np.fft.fft(compressed))
    freqs   = np.fft.fftfreq(len(compressed), d=1/config["sampling_rate"])
    mask    = freqs >= 0

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=freqs[mask]/1e6, y=fft_vals[mask],
        mode='lines', line=dict(color='royalblue'),
        name='FFT'
    ))
    fig3.update_layout(
        xaxis_title="Frequency (MHz)", yaxis_title="Magnitude",
        height=350, hovermode="x unified"
    )
    st.plotly_chart(fig3, use_container_width=True)
