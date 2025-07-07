import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, ifft, fftfreq

# --- Physical Constants ---
INCH_TO_M = 0.0254
c0 = 2000          # base wave speed in solid (m/s)
dispersion_k = 0.1 # dispersion coefficient: c(f)=c0*(1 + k*(f/1MHz)^m)
dispersion_m = 1.2

# --- Layer Definition ---
# thickness_in_inches, Z (Rayl), alpha0 (dB/cm/MHz), n_exponent
LAYERS = [
    (0.1, 1.48e6, 0.01, 1.0),  # fluid
    (0.2, 2.0e6, 0.5, 1.2),
    (0.2, 2.2e6, 0.6, 1.3),
    (0.2, 2.4e6, 0.7, 1.4),
    (0.2, 2.6e6, 0.8, 1.5),
    (0.3, 2.8e6, 0.9, 1.6),
]

t, sig = simulate_with_defects(
        defect_type=None if def_type=="None" else def_type,
        defect_layer=layer_idx
    )
st.line_chart({"A-Scan": sig}, x=t*1e6)

def simulate_with_defects(defect_type=None, defect_layer=None):
    # time-base
    fs = 100e6
    t_max = 20e-6
    t = np.linspace(0, t_max, int(fs*t_max))
    dt = t[1] - t[0]

    # generate pulse
    f0 = 1e6
    pulse = np.sin(2*np.pi*f0*t)*np.exp(-((t-3/f0)**2)/(0.2e-6)**2)

    # FFT
    freqs = fftfreq(len(t), dt)
    P = fft(pulse)

    # build A-scan
    A_scan = np.zeros_like(t)
    Z_prev = LAYERS[0][1]
    depth = 0.0

    for idx, (th_in, Z_i, alpha0, n) in enumerate(LAYERS):
        # convert
        th = th_in * INCH_TO_M
        depth += th

        # dispersion: frequency-dependent speed
        c_f = c0*(1 + dispersion_k*(np.abs(freqs)/1e6)**dispersion_m)

        # attenuation
        alpha_f = alpha0 * (np.abs(freqs)/1e6)**n * 100  # dB/m
        H = np.exp(-alpha_f * th / 20*np.log(10))

        # interface R/T
        R = ((Z_i - Z_prev)/(Z_i + Z_prev))**2
        T = 1 - R

        # defect override
        if defect_type=="Delamination" and idx==defect_layer:
            # delamination acts like a fluid layer: strong R, low T
            R = 0.7; T = 0.3
        if defect_type=="Crack" and idx==defect_layer:
            # crack partial reflection & transmission
            R = 0.5; T = 0.5

        # two-way travel time (frequency averaged)
        c_avg = np.mean(c_f)
        tau = 2*depth/c_avg

        # attenuate & shift in freq domain
        P_i = P * H * T
        # back to time
        p_i = np.real(ifft(P_i))

        # shift
        shifted = np.interp(t, t - tau, p_i * R, left=0, right=0)
        A_scan += shifted

        Z_prev = Z_i

    # plot
    plt.figure(figsize=(10,4))
    plt.plot(t*1e6, A_scan, label="A-Scan")
    plt.title(f"A-Scan with {defect_type or 'No'} Defect")
    plt.xlabel("Time (µs)")
    plt.ylabel("Amplitude")
    plt.grid()
    plt.legend()
    plt.show()

    return t, A_scan
