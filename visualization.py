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
    fig1 = plt.figure(figsize=(12, 3))
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

    ax1.set_xlim(0, x + 1)
    ax1.set_ylim(0, y + H + 0.4)
    ax1.axis('off')
    fig1.suptitle("Cross-Section: Tool → Arm → Sensor → Gap → Pipe Layers", fontsize=12, y=1.02)
    st.pyplot(fig1, use_container_width=True)

    # --------- 2) Top View Drawing ---------
    fig2 = plt.figure(figsize=(5, 5))
    ax2 = fig2.add_subplot(111)

    pipe_id = 6.0
    tool_d = 3.0
    pad_gap = 0.1
    pad_span = 45

    r_inner = pipe_id / 2
    tool_r = tool_d / 2
    r_current = r_inner
    layer_radii = []

    
    # Step 1: Draw pipe layers as full ring segments (Wedges)
    for i, (_, t, _) in enumerate(layer_data):
        r_outer = r_current + t
        color = cmap(i)
        
        ring = Wedge(center=(0, 0),
                     r=r_outer,
                     theta1=0,
                     theta2=360,
                     width=t,
                     facecolor=color,
                     edgecolor=None,
                     lw=0,
                     zorder=1)
        ax2.add_patch(ring)
        layer_radii.append((r_current, r_outer, color))
        r_current = r_outer    

    # Add thin black ring for outer pipe surface
    outer_radius = r_current  # r_current already includes all layer thickness
    ax2.add_patch(Circle((0, 0),
                         radius=outer_radius,
                         edgecolor='black',
                         facecolor='none',
                         lw=1,
                         zorder=10))
    
    # Fluid gap ring
    ax2.add_patch(Circle((0, 0), r_inner, color='skyblue', ec='black', zorder=3))

    # Tool body
    ax2.add_patch(Circle((0, 0), tool_r, color='gray', ec='black', zorder=4))

    # Arms and pads
    for ang in [0, 90, 180, 270]:
        rad = np.deg2rad(ang)
        x0 = tool_r * np.cos(rad)
        y0 = tool_r * np.sin(rad)
        x1 = (r_inner - pad_gap) * np.cos(rad)
        y1 = (r_inner - pad_gap) * np.sin(rad)
        ax2.plot([x0, x1], [y0, y1], 'red', lw=3, zorder=5)
        ax2.add_patch(Arc((0, 0),
                          2 * (r_inner - pad_gap),
                          2 * (r_inner - pad_gap),
                          theta1=ang - pad_span / 2,
                          theta2=ang + pad_span / 2,
                          color='red', lw=6, zorder=5))

    # Optional defects
    if defect_type == "Delamination":
        r_delam = r_inner + sum(layer_data[i][1] for i in range(defect_layer))
        delam_ring = Wedge(center=(0, 0),
                           r=r_delam + 0.01,  # thin white outer ring
                           theta1=225,
                           theta2=315,
                           width=0.05,
                           facecolor='white',
                           edgecolor='red',
                           lw=0.2,
                           zorder=10)
        ax2.add_patch(delam_ring)
        # Add annotation for delamination
        angle = 292.5
        rad = np.deg2rad(angle)
        x = r_delam * np.cos(rad)
        y = r_delam * np.sin(rad)
        xt = (r_delam + total_thickness + 1.0) * np.cos(rad)
        yt = (r_delam + total_thickness + 1.0) * np.sin(rad)
        ax2.annotate("Delamination",
            xy=(x , y),
            xytext=(xt , yt),
            color='red',
            fontsize=7,
            arrowprops=dict(arrowstyle="->", color='red'))

    elif defect_type == "Crack":
        r_start = r_inner + sum(layer_data[i][1] for i in range(defect_layer))
        r_end = r_start + layer_data[defect_layer][1]
        ang = np.deg2rad(10)
        x1 = r_start * np.cos(ang)
        y1 = r_start * np.sin(ang)
        x2 = r_end * np.cos(ang)
        y2 = r_end * np.sin(ang)
        ax2.plot([x1, x2], [y1, y2], 'black', lw=2, linestyle='--', zorder=10)
        # Add annotation for crack
        ax2.annotate("Crack",
            xy=((x1 + x2) / 2, (y1 + y2) / 2),
            xytext=( x2 + total_thickness + 1.0, y2 ),
            color='black',
            fontsize=7,
            arrowprops=dict(arrowstyle="->", color='black'))
    
    for i, (r_in, r_out, color) in enumerate(layer_radii):
        angle = 30 + i * 25
        rad = np.deg2rad(angle)
        x = (r_out - 0.1) * np.cos(rad)
        y = (r_out - 0.1) * np.sin(rad)
        xt = (r_out + total_thickness + 1.0) * np.cos(rad)
        yt = (r_out + total_thickness + 1.0) * np.sin(rad)
        ax2.annotate(f"Layer {i+1}",
                     xy=(x, y), xytext=(xt, yt),
                     color=color, fontsize=7,
                     arrowprops=dict(arrowstyle="->", color=color))

    # Tool Body Annotation
    angle = 315
    rad = np.deg2rad(angle)
    x = tool_r * np.cos(rad)
    y = tool_r * np.sin(rad)
    xt = (r_inner + total_thickness + 1.0) * np.cos(rad)
    yt = (r_inner + total_thickness + 1.0) * np.sin(rad)
    ax2.annotate("Tool Body",
                 xy=(x, y),
                 xytext=(xt, yt),
                 arrowprops=dict(arrowstyle="->", color='black'),
                 fontsize=8,
                 color='black')

    
    # Sensor Annotation
    r_sensor = r_inner - pad_gap  # where pads are drawn
    angle = -10
    rad = np.deg2rad(angle)
    x = r_sensor * np.cos(rad)
    y = r_sensor * np.sin(rad)
    xt = (r_inner + total_thickness + 1.0) * np.cos(rad)
    yt = (r_inner + total_thickness + 1.0) * np.sin(rad)
    ax2.annotate("Sensor Pad",
                 xy=(x, y),
                 xytext=(xt, yt),
                 arrowprops=dict(arrowstyle="->", color='red'),
                 fontsize=8,
                 color='red')

    # Annotation Fluid Gap
    ax2.annotate("Fluid Gap", xy=(r_inner, 0), xytext=(r_inner + total_thickness + 1.0, 0),
                 arrowprops=dict(arrowstyle="->"), fontsize=7)

    ax2.set_aspect('equal')
    ax2.set_xlim(-r_current - 2, r_current + 2)
    ax2.set_ylim(-r_current - 2, r_current + 2)
    ax2.axis('off')
    ax2.set_title("Top View: Tool & Pads inside Multilayer Pipe")

    st.pyplot(fig2)

