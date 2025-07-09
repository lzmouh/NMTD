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
    Simulate raw and pulse-compressed A-scan using multiple modes.
    Returns:
      t_rx       : 1D time axis (s)
      rx         : raw A-scan (amplitude)
      compressed : matched-filter output
      df_params  : DataFrame of echo parameters (mode, layer, R, T, time, amp)
    """
    # --- Unpack config ---
    fs        = config["sampling_rate"]              # Hz
    t_chirp   = np.array(config["tx_chirp_t"])       # s
    tx        = np.array(config["tx_chirp_waveform"])
    fluid_vel = config["fluid_velocity"]             # m/s
    defect    = config["defect_type"]
    defect_i  = config["defect_layer"] - 1           # zero-based
    layers    = config["layer_data"]                 # list of dicts

    # central frequency for attenuation scaling (MHz)
    f0_mhz = (config["chirp_start_mhz"] + config["chirp_end_mhz"]) / 2

    # --- Build depths: fluid gap + each layer interface ---
    gap_m  = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for lyr in layers:
        depths.append(depths[-1] + lyr["thickness"] * INCH_TO_METER)

    # --- Reflection & transmission for each layer interface ---
    R_list, T_list = [], []
    Z_prev = config["Z_fluid"]
    for lyr in layers:
        Z_curr = lyr["Z"]
        R = (Z_curr - Z_prev) / (Z_curr + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_curr

    # --- Define modes: first the fluid gap mode, then one per layer ---
    # fluid gap: no attenuation or dispersion modeled here, just full reflection
    modes = [(fluid_vel, 0.0, 0.0)] + [
        (lyr["v"], lyr["alpha0"], lyr["n_exp"]) for lyr in layers
    ]

    # --- Prepare output arrays ---
    max_delay_s = max(2 * d / DEFAULT_VELOCITY for d in depths) + len(t_chirp)/fs
    n_rx = int(np.ceil(max_delay_s * fs)) + len(t_chirp)
    rx   = np.zeros(n_rx)
    t_rx = np.arange(n_rx) / fs

    # --- Prepare to record parameters ---
    records = []

    # --- Per-mode, per-interface simulation ---
    freqs = fftfreq(len(tx), 1/fs)
    P     = fft(tx)

    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        # frequency‐dependent attenuation filter (per path)
        # we'll compute per-depth inside the loop
        # dispersion coefficient (example)
        beta = 0.05

        for i, depth in enumerate(depths):
            # 1) two-way travel time
            tau_s = 2 * depth / v

            # 2) attenuation H(f) = 10^{-α(f)*path/20}
            path_cm = depth * 100
            alpha_f = alpha0 * (np.abs(freqs)/1e6)**n_exp * 100  # dB/m
            H = 10**(-alpha_f * depth / 20)

            # 3) dispersion phase D(f) = exp(-j·2π·f·(2·depth/c(f)))
            c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D   = np.exp(-1j * 2 * np.pi * freqs * (2*depth / c_f))

            # 4) apply filters in freq domain and invert
            P_i = P * H * D
            p_i = np.real(np.fft.ifft(P_i))

            # 5) determine reflection coefficient
            if i == 0:
                # fluid-gap echo: full reflection (polarity invert)
                R = -1.0
                T = 1.0
            else:
                R = R_list[i-1]
                T = T_list[i-1]

            # 6) defect override
            if defect == "Delamination" and (i-1) == defect_i:
                R *= 0.7;  T *= 0.7
            if defect == "Crack"        and (i-1) == defect_i:
                R *= 0.5;  T *= 0.5

            amp = abs(R)

            # 7) sum into raw A-scan at shifted index
            idx = int(round(tau_s * fs))
            rx[idx:idx+len(p_i)] += amp * p_i

            # before your mode loop, compute tt_fluid_us
            gap_m    = DEFAULT_GAP_INCH * INCH_TO_METER
            tt_fluid = 2 * gap_m / fluid_vel * 1e6    # µs

            # 8) record parameters, now including the fluid‐gap interface
            if i == 0:
                # record the fluid‐gap echo
                records.append({
                    "Mode":           m_idx + 1,
                    "Layer":          "Fluid Gap",
                    "Thickness (in)": round(DEFAULT_GAP_INCH, 3),
                    "Z (MRayl)":      round(config["Z_fluid"], 3),
                    "α0":             0.0,                 # no attenuation here
                    "n exp":          0.0,
                    "R":              -1.0,                # full reflection
                    "T":              1.0,
                    "Time (µs)":      round(tt_fluid, 3),
                    "Amp":            round(abs(R), 3)
                })
            elif i > 0:
                # record the layer‐interface echo as before
                records.append({
                    "Mode":           m_idx + 1,
                    "Layer":          layers[i-1]["name"],
                    "Thickness (in)": round(layers[i-1]["thickness"], 3),
                    "Z (MRayl)":      round(layers[i-1]["Z"], 3),
                    "α0":             round(alpha0, 3),
                    "n exp":          round(n_exp, 3),
                    "R":              round(R, 3),
                    "T":              round(T, 3),
                    "Time (µs)":      round(tau_s * 1e6, 3),
                    "Amp":            round(amp, 3)
                })

    # --- Pulse-compression (matched filter) ---
    compressed = fftconvolve(rx, tx[::-1], mode='same')

    # --- Build DataFrame ---
    df_params = pd.DataFrame.from_records(records)
    # Compute frequency axis
    freqs = np.fft.fftfreq(len(compressed), d=1/config["sampling_rate"])

    return t_rx, rx, compressed, freqs, df_params


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
    
    # --- add the vertical line & annotation for the fluid gap ---
    fluid_row = df[df["Layer"] == "Fluid–Gap"].iloc[0]
    tt_fluid_us = fluid_row["Time (µs)"]
    fig1.add_vline(
        x=tt_fluid,
        line_dash="dash",
        line_color="blue",
        annotation_text="Fluid‐Gap Echo",
        annotation_position="top left",
        annotation_font_color="blue"
    )
    
    # Annotate only Mode 1 echoes
    for _, row in df_mode1.iterrows():
        fig1.add_vline(
            x = row["Time (µs)"],
            line_dash = "dot",
            line_color = "gray",
            annotation_text = f"{row['Layer']}",
            annotation_position = "top right"
        )

    fig1.update_layout(xaxis_title="Time (µs)", yaxis_title="Amp",
                       hovermode="x unified", height=350)
    st.plotly_chart(fig1, use_container_width=True)

    # Compressed A-scan
    st.subheader("🔴 Pulse-Compressed A-Scan")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t_rx*1e6, y=compressed, line=dict(color="firebrick"), name="Compressed"))
    df_mode1 = df[df["Mode"] == 1]
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
