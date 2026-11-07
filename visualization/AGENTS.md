# Visualization maintenance contract

## Compiler boundary

- The user authorizes implementation work inside this package. Compiler changes
  are limited to explicitly requested additive tracing.
- Never replace, reorder, refactor, rename or delete existing compiler statements,
  change algorithm decisions, or fix unrelated bugs. If an existing statement
  must change, show the exact minimal diff and obtain permission unless that
  change is already authorized. Filesystem permissions still apply.
- Keep instrumentation optional and observational. Disabled tracing may import the
  lightweight root `synthesis_trace` interface and make no-op hook calls, as approved
  for the compiler tracing refactor. No visualization/recorder imports, snapshots,
  trace payload construction, proof computations or output writes when disabled.
  Pass only existing compiler values to hooks; snapshot synchronously in the real
  recorder. Check enabled/disabled results, operation sequence and input mutation.
- Raw traces are immutable evidence. Presentation edits belong in a sidecar.
  Missing witnesses require better recording, not invented history.

## Read the smallest relevant surface

| Task | Start here |
|---|---|
| Human workflow and reusable prompts | README.md |
| Short videos, case selection, formula anchors | dyadic_viz/presentation.py |
| Summary/formula animation | dyadic_viz/presentation_scene.py |
| Existing semantic animations | dyadic_viz/kinetic_stage.py |
| Detailed H tensor H row arithmetic | dyadic_viz/kinetic_arithmetic.py |
| Glyphs, vectors, matrices, symbols | dyadic_viz/kinetic_objects.py |
| CLI, artifacts, manifest | visualize_process.py |
| Dispatch and measured timings | dyadic_viz/render_scene.py |
| Narration and timing exports | dyadic_viz/storyboard.py |
| New compiler/ring | docs/trace-contract.md, schema/, dyadic_viz/validation.py, trace_recorder.py |

`handlers.py` and `components.py` are the older panel presentation. The active
renderer uses `kinetic_stage.py`; do not modify the inactive path by mistake.
Exclude virtual environments, media and outputs from source searches.

## Presentation policy

Show one detailed example of each meaningful case, then labelled exact before/
after summaries of repeats. Preserve new cases even late in a run. A lower k
or another column alone is not novelty. Distinguish already-normalized groups,
sign correction, mixing with/without an LDE drop, multi-level drops, swaps,
terminal signs and final exact verification.

The detector is specific to the current profile, not a universal proof classifier.
Use `case_tags` or extend the classifier with a focused fixture for a new branch.
Prefer recipe edits over Python changes for formulas, examples and retained events.
Anchor to event IDs, not movie timestamps. Unknown mathematics must not silently
reuse dyadic rules. Do not infer a new ring's synthesis theorem from its name.

Every source event must appear exactly once, in order, in `source_event_ids`.
Formula events cover no source events. Summaries use recorded endpoints from a
fully validated trace. Never delete source operations to produce a shorter fake
execution. Preserve all verification events and complete operation audit data.
Reject unknown events and unsupported scalars rather than silently skipping them.

Use proper gate symbols, "group" rather than "quartet", and short mathematical
annotations instead of prose panels. Distinguish v, old-scale numerators 2^k v,
and reduced-scale numerators. Displayed fractions are not even integers. Keep
transpose/adjoint, orthogonal/unitary, and inverse-order distinctions accurate.
Author-supplied formulas and prose are not formally checked proof certificates.

Aim for roughly three minutes for a demo; preserve novel cases rather than
indiscriminately speeding up or truncating. Review measured duration and reading
time before recording. Voiceover editing is separate; do not modify an existing
recording without authorization.

## Checks and incremental changes

From this folder, using the visualization Python environment:

```
python -m unittest discover -s tests -p test_presentation.py
python visualize_process.py examples/rich_dyadic_trace.json --storyboard-only --output-dir output/check-plan
python visualize_process.py examples/rich_dyadic_trace.json --presentation examples/presentation.json --quality low --output-dir output/check-preview
```

Full discovery also includes current-compiler integration tests and expects the
compiler in the parent directory. In a standalone extraction run test_validation,
test_storyboard, test_generalization and test_presentation separately; move the
compiler integration tests with its adapter.

Test source immutability, ordered coverage, distinct/late cases, formula anchors
and bounded growth on repeats. Validate exact mathematics before planning.
Preview changed scenes and inspect frames; tests alone do not establish visual
quality. Preserve v1 compatibility. A future ring profile needs exact scalar
parsing/formatting, conjugation, generator checks, invariants and case selection.
Do not claim that generic ring interfaces exist until they are implemented.
