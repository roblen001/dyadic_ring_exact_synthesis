"""Reject inconsistent supplied witnesses using exact arithmetic only.

This module never searches for, chooses, or generates a synthesis operation.
Generator construction below is solely comparison against a supplied witness.
"""

from dataclasses import dataclass, field
from fractions import Fraction
import json
import math
from pathlib import Path
import re

from .trace import TraceValidationError


@dataclass(frozen=True)
class ValidationReport:
    operation_count: int
    event_count: int
    dimension: int
    warnings: list[str] = field(default_factory=list)


def _fail(path, message):
    raise TraceValidationError(f"{path}: {message}")


def _path(parts):
    result = "$"
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def _identity(n):
    return tuple(tuple(Fraction(i == j) for j in range(n)) for i in range(n))


def _multiply(a, b):
    n = len(a)
    return tuple(tuple(sum((a[i][k] * b[k][j] for k in range(n)), Fraction())
                       for j in range(n)) for i in range(n))


def _transpose(a):
    return tuple(zip(*a))


def _structural_check(trace):
    try:
        from jsonschema import Draft202012Validator, validators
    except ImportError as exc:
        raise TraceValidationError(
            "validator: jsonschema is required; install the project's requirements.txt"
        ) from exc
    schema_path = Path(__file__).resolve().parent.parent / "schema" / "synthesis-trace.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TraceValidationError(f"validator: cannot load schema {schema_path}: {exc}") from exc
    strict_validator = validators.extend(
        Draft202012Validator,
        type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
            "integer", lambda checker, value: type(value) is int
        ),
    )
    errors = sorted(strict_validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(trace),
                    key=lambda error: tuple(str(p) for p in error.absolute_path))
    if errors:
        details = [f"{_path(error.absolute_path)}: {error.message}" for error in errors[:8]]
        if len(errors) > 8:
            details.append(f"... and {len(errors) - 8} additional structural errors")
        raise TraceValidationError("Schema validation failed:\n" + "\n".join(details))


def validate_trace(trace) -> ValidationReport:
    """Validate structure, exact witnesses, operation order, and event coherence.

    Success means the supplied trace is internally consistent. It does not prove
    the prose in rule statements and does not synthesize any missing operation.
    """
    _structural_check(trace)
    return _TraceChecker(trace).check()


class _TraceChecker:
    def __init__(self, trace):
        self.t = trace
        self.n = trace["problem"]["dimension"]
        self.identity = _identity(self.n)
        self.order = trace["problem"]["column_order"]
        self.strategy = trace['problem'].get('reduction_strategy', 'columnwise')
        self.matrices = {}
        self.states = trace["states"]
        self.generators = trace["generators"]
        self.operations = trace["operations"]
        self.op_by_id = {}
        self.op_positions = {}
        self.verifications = {}

    def ref(self, table, key, path):
        if key not in table:
            _fail(path, f"unknown reference {key!r}")
        return table[key]

    def matrix(self, key, path):
        return self.ref(self.matrices, key, path)

    def state(self, key, path):
        return self.ref(self.states, key, path)

    def state_matrix(self, key, path):
        state = self.state(key, path)
        return self.matrix(state["matrix_id"], f"$.states.{key}.matrix_id")

    def indices(self, values, path, count=None):
        if count is not None and len(values) != count:
            _fail(path, f"expected {count} indices")
        if len(values) != len(set(values)):
            _fail(path, "indices must be distinct")
        for i, value in enumerate(values):
            if type(value) is not int or not 0 <= value < self.n:
                _fail(f"{path}[{i}]", f"index must be in [0, {self.n})")

    def check(self):
        self.check_matrices()
        self.check_problem()
        self.check_states()
        self.check_generators()
        self.check_operations()
        self.check_result_and_verifications()
        self.check_events()
        warnings = []
        if self.t["provenance"]["kind"] == "mock":
            warnings.append("This is a hand-authored mock trace, not compiler output.")
        return ValidationReport(len(self.operations), len(self.t["events"]), self.n, warnings)

    def check_matrices(self):
        for key, raw in self.t["matrices"].items():
            path = f"$.matrices.{key}"
            if len(raw) != self.n or any(len(row) != self.n for row in raw):
                _fail(path, f"expected a {self.n} by {self.n} matrix")
            matrix = []
            for i, row in enumerate(raw):
                parsed = []
                for j, value in enumerate(row):
                    entry_path = f"{path}[{i}][{j}]"
                    numerator_text = value["numerator"]
                    if not re.fullmatch(r"0|-?[1-9][0-9]*", numerator_text):
                        _fail(entry_path + ".numerator", "expected a canonical signed decimal integer")
                    try:
                        numerator = int(numerator_text)
                    except ValueError as exc:
                        _fail(entry_path + ".numerator", f"integer cannot be parsed: {exc}")
                    exponent = value["denominator_exponent"]
                    if exponent > 0 and numerator % 2 == 0:
                        _fail(entry_path, "dyadic is not canonical: a positive exponent requires an odd numerator")
                    parsed.append(Fraction(numerator, 2 ** exponent))
                matrix.append(tuple(parsed))
            self.matrices[key] = tuple(matrix)

    def check_problem(self):
        p = self.t["problem"]
        self.indices(self.order, "$.problem.column_order", self.n)
        if p["qubit_count"] is not None and self.n != 2 ** p["qubit_count"]:
            _fail("$.problem.qubit_count", "dimension must equal 2**qubit_count")
        self.input = self.matrix(p["input_matrix_id"], "$.problem.input_matrix_id")
        target = self.matrix(p["target_matrix_id"], "$.problem.target_matrix_id")
        if target != self.identity:
            _fail("$.problem.target_matrix_id", "orthogonal_dyadic v1 requires the identity target")
        initial = self.state(p["initial_state_id"], "$.problem.initial_state_id")
        if self.state_matrix(p["initial_state_id"], "$.problem.initial_state_id") != self.input:
            _fail("$.problem.initial_state_id", "initial state must equal the supplied input matrix")
        if initial["completed_columns"]:
            _fail("$.problem.initial_state_id", "initial state must have no completed columns")

    def check_states(self):
        for key, state in self.states.items():
            path = f"$.states.{key}"
            matrix = self.matrix(state["matrix_id"], path + ".matrix_id")
            completed = state["completed_columns"]
            self.indices(completed, path + ".completed_columns")
            if completed != self.order[:len(completed)]:
                _fail(path + ".completed_columns", "completed columns must be a prefix of column_order")
            for column in completed:
                if any(matrix[row][column] != self.identity[row][column] for row in range(self.n)):
                    _fail(path + ".completed_columns", f"completed column {column} is not e_{column}")
            focus = state["focus"]
            if focus is None:
                continue
            self.indices([focus["column"]], path + ".focus.column")
            if focus["target_row"] != focus["column"]:
                _fail(path + ".focus.target_row", "identity reduction requires target_row == column")
            column = [row[focus["column"]] for row in matrix]
            lde = max(value.denominator.bit_length() - 1 for value in column)
            if focus["lde"] != lde:
                _fail(path + ".focus.lde", f"expected exact least denominator exponent {lde}")
            scaled = [value * 2 ** lde for value in column]
            expected = [str(value.numerator) for value in scaled]
            if focus["scaled_vector"] != expected:
                _fail(path + ".focus.scaled_vector", f"expected whole column scaled by 2**{lde}: {expected}")
            for modulus in (2, 4):
                expected_residues = [value.numerator % modulus for value in scaled]
                if focus[f"residues_mod{modulus}"] != expected_residues:
                    _fail(path + f".focus.residues_mod{modulus}",
                          f"expected least nonnegative residues {expected_residues}")

    def check_generators(self):
        block = ((1, 1, 1, 1), (1, -1, 1, -1), (1, 1, -1, -1), (1, -1, -1, 1))
        for key, generator in self.generators.items():
            path = f"$.generators.{key}"
            kind, indices = generator["kind"], generator["indices"]
            self.indices(indices, path + ".indices", {"sign": 1, "swap": 2, "k": 4}[kind])
            expected = [list(row) for row in self.identity]
            if kind == "sign":
                expected[indices[0]][indices[0]] = Fraction(-1)
            elif kind == "swap":
                a, b = indices
                expected[a], expected[b] = expected[b], expected[a]
            else:
                for i, row in enumerate(indices):
                    for j, col in enumerate(indices):
                        expected[row][col] = Fraction(block[i][j], 2)
            actual = self.matrix(generator["matrix_id"], path + ".matrix_id")
            if actual != tuple(tuple(row) for row in expected):
                _fail(path + ".matrix_id", f"matrix does not equal canonical embedded {kind} on ordered indices {indices}")

    def check_operations(self):
        previous = self.input
        previous_completed = []
        for index, op in enumerate(self.operations):
            path = f"$.operations[{index}]"
            if op["id"] in self.op_by_id:
                _fail(path + ".id", "operation IDs must be unique")
            self.op_by_id[op["id"]] = op
            self.op_positions[op["id"]] = index
            generator = self.ref(self.generators, op["generator_id"], path + ".generator_id")
            self.ref(self.t["rules"], op["rule_id"], path + ".rule_id")
            expected_kind = {"sign_correction": "sign", "mixing": "k", "permutation": "swap", "terminal_sign": "sign"}[op["role"]]
            if generator["kind"] != expected_kind:
                _fail(path + ".role", f"role {op['role']} requires a {expected_kind} generator")
            before = self.state(op["before_state_id"], path + ".before_state_id")
            after = self.state(op["after_state_id"], path + ".after_state_id")
            before_matrix = self.state_matrix(op["before_state_id"], path + ".before_state_id")
            after_matrix = self.state_matrix(op["after_state_id"], path + ".after_state_id")
            if before_matrix != previous:
                _fail(path + ".before_state_id", "matrix does not continue the preceding operation (or input)")
            if before["focus"] is None or after["focus"] is None:
                _fail(path, "each operation requires an active focus in both endpoint states")
            if before["focus"]["column"] != after["focus"]["column"]:
                _fail(path + ".after_state_id", "operation must preserve the active focus column")
            if before["completed_columns"] != after["completed_columns"]:
                _fail(path + ".after_state_id", "an operation cannot change completed-column metadata")
            if before["completed_columns"][:len(previous_completed)] != previous_completed:
                _fail(path + ".before_state_id", "completed columns cannot be forgotten")
            actual = _multiply(self.matrices[generator["matrix_id"]], before_matrix)
            if actual != after_matrix:
                _fail(path + ".after_state_id", "exact row-action mismatch: after must equal G * before")
            previous, previous_completed = after_matrix, after["completed_columns"]
        self.reduced = previous

    def check_result_and_verifications(self):
        result = self.t["result"]
        final = self.state(result["final_state_id"], "$.result.final_state_id")
        final_matrix = self.state_matrix(result["final_state_id"], "$.result.final_state_id")
        if final_matrix != self.reduced:
            _fail("$.result.final_state_id", "final matrix must match the last reduction operation (or input)")
        if final["completed_columns"] != self.order:
            _fail("$.result.final_state_id", "final state must list every column as completed in column_order")
        expected_ids = [op["id"] for op in self.operations]
        if result["reduction_operation_ids"] != expected_ids:
            _fail("$.result.reduction_operation_ids", "must list all operations exactly once in chronological reduction order")
        expected_generators = [op["generator_id"] for op in self.operations]
        if [item["generator_id"] for item in result["recovered_factors"]] != expected_generators:
            _fail("$.result.recovered_factors", "written product factors must be inverse reduction generators in chronological reduction order")
        reconstructed = self.identity
        for index, factor in enumerate(result["recovered_factors"]):
            if factor["inverse"] is not True:
                _fail(f"$.result.recovered_factors[{index}].inverse", "recovered factors must be inverses")
            generator = self.ref(self.generators, factor["generator_id"], f"$.result.recovered_factors[{index}].generator_id")
            reconstructed = _multiply(reconstructed, self.matrices[generator["matrix_id"]])
        gates = result["circuit"]["gates"]
        if [gate["generator_id"] for gate in gates] != expected_generators[::-1]:
            _fail("$.result.circuit.gates", "earliest-first circuit must reverse the written recovered factor order")
        if len({gate["id"] for gate in gates}) != len(gates):
            _fail("$.result.circuit.gates", "circuit gate IDs must be unique")
        if any(gate["inverse"] is not True for gate in gates):
            _fail("$.result.circuit.gates", "all recovered circuit gates must be inverses")
        expected_checks = {
            "input_orthogonality": (_multiply(_transpose(self.input), self.input), self.identity),
            "reduction_identity": (self.reduced, self.identity),
            "reconstruction": (reconstructed, self.input),
        }
        seen_kinds = set()
        for index, verification in enumerate(self.t["verifications"]):
            path = f"$.verifications[{index}]"
            if verification["id"] in self.verifications:
                _fail(path + ".id", "verification IDs must be unique")
            self.verifications[verification["id"]] = verification
            kind = verification["kind"]
            if kind in seen_kinds:
                _fail(path + ".kind", "each verification kind must appear exactly once")
            seen_kinds.add(kind)
            expected_left, expected_right = expected_checks[kind]
            for side, expected in (("left", expected_left), ("right", expected_right)):
                actual = self.matrix(verification[f"{side}_matrix_id"], path + f".{side}_matrix_id")
                if actual != expected:
                    _fail(path + f".{side}_matrix_id", f"supplied witness disagrees with recomputed {kind} {side} side")
            passed = expected_left == expected_right
            if verification["passed"] is not passed:
                _fail(path + ".passed", f"passed flag disagrees with exact result ({passed})")
            if not passed:
                _fail(path, f"exact {kind} check failed; only successful traces can render")
        if seen_kinds != set(expected_checks):
            _fail("$.verifications", "exactly one input_orthogonality, reduction_identity, and reconstruction check is required")

    def check_events(self):
        events = self.t["events"]
        if not events or events[0]["type"] != "input" or events[-1]["type"] != "complete":
            _fail("$.events", "input must be first and complete must be last")
        current_id = self.t["problem"]["initial_state_id"]
        active_column = None
        completed_count = 0
        integral_count = 0
        applied_count = 0
        recovery_seen = False
        seen_ids, seen_verifications, seen_sections = set(), set(), set()
        last_section = None
        section_titles = {}

        def adopt_state(state_id, path, *, allow_completion=False, allow_focus_change=False):
            nonlocal current_id
            old = self.state(current_id, path)
            state = self.state(state_id, path)
            if self.state_matrix(state_id, path) != self.state_matrix(current_id, path):
                _fail(path, "non-operation state change must preserve the current matrix")
            if not allow_completion and state["completed_columns"] != old["completed_columns"]:
                _fail(path, "only column_complete may change completed-column metadata")
            if not allow_focus_change:
                old_focus, new_focus = old["focus"], state["focus"]
                if (old_focus is None) != (new_focus is None) or (
                    old_focus is not None and old_focus["column"] != new_focus["column"]
                ):
                    _fail(path, "active focus may change only at a column boundary")
            current_id = state_id
            return state

        def require_active(path):
            if active_column is None:
                _fail(path, "event requires an active column between column_start and column_complete")

        for index, event in enumerate(events):
            path = f"$.events[{index}]"
            kind, payload = event["type"], event["payload"]
            duration = event["narration"]["hold_seconds"]
            if isinstance(duration, float) and not math.isfinite(duration):
                _fail(path + ".narration.hold_seconds", "duration must be finite")
            if event["id"] in seen_ids:
                _fail(path + ".id", "event IDs must be unique")
            seen_ids.add(event["id"])
            section = event["section"]
            section_id = section["id"]
            if section_id != last_section:
                if section_id in seen_sections:
                    _fail(path + ".section.id", "each section must occupy one contiguous event block")
                seen_sections.add(section_id)
                last_section = section_id
            if section_id in section_titles and section_titles[section_id] != section["title"]:
                _fail(path + ".section.title", "one section ID must have one title")
            section_titles[section_id] = section["title"]
            rule_id = event["explanation"]["rule_id"]
            if kind not in ("input", "recovery", "complete") and rule_id is None:
                _fail(path + ".explanation.rule_id", "mathematical events require a supplied explanation rule")
            if rule_id is not None:
                self.ref(self.t["rules"], rule_id, path + ".explanation.rule_id")
            if kind == "input":
                if index != 0 or payload["state_id"] != current_id:
                    _fail(path, "input must occur once and reference problem.initial_state_id")
            elif kind == "column_start":
                if active_column is not None or completed_count >= self.n or recovery_seen:
                    _fail(path, "column_start must open the next unfinished column")
                state = adopt_state(payload["state_id"], path + ".payload.state_id", allow_focus_change=True)
                next_index = (integral_count if self.strategy == 'integral_then_normalize'
                              and integral_count < self.n else completed_count)
                if state["focus"] is None or state["focus"]["column"] != self.order[next_index]:
                    _fail(path + ".payload.state_id", "column_start focus must follow problem.column_order")
                active_column = self.order[next_index]
            elif kind == 'column_integral':
                require_active(path)
                if self.strategy != 'integral_then_normalize' or integral_count >= self.n:
                    _fail(path, 'column_integral belongs only to the first pass of integral_then_normalize')
                state = adopt_state(payload['state_id'], path + '.payload.state_id')
                if (state['focus'] is None or state['focus']['column'] != active_column
                        or state['focus']['lde'] != 0 or active_column != self.order[integral_count]):
                    _fail(path, 'column_integral must close the next first-pass column at exact LDE zero')
                integral_count += 1
                active_column = None
            elif kind in ("lde_analysis", "residue_analysis", "indices_selected"):
                require_active(path)
                state = adopt_state(payload["state_id"], path + ".payload.state_id")
                if state["focus"] is None or state["focus"]["column"] != active_column:
                    _fail(path + ".payload.state_id", "event state must focus the active column")
                if "indices" in payload:
                    self.indices(payload["indices"], path + ".payload.indices")
            elif kind in ("generator_selected", "sign_correction", "generator_applied"):
                require_active(path)
                op = self.ref(self.op_by_id, payload["operation_id"], path + ".payload.operation_id")
                if applied_count >= len(self.operations) or op["id"] != self.operations[applied_count]["id"]:
                    _fail(path + ".payload.operation_id", "operation events must follow reduction order without duplicate application")
                if rule_id != op["rule_id"]:
                    _fail(path + ".explanation.rule_id", "event rule must equal the referenced operation rule")
                state = adopt_state(op["before_state_id"], path + ".payload.operation_id")
                if state["focus"] is None or state["focus"]["column"] != active_column:
                    _fail(path, "operation must preserve the active column focus")
                if kind != "generator_selected":
                    expected_event = "sign_correction" if op["role"] == "sign_correction" else "generator_applied"
                    if kind != expected_event:
                        _fail(path + ".type", f"operation role requires {expected_event}")
                    current_id = op["after_state_id"]
                    applied_count += 1
            elif kind == "lde_reduced":
                require_active(path)
                before_id, after_id = payload["before_state_id"], payload["after_state_id"]
                before = self.state(before_id, path + ".payload.before_state_id")
                after = self.state(after_id, path + ".payload.after_state_id")
                if before["focus"] is None or after["focus"] is None:
                    _fail(path, "LDE comparison requires focused endpoint states")
                if before["focus"]["column"] != active_column or after["focus"]["column"] != active_column:
                    _fail(path, "LDE comparison must concern the active column")
                if after["focus"]["lde"] >= before["focus"]["lde"]:
                    _fail(path, "lde_reduced must compare a strict decrease in exact LDE")
                ids = payload["operation_ids"]
                if not ids:
                    _fail(path + ".payload.operation_ids", "LDE comparison requires a nonempty applied operation batch")
                positions = [self.ref(self.op_positions, op_id, path + ".payload.operation_ids") for op_id in ids]
                if positions != list(range(positions[0], positions[0] + len(positions))) or positions[-1] != applied_count - 1:
                    _fail(path + ".payload.operation_ids", "batch must be contiguous and end with the most recently applied operation")
                first, last = self.operations[positions[0]], self.operations[positions[-1]]
                if self.state_matrix(before_id, path) != self.state_matrix(first["before_state_id"], path):
                    _fail(path + ".payload.before_state_id", "comparison must equal batch starting matrix")
                if self.state_matrix(after_id, path) != self.state_matrix(last["after_state_id"], path):
                    _fail(path + ".payload.after_state_id", "comparison must equal batch ending matrix")
                if before["completed_columns"] != after["completed_columns"] or any(
                    self.states[self.operations[position]["before_state_id"]]["focus"]["column"] != active_column
                    for position in positions
                ):
                    _fail(path + ".payload.operation_ids", "LDE batch must stay within the active column")
                adopt_state(after_id, path + ".payload.after_state_id")
            elif kind == "column_complete":
                require_active(path)
                if self.strategy == 'integral_then_normalize' and integral_count != self.n:
                    _fail(path, 'all columns must be integral before final normalization/completion')
                if payload["column"] != active_column:
                    _fail(path + ".payload.column", "completion must match the active column")
                state = adopt_state(payload["state_id"], path + ".payload.state_id", allow_completion=True, allow_focus_change=True)
                if state["completed_columns"] != self.order[:completed_count + 1]:
                    _fail(path + ".payload.state_id", "completion state must add exactly the active column")
                if state["focus"] is not None and state["focus"]["column"] != active_column:
                    _fail(path + ".payload.state_id", "completion focus must remain on its column or become null")
                completed_count += 1
                active_column = None
            elif kind == "recovery":
                if recovery_seen or applied_count != len(self.operations) or completed_count != self.n:
                    _fail(path, "recovery must occur once after all operations and column completions")
                recovery_seen = True
            elif kind == "verification":
                verification = self.ref(self.verifications, payload["verification_id"], path + ".payload.verification_id")
                if verification["id"] in seen_verifications:
                    _fail(path, "each verification must have exactly one event")
                if verification["kind"] == "reconstruction" and not recovery_seen:
                    _fail(path, "reconstruction verification must follow recovery")
                if verification["kind"] == "reduction_identity" and (applied_count != len(self.operations) or completed_count != self.n):
                    _fail(path, "reduction verification must follow all operations and column completions")
                seen_verifications.add(verification["id"])
            elif kind == "complete":
                if index != len(events) - 1:
                    _fail(path, "complete must occur once, as the final event")
                if payload["state_id"] != self.t["result"]["final_state_id"]:
                    _fail(path + ".payload.state_id", "complete must reference result.final_state_id")
                if active_column is not None or completed_count != self.n or applied_count != len(self.operations):
                    _fail(path, "complete requires all columns and operations to be finished")
                final_focus = self.states[payload["state_id"]]["focus"]
                current_focus = self.states[current_id]["focus"]
                if final_focus is not None and (
                    current_focus is None or final_focus["column"] != current_focus["column"]
                ):
                    _fail(path + ".payload.state_id", "complete may keep the final column focus or clear it")
                adopt_state(payload["state_id"], path + ".payload.state_id", allow_focus_change=True)
        if applied_count != len(self.operations):
            _fail("$.events", "every operation needs exactly one applying event")
        if not recovery_seen:
            _fail("$.events", "a recovery event is required")
        if seen_verifications != set(self.verifications):
            _fail("$.events", "every verification needs exactly one verification event")
