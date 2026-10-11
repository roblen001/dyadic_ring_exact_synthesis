"""Independent contract fixtures, without a synthesis or gate-selection algorithm.

The nontrivial examples only embed or relabel the published four-dimensional
mock. Identity examples supply their already-known column witnesses directly.
"""

import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from dyadic_viz import load_trace, validate_trace
from dyadic_viz.storyboard import build_storyboard
from dyadic_viz.validation import _TraceChecker


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "synthesis_trace.json"


def integer(value):
    return {"numerator": str(value), "denominator_exponent": 0}


def identity_matrix(dimension):
    return [[integer(int(row == column)) for column in range(dimension)]
            for row in range(dimension)]


def identity_focus(dimension, column):
    entries = [int(row == column) for row in range(dimension)]
    return {"column": column, "target_row": column, "lde": 0,
            "scaled_vector": [str(value) for value in entries],
            "residues_mod2": entries.copy(), "residues_mod4": entries.copy()}


def event(event_id, kind, payload, rule="completion", section=None):
    """Attach literal test narration to a supplied semantic event."""
    return {
        "id": event_id, "type": kind,
        "section": section or {"id": "identity", "title": "Known identity witness"},
        "narration": {"text": "Inspect the supplied exact witness.", "hold_seconds": 1},
        "explanation": {"rule_id": rule, "summary": "Supplied test witness", "facts": []},
        "payload": payload,
    }


def identity_trace(dimension, order=None, qubit_count=None):
    """A hand-specified identity run: every column needs zero operations."""
    order = list(range(dimension)) if order is None else list(order)
    trace = load_trace(FIXTURE)
    trace["trace_id"] = f"identity_{dimension}"
    trace["title"] = f"Identity in dimension {dimension}"
    trace["provenance"]["note"] = "Hand-authored identity fixture; no synthesis was run."
    trace["problem"] = {
        "dimension": dimension, "qubit_count": qubit_count,
        "input_matrix_id": "identity", "target_matrix_id": "identity",
        "initial_state_id": "input", "column_order": order,
    }
    trace["matrices"] = {"identity": identity_matrix(dimension)}
    trace["generators"] = {}
    trace["operations"] = []
    trace["states"] = {
        "input": {"matrix_id": "identity", "completed_columns": [], "focus": None},
    }
    trace["events"] = [event("input_event", "input", {"state_id": "input"}, None)]
    for position, column in enumerate(order):
        start_id, done_id = f"c{column}_start", f"c{column}_done"
        for key, completed in ((start_id, order[:position]),
                               (done_id, order[:position + 1])):
            trace["states"][key] = {
                "matrix_id": "identity", "completed_columns": completed,
                "focus": identity_focus(dimension, column),
            }
        trace["events"] += [
            event(f"start_{column}", "column_start", {"state_id": start_id}),
            event(f"done_{column}", "column_complete", {"state_id": done_id, "column": column}),
        ]
    trace["states"]["final"] = {
        "matrix_id": "identity", "completed_columns": order.copy(), "focus": None,
    }
    trace["result"] = {
        "final_state_id": "final", "reduction_operation_ids": [], "recovered_factors": [],
        "circuit": {"representation": "basis_level", "time_order": "earliest_first", "gates": []},
    }
    trace["events"].append(event("recovery_event", "recovery", {}, None))
    for verification in trace["verifications"]:
        verification["left_matrix_id"] = "identity"
        verification["right_matrix_id"] = "identity"
        verification["statement"] = "Both supplied sides equal the identity exactly."
        trace["events"].append(event(
            f"event_{verification['id']}", "verification",
            {"verification_id": verification["id"]}, "verification"))
    trace["events"].append(event("complete_event", "complete", {"state_id": "final"}, None))
    return trace


def padded_eight_trace():
    """Embed every existing witness as diag(witness, I_4), keeping its gates."""
    trace = load_trace(FIXTURE)
    trace["trace_id"] = "padded_eight"
    trace["problem"]["dimension"] = 8
    trace["problem"]["qubit_count"] = 3
    trace["problem"]["column_order"] = list(range(8))
    for key, matrix in list(trace["matrices"].items()):
        embedded = identity_matrix(8)
        for row in range(4):
            for column in range(4):
                embedded[row][column] = copy.deepcopy(matrix[row][column])
        trace["matrices"][key] = embedded
    for state in trace["states"].values():
        if state["focus"] is not None:
            state["focus"]["scaled_vector"] += ["0"] * 4
            state["focus"]["residues_mod2"] += [0] * 4
            state["focus"]["residues_mod4"] += [0] * 4
    trace["states"]["final"]["completed_columns"] = list(range(8))
    insertion = next(index for index, item in enumerate(trace["events"])
                     if item["type"] == "verification"
                     and item["payload"]["verification_id"] == "verify_reduction")
    section = copy.deepcopy(trace["events"][insertion - 1]["section"])
    added_events = []
    for column in range(4, 8):
        start_id, done_id = f"c{column}_start", f"c{column}_done"
        trace["states"][start_id] = {
            "matrix_id": "identity", "completed_columns": list(range(column)),
            "focus": identity_focus(8, column),
        }
        trace["states"][done_id] = {
            "matrix_id": "identity", "completed_columns": list(range(column + 1)),
            "focus": identity_focus(8, column),
        }
        added_events += [
            event(f"padding_start_{column}", "column_start", {"state_id": start_id}, section=section),
            event(f"padding_done_{column}", "column_complete",
                  {"state_id": done_id, "column": column}, section=section),
        ]
    trace["events"][insertion:insertion] = added_events
    return trace


def reverse_basis_labels(trace):
    """Conjugate a known witness by the reversal permutation; choose no gates."""
    result = copy.deepcopy(trace)
    dimension = result["problem"]["dimension"]
    reverse = lambda index: dimension - 1 - index
    result["trace_id"] += "_reversed_basis"
    result["problem"]["column_order"] = [reverse(i) for i in result["problem"]["column_order"]]
    for key, matrix in result["matrices"].items():
        result["matrices"][key] = [row[::-1] for row in matrix[::-1]]
    for state in result["states"].values():
        state["completed_columns"] = [reverse(i) for i in state["completed_columns"]]
        focus = state["focus"]
        if focus is not None:
            focus["column"] = reverse(focus["column"])
            focus["target_row"] = reverse(focus["target_row"])
            for field in ("scaled_vector", "residues_mod2", "residues_mod4"):
                focus[field].reverse()
    for generator in result["generators"].values():
        generator["indices"] = [reverse(i) for i in generator["indices"]]
    for item in result["events"]:
        payload = item["payload"]
        if "column" in payload:
            payload["column"] = reverse(payload["column"])
        if "indices" in payload:
            payload["indices"] = [reverse(i) for i in payload["indices"]]
    # These structural fixtures are never rendered. Avoid leaving misleading
    # numerical prose after changing the basis labels.
    for item in result["events"]:
        item["narration"]["text"] = "Inspect the supplied witness with reversed basis labels."
        item["explanation"]["summary"] = "Basis-relabelled test witness"
        item["explanation"]["facts"] = []
    return result


class GeneralizationTests(unittest.TestCase):
    def test_dimension_one_identity_has_no_operations_or_circuit_gates(self):
        trace = identity_trace(1, qubit_count=0)
        report = validate_trace(trace)
        board = build_storyboard(trace)
        self.assertEqual((report.dimension, report.operation_count), (1, 0))
        self.assertEqual(trace["result"]["circuit"]["gates"], [])
        self.assertTrue(all(item["applied_operation_ids"] == [] for item in board["events"]))
        self.assertEqual(board["events"][-1]["after_state_id"], "final")

    def test_non_qubit_dimension_and_reverse_column_order(self):
        trace = identity_trace(3, order=[2, 1, 0])
        report = validate_trace(trace)
        self.assertEqual(report.dimension, 3)
        self.assertIsNone(trace["problem"]["qubit_count"])
        columns = [item["payload"]["column"] for item in build_storyboard(trace)["events"]
                   if item["type"] == "column_complete"]
        self.assertEqual(columns, [2, 1, 0])

    def test_eight_dimensional_embedding_keeps_exact_known_operations(self):
        trace = padded_eight_trace()
        report = validate_trace(trace)
        board = build_storyboard(trace)
        self.assertEqual((report.dimension, report.operation_count), (8, 4))
        self.assertEqual(board["events"][-1]["applied_operation_ids"],
                         [operation["id"] for operation in trace["operations"]])
        self.assertEqual(sum(item["type"] == "column_complete" for item in board["events"]), 8)
        for state in trace["states"].values():
            if state["focus"] is not None:
                self.assertEqual(len(state["focus"]["scaled_vector"]), 8)

    def test_nontrivial_reversed_order_and_ordered_k_support(self):
        trace = reverse_basis_labels(padded_eight_trace())
        report = validate_trace(trace)
        self.assertEqual((report.dimension, report.operation_count), (8, 4))
        self.assertEqual(trace["problem"]["column_order"], list(range(7, -1, -1)))
        generator = next(item for item in trace["generators"].values() if item["kind"] == "k")
        self.assertEqual(generator["indices"], [7, 6, 5, 4])
        self.assertEqual(build_storyboard(trace)["events"][-1]["after_state_id"], "final")

    def test_successive_equal_lde_operations_are_supported(self):
        trace = padded_eight_trace()
        validate_trace(trace)
        lde_pairs = [
            (trace["states"][op["before_state_id"]]["focus"]["lde"],
             trace["states"][op["after_state_id"]]["focus"]["lde"])
            for op in trace["operations"]
        ]
        self.assertEqual(lde_pairs, [(1, 1), (1, 1), (1, 0), (0, 0)])
        board = build_storyboard(trace)
        applications = [item for item in board["events"]
                        if item["type"] in ("sign_correction", "generator_applied")]
        self.assertEqual([len(item["applied_operation_ids"]) for item in applications], [1, 2, 3, 4])

    def test_large_exact_dyadic_strings_survive_loading_and_exact_parsing(self):
        trace = identity_trace(1, qubit_count=0)
        numerator, exponent = -(2 ** 127 + 1), 137
        # Auxiliary witness data exercises the number contract without pretending
        # that a one-dimensional orthogonal input can have a large denominator.
        trace["matrices"]["large_exact_witness"] = [[
            {"numerator": str(numerator), "denominator_exponent": exponent}
        ]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_text(json.dumps(trace), encoding="utf-8")
            loaded = load_trace(path)
        validate_trace(loaded)
        self.assertEqual(loaded["matrices"]["large_exact_witness"][0][0]["numerator"], str(numerator))
        # Inspect the independent verification parser, not a floating rendering
        # approximation. The last numerator bit must remain significant.
        checker = _TraceChecker(loaded)
        checker.check_matrices()
        parsed = checker.matrices["large_exact_witness"][0][0]
        self.assertEqual(parsed, Fraction(numerator, 2 ** exponent))
        self.assertNotEqual(parsed, Fraction(-(2 ** 127), 2 ** exponent))

    def test_integral_negative_vector_uses_terminal_sign(self):
        # Prescribed O_1 witness: [-1] -> [1], without any residue reduction.
        trace = identity_trace(1, qubit_count=0)
        trace["matrices"]["negative"] = [[integer(-1)]]
        trace["problem"]["input_matrix_id"] = "negative"
        trace["states"]["input"]["matrix_id"] = "negative"
        trace["states"]["c0_start"]["matrix_id"] = "negative"
        trace["states"]["c0_start"]["focus"].update({
            "scaled_vector": ["-1"], "residues_mod2": [1], "residues_mod4": [3]})
        trace["states"]["c0_positive"] = {
            "matrix_id": "identity", "completed_columns": [], "focus": identity_focus(1, 0)}
        trace["generators"] = {
            "sign0": {"kind": "sign", "indices": [0], "matrix_id": "negative", "label": "S[0]"}}
        trace["operations"] = [{
            "id": "terminal", "generator_id": "sign0", "before_state_id": "c0_start",
            "after_state_id": "c0_positive", "role": "terminal_sign", "rule_id": "integral"}]
        trace["events"].insert(2, event("apply_terminal", "generator_applied", {"operation_id": "terminal"}, "integral"))
        trace["result"]["reduction_operation_ids"] = ["terminal"]
        trace["result"]["recovered_factors"] = [{"generator_id": "sign0", "inverse": True}]
        trace["result"]["circuit"]["gates"] = [{
            "id": "gate0", "generator_id": "sign0", "inverse": True, "label": "S[0]"}]
        reconstruction = next(check for check in trace["verifications"] if check["kind"] == "reconstruction")
        reconstruction["left_matrix_id"] = reconstruction["right_matrix_id"] = "negative"
        reconstruction["statement"] = "S[0] equals the original one-dimensional matrix [-1] exactly."
        report = validate_trace(trace)
        self.assertEqual((report.dimension, report.operation_count), (1, 1))


if __name__ == "__main__":
    unittest.main()
