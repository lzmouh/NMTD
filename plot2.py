# plots.py

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq, ifft
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY


def simulate_layer_physics(config):
    layers = config["layer_data"]
    Z_fluid = config["Z_fluid"] * 1e6
    rho_fluid = config["fluid_density"] * 1000
    defect = config["defect_type"]
    defect_idx = config["defect_layer"] - 1

    # --- Time axis ---
    fs = 100e6  # Hz
    t_max = 25e-6
    t = np.linspace(0, t_max, int(fs * t_max))
    dt = t[1] - t[0]

    # --- Transducer pulse ---
    f0 = 1e6
    pulse = np.sin(2 * np.pi * f0 * t) * np.exp(-((t - 3 / f0) ** 2) / (0.2e-6) ** 2)
    P = fft(pulse)
    freqs = fftfreq(len(t), dt)

    # --- Fluid gap ---
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    c_fluid = Z_fluid / rho_fluid
    TT_fluid = 2 * gap_m / c_fluid * 1e6  # µs

    A_scan = np.zeros_like(t)
    A_scan += np.interp(t, t - TT_fluid, pulse, left=0, right=0)

    results = []
    Z_prev = Z_fluid
    amp = 1.0
    depth = gap_m

    for i, (label, thick_in, Z_mrayl) in enumerate(layers):
        thickness = thick_in * INCH_TO_METER
        Z_curr = Z_mrayl * 1e6

        # --- Dispersion model ---
        base_velocity = DEFAULT_VELOCITY
        dispersion_coeff = 0.01  # velocity decrease per MHz
        c_layer = base_velocity - dispersion_coeff * (np.abs(freqs) / 1e6)
        c_layer = np.clip(c_layer, 500, base_velocity)

        # --- Attenuation model ---
        alpha0 = 0.5 + 0.1 * i
        n = 1.2 + 0.05 * i
        alpha_f = alpha0 * (np.abs(freqs) / 1e6) ** n * 100  # dB/m
        H = 10 ** (-alpha_f * thickness / 20)

        # --- Reflection and transmission ---
        R = ((Z_curr - Z_prev) / (Z_curr + Z_prev)) ** 2
        T = 1 - R

        # --- Defect overrides ---
        if defect == "Delamination" and i == defect_idx:
            R, T = 0.7, 0.3
            extra_delay = 0.6  # µs
        else:
            extra_delay = 0
        if defect == "Crack" and i == defect_idx:
            R, T = 0.5, 0.5

        # --- Signal propagation ---
        P_i = P * H * T
        p_i = np.real(ifft(P_i))
        depth += thickness
        tau = (2 * depth / base_velocity) * 1e6 + extra_delay
        echo = R * np.interp(t, t - tau, p_i, left=0, right=0)
        A_scan += echo

        results.append({
            "Layer": label,
            "Thickness (in)": thick_in,
            "Z (MRayl)": Z_mrayl,
            "α0 (dB/cm/MHz)": round(alpha0, 2),
            "n exponent": round(n, 2),
            "Refl Coef": round(R, 3),
            "Trans Coef": round(T, 3),
            "Time (µs)": round(tau, 2),
            "Amp Echo": round(R * amp, 3)
        })

        amp *= T
        Z_prev = Z_curr

    df = pd.DataFrame(results)
    return t, A_scan, freqs, df, TT_fluid


def show_plots2():
    st.title("📊 Ultrasonic A-Scan Simulation Results (Intermediate Steps)")

    # Retrieve config and run the core sim to get timing & layer table
    config = st.session_state["config"]
    t, _, freqs, df_results, TT_fluid = simulate_layer_physics(config)

    # 1) Generate the base transducer pulse
    f0 = 1e6
    pulse = np.sin(2 * np.pi * f0 * t) * np.exp(-((t - 3 / f0) ** 2) / (0.2e-6) ** 2)

    # 2) Fluid echo only
    fluid_only = np.interp(t, t - TT_fluid, pulse, left=0, right=0)

    # 3) Build cumulative A-scan step-by-step
    cumulative = fluid_only.copy()
    steps = [
        ("Pulse (no propagation)", pulse),
        ("Fluid-gap echo only", fluid_only)
    ]

    # Prepare constants
    layers = config["layer_data"]
    Z_prev = config["Z_fluid"] * 1e6
    amp = 1.0
    depth = DEFAULT_GAP_INCH * INCH_TO_METER

    # Repeat the propagation loop but accumulate echoes one layer at a time
    fs = 100e6
    dt = t[1] - t[0]
    P = fft(pulse)
    freqs = fftfreq(len(t), dt)

    for i, (label, thick_in, Z_mrayl) in enumerate(layers):
        thickness = thick_in * INCH_TO_METER
        Z_curr = Z_mrayl * 1e6

        # Attenuation
        alpha0 = 0.5 + 0.1 * i
        n = 1.2 + 0.05 * i
        alpha_f = alpha0 * (np.abs(freqs) / 1e6) ** n * 100
        H = 10 ** (-alpha_f * thickness / 20)

        # R/T
        R = ((Z_curr - Z_prev)/(Z_curr + Z_prev))**2
        T = 1 - R

        # Defect overrides
        extra_delay = 0
        if config["defect_type"]=="Delamination" and i==config["defect_layer"]-1:
            R, T = 0.7, 0.3
            extra_delay = 0.6
        if config["defect_type"]=="Crack" and i==config["defect_layer"]-1:
            R, T = 0.5, 0.5

        # Build echo for this layer
        P_i = P * H * T
        p_i = np.real(ifft(P_i))
        depth += thickness
        tau = 2 * depth / DEFAULT_VELOCITY * 1e6 + extra_delay
        echo_i = R * np.interp(t, t - tau, p_i, left=0, right=0)

        # Accumulate and store
        cumulative += echo_i
        steps.append((f"After {label} echo", cumulative.copy()))

        # Update for next
        amp *= T
        Z_prev = Z_curr

    # 4) Plot each step
    for title, sig in steps:
        st.subheader(title)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t*1e6, y=sig, name=title))
        # mark fluid echo on all
        fig.add_vline(x=TT_fluid, line_dash="dash", line_color="blue",
                      annotation_text="TT_fluid", annotation_position="top left")
        fig.update_layout(xaxis_title="Time (µs)", yaxis_title="Amplitude",
                          height=300, margin={"t":30})
        st.plotly_chart(fig, use_container_width=True)

    # 5) Finally show the layer-by-layer table
    st.subheader("📋 Layer-by-Layer Echo Parameters")
    st.dataframe(df_results)

    # 6) Frequency domain of final A-scan
    st.subheader("🔵 Final A-Scan Frequency Spectrum")
    fft_vals = np.abs(fft(cumulative))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=freqs[:len(freqs)//2]/1e6,
        y=fft_vals[:len(freqs)//2],
        name="FFT"
    ))
    fig2.update_layout(xaxis_title="Frequency (MHz)", yaxis_title="Magnitude", height=300)
    st.plotly_chart(fig2, use_container_width=True)

    # 7) Export options (as before)...
