# config.py

# ----- Physical constants -----
INCH_TO_METER   = 0.0254      # 1 inch = 0.0254 m
DEFAULT_GAP_INCH= 0.1         # fluid pad clearance (in)
DEFAULT_VELOCITY= 2000        # m/s (baseline ultrasonic speed)

# ----- Fluid database -----
fluid_impedance_db = {
    "Water":                1.48,   # MRayl
    "Oil":                  1.20,
    "Water-based Mud (WBM)":1.60,
    "Oil-based Mud (OBM)":  1.30,
    "Diesel":               1.25,
    "Other":                None
}

default_densities = {
    "Water":                1.0,    # g/cc
    "Oil":                  0.85,
    "Water-based Mud (WBM)":1.2,
    "Oil-based Mud (OBM)":  1.1,
    "Diesel":               0.82
}

# ----- Default configuration -----
DEFAULT_CONFIG = {
    # Fluid & layers
    "fluid":            "Water",
    "fluid_density":    1.0,       # g/cc
    "Z_fluid":          1.48,      # MRayl
    "fluid_velocity":   1480,      # m/s (computed)

    "num_layers":       5,
    "layer_data": [
        ["Layer 1", 0.2, 2.5],
        ["Layer 2", 0.2, 2.5],
        ["Layer 3", 0.2, 2.5],
        ["Layer 4", 0.2, 2.5],
        ["Layer 5", 0.2, 2.5]
    ],
    "total_thickness":  1.0,       # inches

    # Defect settings
    "defect_type":      "None",    # "None", "Delamination", or "Crack"
    "defect_layer":     1,         # 1-based index

    # Chirp transmitter defaults
    "chirp_start_mhz":  0.5,       # MHz
    "chirp_end_mhz":    5.0,       # MHz
    "chirp_sweep_us":   50.0,      # µs
    "sampling_rate":    100e6,     # Hz

    # These will be populated by simulator.py
    "tx_chirp_t":       [],        # list of time stamps (s)
    "tx_chirp_waveform":[]         # list of chirp amplitudes
}
