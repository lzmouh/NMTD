import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq
from config import INCH_TO_METER, DEFAULT_VELOCITY

def simulate_response(config):
    layer_data = config["layer_data"]
    Z_fluid = config["Z_fluid"]
    fluid_density = config["fluid_density"]
    defect_type = config["defect_type"]
    defect_layer = config["defect_layer"] - 1  # zero-indexed

    gap_m = 0.1 * INCH_TO_METER
    Z = Z_fluid * 1e6
    rho = fluid_density * 1000
    c = Z / rho
    TT_fluid = 2 * gap_m / c * 1e6  # µs

    times = [TT_fluid]
    amps = [1.0]
    depth = gap_m

    for i, (_, t_in, _) in enumerate(layer_data):
        depth += t_in * INCH_TO_METER
        t = 2 * depth / DEFAULT_VELOCITY * 1e6
        a = 1.0
        if defect_type == "Delamination" and i == defect_layer:
            t += 0.6
            a *= 0.6
        elif defect_type == "Crack" and i == defect_layer:
            a *= 0.5
        times.append(t)
        amps.append(a)

    t_axis = np.linspace(0, max(times) + 3, 3000)
    signal = np.zeros_like(t_axis)
    for t, a in zip(times, amps):
        signal += a * np.exp(-((t_axis - t) ** 2) / (2 * (0.05 ** 2)))
    signal += 0.01 * np.random.randn(len(signal))

    # Auto-crop to where signal has content
    threshold = 0.02
    cutoff = np.argmax(np.abs(signal[::-1]) > threshold)
    cutoff = len(signal) - cutoff if cutoff > 0 else len(signal)
    t_axis_cropped = t_axis[:cutoff]
    signal_cropped = signal[:cutoff]

    return t_axis_cropped, signal_cropped, times, amps, TT_fluid

def show_plots():
    st.title("📊 Ultrasonic Simulation Results")

    config = st.session_state["config"]
    t_axis, signal, echo_times, echo_amps, TT_fluid = simulate_response(config)

    st.subheader("📋 Simulation Parameters Table")
    df = pd.DataFrame(config["layer_data"], columns=["Layer", "Thickness (in)", "Z (MRayl)"])
    df["Echo Time (µs)"] = echo_times[1:]
    st.dataframe(df)

    show_perfect = st.checkbox("Show Perfect Pipe", True)
    superpose = st.checkbox("Superpose Perfect and Defect", True)

    # --- Time Domain Plot ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t_axis, y=signal, name="Defective Pipe", line=dict(color='red')))
    for t in echo_times:
        fig.add_vline(x=t, line_dash="dot", line_color="gray")
    fig.add_vline(x=TT_fluid, line_dash="dash", line_color="blue",
                  annotation_text=f"TT_fluid={TT_fluid:.2f} µs")
    fig.update_layout(
        title="🟢 Time-Domain A-Scan (Auto-cropped)",
        xaxis_title="Time (µs)", yaxis_title="Amplitude",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Frequency Domain Plot ---
    freqs = fftfreq(len(t_axis), 1e-6)
    fft_magnitude = np.abs(fft(signal))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=freqs[:len(freqs)//2], y=fft_magnitude[:len(freqs)//2],
        name="FFT Magnitude", line=dict(color='blue')
    ))
    fig2.update_layout(
        title="🔵 Frequency Domain",
        xaxis_title="Frequency (Hz)", yaxis_title="Magnitude",
        hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Optional Export ---
    st.markdown("### 📤 Export Results")
    export_df = df.copy()
    export_df["TT_fluid (µs)"] = TT_fluid
    st.download_button("📥 Download Table as CSV",
                       data=export_df.to_csv(index=False),
                       file_name="nmted_results.csv",
                       mime="text/csv")
    
