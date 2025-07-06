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

# Define pages
PAGES = {
    "home": "🏠 Home",
    "simulation": "🔬 Simulation",
    "plots": "📊 Plots",
    "visualization": "🧭 Visualization",
    "about": "ℹ️ About"
}

# Track selected page in session state
if "page" not in st.session_state:
    st.session_state.page = "home"

def nav_button(name, key):
    active = (st.session_state.page == key)
    style = f"""
    <style>
    .nav-button-{key} {{
        background-color: {'#4CAF50' if active else '#f0f2f6'};
        color: {'white' if active else '#000000'};
        padding: 0.75em 1em;
        text-align: left;
        border: none;
        border-radius: 0.5em;
        width: 100%;
        font-size: 1.1em;
        margin-bottom: 0.3em;
        cursor: pointer;
    }}
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)
    if st.sidebar.button(name, key=f"navbtn_{key}"):
        st.session_state.page = key

# Render sidebar navigation
st.sidebar.markdown("### 📘 Navigation")
for key, label in PAGES.items():
    nav_button(label, key)

# Page content dispatcher
st.title(PAGES[st.session_state.page])
st.write(f"Currently on **{st.session_state.page.upper()}** page.")

