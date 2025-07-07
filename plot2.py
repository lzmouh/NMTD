import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq

from config import DEFAULT_VELOCITY, INCH_TO_METER

def compute_dispersion(freq):
    """Frequency-dependent velocity dispersion model."""
    return DEFAULT_VELOCITY * (1 + 0.01 * np.log10(freq / 1e5 + 1))

def compute_attenuation(freq, base_alpha=0.5):
    """Frequency-dependent attenuation (dB/inch)."""
    return base_alpha * (freq / 1e6)

def reflection_coeff(Z1, Z2):
    return (Z2 - Z1) / (Z2 + Z1)

def transmission_coeff(Z1, Z2):
    return 2 * Z2 / (Z2 + Z1)

def simulate_signal(layer_data, Z_fluid, fluid_density, defect_type=None, defect_layer=None):
    freq = 1e6  # 1 MHz center frequency
    v_fluid = Z_fluid * 1e6 / (fluid_density * 1000)
    gap_m = 0.1 * INCH_TO_METER
    TT_fluid = 2 * gap_m / v_fluid * 1e6

    times, amps = [TT_fluid], [1.0]
    current_depth = gap_m
    current_Z = Z_fluid
    signal_amp = 1.0

    for i, (_, thickness_in, Z) in enumerate(layer_data):
        thickness_m = thickness_in * INCH_TO_METER
        next_Z = Z
        v_layer = compute_dispersion(freq)
        alpha = compute_attenuation(freq)
        
        refl = reflection_coeff(current_Z, next_Z)
        trans = transmission_coeff(current_Z, next_Z)

        current_depth += thickness_m
        t = 2 * current_depth / v_layer * 1e6
        a = signal_amp * trans * np.exp(-alpha * thickness_in)

        if defect_type == "Delamination" and i == defect_layer:
            t += 0.5
            a *= 0.5
        elif defect_type == "Crack" and i == defect_layer:
            a *= 0.2

        times.append(t)
        amps.append(a)
        current_Z = next_Z

    t_axis = np.linspace(0, max(times)+3, 3000)
    signal = np.zeros_like(t_axis)
    for t, a in zip(times, amps):
        signal += a * np.exp(-((t_axis - t)**2)/(2*(0.05**2)))
    signal += 0.01 * np.random.randn(len(t_axis))

    return t_axis, signal, times, amps, TT_fluid

def show_plots2():
    st.title("📊 Simulation Results")

    config = st.session_state["config"]
    layer_data = config["layer_data"]
    Z_fluid = config["Z_fluid"]
    fluid_density = config["fluid_density"]
    defect_type = config["defect_type"]
    defect_layer = config["defect_layer"] - 1 if config["defect_layer"] > 0 else None

    # Display parameters
    st.subheader("📋 Simulation Parameters")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Fluid Properties**")
        fluid_df = pd.DataFrame([{
            "Fluid": config["fluid"],
            "Z_fluid (MRayl)": Z_fluid,
            "Density (g/cc)": fluid_density,
            "Velocity (m/s)": config["fluid_velocity"]
        }])
        st.dataframe(fluid_df, use_container_width=True)

    with c2:
        st.markdown("**Defect Settings**")
        defect_df = pd.DataFrame([{
            "Defect Type": defect_type,
            "Defect Layer Index": defect_layer + 1 if defect_layer is not None else "-"
        }])
        st.dataframe(defect_df, use_container_width=True)

    st.markdown("**Pipe Layers**")
    layers_df = pd.DataFrame(layer_data, columns=["Layer", "Thickness (in)", "Z (MRayl)"])
    st.dataframe(layers_df, use_container_width=True)

    # Simulation
    t_p, s_p, e_p, a_p, TT_p = simulate_signal(layer_data, Z_fluid, fluid_density)
    t_d, s_d, e_d, a_d, TT_d = simulate_signal(layer_data, Z_fluid, fluid_density,
                                               defect_type if defect_type != "None" else None,
                                               defect_layer)

    show_perfect = st.checkbox("Show Perfect Pipe", True)
    superpose = st.checkbox("Superpose Perfect and Defect", True)

    # Time Domain Plot
    fig = go.Figure()
    if show_perfect and superpose:
        fig.add_trace(go.Scatter(x=t_p, y=s_p, name="Perfect Pipe", line=dict(color="green", dash="dash")))
    fig.add_trace(go.Scatter(x=t_d, y=s_d, name="Defective Pipe", line=dict(color="red")))

    for i, t in enumerate(e_d):
        label = f"Layer {i+1}" if i > 0 else "TT_fluid"
        fig.add_vline(x=t, line_color="blue", line_dash="dot",
                      annotation_text=label, annotation_position="top right")

    fig.update_layout(title="🟢 Time Domain Response",
                      xaxis_title="Time (µs)",
                      yaxis_title="Amplitude",
                      hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # Frequency Domain Plot
    freqs = fftfreq(len(t_d), 1e-6)
    fft_d = np.abs(fft(s_d))
    fft_p = np.abs(fft(s_p))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=freqs[:len(freqs)//2], y=fft_d[:len(freqs)//2],
                              name="Defective Pipe", line=dict(color='red')))
    if show_perfect and superpose:
        fig2.add_trace(go.Scatter(x=freqs[:len(freqs)//2], y=fft_p[:len(freqs)//2],
                                  name="Perfect Pipe", line=dict(dash='dash')))
    fig2.update_layout(title="🔵 Frequency Spectrum",
                       xaxis_title="Frequency (Hz)",
                       yaxis_title="Amplitude")
    st.plotly_chart(fig2, use_container_width=True)
