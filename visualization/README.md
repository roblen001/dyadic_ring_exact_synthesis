# Visualization

This folder contains the optional trace recorder and Manim animation pipeline.
The synthesis algorithm stays in the project root.

## Generate a trace

In `constants.py`, set `GENERATE_VISUALIZATION_TRACE = True` (the default), then
run the project normally from its root:

```powershell
python main.py
```

After exact reconstruction succeeds, the path to a new JSON file in
`visualization/traces/` is printed. Tracing uses your existing NumPy dependency;
it does not import Manim, render a video, or contact a simulator.
Set the flag to `False` to skip the recorder import, snapshot collection, trace
calculations, and file output. Previously generated files are left intact.

The trace is saved before the Qiskit circuit/simulator section. The existing
`main.py` references an undefined `backend` later in that section; that unrelated
code has been left unchanged. A later simulator failure does not remove a saved
exact trace.

## Render the saved JSON

Use a Python 3.12 interpreter for the tested Manim environment. From the project root:

```powershell
python -m venv visualization/.venv
visualization/.venv/Scripts/python.exe -m pip install -r visualization/requirements.txt
visualization/.venv/Scripts/python.exe visualization/visualize_process.py visualization/traces/YOUR_TRACE.json --validate-only
visualization/.venv/Scripts/python.exe visualization/visualize_process.py visualization/traces/YOUR_TRACE.json --quality medium --output-dir visualization/output
```

Replace `YOUR_TRACE.json` with the filename printed by `main.py`. The output is
a silent MP4 plus a narration script, captions, and measured event timings.
`--quality low` is useful for a quick preview. Large matrices and long circuit
sequences currently shrink to fit and may need layout improvements.

The recorder emits schema 1.1.0 with `integral_then_normalize`, matching the
compiler's two passes. `column_integral` marks an integral column without claiming
it is already its target basis vector. Existing 1.0.0 example traces still work.
See `docs/trace-contract.md` and `schema/synthesis-trace.schema.json` for details.
