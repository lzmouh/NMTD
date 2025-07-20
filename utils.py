import numpy as np
import pandas as pd
from scipy.signal import chirp, fftconvolve, butter, sosfilt, windows
from scipy.fft import fft, ifft, fftfreq
from config import FLUID_DB, INCH_TO_METER, DEFAULT_GAP_INCH

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

    layers = config["layer_data"]
    defect_type = config.get("defect_type", "None")
    defect_idx = config.get("defect_layer", -1)

    # Fluid properties
    fluid = config["fluid"]
    c_f = fluid["velocity"]
    rho_f = fluid["density"]
    z_f = c_f * rho_f

    # Chirp parameters
    sweep_len = len(tx)
    group_delay = sweep_len // 2 / fs

    # Depths in meters
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    depths = [gap_m]
    for layer in layers:
        depths.append(depths[-1] + layer["thickness"] * INCH_TO_METER)
    total_thickness = depths[-1]

    print(f"[DEBUG] Total pipe thickness: {total_thickness:.3f} m")

    # Frequencies
    freqs = fftfreq(sweep_len, 1/fs)
    P_tx = fft(tx)

    # Time domain buffer
    max_time = config.get("max_time", 200e-6)  # default to 200 µs
    n_rx = int(2 * fs * max_time)
    t_rx = np.arange(n_rx) / fs
    rx = np.zeros(n_rx)

    # Store records for plotting / analysis
    records = []

    # Modes: fluid + all solid layers
    modes = [(c_f, 0.01, 1.2)]  # Fluid assumed default α₀ and n_exp
    modes += [(layer["v"], layer.get("alpha0", 0.05), layer.get("n_exp", 1.2)) for layer in layers]

    # Impedance handling
    impedances = [z_f] + [layer["Z"] for layer in layers]

    for m_idx, (v, alpha0, n_exp) in enumerate(modes):
        beta = 0.02  # dispersion factor (adjustable)

        for i, depth in enumerate(depths):
            tau = 2 * depth / v  # round-trip time
            echo_time_us = tau * 1e6

            # Attenuation filter (dB -> amplitude)
            alpha_f = alpha0 * (np.abs(freqs)/1e6) ** n_exp
            H = 10 ** (-alpha_f * depth / 20)

            # Dispersion model (β-model)
            c_f_disp = v * (1 + beta * (np.abs(freqs)/1e6)**0.5)
            D = np.exp(-1j * 2 * np.pi * freqs * (2 * depth / c_f_disp))

            # Construct echo in frequency domain
            P_echo = P_tx * H * D
            echo = np.real(ifft(P_echo))

            # Interface R/T
            if i == 0:
                R = -1.0  # reflection from fluid gap
                T = 1.0
            else:
                Z1 = impedances[i - 1]
                Z2 = impedances[i]
                R = (Z2 - Z1) / (Z2 + Z1)
                T = 1 - R**2

            # Defect logic
            if defect_type == "Delamination" and (i-1) == defect_idx:
                R *= 0.7; T *= 0.7
            elif defect_type == "Crack" and (i-1) == defect_idx:
                R *= 0.5; T *= 0.5

            amp = abs(R)

            # Insert echo at correct location (group-delay compensated)
            idx_center = int(round((tau - group_delay) * fs))
            start = idx_center - sweep_len // 2
            end = start + sweep_len

            # Debug insert range
            if start < 0 or end > n_rx:
                print(f"[DEBUG] Echo {m_idx+1}-{i}: Out of bounds! Time: {echo_time_us:.1f} µs, Skipping.")
                continue

            rx[start:end] += amp * echo
            print(f"[DEBUG] Mode {m_idx+1} @ {echo_time_us:.1f} µs | amp={amp:.3f}, R={R:.2f}")

            # Layer info
            if i == 0:
                layer_name = "Fluid Gap"
                thick_in = DEFAULT_GAP_INCH
                Z_layer = z_f
            else:
                layer = layers[i - 1]
                layer_name = layer["name"]
                thick_in = layer["thickness"]
                Z_layer = layer["Z"]

            records.append({
                "Mode": m_idx + 1,
                "Layer": layer_name,
                "Thickness (in)": round(thick_in, 3),
                "Z (MRayl)": round(Z_layer / 1e6, 3),
                "α₀": round(alpha0, 4),
                "n exp": round(n_exp, 3),
                "R": round(R, 3),
                "T": round(T, 3),
                "Time (µs)": round(echo_time_us, 2),
                "Amp": round(amp, 3),
                "IsDirect": True
            })

    # Matched filter response
    compressed = fftconvolve(rx, tx[::-1], mode="same")

    # Check signal level
    if np.max(np.abs(rx)) < 1e-6:
        print("[WARNING] Received signal is extremely weak or zero!")

    df = pd.DataFrame.from_records(records)
    return t_rx, rx, compressed, freqs, df
