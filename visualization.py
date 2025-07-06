import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Arc, Wedge
import numpy as np

def show_visualization(config):
    layer_data = config["layer_data"]
    Z_fluid = config["Z_fluid"]
    defect_type = config["defect_type"]
    defect_layer = config["defect_layer"] - 1  # zero-based
    total_thickness = config.get("total_thickness", 1.0)
    cmap = plt.get_cmap("tab20")

    # -------- 1) Horizontal Cross-Section (Top Bar) --------
    fig1 = plt.figure(figsize=(16, 3))
    ax1 = fig1.add_subplot(111)
    y, H, x = 0.2, 0.6, 0.1

    ax1.add_patch(Rectangle((x, y), 0.25, H, color='gray'))
    ax1.text(x + 0.125, y + H + 0.05, "Tool Body", ha='center')
    x += 0.25

    ax1.add_patch(Rectangle((x, y), 0.2, H, color='skyblue'))
    ax1.add_patch(Rectangle((x, y + H/2 - 0.05), 0.2, 0.1, color='black'))
    ax1.text(x + 0.1, y + H + 0.05, "Fluid + Arm", ha='center')
    x += 0.2

    ax1.add_patch(Rectangle((x, y), 0.15, H, color='red'))
    ax1.text(x + 0.075, y + H + 0.05, "Sensor", ha='center')
    x += 0.15

    ax1.add_patch(Rectangle((x, y), 0.1, H, color='skyblue'))
    ax1.text(x + 0.05, y + H + 0.05, f"Gap\nZ={Z_fluid:.2f}", ha='center')
    x += 0.1

    for i, (label, t, Z) in enumerate(layer_data):
        ax1.add_patch(Rectangle((x, y), t, H, color=cmap(i), ec='black'))
        ax1.text(x + t/2, y + H + 0.05, f"Layer {i+1}\nZ={Z:.2f}\n{t:.2f}\"", ha='center', fontsize=7)

        if defect_type == "Delamination" and i == defect_layer:
            ax1.add_patch(Rectangle((x - 0.01, y), 0.02, H, color='white', ec='red', lw=2))
            ax1.text(x, y + H + 0.05, "Delam.", color='red', fontsize=8, ha='left')
        elif defect_type == "Crack" and i == defect_layer:
            ax1.plot([x, x + t], [y + H / 2, y + H / 2], 'k--', lw=2)
            ax1.text(x + t / 2, y - 0.1, "Crack", ha='center', color='black', fontsize=8)
        x += t

    ax1.set_xlim(0, x + 1)
    ax1.set_ylim(0, y + H + 0.4)
    ax1.axis('off')
    ax1.set_title("Cross-Section: Tool → Arm → Sensor → Gap → Pipe Layers")
    st.pyplot(fig1, use_container_width=True)

    # -------- 2) Top View Drawing --------
    fig2 = plt.figure(figsize=(8, 8))
    ax2 = fig2.add_subplot(111)

    pipe_id = 6.0
    tool_d = 3.0
    pad_gap = 0.1
    pad_span = 45
    r_inner = pipe_id / 2
    tool_r = tool_d / 2
    r_current = r_inner
    layer_radii = []

    for i, (_, t, _) in enumerate(layer_data):
        r_outer = r_current + t
        color = cmap(i)
        ax2.add_patch(Wedge((0, 0), r_outer, 0, 360, width=t, facecolor=color, lw=0))
        layer_radii.append((r_current, r_outer, color))
        r_current = r_outer

    ax2.add_patch(Circle((0, 0), r_current, edgecolor='black', facecolor='none', lw=1))
    ax2.add_patch(Circle((0, 0), r_inner, color='skyblue', ec='black'))
    ax2.add_patch(Circle((0, 0), tool_r, color='gray', ec='black'))

    for ang in [0, 90, 180, 270]:
        rad = np.deg2rad(ang)
        x0 = tool_r * np.cos(rad)
        y0 = tool_r * np.sin(rad)
        x1 = (r_inner - pad_gap) * np.cos(rad)
        y1 = (r_inner - pad_gap) * np.sin(rad)
        ax2.plot([x0, x1], [y0, y1], 'red', lw=3)
        ax2.add_patch(Arc((0, 0), 2 * (r_inner - pad_gap), 2 * (r_inner - pad_gap),
                          theta1=ang - pad_span / 2, theta2=ang + pad_span / 2, color='red', lw=6))

    if defect_type == "Delamination":
        r_delam = r_inner + sum(layer_data[i][1] for i in range(defect_layer))
        ax2.add_patch(Wedge((0, 0), r_delam + 0.01, 270, 315, width=0.05,
                            facecolor='white', edgecolor='red', lw=0.2))
    elif defect_type == "Crack":
        r_start = r_inner + sum(layer_data[i][1] for i in range(defect_layer))
        r_end = r_start + layer_data[defect_layer][1]
        ang = np.deg2rad(10)
        x1, y1 = r_start * np.cos(ang), r_start * np.sin(ang)
        x2, y2 = r_end * np.cos(ang), r_end * np.sin(ang)
        ax2.plot([x1, x2], [y1, y2], 'k--', lw=2)

    ax2.set_aspect('equal')
    ax2.set_xlim(-r_current - 2, r_current + 2)
    ax2.set_ylim(-r_current - 2, r_current + 2)
    ax2.axis('off')
    ax2.set_title("Top View: Tool & Pads inside Multilayer Pipe")
    st.pyplot(fig2)
