# plots.py

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq, ifft
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def simulate_layer_physics(config):
    layers = config["layer_data"]
    Z_fluid = config["Z_fluid"] * 1e6  # Convert MRayl to Rayl
    rho_fluid = config["fluid_density"] * 1000  # g/cc to kg/m³
    defect = config["defect_type"]
    defect_idx = config["defect_layer"] - 1

    fs = 100e6
    t_max = 20e-6
    t = np.linspace(0, t_max, int(fs * t_max))
    dt = t[1] - t[0]

    f0 = 1e6
    pulse = np.sin(2 * np.pi * f0 * t) * np.exp(-((t - 3 / f0) ** 2) / (0.2e-6) ** 2)
    P = fft(pulse)
    freqs = fftfreq(len(t), dt)

    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    c_fluid = Z_fluid / rho_fluid
    TT_fluid = 2 * gap_m / c_fluid * 1e6

    A_scan = np.zeros_like(t)
    A_scan += np.interp(t, t - TT_fluid, pulse, left=0, right=0)

    results = []
    Z_prev = Z_fluid
    amp = 1.0
    depth = gap_m

    for i, layer in enumerate(layers):
        if len(layer) == 3:
            label, thick_in, Z_mrayl = layer
        else:
            label = f"Layer {i+1}"
            thick_in = layer[0] if len(layer) > 0 else 0.2
            Z_mrayl = layer[1] if len(layer) > 1 else 2.5
    
        thick_m = thick_in * INCH_TO_METER
        Z_curr = Z_mrayl * 1e6
    
        alpha0 = 0.5 + 0.1 * i
        n = 1.2 + 0.05 * i
        alpha_f = alpha0 * (np.abs(freqs) / 1e6) ** n * 100  # dB/m
        H = 10 ** (-alpha_f * thick_m / 20)
    
        R = ((Z_curr - Z_prev) / (Z_curr + Z_prev)) ** 2
        T = 1 - R
    
        extra_delay = 0
        if defect == "Delamination" and i == defect_idx:
            R, T = 0.7, 0.3
            extra_delay = 0.6
        elif defect == "Crack" and i == defect_idx:
            R, T = 0.5, 0.5
    
        P_i = P * H * T
        p_i = np.real(ifft(P_i))
    
        depth += thick_m
        tau = (2 * depth / DEFAULT_VELOCITY) * 1e6 + extra_delay
    
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
            "Amp Echo": round(R * amp, 3),
        })
    
        amp *= T
        Z_prev = Z_curr
        
        df = pd.DataFrame(results)
        return t, A_scan, freqs, df, TT_fluid

def show_plots2():
    st.title("📊 Ultrasonic A-Scan Simulation Results")

    config = st.session_state["config"]
    t, A_scan, freqs, df_results, TT_fluid = simulate_layer_physics(config)

    # --- Parameters Table ---
    st.subheader("🔧 Simulation Parameters")
    inputs = {
        "Fluid": config["fluid"],
        "Fluid Density (g/cc)": config["fluid_density"],
        "Z_fluid (MRayl)": config["Z_fluid"],
        "Fluid Velocity (m/s)": round(config["fluid_velocity"], 1),
        "Number of Layers": config["num_layers"],
        "Total Thickness (in)": config["total_thickness"],
        "Defect Type": config["defect_type"],
        "Defect Layer Index": config["defect_layer"]
    }
    st.table(pd.DataFrame(inputs.items(), columns=["Parameter", "Value"]))

    # --- Per-Layer Table ---
    st.subheader("📋 Layer-by-Layer Echo Parameters")
    st.dataframe(df_results)

    # --- Time Domain Plot ---
    st.subheader("🟢 Time-Domain A-Scan")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t * 1e6, y=A_scan, name="A-Scan", line=dict(color='firebrick')))
    fig.add_vline(x=TT_fluid, line_dash="dash", line_color="blue",
                  annotation_text="Fluid Echo", annotation_position="top left")
    for _, row in df_results.iterrows():
        fig.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                      annotation_text=row["Layer"], annotation_position="top right")
    fig.update_layout(
        xaxis_title="Time (µs)",
        yaxis_title="Amplitude",
        height=400,
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Frequency Domain Plot ---
    st.subheader("🔵 Frequency-Domain Spectrum")
    fft_vals = np.abs(fft(A_scan))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=freqs[:len(freqs) // 2] / 1e6,
        y=fft_vals[:len(freqs) // 2],
        name="FFT", line=dict(color='royalblue')
    ))
    fig2.update_layout(
        xaxis_title="Frequency (MHz)",
        yaxis_title="Magnitude",
        height=300,
        hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Export ---
    st.subheader("📤 Export Data")
    csv = df_results.to_csv(index=False).encode()
    st.download_button("📥 Download Echo Table (CSV)", csv, "echo_parameters.csv", "text/csv")

    # Export plots (requires kaleido)
    if st.button("Export Time-Domain Plot (PNG)"):
        fig.write_image("a_scan_plot.png")
        with open("a_scan_plot.png", "rb") as f:
            st.download_button("⬇ Download A-Scan Plot", f.read(), "a_scan_plot.png", "image/png")

    if st.button("Export Frequency Plot (PNG)"):
        fig2.write_image("fft_plot.png")
        with open("fft_plot.png", "rb") as f:
            st.download_button("⬇ Download FFT Plot", f.read(), "fft_plot.png", "image/png")
