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

def simulate_multimode(
    tx, fs,
    fluid_velocity, Z_fluid,
    layer_data,
    defect_type=None,
    defect_layer=None,
    max_time=50e-6,
    fluid_gap_m=0.00254  # 0.1 inch
):
    """
    Simulate multimode ultrasonic A-scan through multilayer non-metallic pipe.
    Returns: (t, rx_raw, echoes_df, rx_aligned, rx_compressed, rx_compressed_aligned)
    """
    # --- Setup Time Base ---
    n_samples = int(max_time * fs)
    t = np.arange(n_samples) / fs
    rx = np.zeros(n_samples)

    # --- Precompute Transducer Chirp Energy ---
    tx_energy = np.sum(np.abs(tx)**2)

    # --- Flatten Layer Properties ---
    thicknesses = np.array([layer["thickness"] for layer in layer_data]) * 0.0254  # in → m
    velocities = np.array([layer["v"] for layer in layer_data])
    Z_layers = np.array([layer["Z"] for layer in layer_data]) * 1e6  # MRayl → Rayl
    alpha0s = np.array([layer["alpha0"] for layer in layer_data])
    nexps = np.array([layer["n_exp"] for layer in layer_data])
    n_layers = len(layer_data)

    # --- Travel Path Setup ---
    z_positions = np.cumsum(thicknesses)  # interface positions
    echoes = []

    # --- Initial fluid gap echo (interface at fluid → layer 1) ---
    r0 = (Z_layers[0] - Z_fluid) / (Z_layers[0] + Z_fluid)
    t0 = 2 * fluid_gap_m / fluid_velocity
    a0 = r0
    i0 = int(round(t0 * fs))
    if 0 <= i0 < n_samples:
        rx[i0] += a0
        echoes.append({"time": t0, "amplitude": a0, "type": "fluid-gap", "layer": 0})

    # --- Down and up propagation through layers ---
    for i in range(n_layers):
        # Propagation to layer bottom
        d = thicknesses[i]
        v = velocities[i]
        alpha0 = alpha0s[i]
        n_exp = nexps[i]

        # Estimate center frequency for attenuation (~mean of sweep)
        f_center = (np.fft.fftfreq(len(tx), d=1/fs)[1:].mean())  # crude, improve if needed
        alpha = alpha0 * (f_center / 1e6) ** n_exp  # Nepers/m

        # Accumulate round-trip time
        t_rt = 2 * d / v
        t_total = 2 * (fluid_gap_m + np.sum(thicknesses[:i+1]) ) / v
        A_total = np.exp(-2 * alpha * d)  # two-way attenuation

        # Reflection at next interface (if not last layer)
        if i < n_layers - 1:
            Z1, Z2 = Z_layers[i], Z_layers[i+1]
            r = (Z2 - Z1) / (Z2 + Z1)
            a = A_total * r

            t_echo = 2 * fluid_gap_m / fluid_velocity + 2 * np.sum(thicknesses[:i+1] / velocities[:i+1])
            idx = int(round(t_echo * fs))
            if 0 <= idx < n_samples:
                rx[idx] += a
                echoes.append({"time": t_echo, "amplitude": a, "type": "interface", "layer": i+1})

        # Delamination
        if defect_type == "Delamination" and defect_layer == i + 1:
            # Insert a large reflection within the layer
            a = 0.9  # strong echo
            t_def = 2 * (fluid_gap_m + np.sum(thicknesses[:i]) + 0.5 * thicknesses[i]) / v
            idx = int(round(t_def * fs))
            if 0 <= idx < n_samples:
                rx[idx] += a
                echoes.append({"time": t_def, "amplitude": a, "type": "delamination", "layer": i+1})

        # Crack (only reflects partway)
        if defect_type == "Crack" and defect_layer == i + 1:
            # Reflect ~halfway through the layer
            a = 0.7  # moderate echo
            t_def = 2 * (fluid_gap_m + np.sum(thicknesses[:i]) + 0.25 * thicknesses[i]) / v
            idx = int(round(t_def * fs))
            if 0 <= idx < n_samples:
                rx[idx] += a
                echoes.append({"time": t_def, "amplitude": a, "type": "crack", "layer": i+1})

    # --- Normalize RX signal to avoid clipping ---
    rx = rx / (np.max(np.abs(rx)) + 1e-9)

    # --- Alignment (group delay) ---
    idx_peak = np.argmax(np.abs(tx))
    tx_padded = np.zeros_like(rx)
    tx_padded[:len(tx)] = tx
    rx_aligned = np.roll(rx, -idx_peak)

    # --- Pulse Compression ---
    matched_filter = tx[::-1]
    rx_compressed = fftconvolve(rx, matched_filter, mode='same')
    rx_compressed_aligned = fftconvolve(rx_aligned, matched_filter, mode='same')
    rx_compressed /= np.max(np.abs(rx_compressed)) + 1e-9
    rx_compressed_aligned /= np.max(np.abs(rx_compressed_aligned)) + 1e-9

    # --- Echoes Table ---
    echoes_df = pd.DataFrame(echoes)

    return t, rx, echoes_df, rx_aligned, rx_compressed, rx_compressed_aligned
