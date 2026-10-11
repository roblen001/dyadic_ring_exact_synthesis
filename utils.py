"""utils for main.py"""

from fractions import Fraction

import numpy as np
from constants import hh


def generate_identity_matrix(size: int) -> np.ndarray:
    """
    Create an identity matrix using exact Fraction values.

    Args:
        size: Number of rows and columns in the matrix.

    Returns:
        An identity matrix with Fraction entries.
    """
    identity = np.empty((size, size), dtype=object)

    for i in range(size):
        for j in range(size):
            if i == j:
                identity[i][j] = Fraction(1)
            else:
                identity[i][j] = Fraction(0)

    return identity


def generator_to_matrix(generator: dict, size: int) -> np.ndarray:
    """
    Convert a stored generator description into its full matrix form.

    Args:
        generator: Generator description containing its type and indices.
        size: Dimension of the full matrix.

    Returns:
        The full exact matrix representing the generator.

    Raises:
        ValueError: If the generator type is not supported.
    """
    G = generate_identity_matrix(size)

    generator_type = generator["type"]
    indices = generator["indices"]

    if generator_type == "sign_flip":
        index = indices[0]
        G[index, index] = Fraction(-1)

    elif generator_type == "swap":
        i, j = indices
        G[[i, j], :] = G[[j, i], :]

    elif generator_type == "hh":
        G[np.ix_(indices, indices)] = hh

    else:
        raise ValueError(f"Unsupported generator type: {generator_type}")

    return G