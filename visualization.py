import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle, Circle, Wedge
import numpy as np
from config import INCH_TO_METER, DEFAULT_GAP_INCH

def show_visualization():
    st.title("📷 Pipe and Tool Visualization")

    config       = st.session_state["config"]
    layer_data   = config["layer_data"]
    Z_fluid      = config["Z_fluid"]
    defect_type  = config["defect_type"]
    defect_layer = config["defect_layer"] - 1  # zero-based
    total_thick  = config.get("total_thickness", sum(l["thickness"] for l in layer_data))
    cmap         = plt.get_cmap("tab20")

    # --------- 1) Horizontal Cross Section ---------
    fig1, ax1 = plt.subplots(figsize=(12, 4))
    y, H, x = 0.2, 0.6, 0.1

    # Tool Body
    W_tool = 0.25
    ax1.add_patch(Rectangle((x, y), W_tool, H, color='gray'))
    ax1.text(x + W_tool/2, y+H+0.05, "Tool Body", ha='center', fontsize=7)
    x += W_tool

    # Arm + Fluid
    W_arm = 0.2
    ax1.add_patch(Rectangle((x, y), W_arm, H, color='skyblue'))
    ax1.add_patch(Rectangle((x, y+H/2-0.05), W_arm, 0.1, color='black'))
    ax1.text(x+W_arm/2, y+H+0.05, "Fluid + Arm", ha='center', fontsize=7)
    x += W_arm

    # Sensor
    W_sensor = 0.15
    ax1.add_patch(Rectangle((x, y), W_sensor, H, color='red'))
    ax1.text(x+W_sensor/2, y+H+0.05, "Sensor", ha='center', fontsize=7)
    x += W_sensor

    # Fluid Gap
    W_gap = DEFAULT_GAP_INCH
    ax1.add_patch(Rectangle((x, y), W_gap, H, color='skyblue'))
    ax1.text(x+W_gap/2, y+H+0.05, f"Gap\nZ={Z_fluid:.2f}", ha='center', fontsize=7)
    x += W_gap

    # Pipe Layers
    for i, layer in enumerate(layer_data):
        t = layer["thickness"]
        Z = layer["Z"]
        name = layer.get("name", f"Layer {i+1}")
        color = cmap(i)

        ax1.add_patch(Rectangle((x, y), t, H, color=color, ec='black'))
        ax1.text(x + t/2, y+H+0.05, f"{name}\nZ={Z:.2f}\n{t:.2f}\"",
                 ha='center', fontsize=7)

        if defect_type=="Delamination" and i==defect_layer:
            ax1.add_patch(Rectangle((x-0.01, y), 0.02, H, color='white', ec='red', lw=2))
            ax1.text(x, y+H+0.05, "Delam.", color='red', fontsize=7, ha='left')
        elif defect_type=="Crack" and i==defect_layer:
            ax1.plot([x, x+t], [y+H/2]*2, 'k--', lw=2)
            ax1.text(x+t/2, y-0.1, "Crack", ha='center', color='black', fontsize=7)

        x += t

    ax1.set_xlim(0, x+0.1)
    ax1.set_ylim(0, y+H+0.1)
    ax1.axis('off')
    fig1.suptitle("Cross-Section: Tool → Arm → Sensor → Gap → Pipe Layers", fontsize=12)
    st.pyplot(fig1, use_container_width=True)

    # --------- 2) Top View Drawing ---------
    fig2, ax2 = plt.subplots(figsize=(8, 8))
    pipe_id, tool_d, pad_gap, pad_span = 6.0, 3.0, 0.1, 45
    r_inner = pipe_id / 2
    tool_r  = tool_d / 2
    r_curr  = r_inner
    layer_radii = []

    # Layers as wedges
    for i, layer in enumerate(layer_data):
        t = layer["thickness"]
        color = cmap(i)
        r_outer = r_curr + t
        ax2.add_patch(Wedge((0,0), r_outer, 0, 360, width=t,
                            facecolor=color, edgecolor=None, lw=0))
        layer_radii.append((r_curr, r_outer, color))
        r_curr = r_outer

    # Outer pipe line
    ax2.add_patch(Circle((0,0), r_curr, facecolor='none', edgecolor='black', lw=1))

    # Fluid ring & tool
    ax2.add_patch(Circle((0,0), r_inner, color='skyblue', ec='black'))
    ax2.add_patch(Circle((0,0), tool_r, color='gray', ec='black'))

    # Arms & pads
    for ang in [0,90,180,270]:
        rad = np.deg2rad(ang)
        x0,y0 = tool_r*np.cos(rad), tool_r*np.sin(rad)
        x1,y1 = (r_inner-pad_gap)*np.cos(rad), (r_inner-pad_gap)*np.sin(rad)
        ax2.plot([x0,x1],[y0,y1], 'red', lw=3)
        ax2.add_patch(Arc((0,0), 2*(r_inner-pad_gap), 2*(r_inner-pad_gap),
                          theta1=ang-pad_span/2, theta2=ang+pad_span/2,
                          color='red', lw=6))

    # Defects
    if defect_type=="Delamination":
        r_delam = r_inner + sum(l["thickness"] for l in layer_data[:defect_layer])
        ax2.add_patch(Wedge((0,0), r_delam+0.01, 225, 315,
                            width=0.05, facecolor='white', edgecolor='red', lw=0.2))
        ang, rad = 292.5, np.deg2rad(292.5)
        x,y = r_delam*np.cos(rad), r_delam*np.sin(rad)
        xt,yt = (r_delam+total_thick+1)*np.cos(rad), (r_delam+total_thick+1)*np.sin(rad)
        ax2.annotate("Delamination", xy=(x,y), xytext=(xt,yt),
                     color='red', fontsize=7,
                     arrowprops=dict(arrowstyle="->", color='red'))
    elif defect_type=="Crack":
        r0 = r_inner + sum(l["thickness"] for l in layer_data[:defect_layer])
        r1 = r0 + layer_data[defect_layer]["thickness"]
        ang, rad = 10, np.deg2rad(10)
        x1,y1 = r0*np.cos(rad), r0*np.sin(rad)
        x2,y2 = r1*np.cos(rad), r1*np.sin(rad)
        ax2.plot([x1,x2],[y1,y2],'k--',lw=2)
        ax2.annotate("Crack", xy=((x1+x2)/2,(y1+y2)/2),
                     xytext=(x2+1, y2),
                     arrowprops=dict(arrowstyle="->",color='black'),
                     fontsize=7)

    # Layer labels
    for i,(r0,r1,c) in enumerate(layer_radii):
        angle, rad = 30+25*i, np.deg2rad(30+25*i)
        x,y = (r1-0.1)*np.cos(rad),(r1-0.1)*np.sin(rad)
        xt,yt = (r1+1.0)*np.cos(rad),(r1+1.0)*np.sin(rad)
        ax2.annotate(f"Layer {i+1}", xy=(x,y), xytext=(xt,yt),
                     color=c, fontsize=7,
                     arrowprops=dict(arrowstyle="->", color=c))

    # Tool & sensor & fluid gap annotations
    for label, radius, color in [
        ("Tool Body", tool_r, 'black'),
        ("Fluid Gap", r_inner, 'blue'),
        ("Sensor Pad", r_inner-pad_gap, 'red')
    ]:
        ang, rad = -45, np.deg2rad(-45)
        x,y = radius*np.cos(rad), radius*np.sin(rad)
        xt,yt = (r_curr+1.0)*np.cos(rad),(r_curr+1.0)*np.sin(rad)
        ax2.annotate(label, xy=(x,y), xytext=(xt,yt),
                     arrowprops=dict(arrowstyle="->", color=color),
                     fontsize=7, color=color)

    ax2.set_aspect('equal')
    ax2.set_xlim(-r_curr-1, r_curr+1)
    ax2.set_ylim(-r_curr-1, r_curr+1)
    ax2.axis('off')
    ax2.set_title("Top View: Tool & Pads inside Multilayer Pipe", fontsize=10)
    st.pyplot(fig2, use_container_width=True)

    # --------- 3) Side View Drawing ---------
    fig3, ax3 = plt.subplots(figsize=(12, 2))
    x, Ht, yt = 0.1, 0.5, 0.2

    # Tool Body (longitudinal)
    L_tool = 1.0
    ax3.add_patch(Rectangle((x, yt), L_tool, Ht, color='gray'))
    ax3.text(x+L_tool/2, yt+Ht+0.05, "Tool Body", ha='center', fontsize=7)
    x += L_tool

    # Fluid Gap
    L_gap = DEFAULT_GAP_INCH
    ax3.add_patch(Rectangle((x, yt), L_gap, Ht, color='skyblue'))
    ax3.text(x+L_gap/2, yt+Ht+0.05, "Fluid Gap", ha='center', fontsize=7)
    x += L_gap

    # Pipe Layers Longitudinal
    for i, layer in enumerate(layer_data):
        t = layer["thickness"]
        name = layer.get("name", f"Layer {i+1}")
        color = cmap(i)
        ax3.add_patch(Rectangle((x, yt), t, Ht, color=color, ec='black'))
        ax3.text(x+t/2, yt+Ht+0.05, name, ha='center', fontsize=7)
        if defect_type=="Delamination" and i==defect_layer:
            ax3.add_patch(Rectangle((x-0.01, yt), 0.02, Ht,
                                    facecolor='white', edgecolor='red', lw=2))
            ax3.text(x, yt+Ht+0.05, "Delam.", color='red', fontsize=7, ha='left')
        elif defect_type=="Crack" and i==defect_layer:
            ax3.plot([x, x+t], [yt+Ht/2]*2, 'k--', lw=2)
            ax3.text(x+t/2, yt-0.1, "Crack", ha='center', fontsize=7)
        x += t

    ax3.set_xlim(0, x+0.5)
    ax3.set_ylim(0, yt+Ht+0.3)
    ax3.axis('off')
    ax3.set_title("Side View: Tool → Gap → Layers", fontsize=10)
    st.pyplot(fig3, use_container_width=True)
