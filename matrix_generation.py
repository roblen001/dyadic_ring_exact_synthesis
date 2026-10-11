"""Generation of matrix over dyadic ring functionality"""

import random
from fractions import Fraction

import numpy as np
from constants import allowed_rings
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator


# qiskit has a way of generating random circuits but does
# not let use restrict the gates used to create the circuit
# since we want our matrix of a dyadic ring we are restricted to
# the following gates: {X, CX, CCX, H⊗H}
def generate_random_dyadic_circuit(num_qubits: int, depth: int) -> QuantumCircuit:
    """
    Create a random circuit using X, CX, CCX, and H⊗H gates.

    Args:
        num_qubits: Number of qubits in the circuit.
        depth: Number of random gate-selection steps to apply.

    Returns:
        A random QuantumCircuit built from X, CX, CCX, and H⊗H gates.
    """
    qc = QuantumCircuit(num_qubits)

    gates = ["x"]

    if num_qubits >= 2:
        gates.extend(["cx", "hh"])

    if num_qubits >= 3:
        gates.append("ccx")

    for _ in range(depth):
        gate = random.choice(gates)

        if gate == "x":
            q = random.randrange(num_qubits)
            qc.x(q)

        elif gate == "cx" and num_qubits >= 2:
            c, t = random.sample(range(num_qubits), 2)
            qc.cx(c, t)

        elif gate == "ccx" and num_qubits >= 3:
            c1, c2, t = random.sample(range(num_qubits), 3)
            qc.ccx(c1, c2, t)

        elif gate == "hh" and num_qubits >= 2:
            q1, q2 = random.sample(range(num_qubits), 2)
            qc.h(q1)
            qc.h(q2)

    return qc


# need to clean the entries from a qiskit circuit into fractions so it works with mod
def to_dyadic_fraction(
    value: float,
    max_exponent: int = 20,
    tolerance: float = 1e-10,
) -> Fraction:
    """
    Convert a floating-point value to an exact dyadic fraction.

    Args:
        value: Floating-point value to convert.
        max_exponent: Largest power of two allowed in the denominator.
        tolerance: Maximum allowed floating-point error.

    Returns:
        The corresponding exact dyadic Fraction.

    Raises:
        ValueError: If no dyadic fraction is found within the tolerance.
    """
    for q in range(max_exponent + 1):
        denominator = 2**q
        numerator = round(value * denominator)

        if abs(value - numerator / denominator) < tolerance:
            return Fraction(numerator, denominator)

    raise ValueError(f"{value} is not sufficiently close to a dyadic fraction.")


def generate_unitary_matrix(
    num_qubits: int, depth: int = 80, ring: str = "dyadic"
) -> np.ndarray:
    """
    Generate a random unitary matrix over a supported ring.

    Args:
        num_qubits: Number of qubits in the generated circuit.
        depth: Number of random gate-selection steps to apply.
        ring: Ring used to determine the allowed circuit generators.

    Returns:
        A matrix over requested ring.

    Raises:
        ValueError: If the requested ring is not currently supported.
    """
    if ring not in allowed_rings:
        raise ValueError(
            f"Rings not in allowed types currently only allow: {allowed_rings}"
        )

    if ring == "dyadic":
        qc = generate_random_dyadic_circuit(num_qubits, depth)
        matrix = Operator(qc).data
        # entries in this form:  0.5+0.j we need fracitons for modulo to work in the synthesis method
        fractional_rows = []
        for row in np.asarray(matrix):
            fractional_row = []

            for entry in row:
                if abs(entry.imag) > 1e-10:
                    raise ValueError(f"Expected real dyadic entry, got {entry}")

                fractional_entry = to_dyadic_fraction(entry.real)
                fractional_row.append(fractional_entry)

            fractional_rows.append(fractional_row)

        fractional_matrix = np.array(fractional_rows, dtype=object)

        return fractional_matrix