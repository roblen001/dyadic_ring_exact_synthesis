# Exact dyadic synthesis visualization

A compiler-independent Manim pipeline for exact synthesis traces over `Z[1/2]`. It validates a supplied run, then animates its mathematical objects: extracted columns, integer lifts, residue clocks, sign flips, row combinations, row swaps, and recovery. Explanatory prose stays in the voiceover script. No synthesizer is implemented.

Start with the [complete contract and compiler emission guide](trace-contract.md), in the requested order: schema, example, required compiler fields, architecture, remaining mathematical choices, implementation. The machine-readable contract is [schema/synthesis-trace.schema.json](../schema/synthesis-trace.schema.json). The realistic mock is [examples/synthesis_trace.json](../examples/synthesis_trace.json).

## Run

Use Python 3.12. A project-local `.venv` has been prepared in this workspace. On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe visualize_process.py examples\synthesis_trace.json --validate-only
.\.venv\Scripts\python.exe visualize_process.py examples\synthesis_trace.json --quality medium
```

With that environment activated, the intended workflow is simply:

```text
python visualize_process.py synthesis_trace.json
```

Other modes:

```text
python visualize_process.py synthesis_trace.json --storyboard-only
python visualize_process.py synthesis_trace.json --quality low
python visualize_process.py synthesis_trace.json --quality high --output-dir my-video
python -m unittest discover -s tests -v
```

Low quality is 480p/15fps; medium is 720p/30fps; high is 1080p/60fps in the pinned Manim release. The CLI renders with Cairo and disables animation caching because trace JSON is external to the scene's source code.

## Fresh environment

```text
python -m venv .venv
python -m pip install -r requirements.txt
```

Activate `.venv` before the second command, or invoke its Python explicitly. Dependencies are Manim Community **0.19.0** and JSON Schema 4.x. This project deliberately pins the tested Manim release. Windows Python 3.12 wheels were used here. Other platforms may need Manim's native Cairo/Pango prerequisites; see [the official installation documentation](https://docs.manim.community/en/v0.19.0/installation.html).

For only validation and script export, install `requirements-validation.txt`. No LaTeX executable is needed: Matplotlib mathtext supplies Computer Modern glyph paths, including exact fractions. No paragraphs, proof panels, status bars, or cards appear in the movie. This pipeline does not synthesize or record speech.

## Outputs

The default output directory is `output/`. A successful render writes:

| File | Purpose |
|---|---|
| `<trace_id>.mp4` | Complete silent animation. |
| `<trace_id>.trace.json` | Immutable copy of the exact rendered input. |
| `<trace_id>.storyboard.json` | Supplied events, operation prefixes, state references, and measured timing. |
| `<trace_id>.narration.md` | Supplied script, timestamps, and explanation/rule/fact editor notes. |
| `<trace_id>.srt` | Draft event-aligned subtitles for editing against your voiceover. |
| `<trace_id>.timeline.json` | Actual event and chapter start/end times. |
| `<trace_id>.manifest.json` | Output locations, quality, duration, and trace SHA-256. |
| `.manim/<run>/.../sections/` | Manim section MP4s and section metadata. |

Manim intermediates are retained for inspection and section editing. The manifest locates them. Each render uses a separate run directory so a failed render cannot accidentally be reported as an old success. Outputs and `.venv` are ignored by Git.

## Source layout

```text
schema/synthesis-trace.schema.json   Closed versioned JSON schema
examples/synthesis_trace.json       Hand-authored signed-quartet witness
docs/trace-contract.md               Public contract + compiler checklist
visualize_process.py                Validate, export, render, package outputs
dyadic_viz/trace.py                  Strict JSON loading
dyadic_viz/validation.py             Exact witness and event-lifecycle checks
dyadic_viz/storyboard.py             Script, storyboard, timeline, SRT exports
dyadic_viz/render_scene.py           Small Manim dispatcher and timing recorder
dyadic_viz/kinetic_stage.py          Continuous mathematical event choreography
dyadic_viz/kinetic_objects.py        Exact math glyphs and movable matrix entries
dyadic_viz/kinetic_arithmetic.py     Supplied K row products and cancellations
tests/                              Contract failures and generic trace tests
```

The renderer requires explicit reasons and preserves them in the storyboard and script. The movie shows supplied exact values moving through each operation. Exact validation detects bad arithmetic, wrong residues, noncanonical dyadics, invalid generator embeddings, inconsistent states, incorrect order, and false verification witnesses. It does **not** formally prove arbitrary explanation text.

V1 ends with a basis-level generator circuit. Hardware/qubit gate lowering and ancilla correctness need additional compiler-provided data and a separately agreed contract. Full details are in the [mathematical scope section](trace-contract.md#5-mathematical-choices-to-settle-before-extending-this-profile).

## Verified in this workspace

- 48 unit tests pass, including exact-number failures, incorrect traces, reversed column order, dimensions 1/3/8, unchanged LDE, and the integral terminal-sign case.
- The kinetic redesign replaces the earlier dashboard renderer. The previous output in `output/` is retained for comparison; the replacement is rendered into `output/kinetic/`.
- The replacement mock rendered at **1280 × 720, 30 fps, 163 seconds**: all 4,890 frames decoded, and all six chapter clips match the measured timeline. Mathematical views and playback of the K chapter were inspected. See `output/kinetic/render-qa.json`; technical validation does not establish an aesthetic match to a reference.
- Voiceover audio and hardware gate lowering are not included. Larger matrices are fitted to the stage; their typography may require a dedicated close-up strategy for presentation use.
