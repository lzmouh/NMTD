import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq
from io import BytesIO
from config import INCH_TO_METER, DEFAULT_VELOCITY

def simulate(layer_data, Z_fluid, fluid_density, defect_type=None, defect_layer=None):
    gap_m = 0.1 * INCH_TO_METER  # fixed gap
    Z = Z_fluid * 1e6  # Rayl
    rho = fluid_density * 1000  # kg/m³
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

    t_axis = np.linspace(0, max(times) + 2, 3000)
    signal = np.zeros_like(t_axis)
    for t, a in zip(times, amps):
        signal += a * np.exp(-((t_axis - t) ** 2) / (2 * (0.05 ** 2)))
    signal += 0.01 * np.random.randn(len(signal))
    return t_axis, signal, times, amps, TT_fluid

def show_plots():
    st.title("📊 Simulation Results")

    config = st.session_state["config"]
    layer_data = config["layer_data"]
    Z_fluid = config["Z_fluid"]
    fluid_density = config["fluid_density"]
    defect_type = config["defect_type"]
    defect_layer = config["defect_layer"] - 1

    show_perfect = st.checkbox("Show Perfect Pipe", True)
    superpose = st.checkbox("Superpose Perfect and Defect", True)

    # Run simulation
    t_p, s_p, e_p, a_p, TT_p = simulate(layer_data, Z_fluid, fluid_density)
    t_d, s_d, e_d, a_d, TT_d = simulate(
        layer_data, Z_fluid, fluid_density,
        defect_type if defect_type != "None" else None,
        defect_layer if defect_type != "None" else None
    )

    # --- Time Domain Plot ---
    fig = go.Figure()
    if show_perfect and superpose:
        fig.add_trace(go.Scatter(x=t_p, y=s_p, name="Perfect Pipe", line=dict(dash='dash', color='green')))
    fig.add_trace(go.Scatter(x=t_d, y=s_d, name="Defective Pipe", line=dict(color='red')))
    for t in e_d:
        fig.add_vline(x=t, line_dash="dot", line_color="gray")
    fig.add_vline(x=TT_d, line_dash="dash", line_color="blue",
                  annotation_text=f"TT_fluid={TT_d:.2f} µs")
    fig.update_layout(title="🟢 A-Scan (Time Domain)",
                      xaxis_title="Time (µs)", yaxis_title="Amplitude",
                      hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # --- Frequency Domain Plot ---
    freqs = fftfreq(len(t_d), 1e-6)
    fft_d = np.abs(fft(s_d))
    fft_p = np.abs(fft(s_p))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=freqs[:len(freqs)//2], y=fft_d[:len(freqs)//2],
                              name="Defective Pipe", line=dict(color='red')))
    if show_perfect and superpose:
        fig2.add_trace(go.Scatter(x=freqs[:len(freqs)//2], y=fft_p[:len(freqs)//2],
                                  name="Perfect Pipe", line=dict(dash='dash')))
    fig2.update_layout(title="🔵 Frequency Domain",
                       xaxis_title="Frequency (Hz)", yaxis_title="Magnitude")
    st.plotly_chart(fig2, use_container_width=True)

    st.success(f"Simulation complete. TT_fluid = {TT_d:.2f} µs")

    # --- Export button for raw signal plot ---
    export_fig = plt.figure(figsize=(10, 4))
    ax = export_fig.add_subplot(111)
    ax.plot(t_d, s_d, label="Defective Pipe", color='red')
    if show_perfect and superpose:
        ax.plot(t_p, s_p, label="Perfect Pipe", linestyle='--', color='green')
    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Amplitude")
    ax.set_title("A-Scan Export")
    ax.legend()
    ax.grid(True)

    buf = BytesIO()
    export_fig.savefig(buf, format="png")
    st.download_button("📥 Download A-Scan Plot (PNG)", data=buf.getvalue(),
                       file_name="ascans_plot.png", mime="image/png")
