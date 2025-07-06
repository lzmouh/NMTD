INCH_TO_METER = 0.0254
DEFAULT_GAP_INCH = 0.1
DEFAULT_VELOCITY = 2000  # m/s

fluid_impedance_db = {
    "Water": 1.48,
    "Oil": 1.20,
    "Water-based Mud (WBM)": 1.60,
    "Oil-based Mud (OBM)": 1.30,
    "Diesel": 1.25,
    "Other": None
}

default_densities = {
    "Water": 1.0,
    "Oil": 0.85,
    "Water-based Mud (WBM)": 1.2,
    "Oil-based Mud (OBM)": 1.1,
    "Diesel": 0.82
}

DEFAULT_CONFIG = {
    "fluid": "Water",
    "Z_fluid": 1.48,
    "fluid_density": 1.0,
    "fluid_velocity": 1480,
    "num_layers": 5,
    "layer_data": [["Layer 1", 0.2, 2.5]] * 5,
    "total_thickness": 1.0,
    "defect_type": "None",
    "defect_layer": 2
}
