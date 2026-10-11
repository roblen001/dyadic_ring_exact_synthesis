"""Handling qiskit circuit generations
"""

import numpy as np
from qiskit import QuantumCircuit
from utils import generator_to_matrix


def create_qiskit_circuit(
    generator_list: list,
    num_qubits: int,
) -> QuantumCircuit:
    """
    Create a Qiskit circuit from the synthesized generator sequence.

    Args:
        generator_list: Ordered generators returned by exact synthesis.
        num_qubits: Number of qubits in the circuit.

    Returns:
        Qiskit circuit implementing the synthesized matrix.
    """
    circuit = QuantumCircuit(num_qubits)
    matrix_size = 2 ** num_qubits

    for generator in reversed(generator_list):
        G = generator_to_matrix(generator, matrix_size)
        G = np.array(G)

        # LIMITATIOON: my synthesis currently returns the papers generators
        # (-1)_[a], X_[a,b], and (H⊗H)_[a,b,c,d],
        # which act directly on selected rows/basis states of the full matrix.
        # Here, each generator is embedded directly as a full Qiskit unitary
        # acting on all qubits

        circuit.unitary(
            G,
            qubits=list(range(num_qubits)),
            label=generator["type"],
        )

    return circuit