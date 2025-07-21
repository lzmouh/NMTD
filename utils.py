import numpy as np
import pandas as pd
from scipy.signal import chirp, fftconvolve, butter, sosfilt, windows
from scipy.fft import fft, ifft, fftfreq
from config import FLUID_DB, INCH_TO_METER, DEFAULT_GAP_INCH

def generate_tx_chirp(fs, sweep_us, f_start_mhz, f_end_mhz):
    """
    Generate a linear chirp signal for transmission.

    Parameters:
    - fs: Sampling rate in Hz
    - sweep_us: Duration in microseconds
    - f_start_mhz: Start frequency in MHz
    - f_end_mhz: End frequency in MHz

    Returns:
    - t: Time axis (seconds)
    - tx: Chirp signal
    """
    duration = sweep_us * 1e-6
    f_start = f_start_mhz * 1e6
    f_end = f_end_mhz * 1e6
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    tx = chirp(t, f0=f_start, f1=f_end, t1=duration, method='linear')
    return t, tx

def acoustic_impedance(rho, c):
    """
    Compute acoustic impedance Z = rho * c.

    Parameters:
    - rho: Density (kg/m³)
    - c: Speed of sound (m/s)

    Returns:
    - Z: Acoustic impedance
    """
    return rho * c


def reflection_transmission(Z1, Z2):
    """
    Compute reflection and transmission coefficients.

    Parameters:
    - Z1: Impedance of medium 1
    - Z2: Impedance of medium 2

    Returns:
    - R: Reflection coefficient
    - T: Transmission coefficient
    """
    R = (Z2 - Z1) / (Z2 + Z1)
    T = 2 * Z2 / (Z2 + Z1)
    return R, T


def attenuation_filter(frequencies, alpha0, n, thickness):
    """
    Compute attenuation filter H(f) = exp(-alpha(f) * d)

    Parameters:
    - frequencies: Frequency array (Hz)
    - alpha0: Attenuation coefficient at 1 Hz (dB/m)
    - n: Frequency exponent
    - thickness: Distance in meters

    Returns:
    - H_att: Complex attenuation filter (magnitude only)
    """
    alpha_f_db = alpha0 * (frequencies ** n)
    alpha_f_np = alpha_f_db * np.log(10) / 20  # Convert dB to Nepers
    return np.exp(-alpha_f_np * thickness)


def dispersion_filter(frequencies, beta, thickness):
    """
    Compute dispersion phase filter H_phi(f) = exp(j * beta * f^2 * d)

    Parameters:
    - frequencies: Frequency array (Hz)
    - beta: Dispersion coefficient
    - thickness: Distance in meters

    Returns:
    - H_phi: Complex phase shift filter
    """
    phase_shift = beta * (frequencies ** 2) * thickness
    return np.exp(1j * phase_shift)


def apply_frequency_domain_filters(signal_t, fs, attenuation_H, dispersion_Hphi):
    """
    Apply frequency-domain attenuation and dispersion to a time-domain signal.

    Parameters:
    - signal_t: Time-domain signal
    - fs: Sampling frequency
    - attenuation_H: Magnitude attenuation filter
    - dispersion_Hphi: Complex phase dispersion filter

    Returns:
    - signal_filtered: Time-domain filtered signal
    """
    N = len(signal_t)
    freqs = fftfreq(N, 1 / fs)
    signal_f = fft(signal_t)
    signal_f_filtered = signal_f * attenuation_H * dispersion_Hphi
    signal_filtered = np.real(ifft(signal_f_filtered))
    return signal_filtered


def insert_echo(signal, delay_time, fs, amplitude, total_length):
    """
    Insert a delayed and scaled echo into a zero-padded signal.

    Parameters:
    - signal: Echo signal (1D array)
    - delay_time: Time delay (s)
    - fs: Sampling frequency
    - amplitude: Scaling factor
    - total_length: Length of output signal

    Returns:
    - output: Echo inserted in zero array
    """
    delay_samples = int(np.round(delay_time * fs))
    echo = amplitude * signal
    output = np.zeros(total_length)
    if delay_samples + len(echo) < total_length:
        output[delay_samples:delay_samples + len(echo)] += echo
    return output


def travel_time(thickness, c):
    """
    Compute one-way travel time through a layer.

    Parameters:
    - thickness: Distance (m)
    - c: Speed of sound (m/s)

    Returns:
    - t: Time (s)
    """
    return thickness / c


def build_echo_metadata(time, interface, amplitude, alpha0, n, Z1, Z2, thickness, R, T):
    """
    Build metadata dictionary for an echo.

    Returns:
    - metadata: Dictionary with echo parameters
    """
    return {
        'time': time,
        'interface': interface,
        'amplitude': amplitude,
        'alpha0': alpha0,
        'n': n,
        'Z1': Z1,
        'Z2': Z2,
        'thickness': thickness,
        'R': R,
        'T': T
    }


def simulate_multilayer_propagation(
    chirp_signal, chirp_t, fluid_props, layers, gap_thickness=2.54e-3, fs=50e6
):
    """
    Simulate ultrasonic propagation through fluid gap and multilayer pipe.

    Parameters:
    - chirp_signal: Time-domain excitation chirp
    - chirp_t: Time axis for chirp
    - fluid_props: {'c': ..., 'rho': ...}
    - layers: List of dicts with layer properties
    - gap_thickness: Distance from transducer to pipe (default 2.54 mm)
    - fs: Sampling frequency

    Returns:
    - received_signal: Composite A-scan signal
    - time_axis: Time array
    - echo_metadata: List of metadata for each echo
    """
    N = len(chirp_signal)
    time_axis = np.arange(0, 2 * N) / fs
    received_signal = np.zeros(2 * N)
    echo_metadata = []

    c_fluid = fluid_props['c']
    rho_fluid = fluid_props['rho']
    Z_prev = acoustic_impedance(rho_fluid, c_fluid)
    t_total = travel_time(gap_thickness, c_fluid)

    for i, layer in enumerate(layers):
        thickness = layer['thickness']
        c = layer['c']
        rho = layer['rho']
        alpha0 = layer['alpha0']
        n = layer['n']
        beta = layer.get('beta', 0.0)

        Z_layer = acoustic_impedance(rho, c)
        R, T = reflection_transmission(Z_prev, Z_layer)

        # FFT frequency array
        freqs = fftfreq(N, 1 / fs)
        freqs = np.abs(freqs)

        # Apply attenuation and dispersion
        H_att = attenuation_filter(freqs, alpha0, n, thickness)
        H_phi = dispersion_filter(freqs, beta, thickness)
        filtered_signal = apply_frequency_domain_filters(chirp_signal, fs, H_att, H_phi)

        # Travel time through this layer
        t_layer = travel_time(thickness, c)

        # Add reflection at entrance
        echo_r = insert_echo(chirp_signal, t_total, fs, R, 2 * N)
        received_signal += echo_r

        echo_metadata.append(build_echo_metadata(
            time=t_total,
            interface=f'Layer {i} Entry',
            amplitude=R,
            alpha0=alpha0,
            n=n,
            Z1=Z_prev,
            Z2=Z_layer,
            thickness=thickness,
            R=R,
            T=T
        ))

        # Transmit through layer
        t_total += t_layer
        chirp_signal = filtered_signal * T
        Z_prev = Z_layer

    # Reflection from outer wall (to fluid or solid)
    R_end = -1.0  # Full reflection if backing is solid/fluid assumed (simplified)
    echo_back = insert_echo(chirp_signal, t_total, fs, R_end, 2 * N)
    received_signal += echo_back

    echo_metadata.append(build_echo_metadata(
        time=t_total,
        interface='Back Wall',
        amplitude=R_end,
        alpha0=None,
        n=None,
        Z1=Z_prev,
        Z2=None,
        thickness=None,
        R=R_end,
        T=None
    ))

    return received_signal, time_axis, echo_metadata
