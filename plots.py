import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import fftconvolve
from scipy.fft import fft, ifft, fftfreq
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def simulate_multimode(config):
    """
    Simulate multi-mode ultrasonic propagation with matched filter compression.
    Returns:
        t_rx         : time axis (s)
        rx           : raw received signal
        compressed   : pulse-compressed signal
        freqs        : frequency axis (Hz)
        df_params    : DataFrame with echo timing, amplitude, layer properties
    """
    # Unpack config
    fs        = config["sampling_rate"]
    t_chirp   = np.array(config["tx_chirp_t"])       # time array
    tx        = np.array(config["tx_chirp_waveform"])# waveform
    layers    = config["layer_data"]
    fluid_vel = config["fluid_velocity"]
    Z_fluid   = config["Z_fluid"]
    defect    = config["defect_type"]
    defect_i  = config["defect_layer"] - 1  # 0-based index

    f0_mhz = (config["chirp_start_mhz"] + config["chirp_end_mhz"]) / 2

    # Interface depths (fluid gap + layer boundaries)
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for lyr in layers:
        depths.append(depths[-1] + lyr["thickness"] * INCH_TO_METER)

    # Reflection & transmission coefficients
    R_list, T_list = [], []
    Z_prev = Z_fluid
    for lyr in layers:
        Z_curr = lyr["Z"]
        R = (Z_curr - Z_prev) / (Z_curr + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_curr

    # Define modes: fluid mode first, then one per layer
    modes = [(fluid_vel, 0.0, 0.0)] + [(lyr["v"], lyr["alpha0"], lyr["n_exp"]) for lyr in layers]

    # Output signal arrays
    max_delay_s = max(2 * d / DEFAULT_VELOCITY for d in depths) + len(t_chirp)/fs
    n_rx = int(np.ceil(max_delay_s * fs)) + len(t_chirp)
    t_rx = np.arange(n_rx) / fs
    rx   = np.zeros(n_rx)

    # FFT of transmitted signal
    freqs = fftfreq(len(tx), 1/fs)
    P     = fft(tx)

    records = []

    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        beta = 0.05  # dispersion strength

        for i, depth in enumerate(depths):
            tau_s = 2 * depth / v
            path_cm = depth * 100
            alpha_f = alpha0 * (np.abs(freqs)/1e6)**n_exp * 100  # dB/m
            H = 10**(-alpha_f * depth / 20)

            c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D = np.exp(-1j * 2 * np.pi * freqs * (2 * depth / c_f))

            P_i = P * H * D
            p_i = np.real(ifft(P_i))

            if i == 0:
                R = -1.0
                T = 1.0
            else:
                R = R_list[i-1]
                T = T_list[i-1]

            if defect == "Delamination" and (i-1) == defect_i:
                R *= 0.7
                T *= 0.7
            elif defect == "Crack" and (i-1) == defect_i:
                R *= 0.5
                T *= 0.5

            amp = abs(R)
            idx = int(round(tau_s * fs))
            rx[idx:idx+len(p_i)] += amp * p_i

            # Record parameters
            if i == 0:
                tt_fluid = 2 * gap_m / fluid_vel * 1e6
                records.append({
                    "Mode": m_idx + 1,
                    "Layer": "Fluid Gap",
                    "Thickness (in)": round(DEFAULT_GAP_INCH, 3),
                    "Z (MRayl)": round(Z_fluid, 3),
                    "α0": 0.0,
                    "n exp": 0.0,
                    "R": -1.0,
                    "T": 1.0,
                    "Time (µs)": round(tt_fluid, 3),
                    "Amp": round(amp, 3)
                })
            elif i > 0:
                lyr = layers[i-1]
                records.append({
                    "Mode": m_idx + 1,
                    "Layer": lyr["name"],
                    "Thickness (in)": round(lyr["thickness"], 3),
                    "Z (MRayl)": round(lyr["Z"], 3),
                    "α0": round(alpha0, 3),
                    "n exp": round(n_exp, 3),
                    "R": round(R, 3),
                    "T": round(T, 3),
                    "Time (µs)": round(tau_s * 1e6, 3),
                    "Amp": round(amp, 3)
                })

    # Matched filter (pulse compression)
    compressed = fftconvolve(rx, tx[::-1], mode='same')

    df_params = pd.DataFrame.from_records(records)
    return t_rx, rx, compressed, freqs, df_params

def show_plots():
    st.title("Multimode Signal Simulation")

    # Run sim
    config = st.session_state["config"]
    t_rx, rx, compressed, freqs, df = simulate_multimode(config)

    # Table of parameters
    
    # select only Mode 1 rows
    df_mode1 = df[df["Mode"] == 1]
    st.subheader("Direct Mode Echo Parameters")
    st.dataframe(df_mode1, use_container_width=True)

    # Raw Signal
    st.subheader("Raw Received Signal")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=t_rx*1e6, y=rx, line=dict(color="green"), name="Raw"))
    
    # --- add the vertical line & annotation for the fluid gap ---
    gap_m    = DEFAULT_GAP_INCH * INCH_TO_METER
    tt_fluid_us = 2 * gap_m / config["fluid_velocity"] * 1e6

    df_mode1 = df[df["Mode"] == 1]
    for _, row in df_mode1.iterrows():
        fig1.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig1.update_layout(xaxis_title="Time (µs)", yaxis_title="Amp",
                       hovermode="x unified", height=600)
    st.plotly_chart(fig1, use_container_width=True)

    # Compressed Signal
    st.subheader("Pulse-Compressed Signal")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t_rx*1e6, y=compressed, line=dict(color="firebrick"), name="Compressed"))
    for _, row in df_mode1.iterrows():
        fig2.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig2.update_layout(xaxis_title="Time (µs)", yaxis_title="Amp",
                       hovermode="x unified", height=600)
    st.plotly_chart(fig2, use_container_width=True)

    # 3) Frequency-domain of compressed signal
    st.subheader("Frequency Spectrum (Compressed Signal)")
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
        height=600, hovermode="x unified"
    )
    st.plotly_chart(fig3, use_container_width=True)
