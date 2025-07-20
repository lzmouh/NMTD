import numpy as np
import pandas as pd
from scipy.signal import chirp, fftconvolve, butter, sosfilt, windows
from scipy.fft import fft, ifft, fftfreq
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
    # --- Unpack configuration ---
    fs = config["sampling_rate"]
    t_chirp = np.array(config["t_chirp"])
    tx = np.array(config["tx"])
    fluid_vel = config["fluid_velocity"]
    defect_type = config["defect_type"]
    defect_idx = config["defect_layer"] - 1
    layers = config["layer_data"]
    f0_mhz = (config["f_start_mhz"] + config["f_end_mhz"]) / 2

    # --- Interface depths (in meters) ---
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]  # fluid gap
    for layer in layers:
        depths.append(depths[-1] + layer["thickness"] * INCH_TO_METER)

    # --- Reflection and transmission coefficients ---
    R_list, T_list = [], []
    Z_prev = config["Z_fluid"]
    for layer in layers:
        Z_curr = layer["Z"]
        R = (Z_curr - Z_prev) / (Z_curr + Z_prev)
        T = 1 - R**2
        R_list.append(R)
        T_list.append(T)
        Z_prev = Z_curr

    # --- Propagation modes: fluid + all layers ---
    modes = [(fluid_vel, 0.0, 0.0)] + [(l["v"], l["alpha0"], l["n_exp"]) for l in layers]

    # --- Max delay and time array ---
    max_depth = depths[-1]
    max_delay = 2 * max_depth / min([v for v, _, _ in modes])
    buffer_s = 10e-6
    n_rx = int(fs * (max_delay + buffer_s + len(tx)/fs))
    t_rx = np.arange(n_rx) / fs
    rx = np.zeros(n_rx)

    # --- FFT of transmitted chirp ---
    freqs = fftfreq(len(tx), d=1/fs)
    P_tx = fft(tx)

    # --- Group delay center for time alignment ---
    group_delay_s = len(tx) / 2 / fs  # midpoint of chirp duration

    # --- Data recording ---
    records = []

    # --- Loop over all modes and depths ---
    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        beta = 0.05  # weak dispersion factor

        for i, depth in enumerate(depths):
            tau_s = 2 * depth / v  # round-trip time

            # Frequency-dependent attenuation (in dB/m)
            alpha_f = alpha0 * (np.abs(freqs)/1e6) ** n_exp * 100
            H = 10 ** (-alpha_f * depth / 20)

            # Dispersion model (simple square-root law)
            c_f = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D = np.exp(-1j * 2 * np.pi * freqs * (2 * depth / c_f))

            # Modified frequency response
            P_mod = P_tx * H * D
            echo = np.real(ifft(P_mod))

            # Interface reflection and transmission
            if i == 0:
                R = -1.0
                T = 1.0
            else:
                R = R_list[i-1]
                T = T_list[i-1]

            # Defect model: apply loss to reflection/transmission
            if defect_type == "Delamination" and (i-1) == defect_idx:
                R *= 0.7; T *= 0.7
            elif defect_type == "Crack" and (i-1) == defect_idx:
                R *= 0.5; T *= 0.5

            amp = abs(R)

            # Align echo using group delay center
            idx_center = int(round((tau_s - group_delay_s) * fs))
            half_len = len(echo) // 2
            start = idx_center - half_len
            end = start + len(echo)

            # Add to signal buffer if within range
            if start >= 0 and end <= len(rx):
                rx[start:end] += amp * echo

            # Record metadata
            if i == 0:
                layer_name = "Fluid Gap"
                thick = DEFAULT_GAP_INCH
                Z = config["Z_fluid"]
            else:
                layer = layers[i - 1]
                layer_name = layer["name"]
                thick = layer["thickness"]
                Z = layer["Z"]

            records.append({
                "Mode": m_idx + 1,
                "Layer": layer_name,
                "Thickness (in)": round(thick, 3),
                "Z (MRayl)": round(Z, 3),
                "α0": round(alpha0, 3),
                "n exp": round(n_exp, 3),
                "R": round(R, 3),
                "T": round(T, 3),
                "Time (µs)": round(tau_s * 1e6, 2),
                "Amp": round(amp, 3)
            })

    # --- Matched filter (pulse compression) ---
    compressed = fftconvolve(rx, tx[::-1], mode='same')

    # --- Output ---
    df = pd.DataFrame.from_records(records)
    return t_rx, rx, compressed, freqs, df
