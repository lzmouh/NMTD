# config.py

# ----- Physical constants -----
INCH_TO_METER    = 0.0254
DEFAULT_GAP_INCH = 0.1
DEFAULT_VELOCITY = 2000

# ----- Fluid database -----
fluid_impedance_db = {
    "Water":                 1.48,
    "Oil":                   1.20,
    "Water-based Mud (WBM)":1.60,
    "Oil-based Mud (OBM)":   1.30,
    "Diesel":                1.25,
    "Other":                 None
}

default_densities = {
    "Water":                 1.0,
    "Oil":                   0.85,
    "Water-based Mud (WBM)":1.2,
    "Oil-based Mud (OBM)":   1.1,
    "Diesel":                0.82
}

# ----- Commercial pipes database -----
PIPE_DB = {
    "GRE (Glass-Reinforced Epoxy)": [
        {
            "name": "Liner",
            "thickness": 0.15,
            "Z": 2.6,
            "material": "GRE (Glass-Reinforced Epoxy)",
            "v": 2500,
            "alpha0": 0.03,
            "n_exp": 1.2,
        },
        {
            "name": "Structural",
            "thickness": 0.6,
            "Z": 3.2,
            "material": "GRE (Glass-Reinforced Epoxy)",
            "v": 2700,
            "alpha0": 0.05,
            "n_exp": 1.3,
        },
        {
            "name": "Coating",
            "thickness": 0.25,
            "Z": 2.2,
            "material": "GRE (Glass-Reinforced Epoxy)",
            "v": 2400,
            "alpha0": 0.02,
            "n_exp": 1.1,
        }
    ],

    "HDPE (High-Density Polyethylene)": [
        {
            "name": "Inner Layer",
            "thickness": 0.25,
            "Z": 1.8,
            "material": "HDPE",
            "v": 2200,
            "alpha0": 0.08,
            "n_exp": 1.6,
        },
        {
            "name": "Middle Core",
            "thickness": 0.5,
            "Z": 1.7,
            "material": "HDPE",
            "v": 2100,
            "alpha0": 0.09,
            "n_exp": 1.5,
        },
        {
            "name": "Outer Jacket",
            "thickness": 0.25,
            "Z": 1.6,
            "material": "HDPE",
            "v": 2150,
            "alpha0": 0.07,
            "n_exp": 1.4,
        }
    ],

    "RTP (Reinforced Thermoplastic Pipe)": [
        {
            "name": "Inner Liner (Polymer)",
            "thickness": 0.2,
            "Z": 1.6,
            "material": "PEEK",
            "v": 2300,
            "alpha0": 0.06,
            "n_exp": 1.3,
        },
        {
            "name": "Reinforcement (Fiberglass)",
            "thickness": 0.5,
            "Z": 3.8,
            "material": "GFRP",
            "v": 3200,
            "alpha0": 0.05,
            "n_exp": 1.2,
        },
        {
            "name": "Outer Jacket",
            "thickness": 0.3,
            "Z": 1.7,
            "material": "HDPE",
            "v": 2100,
            "alpha0": 0.08,
            "n_exp": 1.5,
        }
    ]
}

# ----- Material properties database -----
MATERIAL_DB = {
    "GRE (Glass-Reinforced Epoxy)":   {"v":2000, "alpha0":0.05, "n":1.2},
    "HDPE":                           {"v":1900, "alpha0":0.04, "n":1.1},
    "RTP (Thermoplastic)":           {"v":1800, "alpha0":0.06, "n":1.3},
    "GRP (Glass-Reinforced Plastic)": {"v":1950, "alpha0":0.05, "n":1.2},
    "Custom":                        {"v":None, "alpha0":None, "n":None},
}

# ----- Default configuration -----
DEFAULT_CONFIG = {
    # Fluid & well conditions
    "fluid":            "Water",
    "fluid_density":    1.0,
    "Z_fluid":          1.48,
    "fluid_velocity":   1480,

    # Layers: list of dicts with per-layer params
    "num_layers":       3,
    "layer_data": [
        {
            "name":      "Layer 1",
            "thickness": 0.2,
            "Z":         2.5,
            "material":  "GRE (Glass-Reinforced Epoxy)",
            "v":         MATERIAL_DB["GRE (Glass-Reinforced Epoxy)"]["v"],
            "alpha0":    MATERIAL_DB["GRE (Glass-Reinforced Epoxy)"]["alpha0"],
            "n_exp":     MATERIAL_DB["GRE (Glass-Reinforced Epoxy)"]["n"]
        },
        {
            "name":      "Layer 2",
            "thickness": 0.3,
            "Z":         3.0,
            "material":  "HDPE",
            "v":         MATERIAL_DB["HDPE"]["v"],
            "alpha0":    MATERIAL_DB["HDPE"]["alpha0"],
            "n_exp":     MATERIAL_DB["HDPE"]["n"]
        },
        {
            "name":      "Layer 3",
            "thickness": 0.5,
            "Z":         2.8,
            "material":  "RTP (Thermoplastic)",
            "v":         MATERIAL_DB["RTP (Thermoplastic)"]["v"],
            "alpha0":    MATERIAL_DB["RTP (Thermoplastic)"]["alpha0"],
            "n_exp":     MATERIAL_DB["RTP (Thermoplastic)"]["n"]
        }
    ],

    "total_thickness":  sum([0.2, 0.3, 0.5]),

    # Defect settings
    "defect_type":      "None",
    "defect_layer":     1,

    # Chirp transmitter defaults
    "chirp_start_mhz":  0.5,
    "chirp_end_mhz":    5.0,
    "chirp_sweep_us":   50.0,
    "sampling_rate":    100e6,
    "tx_chirp_t":       [],
    "tx_chirp_waveform":[]
}
