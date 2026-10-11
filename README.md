# Dyadic Ring Exact Synthesis

A project implementing exact synthesis of real orthogonal matrices over the
dyadic ring, Z[1/2]: rational numbers whose denominators are powers of two.
The synthesis follows the construction of Amy, Glaudell, and Ross (2020),
the reference used for propositions, lemmas, and theorems in the code.

The program generates a random matrix, synthesizes it using the generators
`(-1)_[a]`, `X_[a,b]`, and `(H ⊗ H)_[a,b,c,d]`, and checks that their product
reconstructs the original matrix exactly. It then builds a Qiskit circuit and
checks its operator against the input matrix. An optional trace records the
synthesis steps for a Manim animation.

## AI contributions

As stated in the `main.py` docstring, AI (Codex) created the Manim visualization
code in `visualization/`, the animation tracing, docstrings, and README
documentation. The rest of the code, including the synthesis algorithm, was
written in the good old fashion way.

## Run the project

From the project folder, use Python 3.12 and run these commands in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install numpy qiskit
.\.venv\Scripts\python.exe main.py
```

Configure the run in `constants.py`:

- `num_qubits = 4`: generates a 16 × 16 matrix.
- `depth = 80`: controls the random circuit generation steps.
- `GENERATE_VISUALIZATION_TRACE = True`: saves a JSON trace under
  `visualization/traces/` and prints its path. Set it to `False` to skip tracing.

Successful checks print `Synthesis verified successfully.` and
`Qiskit circuit verified successfully.` The final simulator section currently
references an undefined `backend`; it needs a configured backend to run.
The exact verification and trace saving happen before that section.

## Make the animation

Follow [the visualization instructions](visualization/README.md) to install
the rendering dependencies and turn the generated JSON trace into a demo video.
Running `main.py` records the trace; rendering is a separate command.

## Current limitation

Each synthesized generator acts on selected basis states and is embedded as a
full Qiskit unitary on all qubits. The project does not yet decompose those
generators into an optimized hardware gate set.