"""Integration tests for the optional observer, without changing gate choices."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'visualization'))

from exact_synthesis import synthesize
from synthesis_trace import bind_trace, create_trace
from utils import generate_identity_matrix, generator_to_matrix
from visualization.trace_recorder import TraceRecorder
from dyadic_viz.trace import load_trace
from dyadic_viz.validation import validate_trace, TraceValidationError


def sample_matrix():
    trace = load_trace(PROJECT / 'visualization/examples/synthesis_trace.json')
    raw = trace['matrices'][trace['problem']['input_matrix_id']]
    return np.array([[Fraction(int(v['numerator']), 2 ** v['denominator_exponent'])
                      for v in row] for row in raw], dtype=object)


def recorded_run(matrix, directory):
    original = matrix.copy()
    recorder = TraceRecorder(original, output_dir=directory)
    working = matrix.copy()
    generators = synthesize(working, trace=recorder)
    reconstructed = generate_identity_matrix(len(matrix))
    for generator in generators:
        reconstructed = reconstructed @ generator_to_matrix(generator, len(matrix))
    path = recorder.finish(working, generators, reconstructed)
    return generators, working, load_trace(path)


class CompilerTraceTests(unittest.TestCase):
    def test_factory_preserves_legacy_trace_content(self):
        matrix = sample_matrix()
        with tempfile.TemporaryDirectory() as directory:
            expected_generators, expected_matrix, expected_trace = recorded_run(
                matrix, Path(directory) / 'legacy',
            )
            observer = create_trace(
                matrix, enabled=True, output_dir=Path(directory) / 'factory',
            )
            working = matrix.copy()
            generators = synthesize(working, trace=observer)
            reconstructed = generate_identity_matrix(len(matrix))
            for generator in generators:
                reconstructed = reconstructed @ generator_to_matrix(generator, len(matrix))
            path = observer.finish(working, generators, reconstructed)
            actual_trace = load_trace(path)

        self.assertEqual(generators, expected_generators)
        self.assertTrue(np.array_equal(working, expected_matrix))
        self.assertTrue(np.array_equal(matrix, sample_matrix()))
        self.assertEqual(validate_trace(actual_trace).operation_count, len(generators))
        # The timestamp/UUID identify a recording, not its mathematical content.
        actual_trace.pop('trace_id')
        expected_trace.pop('trace_id')
        self.assertEqual(actual_trace, expected_trace)

    def test_bound_operation_snapshots_survive_later_in_place_writes(self):
        working = generate_identity_matrix(2)
        working *= -1
        recorder = TraceRecorder(working)
        generators = []
        observer = bind_trace(recorder, working, generators)
        observer.start_column(0, 0, phase='normalize')
        working[0, :] *= -1
        generators.append({'type': 'sign_flip', 'indices': [0]})
        observer.terminal_sign()

        captured = copy.deepcopy(recorder.data)
        operation = captured['operations'][0]
        matrix_id = captured['states'][operation['after_state_id']]['matrix_id']
        snapshot = captured['matrices'][matrix_id]
        self.assertEqual(snapshot[0][0]['numerator'], '1')
        self.assertEqual(snapshot[1][1]['numerator'], '-1')

        # The compiler changes the same live arrays and generator records later.
        working[1, :] *= -1
        generators[-1]['indices'][0] = 1
        self.assertEqual(recorder.data, captured)

    def test_disabled_factory_has_no_visualization_work_or_retained_state(self):
        script = r'''
import builtins, gc, sys, weakref
from fractions import Fraction
from pathlib import Path
import numpy as np

original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'visualization' or name.startswith('visualization.'):
        raise AssertionError('Disabled tracing imported the visualization package')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import

from synthesis_trace import create_trace
from exact_synthesis import synthesize

class Unreadable:
    def __getattribute__(self, name):
        raise AssertionError('Disabled tracing inspected an input: ' + name)
    def __len__(self):
        raise AssertionError('Disabled tracing measured an input')

destination = Path(sys.argv[1]) / 'must-not-exist'
observer = create_trace(Unreadable(), enabled=False, num_qubits=Unreadable(),
                        output_dir=destination)
working = np.array([[Fraction(-1)]], dtype=object)
reference = weakref.ref(working)
assert synthesize(working, trace=observer) == [{'type': 'sign_flip', 'indices': [0]}]
assert working[0, 0] == 1
del working
gc.collect()
assert reference() is None, 'Disabled tracing retained the working matrix'

other = create_trace(Unreadable(), enabled=False, output_dir=destination)
identity = np.array([[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]], dtype=object)
assert synthesize(identity, trace=other) == []
assert observer.finish(Unreadable(), Unreadable(), Unreadable()) is None
assert other.finish(Unreadable(), Unreadable(), Unreadable()) is None
assert not destination.exists(), 'Disabled tracing created an output directory'
assert not any(name == 'visualization' or name.startswith('visualization.') for name in sys.modules)
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c', script, directory],
                                    cwd=PROJECT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_trace_preserves_generator_sequence_and_matrix(self):
        matrix = sample_matrix()
        plain = matrix.copy()
        expected = synthesize(plain)
        with tempfile.TemporaryDirectory() as directory:
            actual, working, trace = recorded_run(matrix, directory)
        self.assertEqual(actual, expected)
        self.assertTrue(np.array_equal(working, plain))
        self.assertTrue(np.array_equal(matrix, sample_matrix()))
        report = validate_trace(trace)
        self.assertEqual(report.operation_count, len(expected))
        self.assertEqual(trace['problem']['reduction_strategy'], 'integral_then_normalize')
        kinds = [event['type'] for event in trace['events']]
        self.assertEqual(kinds.count('column_integral'), 4)
        self.assertEqual(kinds.count('column_start'), 8)
        self.assertLess(max(i for i,k in enumerate(kinds) if k=='column_integral'),
                        min(i for i,k in enumerate(kinds) if k=='column_complete'))

    def test_empty_identity_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            generators, _, trace = recorded_run(generate_identity_matrix(1), directory)
        self.assertEqual(generators, [])
        self.assertEqual(validate_trace(trace).operation_count, 0)

    def test_four_qubit_exact_trace(self):
        matrix = generate_identity_matrix(16)
        # A prescribed exact fixture made with the project's own existing gate
        # embedding routine. This does not implement or choose synthesis steps.
        for generator in [
            {'type':'hh','indices':[0,1,2,3]},
            {'type':'hh','indices':[0,4,8,12]},
            {'type':'sign_flip','indices':[8]},
            {'type':'hh','indices':[4,5,6,7]},
            {'type':'swap','indices':[3,14]},
            {'type':'hh','indices':[0,3,7,15]},
        ]:
            matrix = matrix @ generator_to_matrix(generator, 16)
        plain = matrix.copy()
        expected = synthesize(plain)
        with tempfile.TemporaryDirectory() as directory:
            actual, working, trace = recorded_run(matrix, directory)
        self.assertEqual(actual, expected)
        self.assertTrue(np.array_equal(working, plain))
        self.assertEqual(validate_trace(trace).dimension, 16)

    def test_reject_false_integral_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, trace = recorded_run(sample_matrix(), directory)
        invalid = copy.deepcopy(trace)
        event = next(e for e in invalid['events'] if e['type']=='column_integral')
        event['payload']['state_id'] = next(e['payload']['state_id'] for e in invalid['events'] if e['type']=='column_start')
        with self.assertRaises(TraceValidationError):
            validate_trace(invalid)

    def test_reject_completion_during_integral_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, trace = recorded_run(generate_identity_matrix(1), directory)
        event = next(e for e in trace['events'] if e['type']=='column_integral')
        event['type'] = 'column_complete'
        event['payload']['column'] = 0
        with self.assertRaisesRegex(TraceValidationError, 'all columns must be integral'):
            validate_trace(trace)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'), 'main.py integration needs Qiskit')
    def test_main_enabled_factory_saves_after_exact_verification(self):
        script = r'''
import constants, random, runpy, sys
import synthesis_trace

constants.GENERATE_VISUALIZATION_TRACE = True
constants.num_qubits, constants.depth = 2, 8
random.seed(17)
original_factory = synthesis_trace.create_trace
def temporary_factory(*args, **kwargs):
    kwargs['output_dir'] = sys.argv[1]
    return original_factory(*args, **kwargs)
synthesis_trace.create_trace = temporary_factory
try:
    runpy.run_path('main.py', run_name='__main__')
except NameError as error:
    assert error.name == 'backend', repr(error)
else:
    raise AssertionError('Expected the pre-existing undefined backend')
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c', script, directory],
                                    cwd=PROJECT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            traces = list(Path(directory).glob('*.json'))
            self.assertEqual(len(traces), 1)
            self.assertGreaterEqual(validate_trace(load_trace(traces[0])).operation_count, 1)
        self.assertLess(result.stdout.index('Synthesis verified successfully.'),
                        result.stdout.index('Visualization trace saved to:'))
        self.assertIn('Qiskit circuit verified successfully.', result.stdout)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'), 'main.py integration needs Qiskit')
    def test_main_flag_false_imports_no_recorder_and_writes_no_trace(self):
        script = r'''
import builtins, constants, random, runpy, sys
constants.GENERATE_VISUALIZATION_TRACE = False
constants.num_qubits, constants.depth = 2, 8
random.seed(17)
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'visualization' or name.startswith('visualization.'):
        raise AssertionError('Disabled tracing imported the visualization package')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
try:
    runpy.run_path('main.py', run_name='__main__')
except NameError as error:
    assert error.name == 'backend', repr(error)
else:
    raise AssertionError('Expected the pre-existing undefined backend')
assert not any(name == 'visualization' or name.startswith('visualization.') for name in sys.modules)
'''
        before = set((PROJECT / 'visualization/traces').glob('*.json'))
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=PROJECT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, set((PROJECT / 'visualization/traces').glob('*.json')))
        self.assertIn('Synthesis verified successfully.', result.stdout)
        self.assertIn('Qiskit circuit verified successfully.', result.stdout)


if __name__ == '__main__':
    unittest.main()
