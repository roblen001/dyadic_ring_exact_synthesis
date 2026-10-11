"""Main Script

Anytime a proposition, lemma, or theorem is quoted it is from the following paper: (Amy, Glaudell, & Ross, 2020) unless expliciltly stated otherwise.

Disclaimer:
    - AI (codex) created the code for visualization using Manim to create a demo video, 
     which is in a seperate folder labeled "visualization".
    - AI also wrote docstrings, readme, and tracing for the animation.
    - The rest of the code was written with ancient methods (my two hands).


# LIMITATION: my synthesis currently returns the papers generators
    # (-1)_[a], X_[a,b], and (H⊗H)_[a,b,c,d],
    # which act directly on selected rows/basis states of the full matrix.
    # But when we run it withh qiski each generator is embedded directly 
    # as a full Qiskit unitary acting on all qubits
"""
import numpy as np
from constants import depth, num_qubits, GENERATE_VISUALIZATION_TRACE
from exact_synthesis import synthesize
from matrix_generation import generate_unitary_matrix
from qiskit import transpile
from qiskit.quantum_info import Operator
from qiskit_circuit import create_qiskit_circuit
from utils import generate_identity_matrix, generator_to_matrix

# 1. randomly select matrix over dyadic ring
matrix = generate_unitary_matrix(num_qubits=num_qubits, depth=depth)
original_matrix = matrix.copy()

# 2. exact synthesis algo we will get G_1*G_2*...*G_l*V = Id following
if GENERATE_VISUALIZATION_TRACE:
    from visualization.trace_recorder import TraceRecorder

    visualization_trace = TraceRecorder(original_matrix, num_qubits=num_qubits)
    synthesis_generators = synthesize(matrix, trace=visualization_trace)
else:
    synthesis_generators = synthesize(matrix)

# reconstruct original matrix from the recorded generators
synthesized_matrix = generate_identity_matrix(len(original_matrix))

for generator in synthesis_generators:
    G = generator_to_matrix(generator, len(original_matrix))
    synthesized_matrix = synthesized_matrix @ G

# check reconstructed matrix equals original matrix
if np.array_equal(original_matrix, synthesized_matrix):
    print("Synthesis verified successfully.")
else:
    raise ValueError("Synthesis verification failed.")

# Save after exact verification, independently of the optional simulator.
if GENERATE_VISUALIZATION_TRACE:
    trace_path = visualization_trace.finish(
        matrix, synthesis_generators, synthesized_matrix
    )
    print(f"Visualization trace saved to: {trace_path}")


# 3. create qiskit circuit from synthesized generators
synthesized_circuit = create_qiskit_circuit(
    synthesis_generators,
    num_qubits,
)

# 4. verify Qiskit circuit implements the original matrix
qiskit_matrix = Operator(synthesized_circuit).data
original_qiskit_matrix = np.array(original_matrix, dtype=complex)

if np.allclose(
    qiskit_matrix,
    original_qiskit_matrix,
    atol=1e-10,
):
    print("Qiskit circuit verified successfully.")
else:
    raise ValueError("Qiskit circuit verification failed.")


# 5. run on the simualtor just to show it runs and hit the requirement

simulation_circuit = synthesized_circuit.copy()

# adds mesurement to the end of the circuit for all teh qubits
simulation_circuit.measure_all()

# convert the qiskit circuit into ionq compatible gate set
simulation_circuit = transpile(
    simulation_circuit,
    backend=backend
)

job = backend.run(
    simulation_circuit,
    shots=1000
)

result = job.result()
counts = result.get_counts()

print("IonQ simulator run completed successfully.")
print(counts)

# 7. save trace stack for manim visualization
