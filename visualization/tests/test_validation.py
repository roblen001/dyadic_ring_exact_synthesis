"""Contract checks for a supplied trace; no synthesis algorithm is exercised."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from dyadic_viz import TraceValidationError, load_trace, validate_trace


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "synthesis_trace.json"


class LoadingTests(unittest.TestCase):
    def parse_text(self, content):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.json"
            path.write_text(content, encoding="utf-8")
            return load_trace(path)

    def test_duplicate_nested_json_key_is_rejected(self):
        with self.assertRaisesRegex(TraceValidationError, "duplicate key 'numerator'"):
            self.parse_text('{"matrix": {"numerator": "1", "numerator": "3"}}')

    def test_nonfinite_and_nonobject_json_are_rejected(self):
        for content in ('{"x": NaN}', '{"x": Infinity}', '[]', '{broken'):
            with self.subTest(content=content), self.assertRaises(TraceValidationError):
                self.parse_text(content)

    def test_validation_import_does_not_import_manim(self):
        command = [sys.executable, "-c", "import dyadic_viz; import sys; assert 'manim' not in sys.modules"]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class ExactValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_trace(FIXTURE)

    def setUp(self):
        self.trace = copy.deepcopy(self.reference)

    def event(self, kind):
        return next(event for event in self.trace["events"] if event["type"] == kind)

    def focused_state(self):
        return next(state for state in self.trace["states"].values() if state["focus"] is not None)

    def reject(self, pattern):
        with self.assertRaisesRegex(TraceValidationError, pattern):
            validate_trace(self.trace)

    def test_mock_fixture_passes_with_honest_provenance(self):
        report = validate_trace(self.trace)
        self.assertEqual(report.operation_count, len(self.trace["operations"]))
        self.assertEqual(report.event_count, len(self.trace["events"]))
        self.assertEqual(report.dimension, self.trace["problem"]["dimension"])
        self.assertTrue(any("mock" in warning for warning in report.warnings))

    def test_validation_does_not_mutate_trace(self):
        before = json.dumps(self.trace, sort_keys=True)
        validate_trace(self.trace)
        self.assertEqual(before, json.dumps(self.trace, sort_keys=True))

    def test_unknown_event_and_extra_fields_are_rejected(self):
        self.trace["events"][1]["type"] = "please_synthesize"
        self.reject("Schema validation failed")
        self.trace = copy.deepcopy(self.reference)
        self.trace["solver_options"] = {"autofill": True}
        self.reject("Additional properties")

    def test_noncanonical_exact_numbers_are_rejected(self):
        matrix = next(iter(self.trace["matrices"].values()))
        matrix[0][0] = {"numerator": "2", "denominator_exponent": 1}
        self.reject("canonical")

    def test_floating_matrix_values_are_rejected(self):
        matrix = next(iter(self.trace["matrices"].values()))
        matrix[0][0] = 0.5
        self.reject("Schema validation failed")

    def test_noninteger_dimension_has_actionable_error(self):
        self.trace["problem"]["dimension"] = float(self.trace["problem"]["dimension"])
        self.reject(r"\$\.problem\.dimension")

    def test_unknown_matrix_reference_is_rejected(self):
        self.trace["problem"]["input_matrix_id"] = "absent"
        self.reject(r"problem.input_matrix_id: unknown reference")

    def test_least_denominator_exponent_is_checked_exactly(self):
        self.focused_state()["focus"]["lde"] += 1
        self.reject("least denominator exponent")

    def test_scaled_vector_is_checked_exactly(self):
        self.focused_state()["focus"]["scaled_vector"][0] = "123"
        self.reject("whole column scaled")

    def test_residue_witnesses_are_checked_exactly(self):
        state = self.focused_state()
        state["focus"]["residues_mod4"][0] = (state["focus"]["residues_mod4"][0] + 1) % 4
        self.reject("least nonnegative residues")

    def test_qubit_count_and_column_order_are_checked(self):
        self.trace["problem"]["qubit_count"] = 99
        self.reject("dimension must equal")
        self.trace = copy.deepcopy(self.reference)
        self.trace["problem"]["column_order"].pop()
        self.reject("expected .* indices")

    def test_generators_are_compared_with_canonical_embedded_matrices(self):
        generator = next(g for g in self.trace["generators"].values() if g["kind"] == "k")
        generator["matrix_id"] = self.trace["problem"]["target_matrix_id"]
        self.reject("canonical embedded k")

    def test_duplicate_generator_indices_are_rejected(self):
        generator = next(g for g in self.trace["generators"].values() if g["kind"] == "k")
        generator["indices"][1] = generator["indices"][0]
        self.reject("Schema validation failed")

    def test_k_generator_indices_are_ordered(self):
        generator = next(g for g in self.trace["generators"].values() if g["kind"] == "k")
        generator["indices"][0], generator["indices"][1] = generator["indices"][1], generator["indices"][0]
        self.reject("canonical embedded k")

    def test_row_action_cannot_be_faked_with_consistent_state_metadata(self):
        op = self.trace["operations"][0]
        op["after_state_id"] = op["before_state_id"]
        self.reject("row-action mismatch")

    def test_operation_chain_cannot_jump(self):
        self.trace["operations"][1]["before_state_id"] = self.trace["operations"][0]["before_state_id"]
        self.reject("does not continue")

    def test_completed_columns_must_already_equal_basis_vectors(self):
        initial = self.trace["states"][self.trace["problem"]["initial_state_id"]]
        fake = copy.deepcopy(initial)
        fake["completed_columns"] = self.trace["problem"]["column_order"][:1]
        self.trace["states"]["fake_completion"] = fake
        self.reject("completed column .* is not")

    def test_reduction_sequence_cannot_be_reordered(self):
        self.trace["result"]["reduction_operation_ids"].reverse()
        self.reject("chronological reduction order")

    def test_recovered_written_product_order_is_checked(self):
        self.trace["result"]["recovered_factors"].reverse()
        self.reject("written product factors")

    def test_circuit_time_order_is_reverse_of_written_product(self):
        self.trace["result"]["circuit"]["gates"].reverse()
        self.reject("earliest-first circuit must reverse")

    def test_verification_flags_are_not_trusted(self):
        self.trace["verifications"][0]["passed"] = False
        self.reject("passed flag disagrees")

    def test_verification_matrix_witnesses_are_not_trusted(self):
        check = next(v for v in self.trace["verifications"] if v["kind"] == "reconstruction")
        check["left_matrix_id"] = self.trace["problem"]["target_matrix_id"]
        self.reject("supplied witness disagrees")

    def test_operation_application_cannot_be_duplicated(self):
        index = next(i for i, e in enumerate(self.trace["events"]) if e["type"] in ("generator_applied", "sign_correction"))
        duplicate = copy.deepcopy(self.trace["events"][index])
        duplicate["id"] = "duplicate_application"
        self.trace["events"].insert(index + 1, duplicate)
        self.reject("reduction order without duplicate application")

    def test_operation_application_cannot_be_omitted(self):
        index = next(i for i, e in enumerate(self.trace["events"]) if e["type"] in ("generator_applied", "sign_correction"))
        self.trace["events"].pop(index)
        self.reject("reduction order|non-operation state change|batch must be contiguous")

    def test_missing_mathematical_reason_is_rejected(self):
        self.event("lde_analysis")["explanation"]["rule_id"] = None
        self.reject("mathematical events require")

    def test_event_operation_rule_must_agree(self):
        event = self.event("generator_selected")
        other_rule = next(key for key in self.trace["rules"] if key != event["explanation"]["rule_id"])
        event["explanation"]["rule_id"] = other_rule
        self.reject("event rule must equal")

    def test_nonoperation_event_cannot_change_matrix(self):
        event = self.event("lde_analysis")
        op = self.trace["operations"][0]
        event["payload"]["state_id"] = op["after_state_id"]
        self.reject("non-operation state change must preserve")

    def test_lde_comparison_must_actually_decrease(self):
        event = self.event("lde_reduced")
        event["payload"]["before_state_id"] = event["payload"]["after_state_id"]
        self.reject("strict decrease")

    def test_lde_batch_must_be_contiguous(self):
        event = self.event("lde_reduced")
        ids = event["payload"]["operation_ids"]
        self.assertGreaterEqual(len(ids), 2, "mock should demonstrate a complete reduction batch")
        event["payload"]["operation_ids"] = ids[::-1]
        self.reject("batch must be contiguous")

    def test_section_cannot_reappear(self):
        events = self.trace["events"]
        first_section = copy.deepcopy(events[0]["section"])
        first_change = next(i for i, e in enumerate(events) if e["section"]["id"] != first_section["id"])
        events[first_change + 1]["section"] = first_section
        self.reject("contiguous event block")

    def test_missing_recovery_is_rejected(self):
        self.trace["events"] = [e for e in self.trace["events"] if e["type"] != "recovery"]
        self.reject("reconstruction verification must follow recovery|recovery event is required")

    def test_each_verification_needs_an_event(self):
        index = next(i for i, e in enumerate(self.trace["events"]) if e["type"] == "verification")
        self.trace["events"].pop(index)
        self.reject("every verification needs")

    def test_nonfinite_narration_duration_is_rejected(self):
        self.trace["events"][0]["narration"]["hold_seconds"] = float("inf")
        self.reject("duration must be finite")

    def test_final_event_cannot_reintroduce_an_unrelated_focus(self):
        final = self.trace["states"][self.trace["result"]["final_state_id"]]
        completed_first = next(
            state for state in self.trace["states"].values()
            if state["focus"] is not None and state["focus"]["column"] == 0
            and state["focus"]["lde"] == 0
        )
        final["focus"] = copy.deepcopy(completed_first["focus"])
        self.reject("completion focus|complete may keep")


if __name__ == "__main__":
    unittest.main()
