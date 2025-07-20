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
    # --- Extract fluid ---
    fluid_name = config["fluid"]
    if fluid_name == "Other":
        rho_f = config["fluid_density"] * 1000      # g/cc → kg/m³
        c_f = config["fluid_velocity"]              # m/s
        z_f = rho_f * c_f                           # Rayl
    else:
        fluid = FLUID_DB[fluid_name]
        z_f = fluid["Z"] * 1e6                      # MRayl → Rayl
        rho_f = fluid["density"] * 1000             # g/cc → kg/m³
        c_f = z_f / rho_f                           # m/s

    tx = np.array(config["tx"])
    t_chirp = np.array(config["t_chirp"])
    fs = config["sampling_rate"]
    dt = 1 / fs

    # --- Simulation domain ---
    n_rx = int(2 * fs * config["max_time"])     # total length
    rx = np.zeros(n_rx)
    t_rx = np.arange(n_rx) * dt

    # --- Parameters ---
    gap_thickness = 0.1 * 0.0254  # 0.1 inch in meters

    # --- Accumulate TOF and signal ---
    tof = 2 * gap_thickness / c_f
    echoes = []
    total_thickness = 0

    for i, layer in enumerate(config["layer_data"]):
        d = layer["thickness"] * 0.0254  # inches → meters
        c = layer["v"]
        #rho = layer["d"] * 1000
        z = layer["Z"]
        alpha0 = layer.get("alpha0", 0.0)
        n_exp = layer.get("n_exp", 1.0)

        # Transmission and reflection at fluid-layer interface
        R = (z - z_f) / (z + z_f)
        T = 2 * z / (z + z_f)

        # Frequency-dependent attenuation
        f = np.fft.fftfreq(len(tx), d=dt)
        f_abs = np.abs(f)
        attenuation = np.exp(-alpha0 * (f_abs ** n_exp) * d)

        # Forward pulse through layer
        tx_fft = np.fft.fft(tx)
        tx_atten = np.fft.ifft(tx_fft * attenuation).real

        # Round trip TOF to this layer's front interface
        tof_layer = tof
        sample_idx = int(round(tof_layer / dt))

        if sample_idx + len(tx_atten) < len(rx):
            rx[sample_idx:sample_idx + len(tx_atten)] += T * tx_atten

        # Save metadata for this direct arrival
        echoes.append({
            "Layer": layer["name"],
            "Mode": 1,
            "Time (µs)": tof_layer * 1e6,
            "Amp": np.max(np.abs(T * tx_atten)),
            "Thickness (in)": d / 0.0254,
            "Z (MRayl)": z / 1e6,
            "α₀": alpha0,
            "n_exp": n_exp,
            "R": R,
            "T": T
        })

        # Update TOF for next layer
        tof += 2 * d / c
        z_f = z  # fluid becomes this layer (next reflection interface)

        total_thickness += d

    # --- Optional final backwall reflection (total thickness) ---
    # (not added for now; can be simulated later)

    # --- Pulse compression via matched filter ---
    compressed = fftconvolve(rx, tx[::-1], mode='same')

    # --- Create DataFrame of echoes ---
    df = pd.DataFrame(echoes)

    return t_rx, rx, compressed, np.fft.fftfreq(len(rx), d=1/fs), df
