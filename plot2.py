import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq, ifft
from config import DEFAULT_CONFIG

def simulate_with_extensions(layer_data, Z_fluid, fluid_density, defect_type=None, defect_layer=None):
    INCH_TO_M = 0.0254
    c0 = 2000
    dispersion_k = 0.1
    dispersion_m = 1.2

    fs = 100e6
    t_max = 20e-6
    t = np.linspace(0, t_max, int(fs * t_max))
    dt = t[1] - t[0]

    f0 = 1e6
    pulse = np.sin(2 * np.pi * f0 * t) * np.exp(-((t - 3 / f0) ** 2) / (0.2e-6) ** 2)
    freqs = fftfreq(len(t), dt)
    P = fft(pulse)

    A_scan = np.zeros_like(t)
    Z_prev = Z_fluid * 1e6
    depth = 0.1 * INCH_TO_M

    c_f = c0 * (1 + dispersion_k * (np.abs(freqs) / 1e6) ** dispersion_m)
    c_avg = np.mean(c_f)
    tau_fluid = 2 * depth / c_avg
    A_scan += np.interp(t, t - tau_fluid, pulse, left=0, right=0)

    for idx, (_, t_in, Z_i) in enumerate(layer_data):
        th = t_in * INCH_TO_M
        depth += th
        alpha0 = 0.8 + 0.2 * idx
        n = 1.2 + 0.1 * idx
        alpha_f = alpha0 * (np.abs(freqs) / 1e6) ** n * 100
        H = np.exp(-alpha_f * th / 20 * np.log(10))

        R = ((Z_i * 1e6 - Z_prev) / (Z_i * 1e6 + Z_prev)) ** 2
        T = 1 - R

        if defect_type == "Delamination" and idx == defect_layer:
            R = 0.7
            T = 0.3
        elif defect_type == "Crack" and idx == defect_layer:
            R = 0.5
            T = 0.5

        P_i = P * H * T
        p_i = np.real(ifft(P_i))
        tau = 2 * depth / c_avg
        shifted = np.interp(t, t - tau, p_i * R, left=0, right=0)
        A_scan += shifted
        Z_prev = Z_i * 1e6

    return t, A_scan, tau_fluid


def show_plots():
    config = st.session_state.get("config", DEFAULT_CONFIG)
    layer_data = config["layer_data"]
    Z_fluid = config["Z_fluid"]
    fluid_density = config["fluid_density"]
    defect_type = config["defect_type"]
    defect_layer = config["defect_layer"] - 1

    t_d, s_d, TT_d = simulate_with_extensions(
        layer_data, Z_fluid, fluid_density,
        defect_type if defect_type != "None" else None,
        defect_layer if defect_type != "None" else None
    )

    show_fft = st.checkbox("Show Frequency Domain", True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t_d * 1e6, s_d, label="Simulated A-Scan")
    ax.axvline(TT_d * 1e6, color='blue', linestyle='--', label=f"TT_fluid = {TT_d*1e6:.2f} µs")
    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Amplitude")
    ax.grid(True)
    ax.legend()
    ax.set_title("A-Scan with Defect")
    st.pyplot(fig)

    if show_fft:
        fft_vals = np.abs(fft(s_d))
        freqs = fftfreq(len(t_d), t_d[1] - t_d[0])
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.plot(freqs[:len(freqs)//2] / 1e6, fft_vals[:len(freqs)//2])
        ax2.set_xlabel("Frequency (MHz)")
        ax2.set_ylabel("Magnitude")
        ax2.set_title("FFT of A-Scan")
        ax2.grid(True)
        st.pyplot(fig2)
