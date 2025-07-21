import numpy as np
import pandas as pd
from scipy.signal import chirp, fftconvolve, butter, sosfilt, windows, filtfilt, hilbert
from scipy.fft import fft, ifft, fftfreq
from config import FLUID_DB, INCH_TO_METER, DEFAULT_GAP_INCH

def calculate_group_delay(tx, fs):
    """
    Estimate group delay from autocorrelation peak of transmit signal.
    
    Parameters:
        tx (np.ndarray): Transmit chirp signal
        fs (float): Sampling rate in Hz

    Returns:
        float: Group delay in seconds
    """

    energy = np.abs(tx) ** 2
    center_index = np.sum(np.arange(len(tx)) * energy) / np.sum(energy)
    delay_samples = int(np.round(center_index))
    return delay_samples / fs
    
def bandpass_filter(signal, fs, fmin, fmax, order=4):
    """
    Apply zero-phase Butterworth bandpass filter to a signal.
    
    Parameters:
        signal (np.ndarray): Input signal
        fs (float): Sampling rate in Hz
        fmin (float): Minimum frequency in Hz
        fmax (float): Maximum frequency in Hz
        order (int): Filter order

    Returns:
        np.ndarray: Filtered signal
    """
    nyq = 0.5 * fs
    low = fmin / nyq
    high = fmax / nyq
    if low >= 1 or high >= 1:
        raise ValueError("Filter frequencies must be below Nyquist.")
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

def matched_filter_compress(rx, tx):
    """
    Perform pulse compression using matched filtering.

    Parameters:
        rx (np.ndarray): Received signal
        tx (np.ndarray): Transmitted chirp signal (template)

    Returns:
        np.ndarray: Pulse-compressed signal
    """
    tx_matched = tx[::-1]  # Time-reverse the chirp for matched filtering
    compressed = np.convolve(rx, tx_matched, mode='same')
    return compressed

def generate_tx_chirp(fs, sweep_us, f_start_mhz, f_end_mhz):
    """
    Generate a linear chirp signal for transmission with tapering.

    Parameters:
    - fs: Sampling rate in Hz
    - sweep_us: Duration in microseconds
    - f_start_mhz: Start frequency in MHz
    - f_end_mhz: End frequency in MHz

    Returns:
    - t: Time axis (seconds)
    - tx: Tapered chirp signal
    """
    # Convert units
    duration = sweep_us * 1e-6
    f_start = f_start_mhz * 1e6
    f_end = f_end_mhz * 1e6

    # Time vector
    N = int(fs * duration)
    t = np.linspace(0, duration, N, endpoint=False)

    # Generate linear chirp
    tx = chirp(t, f0=f_start, f1=f_end, t1=duration, method='linear')

    # Apply tukey window taper
    tx *= windows.tukey(N, alpha=0.1)
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
    T = np.sqrt(1 - R**2)  # Ensure energy conservation
    #T = 2 * Z1 / (Z1 + Z2)  # Amplitude transmission coefficient
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
    chirp_signal,
    chirp_t,
    fluid_props,
    layers,
    gap_thickness=DEFAULT_GAP_INCH * INCH_TO_METER,
    fs=50e6,
    noise_level=0.01,
    max_internal_reflections=2,
    include_synthetic_transverse=True
):
    """
    Simulate ultrasonic propagation through fluid and multilayer structure with noise, internal echoes, and synthetic transverse mode.

    Parameters:
    - chirp_signal: Tx chirp (1D array)
    - chirp_t: Time axis of chirp (s)
    - fluid_props: Dict with 'c' and 'rho'
    - layers: List of dicts, each with 'c', 'rho', 'thickness', 'alpha0', 'n', 'beta'
    - gap_thickness: Fluid gap to first layer (m)
    - fs: Sampling frequency (Hz)
    - noise_level: Relative amplitude of additive white noise
    - max_internal_reflections: Number of intra-layer reflections to simulate
    - include_synthetic_transverse: If True, adds simulated transverse echo

    Returns:
    - received_signal: Simulated received A-scan
    - time_axis: Time array
    - echo_metadata: List of echo metadata dicts
    """
    N = len(chirp_signal)
    time_axis = np.arange(0, 2 * N) / fs
    received_signal = np.zeros(2 * N)
    echo_metadata = []

    # Fluid properties
    c_fluid = fluid_props['c']                   # m/s
    Z_prev = fluid_props['Z']
    t_total = 2 * travel_time(gap_thickness, c_fluid)

    # Estimate group delay
    group_delay = calculate_group_delay(chirp_signal, fs)
    signal_in = chirp_signal.copy()

    for i, layer in enumerate(layers):
        thickness = layer['thickness']                # m
        c = layer['c']                                # m/s
        rho = layer['rho'] # * 1000                     # g/cc → kg/m³
        alpha0 = layer['alpha0']                      # Np/m at 1 MHz
        n = layer['n']                                # frequency exponent
        beta = layer.get('beta', 0.0)                 # s²/m

        # Acoustic impedance
        Z_layer = acoustic_impedance(rho, c)          # Rayl
        #Z_layer = layer['Z'] * 1e6  # MRayl → Rayl
        R, T = reflection_transmission(Z_prev, Z_layer)

        # FFT filters
        freqs = fftfreq(N, 1 / fs)
        freqs = np.abs(freqs)
        H_att = attenuation_filter(freqs, alpha0, n, thickness)
        H_phi = dispersion_filter(freqs, beta, thickness)
        filtered = apply_frequency_domain_filters(signal_in, fs, H_att, H_phi)

        # Travel time through this layer
        t_layer = travel_time(thickness, c)

        # Primary reflection at interface
        delay = t_total
        echo_r = insert_echo(signal_in, delay, fs, R, 2 * N)
        received_signal += echo_r

        echo_metadata.append(build_echo_metadata(
            time=delay,
            interface=f'Layer {i} Entry',
            amplitude=R,
            alpha0=alpha0,
            n=n,
            Z1=Z_prev,
            Z2=Z_layer,
            thickness=thickness,
            R=None,
            T=None
        ))

        # Internal reflections within this layer
        for k in range(1, max_internal_reflections + 1):
            delay_internal = t_total + 2 * k * t_layer 
            amp_internal = (R ** k) * (T ** 2)
            echo_multi = insert_echo(signal_in, delay_internal, fs, amp_internal, 2 * N)
            received_signal += echo_multi

            echo_metadata.append(build_echo_metadata(
                time=delay_internal,
                interface=f'Layer {i} Internal Echo {k}',
                amplitude=amp_internal,
                alpha0=alpha0,
                n=n,
                Z1=Z_layer,
                Z2=Z_layer,
                thickness=thickness,
                R=R,
                T=T
            ))

        # Optional synthetic transverse mode echo
        if include_synthetic_transverse:
            t_trans = 1.3 * t_total
            amp_trans = 0.3 * R
            echo_trans = insert_echo(
                signal_in * 0.3,
                t_trans,
                fs,
                amp_trans,
                2 * N
            )
            received_signal += echo_trans

            echo_metadata.append(build_echo_metadata(
                time=t_trans,
                interface=f'Layer {i} Synthetic T-mode',
                amplitude=amp_trans,
                alpha0=alpha0,
                n=n,
                Z1=Z_prev,
                Z2=Z_layer,
                thickness=thickness,
                R=R,
                T=T
            ))

        # Transmitted signal continues
        t_total += travel_time(thickness, c) #t_layer
        signal_in = filtered * T
        Z_prev = Z_layer

    # Final back-wall reflection (layer-fluid interface)
    Z_fluid = acoustic_impedance(fluid_props['rho'], fluid_props['c'])
    R_end, T_end = reflection_transmission(Z_prev, Z_fluid)
    delay_back = t_total
    echo_back = insert_echo(signal_in, delay_back, fs, R_end, 2 * N)
    received_signal += echo_back
    
    echo_metadata.append(build_echo_metadata(
        time=delay_back,
        interface='Back Wall',
        amplitude=R_end,
        alpha0=None,
        n=None,
        Z1=Z_prev,
        Z2=Z_fluid,
        thickness=None,
        R=R_end,
        T=T_end
    ))
    # Add background Gaussian noise
    if noise_level > 0:
        noise = noise_level * np.random.normal(size=received_signal.shape)
        received_signal += noise

    return received_signal, time_axis, echo_metadata
