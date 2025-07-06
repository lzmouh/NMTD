import streamlit as st
import json
from config import DEFAULT_CONFIG
from simulator import show_simulator
from plots import show_plots
from visualization import show_visualization
from about import show_about

# Inject custom CSS
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="NMTD Simulator", layout="wide")

# Session state initialization
if "config" not in st.session_state:
    st.session_state["config"] = json.loads(json.dumps(DEFAULT_CONFIG))  # Deep copy

# Elegant button menu
st.sidebar.title("Navigation")
page = st.sidebar.radio("📘 Go to", ["Simulator", "Plots", "Visualization", "About"])

if page == "Simulator":
    show_simulator()
elif page == "Plots":
    show_plots()
elif page == "Visualization":
    show_visualization(config)
elif page == "About":
    show_about()
