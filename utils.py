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
    """
    Simulate multi-mode ultrasonic propagation through layered pipe.
    Returns:
        t_rx: time array for received signal
        rx_signal: raw received signal with all modes
        compressed: pulse-compressed signal
        freqs: frequency array
        df: echo metadata dataframe with direct arrival flag
    """
    fs = config["sampling_rate"]
    t_chirp = np.array(config["t_chirp"])
    tx = np.array(config["tx"])
    layers = config["pipe_layers"]
    fluid = config["fluid"]
    gap_thickness = 0.1 * 0.0254  # 0.1 inch in meters

    c_f = fluid["velocity"]
    rho_f = fluid["density"]
    z_f = c_f * rho_f

    t_total = 400e-6  # 400 µs
    n_rx = int(t_total * fs)
    t_rx = np.arange(n_rx) / fs
    rx_signal = np.zeros(n_rx)

    freqs = np.fft.fftfreq(len(tx), d=1/fs)
    freqs_hz = freqs[freqs >= 0]
    
    echo_table = []
    interface_times = []
    distance = gap_thickness

    v_prev = c_f
    z_prev = z_f
    layer_names = ["Fluid"]

    for i, layer in enumerate(layers):
        v = layer["velocity"]
        rho = layer["density"]
        alpha0 = layer["alpha0"]
        n_exp = layer["n_exp"]
        z = v * rho
        d = layer["thickness"] * 0.0254  # inches to meters

        # Reflection and transmission at this interface
        R = (z - z_prev) / (z + z_prev)
        T = 2 * z / (z + z_prev)

        # Time of flight (one-way)
        TT = distance / v
        TT_us = TT * 1e6

        # Attenuation (frequency dependent)
        alpha_f = alpha0 * (freqs_hz / 1e6) ** n_exp  # Np/m
        att_linear = np.exp(-2 * alpha_f * d)

        # Delay samples
        t_delay = 2 * distance / v  # round-trip
        idx_delay = int(np.round(t_delay * fs))

        if idx_delay < len(rx_signal):
            # Attenuate signal in frequency domain
            TX = np.fft.fft(tx, n=len(rx_signal))
            ATT = np.ones_like(TX)
            ATT[:len(alpha_f)] = att_linear
            RX = TX * ATT
            rx_att = np.fft.ifft(RX).real

            # Insert echo
            rx_signal[idx_delay:idx_delay+len(tx)] += R * rx_att[:len(rx_signal)-idx_delay]

            # Store metadata
            echo_table.append({
                "Layer": layer["name"],
                "Interface": f"{layer_names[-1]}–{layer['name']}",
                "Time (µs)": t_delay * 1e6,
                "Amp": R,
                "Z (MRayl)": z / 1e6,
                "Thickness (in)": layer["thickness"],
                "α₀": alpha0,
                "n_exp": n_exp,
                "Mode": i + 1,
                "IsDirect": True,
                "TT (µs)": t_delay * 1e6,
                "Calc Thickness (in)": (v * t_delay / 2) * 39.3701,
            })

        # Prep for next
        distance += d
        z_prev = z
        v_prev = v
        layer_names.append(layer["name"])

    # Last reflection (backwall or fluid behind)
    z_back = config["backing"]["velocity"] * config["backing"]["density"]
    R_back = (z_back - z_prev) / (z_back + z_prev)
    t_delay = 2 * distance / v_prev
    idx_delay = int(np.round(t_delay * fs))

    if idx_delay < len(rx_signal):
        RX = np.fft.fft(tx, n=len(rx_signal))
        rx_back = np.fft.ifft(RX).real
        rx_signal[idx_delay:idx_delay+len(tx)] += R_back * rx_back[:len(rx_signal)-idx_delay]

        echo_table.append({
            "Layer": "Backing",
            "Interface": f"{layer_names[-1]}–Backing",
            "Time (µs)": t_delay * 1e6,
            "Amp": R_back,
            "Z (MRayl)": z_back / 1e6,
            "Thickness (in)": 0.0,
            "α₀": 0,
            "n_exp": 0,
            "Mode": len(layers) + 1,
            "IsDirect": True,
            "TT (µs)": t_delay * 1e6,
            "Calc Thickness (in)": (v_prev * t_delay / 2) * 39.3701,
        })

    # Pulse compression (matched filter)
    compressed = fftconvolve(rx_signal, tx[::-1], mode='same')

    df = pd.DataFrame(echo_table)
    return t_rx, rx_signal, compressed, freqs_hz, df
