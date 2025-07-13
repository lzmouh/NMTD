import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import fftconvolve
from scipy.fft import fft, ifft, fftfreq
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY
from scipy.signal import hilbert

def align_by_group_delay(fs, tx_chirp, t_chirp, raw_signal, tt_fluid_us=None):
    """
    Aligns raw A-scan using group delay center of chirp.

    Parameters:
    - fs: sampling frequency (Hz)
    - tx_chirp: transmitted chirp signal (1D array)
    - t_chirp: time axis for chirp (1D array)
    - raw_signal: measured raw A-scan signal (1D array)
    - tt_fluid_us: optional travel time (for visual comparison)

    Returns:
    - t_aligned: time axis (µs), aligned so t=0 is group delay center
    - raw_aligned: aligned signal
    - gd_time: group delay time (s)
    """
    # 1. Compute group delay using Hilbert envelope peak
    chirp_env = np.abs(hilbert(tx_chirp))
    gd_index = np.argmax(chirp_env)
    gd_time = t_chirp[gd_index]

    # 2. Shift the signal so group delay becomes time zero
    n_shift = gd_index
    raw_aligned = np.zeros_like(raw_signal)
    raw_aligned[:len(raw_signal) - n_shift] = raw_signal[n_shift:]

    # 3. Adjust time axis accordingly
    t_aligned = (np.arange(len(raw_signal)) - gd_index) / fs * 1e6  # µs

    return t_aligned, raw_aligned, gd_time


def simulate_multimode(config):
    """
    Simulate raw and pulse-compressed signal using multi-mode modeling.
    Includes dispersion, attenuation, reflection/transmission.
    """
    # --- Unpack config ---
    fs        = config["sampling_rate"]               # Hz
    t_chirp   = np.array(config["tx_chirp_t"])        # s
    tx        = np.array(config["tx_chirp_waveform"]) # waveform
    fluid_vel = config["fluid_velocity"]              # m/s
    defect    = config["defect_type"]
    defect_i  = config["defect_layer"] - 1
    layers    = config["layer_data"]

    # Central frequency for attenuation scaling (MHz)
    f0_mhz = (config["chirp_start_mhz"] + config["chirp_end_mhz"]) / 2

    # --- Build interface depths ---
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for layer in layers:
        depths.append(depths[-1] + layer["thickness"] * INCH_TO_METER)

    # --- Interface reflection/transmission ---
    R_list, T_list = [], []
    Z_prev = config["Z_fluid"]
    for layer in layers:
        Z_curr = layer["Z"]
        R = (Z_curr - Z_prev) / (Z_curr + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_curr

    # --- Define modes: fluid-gap first, then one per layer ---
    modes = [(fluid_vel, 0.0, 0.0)] + [
        (layer["v"], layer["alpha0"], layer["n_exp"]) for layer in layers
    ]

    # --- Setup Rx time axis ---
    max_delay = max(2*d/DEFAULT_VELOCITY for d in depths) + len(t_chirp)/fs
    n_rx = int(np.ceil(max_delay * fs)) + len(t_chirp)
    t_rx = np.arange(n_rx) / fs
    rx = np.zeros(n_rx)

    # --- FFT of transmitted chirp ---
    freqs = fftfreq(len(tx), 1/fs)
    P = fft(tx)

    records = []

    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        beta = 0.05  # weak dispersion constant

        for i, depth in enumerate(depths):
            # Travel time
            tau_s = 2 * depth / v

            # Attenuation
            alpha_f = alpha0 * (np.abs(freqs)/1e6)**n_exp * 100  # dB/m
            H = 10**(-alpha_f * depth / 20)

            # Dispersion
            c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D = np.exp(-1j * 2*np.pi*freqs * (2*depth / c_f))

            # Filtered pulse
            P_i = P * H * D
            p_i = np.real(ifft(P_i))

            # Reflection and transmission
            if i == 0:
                R, T = -1.0, 1.0
            else:
                R, T = R_list[i-1], T_list[i-1]

            # Defect override
            if defect == "Delamination" and (i-1) == defect_i:
                R *= 0.7; T *= 0.7
            if defect == "Crack" and (i-1) == defect_i:
                R *= 0.5; T *= 0.5

            amp = abs(R)
            idx = int(round(tau_s * fs))
            rx[idx:idx+len(p_i)] += amp * p_i

            # Record parameters
            if i == 0:
                tt_fluid = 2 * depth / fluid_vel * 1e6  # µs
                records.append({
                    "Mode":           m_idx + 1,
                    "Layer":          "Fluid Gap",
                    "Thickness (in)": round(DEFAULT_GAP_INCH, 3),
                    "Z (MRayl)":      round(config["Z_fluid"], 3),
                    "α0":             0.0,
                    "n exp":          0.0,
                    "R":              -1.0,
                    "T":              1.0,
                    "Time (µs)":      round(tt_fluid, 3),
                    "Amp":            round(amp, 3)
                })
            elif i > 0:
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

    # --- Matched filtering (pulse compression) ---
    compressed = fftconvolve(rx, tx[::-1], mode='same')
    compressed = np.roll(compressed, -len(tx)//2)  # align peak with true echo time

    df = pd.DataFrame.from_records(records)
    return t_rx, rx, compressed, freqs, df
    
def show_plots():
    st.title("Multimode Signal Simulation")
    config = st.session_state["config"]
    fs = config["sampling_rate"]

    # Run simulation
    t_rx, rx, compressed, freqs, df = simulate_multimode(config)

    # Align to group delay toggle
    align = st.toggle("🔄 Align Raw Signal to Chirp Group Delay", value=True)

    if align:
        t_chirp = np.array(config["tx_chirp_t"])
        tx = np.array(config["tx_chirp_waveform"])
        t_aligned, raw_aligned, gd_s = align_by_group_delay(fs, tx, t_chirp, rx)
        st.success(f"Signal aligned to chirp group delay at **{gd_s*1e6:.2f} µs**")
    else:
        t_aligned = t_rx * 1e6
        raw_aligned = rx

    # Extract Mode 1 echoes (direct reflections)
    df_mode1 = df[df["Mode"] == 1]

    # Get fluid gap echo (optional)
    fluid_row = df[df["Layer"].str.contains("Fluid", case=False)].iloc[0] if "Fluid" in df["Layer"].values else None
    tt_fluid = fluid_row["Time (µs)"] if fluid_row is not None else None

    # --- Raw A-scan ---
    st.subheader("🟢 Raw Signal (Aligned if selected)")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=t_aligned, y=raw_aligned, name="Raw", line=dict(color="teal")))

    # Annotate echoes (only direct)
    for _, row in df_mode1.iterrows():
        fig1.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                       annotation_text=row["Layer"], annotation_position="top right")

    # Fluid gap echo annotation
    if tt_fluid:
        fig1.add_vline(x=tt_fluid, line_dash="dash", line_color="blue",
                       annotation_text="Fluid Gap", annotation_position="top left")

    fig1.update_layout(
        xaxis_title="Time (µs)", yaxis_title="Amplitude",
        hovermode="x unified", height=400
    )
    st.plotly_chart(fig1, use_container_width=True)

    # --- Pulse Compressed ---
    st.subheader("🔴 Pulse-Compressed A-Scan")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t_aligned, y=compressed, name="Compressed", line=dict(color="firebrick")))

    for _, row in df_mode1.iterrows():
        fig2.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                       annotation_text=row["Layer"], annotation_position="top right")

    if tt_fluid:
        fig2.add_vline(x=tt_fluid, line_dash="dash", line_color="blue",
                       annotation_text="Fluid Gap", annotation_position="top left")

    fig2.update_layout(
        xaxis_title="Time (µs)", yaxis_title="Amplitude",
        hovermode="x unified", height=400
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Frequency Spectrum ---
    st.subheader("🔵 Frequency Spectrum")
    fft_vals = np.abs(fft(raw_aligned))
    freq_axis = np.fft.fftfreq(len(raw_aligned), d=1/fs) / 1e6
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=freq_axis[:len(freq_axis)//2],
                              y=fft_vals[:len(freq_axis)//2],
                              name="FFT", line=dict(color="royalblue")))
    fig3.update_layout(
        xaxis_title="Frequency (MHz)", yaxis_title="Magnitude",
        hovermode="x unified", height=300
    )
    st.plotly_chart(fig3, use_container_width=True)

    # --- Echo Table ---
    st.subheader("📋 Mode-1 Echo Parameters")
    st.dataframe(df_mode1.reset_index(drop=True))
