import streamlit as st

def show_about():
    st.title("ℹ️ About the NMTD Simulator")
    st.markdown("""
The **Non-Metallic Tubular Defectoscope (NMTD)** simulator is a tool designed to test and visualize ultrasonic signals
in multilayer non-metallic pipes like GRE, HDPE, or RTP used in the oil & gas sector.

### Purpose
To support the evaluation and integrity logging of non-metallic tubulars, which cannot be tested by conventional metallic inspection tools.
This tool aids design, development, and early feasibility testing of ultrasonic-based defectoscopy.

### Key Capabilities
- Simulate ultrasonic A-scan response with or without defects.
- Display amplitude and time shift due to delamination or cracks.
- Visualize cross-section and top view of the pipe and sensor deployment.

### Developed by: 
**Mohamed LARBI ZEGHLACHE**
 EXPEC-ARC / PTD / AWSFA - 2025
""")
