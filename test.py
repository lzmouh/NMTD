import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import fftconvolve
from scipy.signal import chirp
from scipy.fft import fft, ifft, fftfreq

# ---------- simulate_multimode (simplified) ----------
def simulate_multimode(config):
    fs      = config["sampling_rate"]
    t_chirp = np.array(config["tx_chirp_t"])
    tx      = np.array(config["tx_chirp_waveform"])
    layers  = config["layer_data"]
    fluid_v = config["fluid_velocity"]
    gap_in  = 0.1  # inches

    # depths
    gap_m = gap_in * 0.0254
    depths = [gap_m]
    for lyr in layers:
        depths.append(depths[-1] + lyr["thickness"] * 0.0254)

    # prepare
    n_rx = len(t_chirp)*4
    t_rx = np.arange(n_rx)/fs
    rx   = np.zeros(n_rx)
    records = []

    for i, depth in enumerate(depths):
        tau = 2*depth / (fluid_v if i==0 else layers[i-1]["v"])
        idx = int(round(tau*fs))
        # use chirp itself as echo for demo
        echo = np.interp(t_rx, t_rx - tau, tx)
        rx[idx:idx+len(tx)] += echo
        rec = {
            "Layer": "Fluid Gap" if i==0 else layers[i-1]["name"],
            "Time": round(tau*1e6,2)
        }
        records.append(rec)

    compressed = fftconvolve(rx, tx[::-1], mode="same")
    df = pd.DataFrame(records)
    return t_rx, rx, compressed, df

def show_test():
    # ---------- Example config ----------
    fs = 100e6
    dur = 50e-6
    t_chirp = np.linspace(0, dur, int(fs*dur))
    tx = chirp(t_chirp, f0=0.5e6, f1=5e6, t1=dur)
    config = {
        "sampling_rate": fs,
        "tx_chirp_t": t_chirp.tolist(),
        "tx_chirp_waveform": tx.tolist(),
        "fluid_velocity": 1480,
        "layer_data": [
            {"name":"Layer1","thickness":0.2,"v":1600},
            {"name":"Layer2","thickness":0.3,"v":1500},
            {"name":"Layer3","thickness":0.5,"v":1400},
        ]
    }
    
    # ---------- Run simulation ----------
    t_rx, rx, comp, df = simulate_multimode(config)
    
    # ---------- Plot Raw A-Scan ----------
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=t_rx*1e6, y=rx, name="Raw A-scan"))
    for _, row in df.iterrows():
        fig1.add_vline(x=row["Time"], line_dash="dash" if row["Layer"]=="Fluid Gap" else "dot",
                       line_color="blue" if row["Layer"]=="Fluid Gap" else "gray",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig1.update_layout(title="Raw A-Scan with Fluid & Layer Echoes", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=400)
    
    # ---------- Plot Compressed A-Scan ----------
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t_rx*1e6, y=comp, name="Compressed"))
    for _, row in df.iterrows():
        fig2.add_vline(x=row["Time"], line_dash="dash" if row["Layer"]=="Fluid Gap" else "dot",
                       line_color="blue" if row["Layer"]=="Fluid Gap" else "gray",
                       annotation_text=row["Layer"], annotation_position="top right")
    fig2.update_layout(title="Compressed A-Scan with Fluid & Layer Echoes", xaxis_title="Time (µs)", yaxis_title="Amplitude", height=400)
    
    fig1.show()
    fig2.show()
