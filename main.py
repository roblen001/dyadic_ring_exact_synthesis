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
print(f"[Generate] Creating a {2**num_qubits} x {2**num_qubits} matrix "
      f"({num_qubits} qubits, {depth} random generation steps).", flush=True)
print(f"[Trace] Recording is {'enabled' if GENERATE_VISUALIZATION_TRACE else 'disabled'}.", flush=True)

matrix = generate_unitary_matrix(num_qubits=num_qubits, depth=depth)
original_matrix = matrix.copy()

print("[Generate] Exact dyadic matrix ready. Starting synthesis.", flush=True)

# 2. exact synthesis algo we will get G_1*G_2*...*G_l*V = Id following
if GENERATE_VISUALIZATION_TRACE:
    from visualization.trace_recorder import TraceRecorder

    visualization_trace = TraceRecorder(original_matrix, num_qubits=num_qubits)
    synthesis_generators = synthesize(matrix, trace=visualization_trace)
else:
    synthesis_generators = synthesize(matrix)

# reconstruct original matrix from the recorded generators
print(f"[Verify] Reconstructing the input from {len(synthesis_generators)} generators.", flush=True)

synthesized_matrix = generate_identity_matrix(len(original_matrix))

for generator in synthesis_generators:
    G = generator_to_matrix(generator, len(original_matrix))
    synthesized_matrix = synthesized_matrix @ G

# check reconstructed matrix equals original matrix
if np.array_equal(original_matrix, synthesized_matrix):
    print("Synthesis verified successfully.", flush=True)
else:
    raise ValueError("Synthesis verification failed.")

# Save after exact verification, independently of the optional simulator.
if GENERATE_VISUALIZATION_TRACE:
    print("[Trace] Finalizing and saving the visualization trace...", flush=True)
    trace_path = visualization_trace.finish(
        matrix, synthesis_generators, synthesized_matrix
    )
    print(f"Visualization trace saved to: {trace_path}", flush=True)


# 3. create qiskit circuit from synthesized generators
print("[Qiskit] Building the circuit from the synthesized generators...", flush=True)

synthesized_circuit = create_qiskit_circuit(
    synthesis_generators,
    num_qubits,
)

# 4. verify Qiskit circuit implements the original matrix
print("[Qiskit] Computing its operator and checking against the input matrix...", flush=True)

qiskit_matrix = Operator(synthesized_circuit).data
original_qiskit_matrix = np.array(original_matrix, dtype=complex)

if np.allclose(
    qiskit_matrix,
    original_qiskit_matrix,
    atol=1e-10,
):
    print("Qiskit circuit verified successfully.", flush=True)
    print("[Done] Synthesis and circuit verification complete.", flush=True)
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
