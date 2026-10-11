"""General Constants"""

# configs maybe move to configs.py
allowed_rings = ["dyadic"]
num_qubits = 3
depth = 80

# record a JSON trace for the optional Manim visualization.
GENERATE_VISUALIZATION_TRACE = False

from fractions import Fraction

import numpy as np

# H⊗H
hh = Fraction(1, 2) * np.array([
    [1,  1,  1,  1],
    [1, -1,  1, -1],
    [1,  1, -1, -1],
    [1, -1, -1,  1]
], dtype=object)