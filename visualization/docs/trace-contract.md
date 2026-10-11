# Compiler → visualization contract, versions 1.0.0 and 1.1.0

## Project integration: two-pass traces (1.1.0)

The project's existing compiler first makes every column integral, then calls
its signed-permutation normalization pass. The recorder preserves this order.
Its traces use `schema_version: "1.1.0"` and the additional problem field
`reduction_strategy: "integral_then_normalize"`.

During the first pass, each column has `column_start`, its recorded analysis and
operations, then `column_integral` with payload `{state_id}`. This event requires
an exact active-column LDE of zero and ends the active column without adding it
to `completed_columns`. It does not claim that the column already equals `e_j`.
After every column has become integral, a second set of `column_start` events
records the final swaps/signs and `column_complete` events in column order.
All other state, generator, operation, recovery, and verification requirements
below remain unchanged. The event envelope and a non-null explanation rule are
required for `column_integral`, just as for the other mathematical events.

Existing `1.0.0` files remain supported and use the original single-pass
`columnwise` lifecycle below. Version `1.1.0` requires `reduction_strategy`,
which can be either `columnwise` or `integral_then_normalize`.

`visualization/trace_recorder.py` implements this recording adapter. It reads
snapshots and decisions from optional callbacks; it neither chooses nor applies
synthesis operations. In the root `constants.py`, the default
`GENERATE_VISUALIZATION_TRACE = True` enables collection in `main.py`.
When false, `main.py` skips the recorder import, construction, callbacks' bodies,
and file creation. The existing algorithm's default `trace=None` remains usable
by other callers without any tracing dependencies.

The remaining sections describe the original 1.0.0 record shapes and invariants,
with the two-pass lifecycle exception stated above.

This is the integration agreement for a compiler that emits complete, successful reductions of real orthogonal matrices over `Z[1/2]`. The compiler owns all mathematical choices and proof explanations. The visualization accepts only a trace; it never invokes a synthesizer.

The normative contract has two parts: [JSON Schema](../schema/synthesis-trace.schema.json) specifies every field and allowed type; the semantic requirements below specify exact equalities, references, and ordering. Both are enforced by `dyadic_viz.validation.validate_trace`. Unknown fields, unknown events, and unsupported schema versions are errors. A schema-only check is not sufficient.

## 1. Complete data contract

### Mathematical profile and number format

The v1 profile is `orthogonal_dyadic`: real `n × n` matrices satisfying `U^T U = I`. General dyadic matrices that are not orthogonal do not belong to this synthesis problem. `n` need not be a power of two. Supply `qubit_count: null` for a purely matrix-level interpretation; a non-null count `q` requires `n = 2^q`.

Each scalar is a canonical dyadic:

```json
{"numerator": "-3", "denominator_exponent": 2}
```

This means exactly `-3 / 2^2`. Numerators and integer lifts are decimal **strings**, so JSON consumers cannot round large integers. No `+` signs, leading zeroes, `-0`, decimal points, or scientific notation. Zero is `{"numerator":"0","denominator_exponent":0}`. A nonzero number with positive exponent has an odd numerator. Integers have exponent zero. Negative exponents are forbidden. Example: encode `2/4` as `1/2`, not as `2/4`.

All matrix entries use this representation, including input, snapshots, generator embeddings, identity, and verification witnesses. Every matrix in `matrices` is full dimension, in row-major nested arrays. An integer lift is stored as a vector, with one entry per original row. A scaled **whole matrix** is unnecessary for this column proof; if your explanation uses one, v1 must be extended rather than asking the renderer to reconstruct an unstated witness.

All indices are zero-based. Row labels, column labels, and ordered generator support refer to matrix coordinates. They are not qubit-wire indices. Every reference resolves within the same file. IDs match `[A-Za-z][A-Za-z0-9_.-]*`; scoped dictionaries permit the same ID in different namespaces.

### Top-level objects

| Field | Compiler responsibility |
|---|---|
| `schema_version` | Exactly `"1.0.0"`. |
| `trace_id`, `title` | Stable filename-safe ID; human-readable animation title. |
| `provenance` | `kind` (`compiler` or `mock`), `producer`, and an honest `note`. |
| `conventions` | `profile:"orthogonal_dyadic"`, `action:"left"`, `index_base:0`, a literal `basis_order` description, `circuit_time_order:"earliest_first"`. |
| `problem` | `dimension`, nullable `qubit_count`, `input_matrix_id`, `target_matrix_id`, `initial_state_id`, and a full permutation `column_order`. Target matrix is identity. |
| `matrices` | Dictionary `matrix_id → exact n × n matrix`. Deduplication is permitted. |
| `rules` | Dictionary `rule_id → {title, statement, source_url}`. URL may be null for your own explanatory statement. |
| `states` | Dictionary of named snapshots, detailed below. |
| `generators` | Dictionary of supplied generators and their full embedded matrices. |
| `operations` | All actual atomic left multiplications in chronological reduction order. |
| `events` | Ordered explanatory animation events; the renderer follows this order literally. |
| `result` | Final state, reduction IDs, recovered product factors, and time-ordered basis-level circuit. |
| `verifications` | Exact input orthogonality, reduction endpoint, and reconstruction checks, exactly once each. |

Nothing depends on a Python class, callback, source-language enum, external file, or compiler implementation. JSON is the complete interchange format. The renderer does not fetch rule URLs.

### Snapshots

Every state has exactly:

```json
{
  "matrix_id": "input",
  "completed_columns": [],
  "focus": {
    "column": 0,
    "target_row": 0,
    "lde": 1,
    "scaled_vector": ["1", "-1", "-1", "1"],
    "residues_mod2": [1, 1, 1, 1],
    "residues_mod4": [1, 3, 3, 1]
  }
}
```

`focus` may be null when no column is being displayed. Otherwise `target_row = column`, `lde` is the active column's **least** nonnegative exponent `k`, and `scaled_vector = 2^k × column`, using the current matrix. Residues are least nonnegative residues, including for negative integers. All three arrays have length `n`.

For canonical dyadics, the checker can verify the column LDE by the largest denominator exponent. That is a consistency check, not a renderer decision. The compiler must still supply the LDE, minimality explanation, and any odd witness the viewer needs.

`completed_columns` is the completed prefix of `problem.column_order`; the initial state must have an empty prefix, even for identity input. Each listed column must equal `e_j` exactly. Every later operation must preserve it. Creating a new state solely to change focus or completion metadata is allowed; its matrix must remain the same. After a `column_complete`, focus may remain on that column or become null. The next `column_start` sets the new focus.

### Generators and operations

Each generator is `{kind, indices, matrix_id, label}`. V1 supports these exact atomic generators:

| `kind` | Ordered support | Full matrix |
|---|---|---|
| `sign` | One row | Identity with that diagonal entry changed to `-1`. |
| `swap` | Two distinct rows | Identity with those rows exchanged. |
| `k` | Four distinct rows | Identity off the support; the following block on the ordered support. |

```text
K = 1/2 × [[1,  1,  1,  1],
           [1, -1,  1, -1],
           [1,  1, -1, -1],
           [1, -1, -1,  1]] = H tensor H
```

The order of K's indices defines the embedding. The compiler must provide the **full embedded matrix**; the validator compares it to the named generator. The renderer can display its support block and act on the full snapshot. All three atomic generators are self-inverse. This does not imply that a product of them is self-inverse.

An operation is:

```json
{
  "id": "op_s1",
  "generator_id": "s1",
  "before_state_id": "c0_start",
  "after_state_id": "c0_sign1",
  "role": "sign_correction",
  "rule_id": "signs"
}
```

Roles are `sign_correction`, `mixing`, `permutation`, or `terminal_sign`, requiring respectively a sign, K, swap, or sign generator. Every operation must have active focus before and after, preserve the focus column and completed-column metadata, and satisfy `M_after = G × M_before` exactly. Adjacent operation matrices join; intervening metadata changes are allowed. The first operation starts at the input matrix. Empty operation lists are valid, for example for an identity input.

Sign corrections are separate atomic operations, including separate snapshots. The facts explaining which signs were chosen belong to events. No grouped word is silently treated as a single self-inverse generator.

### Events and explicit reasons

Every event contains these common fields:

```json
{
  "id": "event_07",
  "type": "residue_analysis",
  "section": {"id": "column_zero", "title": "Column 0: expose the arithmetic"},
  "narration": {
    "text": "The residues are one, three, three, one.",
    "hold_seconds": 3
  },
  "explanation": {
    "rule_id": "signs",
    "summary": "Two residues need sign corrections",
    "facts": [
      {"label": "Residues", "text": "w mod 4 = (1, 3, 3, 1)^T"},
      {"label": "Sign choices", "text": "Flip rows 1 and 2."}
    ]
  },
  "payload": {"state_id": "c0_start", "modulus": 4, "indices": [0, 1, 2, 3]}
}
```

The rule supplies the general statement. `summary`, `facts`, and `narration` supply this run's explanation, including the choice of indices, parity counts, minimality witnesses, preservation argument, or equality at the old scale. These are literal text, not executable TeX or a template into which the renderer invents reasons. Facts are flexible named prose records because different proof presentations need different explanatory detail. A populated text field is not a formal proof certificate: the checker cannot establish the truth or completeness of arbitrary prose.

`rule_id` is required and non-null for all mathematical event types except `input`, `recovery`, and `complete`; for those three it may be null. Their explanation and narration are still required. Selection/application event rules must match the referenced operation's rule. A renderer must reject missing required data rather than substitute a guessed reason.

`hold_seconds` is a finite nonnegative **minimum hold after the event's animation**. It is not an absolute timestamp. The kinetic renderer keeps prose off-screen and exports it to the narration script. Section IDs occupy contiguous blocks and always have the same title. Actual chapter times are measured during rendering.

| Event type | Exact payload | Presentation / meaning |
|---|---|---|
| `input` | `{state_id}` | Introduce the input, membership explanation, provenance, and conventions. First, exactly once. |
| `column_start` | `{state_id}` | Open the next column in `column_order`. |
| `lde_analysis` | `{state_id}` | Display supplied LDE, integral lift, and minimality reason. |
| `residue_analysis` | `{state_id, modulus, indices}` | Modulus is 2 or 4; display supplied residues and highlight the supplied indices. |
| `indices_selected` | `{state_id, indices, purpose}` | Nonempty selection, with its stated purpose. |
| `generator_selected` | `{operation_id}` | Show the next supplied generator without applying it. |
| `sign_correction` | `{operation_id}` | Apply exactly one operation with role `sign_correction`. |
| `generator_applied` | `{operation_id}` | Apply exactly one operation of any other role. |
| `lde_reduced` | `{before_state_id, after_state_id, operation_ids}` | Compare a strictly smaller active-column LDE after a nonempty contiguous batch ending at the most recent operation. |
| `column_complete` | `{state_id, column}` | Add the active column to the completed prefix; its exact target is verified. |
| `recovery` | `{}` | Display the supplied recovered product and supplied circuit sequence. Once, after all columns. |
| `verification` | `{verification_id}` | Display one supplied exact check. Exactly one per verification record. |
| `complete` | `{state_id}` | Final state and successful completion. Last, exactly once. |

Each operation appears in exactly one applying event, in chronological operation order. Analysis events may repeat. Selecting a generator does not increment the operation count. A `terminal_sign` uses `generator_applied`, since it is the integral base case rather than odd-residue normalization.

Non-operation events cannot change the matrix. An LDE comparison is explanatory; it does not apply its batch again. Intermediate quartet operations can leave the column LDE unchanged. A whole-matrix LDE is not assumed to decrease. Emit `lde_reduced` only for a genuine decrease over the supplied batch. The usual multi-quartet sweep can be represented by any number of analysis, sign, and K operations before this event.

### Reduction, product, and circuit order

If reduction operations in chronological order are `g1, ..., gm`, then:

```text
M0 = U
Mt = gt Mt-1
gm ... g2 g1 U = I
U = g1^-1 g2^-1 ... gm^-1
```

`result` contains:

- `final_state_id`: exact identity state with all columns completed.
- `reduction_operation_ids`: every operation ID in reduction chronology.
- `recovered_factors`: `{generator_id, inverse:true}` records in the **written left-to-right product order**, the same generator order as reduction chronology.
- `circuit`: `{representation:"basis_level", time_order:"earliest_first", gates:[...]}`. Each gate has `id`, `generator_id`, `inverse:true`, `label`. Time order on column kets is the **reverse** of the recovered factor list.

There is no separate accumulated-sequence field in every snapshot. The prefix of `operations` reached by applying events is unambiguous, and the storyboard exports that prefix. This avoids inconsistent copies. The compiler must still explicitly emit the final recovered factors and circuit order; the renderer does not derive them as mathematical reasoning.

### Exact verification

Every verification is `{id, kind, passed, left_matrix_id, right_matrix_id, statement}`. Supply exactly these three kinds:

| Kind | Meaning of left witness | Meaning of right witness |
|---|---|---|
| `input_orthogonality` | `U^T U` | Identity. |
| `reduction_identity` | `gm ... g1 U`, also the final snapshot | Identity. |
| `reconstruction` | Supplied recovered product in written order | Original input. |

Witness matrices can reuse existing matrix IDs. The checker recomputes these equalities with exact `Fraction` arithmetic, verifies the witnesses and flags, and refuses failed traces. No floating tolerance or global-phase equivalence is used. The rendering profile accepts complete successful runs; partial/failing traces need a future diagnostic profile.

The input check may be displayed at introduction. Reduction verification must follow all operations and column completions. Reconstruction verification must follow recovery. `complete` closes the run after all three check events.

## 2. Realistic example

The full ready-to-run file is [examples/synthesis_trace.json](../examples/synthesis_trace.json): 4 dimensions, 14 state records, 4 operations, and 32 explanatory events.

```text
U = 1/2 × [[ 1, 1,  1,  1],
           [-1, 1, -1,  1],
           [-1, 1,  1, -1],
           [ 1, 1, -1, -1]]

Reduction chronology: S[1], S[2], K[0,1,2,3], X[1,3]
Written recovery:     U = S[1] S[2] K[0,1,2,3] X[1,3]
Circuit chronology:  X[1,3], K[0,1,2,3], S[2], S[1]
```

The first column has LDE 1 and integer lift `(1,-1,-1,1)`. Its modulo-four residues are `(1,3,3,1)`. The two prescribed signs make that lift `(1,1,1,1)`. The supplied K witness gives `(2,0,0,0)` at the old scale, so the actual column is `e_0`, with LDE 0. The current matrix is then `X[1,3]`; the last swap gives identity. Columns 2 and 3 require no operations but still have start, LDE, and completion events. This is a hand-authored witness, not output from a newly implemented synthesis algorithm.

The example exercises one denominator level. It does not claim to demonstrate multiple denominator levels or all proof branches. The renderer and contract accept longer runs; larger fixtures and no-operation identity cases are tested separately.

## 3. Exactly what the compiler must emit

1. **At initialization:** record dimensions, interpretation of basis order, column order, exact input and identity; calculate the input orthogonality witness; define the proof rules your run will cite. Make the initial state and introduction event.
2. **At a column boundary:** record its index, exact current matrix, completed prefix, target row, exact LDE, full integer lift, and both residue arrays. Emit `column_start` and the explanatory analysis you want narrated.
3. **At each mathematical choice:** record the selected indices in their intended order, their purpose, and the actual reason used in this run. Supply counts, congruences, selected signs, odd/minimality witnesses, and fixed-column arguments in `facts` and narration as relevant. Do not leave the viewer-facing reason implicit in your source code.
4. **Before and after every atomic multiplication:** register the generator and full embedding; capture both exact snapshots, including fresh lift/residue data for the active column; append an operation with its rule and role; emit exactly one applying event. Optionally emit its selection event first.
5. **At a denominator decrease:** emit an explicit comparison with both endpoint states and the contiguous operation batch that just achieved it. Explain why that batch, rather than necessarily each individual generator, removes one or more denominator powers. Record any old-scale intermediate equality as a literal fact when you want it shown.
6. **At column completion:** record a state that adds exactly this column to the completed prefix, with the same current matrix, and emit `column_complete`.
7. **At the end:** emit the full reduction operation IDs, inverse factors in written order, and inverse gates in execution order. Supply all three exact verification witnesses/flags and their events, recovery, and completion.
8. **For narration:** every event needs text and a minimum hold; every event belongs to a titled contiguous section. Prefer short claims and one idea per event. Narration and explanatory notes are exported for voiceover editing, without being burned into the movie.

You may buffer these records and write one JSON file at the end. You may deduplicate matrices and generators. You do not have to reproduce the mock's IDs, its ascending column order, its number of events, or its exact wording. You do have to follow the references, event lifecycle, and exact invariants above.

## 4. Manim architecture

```text
compiler (owned by you)
  ↓ JSON only
trace.py                 strict parsing; duplicate-key rejection
validation.py            schema + exact witness/order consistency
storyboard.py            literal event plan, script, measured captions
visualize_process.py     command line, immutable input copy, Manim subprocess
  ↓
render_scene.py          thin dispatcher; sections + actual timestamps
kinetic_stage.py         continuous event choreography; presentation state
kinetic_objects.py       Computer Modern glyph paths; movable exact entries
kinetic_arithmetic.py    supplied K row products and cancellations
  ↓
MP4 + sections + storyboard + narration Markdown + timeline + SRT
```

The stage uses exact fractions, extracted columns, supplied integer lifts, residue clocks, moving signs and rows, and basis-level circuits. K close-ups substitute the supplied coefficients and actual column entries into row products, then animate each sum into its supplied result. No synthesis choices or new denominator witnesses are generated. Explanations, rules, and facts remain in the storyboard and narration editor notes.

Every event type has a handler. `TraceScene` does not implement the proof or contain all choreography. Stable row colors connect entries across views; green marks completed columns. The background is black. Matplotlib mathtext produces mathematical SVG paths without a LaTeX installation. Trace prose is never executed as TeX, markup, or Python and is not shown in paragraph blocks.

Matrices and vectors are fitted to the available stage; K close-ups retain the generator's ordered four-coordinate support. Values are never replaced by approximate decimals. Very large matrices and long generator words can become too small to read and need a future close-up/pagination strategy. Dense snapshots and cubic exact validation can also be expensive for large dimensions.

## 5. Mathematical choices to settle before extending this profile

No further information is needed to emit v1 if the profile above matches your intended proof. The compiler can choose its column order and wording through the existing fields. Confirm these scope decisions in your own implementation before coding against them:

- **Matrix class:** real dyadic orthogonal matrices, identity endpoint, exact equality. Complex Gaussian dyadics, rectangular isometries, other rings, or phase-quotiented results require another explicit profile.
- **Conventions:** left row action, zero-based indices, exact ordered K block above, and column-ket circuit semantics. Convert your internal convention at the JSON boundary if it differs.
- **Proof presentation:** the precise rule references and run-specific reasons you want narrated, especially quartet coverage, sign choices, minimality, and preservation of completed columns. The renderer cannot supply omitted mathematics.
- **Qubit lowering:** the v1 final circuit is an exact **basis-level generator circuit**. For a hardware/qubit gate circuit, provide the gate alphabet, bit order, controls, allowed ancillas and their clean/dirty convention, lowering sequence, and an exact correctness witness. That is additional compiler output. Some elementary decompositions leave `Z[1/2]` at intermediate gates, so blindly requiring every lowered gate matrix to be dyadic would be wrong. Such a layer needs a separately agreed symbolic/exact representation.
- **Ancilla verification:** if used later, specify whether correctness means full-space equality or equality only on a prepared-ancilla subspace, and what must happen to the ancilla at the output. V1 makes no implicit ancilla claim.

The current pipeline is fully usable at the matrix-generator level. Native gate lowering and new algebraic domains are extensions, not work hidden inside the renderer.

## 6. Implementation and use

See [README.md](../README.md) for setup and commands. Validation and storyboard export can run without Manim. Default rendering produces an MP4 automatically; `--quality high` requests a 1080p render. Voiceover audio is supplied by you; the renderer exports silent video plus editing cues. Draft subtitles align to event spans and should be adjusted to your recorded speech if you depart from the script.

The normative mathematical conventions were checked against [Amy–Glaudell–Ross, §5.1](https://arxiv.org/pdf/1908.06076) and the explicit K/embedding conventions in [Li–Ross–Selinger, §§2–3](https://arxiv.org/pdf/2106.01175). The mock is an independently checked prescribed witness. Refer to the original papers for the full synthesis proof; no compiler algorithm is included in this repository.
