# plots.py

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq, ifft
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY


def simulate_layer_physics(config):
    layers      = config["layer_data"]
    Z_fluid     = config["Z_fluid"] * 1e6
    rho_fluid   = config["fluid_density"] * 1000
    defect      = config["defect_type"]
    defect_idx  = config["defect_layer"] - 1

    # Time axis
    fs    = 100e6
    t_max = 25e-6
    t     = np.linspace(0, t_max, int(fs * t_max))
    dt    = t[1] - t[0]

    # Transducer pulse
    f0    = 1e6
    pulse = np.sin(2*np.pi*f0*t) * np.exp(-((t-3/f0)**2)/(0.2e-6)**2)
    P     = fft(pulse)
    freqs = fftfreq(len(t), dt)

    # Fluid gap echo
    gap_m    = DEFAULT_GAP_INCH * INCH_TO_METER
    c_fluid  = Z_fluid / rho_fluid
    TT_fluid = 2 * gap_m / c_fluid * 1e6

    A_scan = np.zeros_like(t)
    A_scan += np.interp(t, t - TT_fluid, pulse, left=0, right=0)

    results = []
    Z_prev = Z_fluid
    amp    = 1.0
    depth  = gap_m

    for i, (label, thick_in, Z_mrayl) in enumerate(layers):
        thickness = thick_in * INCH_TO_METER
        Z_curr    = Z_mrayl * 1e6

        # ——————————————————————————
        # EXAGGERATED LOW-DECAY PARAMETERS
        alpha0 = 0.01        # was 0.5+0.1*i, now tiny
        n      = 0.1         # was 1.2+0.05*i, now small
        alpha_f = alpha0 * (np.abs(freqs)/1e6)**n * 100  # dB/m
        H       = 10**(-alpha_f * thickness / 20)

        # Force very high transmission
        R = 0.01
        T = 0.99

        # Defect overrides (unchanged)
        extra_delay = 0
        if defect=="Delamination" and i==defect_idx:
            R, T = 0.7, 0.3
            extra_delay = 0.6
        elif defect=="Crack" and i==defect_idx:
            R, T = 0.5, 0.5
        # ——————————————————————————

        # Propagate
        P_i = P * H * T
        p_i = np.real(ifft(P_i))
        depth += thickness
        tau   = (2 * depth / DEFAULT_VELOCITY) * 1e6 + extra_delay
        echo  = R * np.interp(t, t - tau, p_i, left=0, right=0)
        A_scan += echo

        results.append({
            "Layer": label,
            "Thickness (in)": thick_in,
            "Z (MRayl)": Z_mrayl,
            "α0 (dB/cm/MHz)": round(alpha0, 3),
            "n exponent": round(n, 3),
            "Refl Coef": round(R, 3),
            "Trans Coef": round(T, 3),
            "Time (µs)": round(tau, 2),
            "Amp Echo": round(R * amp, 3),
        })

        amp    *= T
        Z_prev  = Z_curr

    df = pd.DataFrame(results)
    return t, A_scan, freqs, df, TT_fluid

def show_plots2():
    st.title("📊 Ultrasonic A-scan Intermediate Steps")

    config = st.session_state["config"]
    t, _, freqs, df_results, _ = simulate_layer_physics(config)

    # 1) Transducer pulse
    f0 = 1e6
    pulse = np.sin(2 * np.pi * f0 * t) * np.exp(-((t - 3 / f0) ** 2) / (0.2e-6) ** 2)
    st.subheader("1) Raw Transducer Pulse")
    fig0 = go.Figure([go.Scatter(x=t*1e6, y=pulse, name="Pulse")])
    fig0.update_layout(xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
    st.plotly_chart(fig0, use_container_width=True)

    # 2) Fluid‐gap echo only
    # use the user‐defined fluid_velocity from config
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    v_fluid = config["fluid_velocity"]         # m/s
    TT_fluid = 2 * gap_m / v_fluid * 1e6       # µs

    fluid_echo = np.interp(t, t - TT_fluid*1e-6, pulse, left=0, right=0)
    st.subheader(f"2) Fluid‐Gap Echo Only (TT_fluid = {TT_fluid:.2f} µs)")
    fig1 = go.Figure([go.Scatter(x=t*1e6, y=fluid_echo, name="Fluid Echo")])
    fig1.update_layout(xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
    st.plotly_chart(fig1, use_container_width=True)

    # 3) Build cumulative A-scan step‐by‐step
    cumulative = fluid_echo.copy()
    steps = [("Fluid Echo Only", cumulative.copy())]

    # Prepare for per‐layer echoes
    Z_prev = config["Z_fluid"] * 1e6
    amp = 1.0
    depth = gap_m
    P = fft(pulse)
    dt = t[1] - t[0]
    freqs = fftfreq(len(t), dt)

    for i, (label, thick_in, Z_mrayl) in enumerate(config["layer_data"]):
        # same physics as in simulate_layer_physics, but avoid re‐calculating TT_fluid
        thickness = thick_in * INCH_TO_METER
        Z_curr = Z_mrayl * 1e6

        # attenuation only (skip dispersion to keep it simple)
        alpha0 = 0.5 + 0.1 * i
        n = 1.2 + 0.05 * i
        alpha_f = alpha0 * (np.abs(freqs) / 1e6) ** n * 100
        H = 10 ** (-alpha_f * thickness / 20)

        R = ((Z_curr - Z_prev) / (Z_curr + Z_prev)) ** 2
        T = 1 - R

        # defect overrides
        extra_delay = 0
        if config["defect_type"] == "Delamination" and i == config["defect_layer"] - 1:
            R, T = 0.7, 0.3
            extra_delay = 0.6
        if config["defect_type"] == "Crack" and i == config["defect_layer"] - 1:
            R, T = 0.5, 0.5

        P_i = P * H * T
        p_i = np.real(ifft(P_i))
        depth += thickness
        tau = (2 * depth / DEFAULT_VELOCITY) * 1e6 + extra_delay

        echo_i = R * np.interp(t, t - tau*1e-6, p_i, left=0, right=0)
        cumulative += echo_i
        steps.append((f"After {label}", cumulative.copy()))

        amp *= T
        Z_prev = Z_curr

    # 4) Plot each cumulative step
    for title, sig in steps:
        st.subheader(f"3) {title}")
        fig = go.Figure([go.Scatter(x=t*1e6, y=sig, name=title)])
        # mark fluid echo line
        fig.add_vline(x=TT_fluid, line_dash="dash", line_color="blue",
                      annotation_text="TT_fluid", annotation_position="top left")
        fig.update_layout(xaxis_title="Time (µs)", yaxis_title="Amplitude", height=300)
        st.plotly_chart(fig, use_container_width=True)

    # 5) Final FFT
    st.subheader("🔵 Final A-Scan Frequency Spectrum")
    fft_vals = np.abs(fft(steps[-1][1]))
    fig2 = go.Figure([go.Scatter(x=freqs[:len(freqs)//2]/1e6,
                                 y=fft_vals[:len(freqs)//2],
                                 name="FFT")])
    fig2.update_layout(xaxis_title="Frequency (MHz)", yaxis_title="Magnitude", height=300)
    st.plotly_chart(fig2, use_container_width=True)
