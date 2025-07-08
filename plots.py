import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import fftconvolve
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def simulate_received_signal(config):
    """
    Build the raw received A-scan by summing delayed, attenuated echoes of the chirp.
    Returns:
      t_rx      : time axis (s)
      rx        : raw received signal
      delays_us : list of echo times in µs
      amps      : list of echo amplitude factors
    """
    # Unpack config
    fs       = config["sampling_rate"]           # Hz
    t_chirp  = np.array(config["tx_chirp_t"])    # s
    tx       = np.array(config["tx_chirp_waveform"])
    layers   = config["layer_data"]
    defect   = config["defect_type"]
    defect_i = config["defect_layer"] - 1

    # Central frequency (approx mid‐band)
    f0 = (config["chirp_start_mhz"] + config["chirp_end_mhz"]) / 2 * 1e6  # Hz

    # Compute depths for fluid gap + each interface
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for _, thick_in, _ in layers:
        depths.append(depths[-1] + thick_in * INCH_TO_METER)

    # Reflection & attenuation parameters per layer
    Z_prev = config["Z_fluid"]                    # MRayl
    R_list, T_list = [], []
    for (_, _, Z_m) in layers:
        R = (Z_m - Z_prev) / (Z_m + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_m

    # Total signal length: allow for last echo + chirp duration
    max_delay = max(2*d / DEFAULT_VELOCITY for d in depths)
    n_rx = int((max_delay + len(t_chirp)/fs + 1e-6) * fs)
    rx   = np.zeros(n_rx)
    t_rx = np.arange(n_rx) / fs

    delays_us = []
    amps      = []

    # First echo: fluid-gap (assume full reflection R=-1)
    delay0_s = 2 * gap_m / config["fluid_velocity"]
    amp0     = 1.0
    if defect=="Delamination" and defect_i== -1:
        amp0 *= 0.7
    elif defect=="Crack" and defect_i== -1:
        amp0 *= 0.5
    idx0 = int(delay0_s * fs)
    rx[idx0:idx0+len(tx)] += amp0 * tx
    delays_us.append(delay0_s * 1e6)
    amps.append(amp0)

    # Now each layer echo
    for i, depth in enumerate(depths[1:], start=0):
        # two‐way travel time using baseline velocity
        delay_s = 2 * depth / DEFAULT_VELOCITY
        # attenuation α(f0) model: α0(dB/cm/MHz) * f0(MHz) * path(cm)
        alpha0 = 0.5 + 0.1 * i
        path_cm = depth * 100
        att_factor = 10 ** ( - alpha0 * (f0/1e6) * path_cm / 20)
        # reflection coefficient
        R = R_list[i]
        amp = att_factor * abs(R)
        # defect override
        if defect=="Delamination" and i==defect_i:
            amp *= 0.7
        if defect=="Crack" and i==defect_i:
            amp *= 0.5

        idx = int(delay_s * fs)
        rx[idx:idx+len(tx)] += amp * tx
        delays_us.append(delay_s * 1e6)
        amps.append(amp)

    return t_rx, rx, delays_us, amps

def show_plots():
    st.title("📊 NMTD A-Scan: Raw & Pulse-Compressed")

    config = st.session_state["config"]
    t_rx, rx, delays_us, amps = simulate_received_signal(config)

    # Build DataFrame of echoes
    df = pd.DataFrame({
        "Echo #":     np.arange(len(delays_us)) + 1,
        "Time (µs)":  [round(d,2) for d in delays_us],
        "Amplitude":  [round(a,3) for a in amps]
    })

    st.subheader("📋 Echo Table")
    st.dataframe(df, use_container_width=True)

    # 1) Raw received A-scan
    st.subheader("🟢 Raw Received A-Scan")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=t_rx*1e6, y=rx,
        mode='lines', line=dict(color='darkgreen'),
        name='Raw A-scan'
    ))
    # Mark each echo time
    for d, lbl in zip(delays_us, df["Echo #"]):
        fig1.add_vline(x=d, line_dash="dot", line_color="gray",
                       annotation_text=f"Echo {lbl}", annotation_position="top right")
    fig1.update_layout(
        xaxis_title="Time (µs)", yaxis_title="Amplitude",
        title="Raw A-Scan (Uncompressed)", hovermode="x unified", height=400
    )
    st.plotly_chart(fig1, use_container_width=True)

    # 2) Matched-filter (pulse compression)
    st.subheader("🔵 Pulse-Compressed A-Scan")
    tx = np.array(config["tx_chirp_waveform"])
    compressed = fftconvolve(rx, tx[::-1], mode='same')

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=t_rx*1e6, y=compressed,
        mode='lines', line=dict(color='firebrick'),
        name='Compressed A-scan'
    ))
    for d, lbl in zip(delays_us, df["Echo #"]):
        fig2.add_vline(x=d, line_dash="dot", line_color="gray",
                       annotation_text=f"Echo {lbl}", annotation_position="top right")
    fig2.update_layout(
        xaxis_title="Time (µs)", yaxis_title="Amplitude",
        title="Pulse-Compressed A-Scan", hovermode="x unified", height=400
    )
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
