# Compiler-pass visualization

Humans supply the compiler, examples, and editorial direction; the assistant
maintains this package. You do not need to learn Manim.

**Compiler boundary: add tracing only.** Do not replace, delete, reorder,
refactor, rename, or fix existing compiler statements. Preserve algorithm choices,
results, and numerical behavior. Permission to develop this package does not
authorize changes to the compiler beyond additive instrumentation.

## Prompts to copy

There are no magic keywords. Supply both repository paths, entry point and input.

### Connect a compiler

> Use the visualization package at `<visualization path>` with my compiler at
> `<compiler path>`. Read its README and AGENTS.md first. My entry point is
> `<command>` and a representative input is `<input/path>`. Add only the tracing
> needed to record its complete exact execution. Never replace, delete, reorder,
> refactor or fix existing compiler statements. Keep tracing optional: when
> disabled, no trace imports, snapshots, trace computations or output writes.
> If changing an existing statement is unavoidable, show the exact minimal change
> and obtain my permission first. Verify that tracing on/off preserves results,
> operation sequence and input mutation behavior. Adapt the visualization to my
> actual number system and proof rules; do not assume the real dyadic proof applies
> to another ring. Document the command and output path. Validate before rendering.

Record existing decisions, exact before/after states, operation order, branch
reasons and witnesses. Never choose extra operations or invent a prettier history.

### Make a short demo

> Visualize `<trace.json>` in compact mode. Explain one representative example
> of each genuinely different case. Include already-normalized residues and
> residues requiring correction if both occur. Condense repeated groups,
> denominator levels, checks and swaps into labelled before/after summaries.
> Preserve the full raw trace and exact verification. Review case coverage and
> narration, render a low-quality preview and report its actual duration. Aim for
> about three minutes without hiding new mathematical cases to hit a time limit.
> Use mathematical symbols and motion, not paragraphs on screen.

### Revise the explanation

> For `<trace.json>` and `<presentation.json>`, add `<formula or visual idea>`
> after `<event ID, described operation, or current video timestamp>`. Keep the
> compiler and raw trace unchanged. Resolve timestamps to source events and use
> a presentation overlay where possible. Add a reusable scene component only
> when needed. Distinguish the actual column from its scaled numerator vector.
> Revalidate, preview the change, and update narration and timing exports.

The assistant chooses the implementation inside this package. Missing information
requires additional recording or a clearly identified derived artifact with
provenance. Never overwrite compiler evidence or fabricate states for an animation.

## Generate a trace with the current compiler

From the compiler root, set GENERATE_VISUALIZATION_TRACE = True in constants.py
and run `python main.py`. After exact reconstruction succeeds, the program prints
the new JSON path in visualization/traces/. False skips recorder imports,
collection, trace calculations and output. Existing traces are left intact.
The lightweight `synthesis_trace.py` interface is still imported and its hooks
make no-op calls when recording is disabled.
Tracing does not import Manim, render videos, or contact a simulator. A later
unrelated simulator failure does not remove a successfully saved trace.

### Writing compiler hooks

`main.py` calls `create_trace(original_matrix, enabled=GENERATE_VISUALIZATION_TRACE,
num_qubits=num_qubits)` once, passes the result to `synthesize`, and calls
`trace.finish(reduced_matrix, generators, reconstructed_matrix)` only after exact
reconstruction succeeds. The factory selects a real recorder or a stateless
do-nothing observer, so callers do not need visualization conditionals.

At compiler entry, `bind_trace(trace, matrix, generator_list)` binds the live
matrix and generator list. The compiler then uses short semantic hooks:

```python
trace.start_column(i, lde)
# ... existing choices and matrix operations ...
trace.sign_correction()  # immediately after the sign flip and generator append
trace.mixing()           # immediately after H tensor H and generator append
trace.finish_sweep(lde)
trace.column_integral(i)
```

The normalization pass uses `trace.start_column(i, 0, phase="normalize")`,
`trace.permutation()`, `trace.terminal_sign()`, and `trace.column_complete(i)`.
Before a sweep, `trace.start_sweep(lde, scaled_column, odd_indices, groups,
sign_indices)` receives the compiler's actual decisions. Keep these hooks at
their semantic boundaries; operations snapshot immediately, never after a later
mutation. Pass already-computed values, not `.copy()`, formatting, or new payloads.

The adapter delegates to `visualization/trace_recorder.py`, which owns snapshots,
narration, exact checks and JSON output. Existing `synthesize(matrix)` and
`synthesize(matrix, trace=TraceRecorder(...))` callers remain supported.

## Run the visualization

Use Python 3.12 for the tested environment. From the **visualization folder**:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --only-binary=av -r requirements.txt
.venv/Scripts/python.exe visualize_process.py traces/YOUR_TRACE.json --validate-only
.venv/Scripts/python.exe visualize_process.py traces/YOUR_TRACE.json --quality low --output-dir output/preview
```

Replace YOUR_TRACE.json with your file. Always invoke the script with Python.
From the compiler root, prefix the command paths with visualization/, or use your
activated visualization environment. Low quality is 480p/15 fps, medium is
720p/30 fps, and high is 1080p/60 fps. Quality does not select mathematical steps.

## Short videos are the default

`--detail compact` is the default. It shows the first example of each recognized
case in detail and condenses consecutive repeats. Cases include sign correction
versus already-normalized groups, mixing with/without an immediate LDE decrease,
multi-level drops, swaps, terminal signs and verification. A new rule ID or an
author-supplied case tag also preserves detail. A different k or another column
alone is not a new case. Long recovery circuits use a bounded overview; the full
gate sequence remains in the trace.

This is a policy for the current dyadic profile, not automatic understanding of
all proofs. Name extra important branches so the assistant can tag them.
Compact is not a hard three-minute truncation: distinct cases or retained detail
may take longer. Renders over four minutes print a review note.
Use `--detail full` only when you want an exhaustive movie.

Use `--storyboard-only` to inspect case decisions and coverage before rendering.
Use a new output directory for each revision:

```powershell
.venv/Scripts/python.exe visualize_process.py traces/YOUR_TRACE.json --storyboard-only --output-dir output/plan
.venv/Scripts/python.exe visualize_process.py traces/YOUR_TRACE.json --presentation presentation.json --quality low --output-dir output/revision
```

Compact timings are visual timings: narration is a draft to edit and rehearse,
not automatic speech synchronization. Existing manually edited videos are not
regenerated by these changes. Large matrices still need a readability review.

## Formulas and editorial settings

Pass a separate JSON file with `--presentation presentation.json`. Replace event
IDs with those from your trace/storyboard. A formula keeps its surrounding action
in detail, so its anchor cannot drift to another step.

```json
{
  "version": 1,
  "examples_per_case": 1,
  "retain_events": ["event_00018"],
  "case_tags": {"event_00030": "special boundary case"},
  "formulas": [
    {
      "after_event": "event_00009",
      "expression": "v = w/2^k",
      "hold_seconds": 2,
      "narration": "The vector and its scaled integer representation are different objects."
    }
  ]
}
```

Expressions use Matplotlib mathtext without dollar delimiters, not arbitrary
LaTeX. Double backslashes in JSON. Rendering checks syntax; inspect layout in a
preview and check mathematical meaning. An annotation is not a verified theorem.
[examples/presentation.json](examples/presentation.json) works with
[examples/rich_dyadic_trace.json](examples/rich_dyadic_trace.json).

## Saved artifacts

- MP4: silent animation, without prose captions burned in.
- .storyboard.json: presented events, source coverage, case decisions and timings.
- .narration.md / .srt: editorial drafts aligned to presented events.
- .timeline.json: actual timings and source-event references.
- .trace.json: complete validated input, including condensed operations.
- .presentation.json / .manifest.json: settings, hashes, quality and duration.

Every source event remains accounted for once, in order. Summaries show recorded
endpoints and label omissions; they do not claim skipped operations never happened.
Full original narration stays in the raw trace.

## Assistant maintenance / future standalone repository

Read [AGENTS.md](AGENTS.md) for the short implementation map. Read
[docs/trace-contract.md](docs/trace-contract.md) and schema/ when adapting traces.
Rendering does not import the compiler. Keep trace_recorder.py and current-compiler
integration tests with its adapter when extracting the package.

Supported: complete successful real orthogonal dyadic traces, schemas 1.0.0 and
1.1.0, including integral-then-normalize passes. Z[i,1/2] requires exact complex
numbers, a new mathematical profile, validation and appropriate scenes; changing
a ring label is insufficient.
