import numpy as np
import pandas as pd
from scipy.signal import chirp, fftconvolve, butter, sosfilt, windows
from scipy.fft import fft, fftfreq
from config import INCH_TO_METER, DEFAULT_GAP_INCH

def generate_tx_chirp(fs, sweep_us, f_start_mhz, f_end_mhz):
    sweep_s = sweep_us * 1e-6  # Convert µs to seconds
    f_start = f_start_mhz * 1e6
    f_end = f_end_mhz * 1e6

    n = int(fs * sweep_s)
    t_chirp = np.linspace(0, sweep_s, n, endpoint=False)
    tx = chirp(t_chirp, f0=f_start, f1=f_end, t1=sweep_s, method='linear')
    tx *= windows.tukey(n, alpha=0.1)
    return t_chirp, tx

def calculate_group_delay(tx, fs):
    spectrum = fft(tx)
    freqs = fftfreq(len(tx), d=1/fs)
    phase = np.unwrap(np.angle(spectrum))
    dphi_df = np.gradient(phase, freqs)
    mask = (freqs > 1e6) & (freqs < 5e6)
    return np.mean(dphi_df[mask])

def bandpass_filter(signal, fs, fmin, fmax, order=4):
    sos = butter(order, [fmin, fmax], btype='bandpass', fs=fs, output='sos')
    return sosfilt(sos, signal)

def simulate_multimode(config):
    fs = config["sampling_rate"]
    t_chirp = np.array(config["t_chirp"])
    tx = np.array(config["tx"])
    fluid_vel = config["fluid_velocity"]
    defect = config["defect_type"]
    defect_i = config["defect_layer"] - 1
    layers = config["layer_data"]
    f0_mhz = (config["f_start_mhz"] + config["f_end_mhz"]) / 2

    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for lyr in layers:
        depths.append(depths[-1] + lyr["thickness"] * INCH_TO_METER)

    R_list, T_list = [], []
    Z_prev = config["Z_fluid"]
    for lyr in layers:
        Z_curr = lyr["Z"]
        R = (Z_curr - Z_prev) / (Z_curr + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_curr

    # Mode list includes fluid gap + each layer's acoustic properties
    modes = [(fluid_vel, 0.0, 0.0)] + [
        (lyr["v"], lyr.get("alpha0", 0.05), lyr.get("n_exp", 1.2)) for lyr in layers
    ]

    max_delay = 2 * depths[-1] / min([v for v, _, _ in modes])
    n_rx = int(fs * (max_delay + len(t_chirp)/fs + 10e-6))
    rx = np.zeros(n_rx)
    t_rx = np.arange(n_rx) / fs

    freqs = fftfreq(len(tx), d=1/fs)
    P = fft(tx)
    beta = 0.05  # dispersion coefficient
    records = []

    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        for i, depth in enumerate(depths):
            tau_s = 2 * depth / v
            alpha_f = alpha0 * (np.abs(freqs)/1e6)**n_exp * 100  # dB/m
            H = 10 ** (-alpha_f * depth / 20)
            c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D = np.exp(-1j * 2 * np.pi * freqs * (2 * depth / c_f))
            P_i = P * H * D
            p_i = np.real(np.fft.ifft(P_i))

            if i == 0:
                R = -1.0
                T = 1.0
            else:
                R = R_list[i-1]
                T = T_list[i-1]

            # Defect attenuation
            if defect == "Delamination" and (i-1) == defect_i:
                R *= 0.7
                T *= 0.7
            elif defect == "Crack" and (i-1) == defect_i:
                R *= 0.5
                T *= 0.5

            amp = abs(R)
            group_delay = len(tx) // 2 / fs 
            idx = int(round((tau_s - group_delay) * fs))
            start = idx - len(p_i) // 2
            end = start + len(p_i)
            if 0 <= start and end <= len(rx):
                rx[start:end] += amp * p_i
    
            # --- Table output record ---
            if i == 0:
                records.append({
                    "Mode": m_idx + 1,
                    "Layer": "Fluid Gap",
                    "Thickness (in)": round(DEFAULT_GAP_INCH, 3),
                    "Z (MRayl)": round(config["Z_fluid"], 3),
                    "α₀": 0.0,
                    "n exp": 0.0,
                    "R": round(R, 3),
                    "T": round(T, 3),
                    "Time (µs)": round(tau_s * 1e6, 2),
                    "Amp": round(amp, 3)
                })
            elif i > 0:
                lyr = layers[i-1]
                records.append({
                    "Mode": m_idx + 1,
                    "Layer": lyr["name"],
                    "Thickness (in)": round(lyr["thickness"], 3),
                    "Z (MRayl)": round(lyr["Z"], 3),
                    "α₀": round(lyr.get("alpha0", alpha0), 3),
                    "n exp": round(lyr.get("n_exp", n_exp), 3),
                    "R": round(R, 3),
                    "T": round(T, 3),
                    "Time (µs)": round(tau_s * 1e6, 2),
                    "Amp": round(amp, 3)
                })

    # Pulse compression
    compressed = fftconvolve(rx, tx[::-1], mode='same')
    df = pd.DataFrame.from_records(records)

    return t_rx, rx, compressed, freqs, df
