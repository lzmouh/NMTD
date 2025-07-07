import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.fft import fft, fftfreq, ifft
from config import INCH_TO_METER, DEFAULT_GAP_INCH, DEFAULT_VELOCITY

def simulate_layer_physics(config):
    """
    Runs the full ultrasonic propagation simulation including:
    • frequency-dependent dispersion c(f)
    • per-layer attenuation and amplitude scaling
    • reflection & transmission at each interface
    • defect overrides for crack/delamination
    """
    # Unpack config
    layers = config["layer_data"]
    Z_fluid = config["Z_fluid"] * 1e6       # MRayl → Rayl
    rho_fluid = config["fluid_density"]*1000
    defect = config["defect_type"]
    defect_idx = config["defect_layer"] - 1

    # Time axis
    fs = 100e6  # 100 MHz sampling
    t_max = 20e-6
    t = np.linspace(0, t_max, int(fs*t_max))
    dt = t[1] - t[0]

    # Generate base pulse
    f0 = 1e6
    pulse = np.sin(2*np.pi*f0*t) * np.exp(-((t-3/f0)**2)/(0.2e-6)**2)
    P = fft(pulse)
    freqs = fftfreq(len(t), dt)

    # Fluid gap
    gap_m = DEFAULT_GAP_INCH * INCH_TO_METER
    c_fluid = Z_fluid / rho_fluid
    TT_fluid = 2*gap_m/c_fluid*1e6  # µs

    # Prepare results list
    results = []
    A_scan = np.zeros_like(t)
    # initial echo from fluid interface
    A_scan += np.interp(t, t-TT_fluid, pulse, left=0, right=0)

    Z_prev = Z_fluid
    amp = 1.0
    depth = gap_m

    # Loop through layers
    for i, (label, thick_in, Z_mrayl) in enumerate(layers):
        # convert units
        thickness = thick_in * INCH_TO_METER
        Z_curr = Z_mrayl * 1e6

        # --- Attenuation parameters ---
        alpha0 = 0.5 + 0.1*i      # dB/cm/MHz (example)
        n = 1.2 + 0.05*i          # exponent
        alpha_f = alpha0 * (np.abs(freqs)/1e6)**n * 100  # dB/m
        H = 10**(-alpha_f * thickness / 20)              # Attenuation transfer function
        
        # --- Dispersion: frequency-dependent velocity ---
        c0 = DEFAULT_VELOCITY      # m/s baseline
        k_disp = 0.05              # dispersion coefficient
        n_disp = 0.5               # power exponent
        c_f = c0 * (1 + k_disp * (np.abs(freqs)/1e6)**n_disp)  # velocity vs frequency
        
        # Phase delay for each frequency component (2-way travel time)
        phase_delay = 2 * thickness / c_f                  # seconds
        phi = 2 * np.pi * freqs * phase_delay              # phase shift (radians)
        D = np.exp(-1j * phi)                              # Dispersion transfer function
        
        # --- Combine all effects ---
        P_i = P * H * D * T                                # Apply attenuation, dispersion, transmission
        p_i = np.real(ifft(P_i))                           # Inverse FFT to get time-domain response


        # reflection/transmission
        R = ((Z_curr-Z_prev)/(Z_curr+Z_prev))**2
        T = 1 - R

        # defect overrides
        if defect=="Delamination" and i==defect_idx:
            R, T = 0.7, 0.3
            # add extra delay
            extra_delay = 0.6  # µs
        else:
            extra_delay = 0
        if defect=="Crack" and i==defect_idx:
            R, T = 0.5, 0.5

        # propagate
        P_i = P * H * T
        p_i = np.real(ifft(P_i))
        depth += thickness
        tau = (2*depth/DEFAULT_VELOCITY)*1e6 + extra_delay

        # add reflection echo
        echo = R * np.interp(t, t-tau, p_i, left=0, right=0)
        A_scan += echo

        # record results
        results.append({
            "Layer": label,
            "Thickness (in)": thick_in,
            "Z (MRayl)": Z_mrayl,
            "α0 (dB/cm/MHz)": round(alpha0,2),
            "n exponent": round(n,2),
            "Refl Coef": round(R,3),
            "Trans Coef": round(T,3),
            "Time (µs)": round(tau,2),
            "Amp Echo": round(R*amp,3),
        })

        # update for next
        amp *= T
        Z_prev = Z_curr

    df = pd.DataFrame(results)
    return t, A_scan, freqs, df, TT_fluid

def show_plots2():
    st.title("📊 Ultrasonic A-Scan Simulation Results")

    # run simulation
    config = st.session_state["config"]
    t, A_scan, freqs, df_results, TT_fluid = simulate_layer_physics(config)

    # Display constants & inputs
    st.subheader("🔧 Simulation Inputs & Constants")
    inputs = {
        "Fluid": config["fluid"],
        "Fluid Density (g/cc)": config["fluid_density"],
        "Z_fluid (MRayl)": config["Z_fluid"],
        "Num Layers": config["num_layers"],
        "Total Thickness (in)": config["total_thickness"],
        "Defect Type": config["defect_type"],
        "Defect Layer": config["defect_layer"],
    }
    st.table(pd.DataFrame.from_dict(inputs, orient="index", columns=["Value"]))

    # Layer-by-layer results table
    st.subheader("📋 Layer-by-Layer Echo Parameters")
    st.dataframe(df_results)

    # Time-domain plot
    st.subheader("🟢 Time-Domain A-Scan (Echo Peaks Highlighted)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t*1e6, y=A_scan, name="A-Scan", line=dict(color='firebrick')))
    # mark fluid echo
    fig.add_vline(x=TT_fluid, line_dash="dash", line_color="blue",
                  annotation_text="Fluid Echo", annotation_position="top left")
    # mark each layer echo
    for idx, row in df_results.iterrows():
        fig.add_vline(x=row["Time (µs)"], line_dash="dot", line_color="gray",
                      annotation_text=row["Layer"], annotation_position="top right")
    fig.update_layout(
        xaxis_title="Time (µs)", yaxis_title="Amplitude",
        hovermode="x unified", height=400
    )
    st.plotly_chart(fig, use_container_width=True)

    # Frequency-domain plot
    st.subheader("🔵 Frequency-Domain Spectrum")
    fft_vals = np.abs(fft(A_scan))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=freqs[:len(freqs)//2]/1e6,
        y=fft_vals[:len(freqs)//2],
        name="FFT", line=dict(color='royalblue')
    ))
    fig2.update_layout(
        xaxis_title="Frequency (MHz)", yaxis_title="Magnitude",
        hovermode="x unified", height=300
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Export options
    st.subheader("📤 Export Data & Plots")
    csv = df_results.to_csv(index=False).encode()
    st.download_button("Download Echo Table (CSV)", csv, "echo_params.csv", "text/csv")

    # Export images
    if st.button("Download Time-Domain Plot (PNG)"):
        fig.write_image("time_domain.png")
        with open("time_domain.png","rb") as f:
            st.download_button("⬇ Download PNG", f.read(), "time_domain.png","image/png")
    if st.button("Download Frequency Plot (PNG)"):
        fig2.write_image("frequency_domain.png")
        with open("frequency_domain.png","rb") as f:
            st.download_button("⬇ Download PNG", f.read(), "frequency_domain.png","image/png")
