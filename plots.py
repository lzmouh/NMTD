import streamlit as st
import plotly.graph_objects as go
import numpy as np
from utils import simulate_multimode, calculate_group_delay, bandpass_filter, generate_tx_chirp 

def show_plots():
    st.title("Non-metalic Tubualrs Defectoscope NMTD")
    st.subheader("Ultrasonic Simulation App")

    if "config" not in st.session_state:
        st.warning("⚠️ Configuration not found. Please visit the **Simulator** page first.")
        st.stop()

    config = st.session_state["config"]

    # Settings
    st.sidebar.header("Signal Processing Options")
    align = st.sidebar.checkbox("Align to Group Delay", True)
    apply_filter = st.sidebar.checkbox("Apply Bandpass Filter", False)
    fmin = st.sidebar.number_input("Min Freq (MHz)", 0.1, 20.0, 0.5) * 1e6
    fmax = st.sidebar.number_input("Max Freq (MHz)", 0.1, 20.0, 5.0) * 1e6

