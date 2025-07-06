import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle, Circle, Wedge
import numpy as np
from config import INCH_TO_METER

def show_visualization():
    st.title("📷 Pipe and Tool Visualization")
    config = st.session_state["config"]
    layer_data = config["layer_data"]
    Z_fluid = config["Z_fluid"]
    defect_type = config["defect_type"]
    defect_layer = config["defect_layer"] - 1  # convert to zero-index
    total_thickness = config.get("total_thickness", 1.0)
    cmap = plt.get_cmap("tab20")
    
    # --------- 1) Horizontal Cross Section (FULL WIDTH) ---------
    fig1 = plt.figure(figsize=(12, 4))
    ax1 = fig1.add_subplot(111)

    y = 0.2
    H = 0.6
    x = 0.1

    # Tool Body
    W_tool = 0.25
    ax1.add_patch(Rectangle((x, y), W_tool, H, color='gray'))
    ax1.text(x + W_tool / 2, y + H + 0.05, "Tool Body", ha='center')
    x += W_tool

    # Arm + Fluid
    W_arm = 0.2
    ax1.add_patch(Rectangle((x, y), W_arm, H, color='skyblue'))
    ax1.add_patch(Rectangle((x, y + H / 2 - 0.05), W_arm, 0.1, color='black'))
    ax1.text(x + W_arm / 2, y + H + 0.05, "Fluid + Arm", ha='center')
    x += W_arm

    # Sensor
    W_sensor = 0.15
    ax1.add_patch(Rectangle((x, y), W_sensor, H, color='red'))
    ax1.text(x + W_sensor / 2, y + H + 0.05, "Sensor", ha='center')
    x += W_sensor

    # Fluid Gap
    W_gap = 0.1
    ax1.add_patch(Rectangle((x, y), W_gap, H, color='skyblue'))
    ax1.text(x + W_gap / 2, y + H + 0.05, f"Gap\nZ={Z_fluid:.2f}", ha='center')
    x += W_gap

    # Pipe Layers
    for i, (label, t, Z) in enumerate(layer_data):
        W = t
        color = cmap(i)
        ax1.add_patch(Rectangle((x, y), W, H, color=color, ec='black'))
        ax1.text(x + W / 2, y + H + 0.05, f"Layer {i+1}\nZ={Z:.2f}\n{t:.2f}\"",
                 ha='center', fontsize=7)

        if defect_type == "Delamination" and i == defect_layer:
            ax1.add_patch(Rectangle((x - 0.01, y), 0.02, H,
                                    color='white', ec='red', lw=2))
            ax1.text(x, y + H + 0.05, "Delam.", color='red', fontsize=7, ha='left')
        elif defect_type == "Crack" and i == defect_layer:
            ax1.plot([x, x + W], [y + H / 2, y + H / 2], 'k--', lw=2)
            ax1.text(x + W / 2, y - 0.1, "Crack", ha='center', color='black', fontsize=7)
        x += W

    ax1.set_xlim(0, x )
    #ax1.set_ylim(0, y + H + 0.4)
    ax1.axis('off')
    fig1.suptitle("Cross-Section: Tool → Arm → Sensor → Gap → Pipe Layers", fontsize=8)
    st.pyplot(fig1, use_container_width=True)
