import streamlit as st
import numpy as np
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from scipy.signal import fftconvolve, hilbert, butter, filtfilt
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
    
    # 2) compute aligned raw & compressed
    tx    = np.array(config["tx_chirp_waveform"])
    t_tx  = np.array(config["tx_chirp_t"])
    t_al, raw_al = align_by_group_delay(fs, tx, t_tx, raw_rx)
    _,    comp_al = align_by_group_delay(fs, tx, t_tx, comp_rx)

    # 3) extract direct‐mode (Mode 1) echo times
    df1 = df[df["Mode"] == 1]
    echo_times = df1["Time (µs)"].values
    
    df = pd.DataFrame.from_records(records)
    return t_rx, rx, compressed, freqs, df
    
# --- Helper: group-delay alignment ---
def align_by_group_delay(fs, tx, t_tx, rx):
    env = np.abs(hilbert(tx))
    gd_idx = int(np.argmax(env))
    n = len(rx)
    aligned = np.zeros_like(rx)
    aligned[:n-gd_idx] = rx[gd_idx:]
    t = (np.arange(n) - gd_idx) / fs * 1e6
    return t, aligned

# --- Helper: design & apply bandpass ---
def bandpass_filter(data, fs, lowcut, highcut, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return filtfilt(b, a, data)

def show_plots():
    st.title("📊 Ultrasonic A-Scan: Raw & Compressed with Alignment")

    # 1) Simulation
    config = st.session_state["config"]
    fs = config["sampling_rate"]
    t_rx, raw_rx, comp_rx, freqs, df = simulate_multimode(config)

    # 2) Band-pass filter settings
    st.sidebar.markdown("###Band-Pass Filter")
    apply_bp = st.sidebar.checkbox("Apply band-pass filter", False)
    lowcut  = st.sidebar.number_input("Low cut (MHz)",  0.05, 10.0, 0.5, step=0.05) * 1e6
    highcut = st.sidebar.number_input("High cut (MHz)", 0.05, 20.0, 5.0, step=0.05) * 1e6
    order   = st.sidebar.slider("Filter order", 2, 8, 4)

    # 3) Align toggle
    align = st.sidebar.checkbox("Align to chirp group delay", True)

    # 4) Prepare signals
    rx = raw_rx.copy()
    # apply BP if requested
    if apply_bp:
        rx = bandpass_filter(rx, fs, lowcut, highcut, order)

    # aligned raw
    t_al, rx_al = (t_rx*1e6, rx)
    # need tx and t_tx for alignment
    t_tx = np.array(config["tx_chirp_t"])
    tx   = np.array(config["tx_chirp_waveform"])
    if align:
        t_al, rx_al = align_by_group_delay(fs, tx, t_tx, rx)

    # compress on (possibly filtered) raw
    comp = fftconvolve(rx, tx[::-1], mode='same')
    # align compressed
    comp_al = comp.copy()
    if align:
        _, comp_al = align_by_group_delay(fs, tx, t_tx, comp)

    # 5) Direct-mode echoes (mode 1)
    df1 = df[df["Mode"] == 1]
    echo_times = df1["Time (µs)"].values
    
    # 4) build 2×2 subplot figure
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Raw A-Scan",
            "Aligned A-Scan",
            "Pulse-Compressed A-Scan",
            "Receiver Signal Spectrum"
        ]
    )

    # Row 1, Col 1: Raw A-Scan
    fig.add_trace(
        go.Scatter(x=t_rx * 1e6, y=raw_rx, name="Raw", line=dict(color="black")),
        row=1, col=1
    )
    for t in echo_times:
        fig.add_vline(x=t, line_dash="dot", line_color="gray", row=1, col=1)
    fig.update_xaxes(title_text="Time (µs)", row=1, col=1)
    fig.update_yaxes(title_text="Amplitude", row=1, col=1)

    # Row 1, Col 2: Aligned A-Scan
    fig.add_trace(
        go.Scatter(x=t_al, y=raw_al, name="Aligned", line=dict(color="teal")),
        row=1, col=2
    )
    for t in echo_times:
        fig.add_vline(x=t, line_dash="dot", line_color="gray", row=1, col=2)
    fig.update_xaxes(title_text="Time (µs)", row=1, col=2)
    fig.update_yaxes(title_text="Amplitude", row=1, col=2)

    # Row 2, Col 1: Pulse-Compressed A-Scan
    fig.add_trace(
        go.Scatter(x=t_rx * 1e6, y=comp_rx, name="Compressed", line=dict(color="firebrick")),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=t_al, y=comp_al, name="Aligned Compressed", line=dict(color="orange", dash="dash")),
        row=2, col=1
    )
    for t in echo_times:
        fig.add_vline(x=t, line_dash="dot", line_color="gray", row=2, col=1)
    fig.update_xaxes(title_text="Time (µs)", row=2, col=1)
    fig.update_yaxes(title_text="Amplitude", row=2, col=1)

    # Row 2, Col 2: Receiver Signal Spectrum
    fft_vals = np.abs(fft(raw_rx))
    freq_axis = fftfreq(len(raw_rx), d=1/fs) / 1e6
    half = len(freq_axis)//2
    fig.add_trace(
        go.Scatter(
            x=freq_axis[:half],
            y=fft_vals[:half],
            name="Spectrum",
            line=dict(color="royalblue")
        ),
        row=2, col=2
    )
    fig.update_xaxes(title_text="Frequency (MHz)", row=2, col=2)
    fig.update_yaxes(title_text="Magnitude", row=2, col=2)

    # 5) common layout updates
    fig.update_layout(
        height=800,
        showlegend=False,
        title_text="Ultrasonic A-Scan: Raw, Aligned, Compressed, & Spectrum"
    )

    # 6) display figure
    st.plotly_chart(fig, use_container_width=True)
