# plots.py

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq, ifft
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def simulate_layer_physics(config):
    """
    Full ultrasonic simulation:
      • frequency-dependent dispersion c(f)
      • per-layer attenuation α(f)
      • reflection & transmission at each interface
      • defect overrides (delamination, crack)
    """
    layers     = config["layer_data"]
    Z_fluid    = config["Z_fluid"] * 1e6
    rho_fluid  = config["fluid_density"] * 1000
    defect     = config["defect_type"]
    defect_idx = config["defect_layer"] - 1

    # Time axis (0 to 25 µs at 100 MHz sample rate)
    fs    = 100e6
    t_max = 25e-6
    t     = np.linspace(0, t_max, int(fs * t_max))
    dt    = t[1] - t[0]

    # Transducer pulse (1 MHz centre)
    f0    = 1e6
    pulse = np.sin(2 * np.pi * f0 * t) \
            * np.exp(-((t - 3 / f0) ** 2) / (0.2e-6) ** 2)
    P     = fft(pulse)
    freqs = fftfreq(len(t), dt)

    # Fluid gap echo
    gap_m    = DEFAULT_GAP_INCH * INCH_TO_METER
    c_fluid  = Z_fluid / rho_fluid
    TT_fluid = 2 * gap_m / c_fluid * 1e6  # µs

    # start A-scan with fluid echo
    A_scan = np.zeros_like(t)
    A_scan += np.interp(t, t - TT_fluid*1e-6, pulse, left=0, right=0)

    results = []
    Z_prev = Z_fluid
    amp    = 1.0
    depth  = gap_m

    for i, (label, thick_in, Z_mrayl) in enumerate(layers):
        thickness = thick_in * INCH_TO_METER
        Z_curr    = Z_mrayl * 1e6

        # Dispersion (simple linear model)
        beta   = 0.01  # m/s per MHz
        c_layer = DEFAULT_VELOCITY + beta * (np.abs(freqs) / 1e6)
        delay  = 2 * thickness / c_layer  # two-way
        phase_shift = np.exp(-1j * 2 * np.pi * freqs * delay)

        # Attenuation α(f) = α0·(f/1MHz)^n  [dB/cm/MHz]
        alpha0 = 0.5 + 0.1 * i
        n      = 1.2 + 0.05 * i
        alpha_f = alpha0 * (np.abs(freqs) / 1e6) ** n * 100  # dB/m
        H       = 10 ** (-alpha_f * thickness / 20)

        # Reflection & transmission
        R = ((Z_curr - Z_prev) / (Z_curr + Z_prev)) ** 2
        T = 1 - R

        # Defect overrides
        extra_delay = 0
        if defect == "Delamination" and i == defect_idx:
            R, T = 0.7, 0.3
            extra_delay = 0.6
        elif defect == "Crack" and i == defect_idx:
            R, T = 0.5, 0.5

        # Build layer echo
        P_i = P * phase_shift * H * T
        p_i = np.real(ifft(P_i))
        depth += thickness
        tau   = (2 * depth / DEFAULT_VELOCITY) * 1e6 + extra_delay
        echo  = R * np.interp(t, t - tau*1e-6, p_i, left=0, right=0)
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
            "Amp Echo": round(R * amp, 3),
        })

        amp    *= T
        Z_prev  = Z_curr

    df = pd.DataFrame(results)
    return t, A_scan, freqs, df, TT_fluid


def show_plots2():
    st.title("📊 Ultrasonic A-Scan Simulation Results")

    config = st.session_state["config"]
    t, A_scan, freqs, df_results, TT_fluid = simulate_layer_physics(config)

    # 1) Input summary
    st.subheader("🔧 Simulation Inputs & Constants")
    summary = {
        "Fluid": config["fluid"],
        "Fluid Density (g/cc)": config["fluid_density"],
        "Z_fluid (MRayl)": config["Z_fluid"],
        "Num Layers": config["num_layers"],
        "Total Thickness (in)": config["total_thickness"],
        "Defect Type": config["defect_type"],
        "Defect Layer": config["defect_layer"],
    }
    st.table(pd.DataFrame(summary.items(), columns=["Parameter", "Value"]))

    # 2) Layer echo table
    st.subheader("📋 Layer-by-Layer Echo Parameters")
    st.dataframe(df_results, use_container_width=True)

    # 3) Full A-scan plot (no cropping)
    st.subheader("🟢 Time-Domain A-Scan (Full)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t * 1e6, y=A_scan,
        name="A-Scan", line=dict(color="firebrick")
    ))
    # mark fluid echo
    fig.add_vline(x=TT_fluid, line_dash="dash", line_color="blue",
                  annotation_text="Fluid Echo", annotation_position="top left")
    # mark each layer echo
    for _, row in df_results.iterrows():
        fig.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                      annotation_text=row["Layer"], annotation_position="top right")
    fig.update_layout(
        xaxis_title="Time (µs)",
        yaxis_title="Amplitude",
        hovermode="x unified",
        height=450
    )
    st.plotly_chart(fig, use_container_width=True)

    # 4) Frequency-domain plot
    st.subheader("🔵 Frequency-Domain Spectrum")
    fft_vals = np.abs(fft(A_scan))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=freqs[:len(freqs)//2] / 1e6,
        y=fft_vals[:len(freqs)//2],
        name="FFT", line=dict(color="navy")
    ))
    fig2.update_layout(
        xaxis_title="Frequency (MHz)",
        yaxis_title="Magnitude",
        height=350,
        hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)
