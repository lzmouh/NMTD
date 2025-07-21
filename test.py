# config.py

# ----- Physical constants -----
INCH_TO_METER    = 0.0254
DEFAULT_GAP_INCH = 0.1
DEFAULT_VELOCITY = 2000

# ----- Fluid property database -----
FLUID_DB = {
    "Water": {
        "name": "Water",
        "velocity": 1480,
        "density": 1.0,
        "Z": 1.48
    },
    "Oil": {
        "name": "Oil",
        "velocity": 1400,
        "density": 0.85,
        "Z": 1.20
    },
    "Water-based Mud (WBM)": {
        "name": "Water-based Mud (WBM)",
        "velocity": 1450,
        "density": 1.2,
        "Z": 1.60
    },
    "Oil-based Mud (OBM)": {
        "name": "Oil-based Mud (OBM)",
        "velocity": 1420,
        "density": 1.1,
        "Z": 1.30
    },
    "Diesel": {
        "name": "Diesel",
        "velocity": 1390,
        "density": 0.82,
        "Z": 1.25
    },
    "Other": {
        "name": "Other",
        "velocity": 1450,
        "density": 1.0,
        "Z": 1.45
    }
}

# ----- Commercial pipes database -----
PIPE_DB = {
    "RTP_HDPE_Glass_HDPE": {
        "description": "Reinforced Thermoplastic Pipe with HDPE–Glass–HDPE layers",
        "layers": [
            {"name": "Inner HDPE", "material": "HDPE", "Z": 1.9, "v": 2200, "alpha0": 0.3, "n_exp": 1.2, "thickness": 0.2},
            {"name": "Glass Reinforcement", "material": "Glass Fiber", "Z": 2.7, "v": 2700, "alpha0": 0.5, "n_exp": 1.4, "thickness": 0.4},
            {"name": "Outer HDPE", "material": "HDPE", "Z": 1.9, "v": 2200, "alpha0": 0.3, "n_exp": 1.2, "thickness": 0.2}
        ],
        "bonded": True,
        "total_thickness": 0.8,
        "pressure_rating_bar": 200
    },

    "TCP_PEEK_Carbon_PEEK": {
        "description": "Thermoplastic Composite Pipe with PEEK–Carbon–PEEK",
        "layers": [
            {"name": "Inner PEEK", "material": "PEEK", "Z": 2.3, "v": 2450, "alpha0": 0.4, "n_exp": 1.3, "thickness": 0.15},
            {"name": "Carbon Fiber", "material": "Carbon Fiber", "Z": 3.5, "v": 2800, "alpha0": 0.6, "n_exp": 1.5, "thickness": 0.5},
            {"name": "Outer PEEK", "material": "PEEK", "Z": 2.3, "v": 2450, "alpha0": 0.4, "n_exp": 1.3, "thickness": 0.15}
        ],
        "bonded": True,
        "total_thickness": 0.8,
        "temperature_C": 160
    },

    "GRE_Epoxy_GRE_Epoxy": {
        "description": "Glass Reinforced Epoxy with alternating Epoxy–Glass–Epoxy layers",
        "layers": [
            {"name": "Inner Epoxy", "material": "Epoxy", "Z": 2.0, "v": 2500, "alpha0": 0.35, "n_exp": 1.3, "thickness": 0.15},
            {"name": "Glass Reinforcement", "material": "Glass Fiber", "Z": 2.7, "v": 2700, "alpha0": 0.55, "n_exp": 1.4, "thickness": 0.4},
            {"name": "Outer Epoxy", "material": "Epoxy", "Z": 2.0, "v": 2500, "alpha0": 0.35, "n_exp": 1.3, "thickness": 0.15}
        ],
        "bonded": True,
        "total_thickness": 0.7,
        "temperature_C": 120
    },

    "HDPE_SingleLayer": {
        "description": "Standard HDPE single layer pipe",
        "layers": [
            {"name": "HDPE", "material": "HDPE", "Z": 1.9, "v": 2200, "alpha0": 0.3, "n_exp": 1.2, "thickness": 1.0}
        ],
        "bonded": False,
        "total_thickness": 1.0,
        "pressure_rating_bar": 160
    }
}

# ----- Layer type database -----
LAYER_DB = {
    "Anti-Corrosion Layer":       {"thickness": 0.12, "Z": 1.8, "v": 2000, "alpha0": 0.08, "n_exp": 1.4},
    "Barrier Layer":              {"thickness": 0.10, "Z": 3.0, "v": 2600, "alpha0": 0.05, "n_exp": 1.3},
    "Braided Jacket":             {"thickness": 0.20, "Z": 2.6, "v": 2600, "alpha0": 0.05, "n_exp": 1.3},
    "Carbon Fiber":               {"thickness": 0.50, "Z": 3.5, "v": 2800, "alpha0": 0.6,  "n_exp": 1.5},
    "Coating":                    {"thickness": 0.20, "Z": 2.2, "v": 2400, "alpha0": 0.02, "n_exp": 1.1},
    "Conductive Shield":          {"thickness": 0.10, "Z": 3.5, "v": 2800, "alpha0": 0.04, "n_exp": 1.2},
    "Epoxy Matrix":               {"thickness": 0.30, "Z": 2.5, "v": 2400, "alpha0": 0.05, "n_exp": 1.2},
    "Glass Fabric":               {"thickness": 0.25, "Z": 3.3, "v": 3000, "alpha0": 0.04, "n_exp": 1.3},
    "Glass Reinforcement":        {"thickness": 0.40, "Z": 2.7, "v": 2700, "alpha0": 0.55, "n_exp": 1.4},
    "HDPE":                       {"thickness": 1.00, "Z": 1.9, "v": 2200, "alpha0": 0.3,  "n_exp": 1.2},
    "Helical Wrap":               {"thickness": 0.35, "Z": 2.4, "v": 2600, "alpha0": 0.05, "n_exp": 1.3},
    "Inner Epoxy":                {"thickness": 0.15, "Z": 2.0, "v": 2500, "alpha0": 0.35, "n_exp": 1.3},
    "Inner HDPE":                 {"thickness": 0.20, "Z": 1.9, "v": 2200, "alpha0": 0.3,  "n_exp": 1.2},
    "Inner Liner":                {"thickness": 0.15, "Z": 2.6, "v": 2500, "alpha0": 0.03, "n_exp": 1.2},
    "Inner Liner (Polymer)":      {"thickness": 0.20, "Z": 1.6, "v": 2300, "alpha0": 0.06, "n_exp": 1.3},
    "Insulation":                 {"thickness": 0.40, "Z": 1.5, "v": 1800, "alpha0": 0.10, "n_exp": 1.5},
    "Outer Epoxy":                {"thickness": 0.15, "Z": 2.0, "v": 2500, "alpha0": 0.35, "n_exp": 1.3},
    "Outer HDPE":                 {"thickness": 0.20, "Z": 1.9, "v": 2200, "alpha0": 0.3,  "n_exp": 1.2},
    "Outer Jacket":               {"thickness": 0.25, "Z": 1.7, "v": 2150, "alpha0": 0.07, "n_exp": 1.4},
    "PEEK":                       {"thickness": 0.15, "Z": 2.3, "v": 2450, "alpha0": 0.4,  "n_exp": 1.3},
    "Polymer Core":               {"thickness": 0.30, "Z": 1.9, "v": 2300, "alpha0": 0.06, "n_exp": 1.3},
    "Protective Sheath":          {"thickness": 0.25, "Z": 2.0, "v": 2100, "alpha0": 0.06, "n_exp": 1.4},
    "Reinforced Core":            {"thickness": 0.50, "Z": 3.0, "v": 2900, "alpha0": 0.06, "n_exp": 1.3},
    "Reinforcement (Fiberglass)": {"thickness": 0.50, "Z": 3.8, "v": 3200, "alpha0": 0.05, "n_exp": 1.2},
    "Reinforcement Layer":        {"thickness": 0.50, "Z": 3.8, "v": 3200, "alpha0": 0.04, "n_exp": 1.2},
    "Structural Layer":           {"thickness": 0.60, "Z": 3.2, "v": 2700, "alpha0": 0.05, "n_exp": 1.3},
    "Thermoplastic Tape":         {"thickness": 0.20, "Z": 2.0, "v": 2200, "alpha0": 0.06, "n_exp": 1.3},
    "Woven Fiber":                {"thickness": 0.30, "Z": 2.8, "v": 2500, "alpha0": 0.07, "n_exp": 1.2}
}

# ----- Default configuration -----
DEFAULT_CONFIG = {
    "pipe_type": "Custom Pipe",
    "fluid": "Water",
    "fluid_density": 1.0,            # g/cc
    "Z_fluid": 1.48,                 # MRayl
    "fluid_velocity": 1480,          # m/s (computed dynamically if needed)

    "num_layers": 3,
    "layer_data": [
        {
            "name": "Liner",
            "material": "GRE (Glass-Reinforced Epoxy)",
            "thickness": 0.15,
            "Z": 2.6,
            "v": 2500,
            "alpha0": 0.03,
            "n_exp": 1.2
        },
        {
            "name": "Structural",
            "material": "GRE (Glass-Reinforced Epoxy)",
            "thickness": 0.6,
            "Z": 3.2,
            "v": 2700,
            "alpha0": 0.05,
            "n_exp": 1.3
        },
        {
            "name": "Coating",
            "material": "GRE (Glass-Reinforced Epoxy)",
            "thickness": 0.25,
            "Z": 2.2,
            "v": 2400,
            "alpha0": 0.02,
            "n_exp": 1.1
        }
    ],

    "total_thickness": 1.0,           # in

    "defect_type": "None",            # or "Crack", "Delamination"
    "defect_layer": 1,                # 1-indexed

    "f_start_mhz": 0.5,
    "f_end_mhz": 5.0,
    "sweep_us": 50.0,
    "sampling_rate": 100_000_000      # Hz (100 MHz)
}

