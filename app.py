import streamlit as st
import json
from config import DEFAULT_CONFIG
from simulator import show_simulator
from plots import show_plots
from plot2 import show_plots2
from visualization import show_visualization
from about import show_about
from streamlit_option_menu import option_menu

st.set_page_config(page_title="NMTD App", layout="wide")

# Sidebar navigation
with st.sidebar:
    page = option_menu(
        menu_title="NMTD Menu",
        options=["Simulator", "Plots", "Plot2", "Visualization", "About"],
        icons=["cpu", "bar-chart-line", "bounding-box", "info-circle"],
        default_index=0,
        styles={
            "container": {
                "padding": "5px",
                "background-color": "#f0f2f6",
                "width": "100%",
            },
            "icon": {
                "color": "black",
                "font-size": "18px"
            },
            "nav-link": {
                "font-size": "18px",
                "text-align": "left",
                "margin": "5px",
                "padding": "10px",
                "border-radius": "6px",
                "--hover-color": "#d3d3d3"
            },
            "nav-link-selected": {
                "background-color": "#a9a9a9",
                "color": "white"
            }
        }
    )

# Page dispatch
if page == "Simulator":
    show_simulator()
elif page == "Plots":
    show_plots()
elif page == "Visualization":
    show_visualization()
elif page == "About":
    show_about()
