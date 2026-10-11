<img width="1672" height="941" alt="dyadic-ring-exact-synthesis" src="https://github.com/user-attachments/assets/daa469e3-b34d-477d-b1fd-473f78aa2d2b" />

# Dyadic Ring Exact Synthesis

Exact synthesis and visualization of quantum operations over the dyadic ring Z[1/2], following the construction of Amy, Glaudell, and Ross (2020).

The project takes a randomly generated real unitary matrix whose entries are
dyadic fractions, reduces it exactly to the identity using the generators

- `(-1)_[a]`
- `X_[a,b]`
- `(H ⊗ H)_[a,b,c,d]`

and records the sequence of generators used in the reduction.

The generator sequence is then used to reconstruct the original matrix exactly,
providing a direct verification of the synthesis algorithm. The result is also
converted into a Qiskit circuit and independently checked against the original
matrix.

An optional execution trace can be generated and passed to a Manim visualization
that animates the number-theoretic steps of the proof.

## Why this project?

Quantum hardware can only directly perform certain elementary operations, while
algorithms are naturally described by larger unitary matrices. Exact synthesis
asks when a matrix can be decomposed exactly into a restricted collection of
allowed operations and how to construct that decomposition.

This project focuses on the dyadic case

D = Z[1/2] = {u / 2^q | u is an integer and q is a natural number}

The implementation follows Section 5.1 of Amy, Glaudell, and Ross (2020).

The key mathematical idea is to repeatedly reduce the least denominator exponent
of each column. Odd numerator entries are grouped in sets of four, corrected
modulo 4 using sign changes, and acted on by `H ⊗ H`. Once the denominator
exponent reaches zero, sign changes and swaps reduce the column to the
corresponding standard basis vector.

Applying this process to every column reduces the complete matrix to the
identity.

## Project pipeline

The main program performs the following steps:

1. Generate a random real unitary matrix over the dyadic ring.
2. Run the exact synthesis algorithm.
3. Reduce the matrix to the identity while recording every generator.
4. Reconstruct the original matrix from the recorded generators.
5. Verify the reconstruction using exact `Fraction` arithmetic.
6. Build a Qiskit realization of the synthesized generators.
7. Verify the Qiskit circuit operator against the original matrix.
8. Run the circuit on the simulator selected by Qollab.
9. Optionally save a detailed JSON synthesis trace for visualization.

The two main correctness checks are

V_reduced = I

and

V_synthesized = V_original.

Because the synthesis uses Python `Fraction` objects, the mathematical
reconstruction is checked using exact equality rather than floating-point
tolerance.

The Qiskit representation uses floating-point values, so that verification uses
numerical approximate equality.

## Run the project locally

The core synthesis and verification code can be run with Python 3.12.

From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install numpy qiskit
.\.venv\Scripts\python.exe main.py
```

Run parameters can be changed in `constants.py`.

For example:

- `num_qubits = 4` generates a 16 × 16 matrix.
- `depth = 80` controls the number of random gate-selection steps used to
  generate the input matrix.
- `GENERATE_VISUALIZATION_TRACE = True` saves a JSON synthesis trace under
  `visualization/traces/`.
- Set `GENERATE_VISUALIZATION_TRACE = False` to skip trace generation.

Successful verification prints:

```text
Synthesis verified successfully.
Qiskit circuit verified successfully.
```

## Running on Qollab

The submitted Qollab version uses the `backend` object supplied by the Qollab
runtime.

The circuit is transpiled for the selected backend and submitted with

```python
simulation_circuit = transpile(
    simulation_circuit,
    backend=backend
)

job = backend.run(
    simulation_circuit,
    shots=1000
)
```

This means the Qollab version does not require an IonQ API key or a manually
configured `IonQProvider`.

For a purely local run, a compatible Qiskit backend must be configured separately
if the simulator section is enabled.

## Visualization

The `visualization/` directory contains the Manim visualization tooling.

The synthesis algorithm can optionally save a JSON trace containing information
such as

- the current column
- least denominator exponent
- scaled integer vector
- odd-entry groups
- modulo-4 sign corrections
- applied generators
- before/after matrix states
- final generator sequence

The Manim code reads this trace and produces an animation explaining how the
mathematical proof becomes an executable synthesis procedure.

The Manim renderer is intentionally separate from the main Qollab execution path
so that the Qollab project does not depend on Manim.

See [`visualization/README.md`](visualization/README.md) for local rendering
instructions.

## Current limitation

The synthesis algorithm produces the generators used directly in Section 5.1:

- `(-1)_[a]`
- `X_[a,b]`
- `(H ⊗ H)_[a,b,c,d]`

These operations act on selected basis states of the complete matrix.

In the current Qiskit implementation, each synthesized generator is embedded as
a full unitary operation acting on the qubit register.

The paper goes one step further in Proposition 4.4 and shows that these
generators can be implemented using the gate set

{X, CX, CCX, HxH}

with at most one clean ancilla.

That final gate-level construction from Proposition 4.4 is not implemented in
this project.

Therefore the project implements the Section 5.1 exact generator synthesis and
verification, but does not claim to implement the complete Proposition 4.4
decomposition into primitive circuit gates.

## Reference

Matthew Amy, Andrew N. Glaudell, and Neil J. Ross.

**Number-Theoretic Characterizations of Some Restricted Clifford+T Circuits.**

Quantum 4, 252 (2020).

The mathematical synthesis algorithm, lemmas, and theorem numbering referenced
in this repository come from this paper.

## AI contributions

AI tools were used during development.

Codex was used to create the Manim visualization code in `visualization/`,
animation tracing support, docstrings, and README/documentation assistance.

The exact synthesis algorithm itself was implemented manually while working
through the mathematical construction in Amy, Glaudell, and Ross (2020).

## Hackathon

This project was developed for the Qollab × IonQ quantum hackathon.

This effort is supported by Qollab & IonQ.

## Demo

Demo video: **[ADD PUBLIC DEMO VIDEO LINK HERE]**

The demo shows a nontrivial dyadic matrix being synthesized, verified, and
visualized step by step.

## License

MIT License.
