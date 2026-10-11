"""Record decisions and snapshots from the user's existing synthesis code.

This observer never chooses or applies a generator. Every applied generator,
quartet, sign choice, and matrix snapshot comes from the synthesis callbacks.
It is imported only when GENERATE_VISUALIZATION_TRACE is enabled in main.py.
Recording needs the project's NumPy dependency and the Python standard library;
Manim and JSON Schema are only needed when validating/rendering the saved file.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
from uuid import uuid4

import numpy as np

from utils import generate_identity_matrix, generator_to_matrix


RULES = {
    'column': ('Track a column',
               'Denominator reduction and final signed-permutation normalization are separate passes.'),
    'lde': ('Least denominator exponent',
            'The least k with 2^k v integral is recorded for the active column.'),
    'parity': ('Odd entries form quartets',
               'At positive k, the integral lift of a unit column has squared norm 4^k; its number of odd entries is divisible by four.'),
    'signs': ('Normalize odd residues',
              'An odd integer is 1 or 3 modulo four. Negating a residue-three entry makes it residue one.'),
    'mixing': ('Four-row Hadamard action',
               'Applying H tensor H to four integers congruent to one modulo four produces even integers on those rows.'),
    'integral': ('Integral unit column',
                 'An integral unit column has one nonzero entry, equal to plus or minus one. A row swap and optional sign change put it in its target position.'),
    'completion': ('Fixed basis column',
                   'A completed column equals its corresponding positive basis vector and is preserved by subsequent operations.'),
    'verification': ('Exact equality',
                     'Orthogonality, reduction, and reconstruction are checked with exact rational entries.'),
    'recovery': ('Recover the input',
                 'Chronological left reductions g1,...,gm give U=g1^-1...gm^-1. The circuit executes these factors right to left.'),
}


def _fraction(value):
    if isinstance(value, (float, complex, np.floating, np.complexfloating)):
        raise TypeError('Visualization traces require exact entries, not floats or complex values.')
    return Fraction(value)


def _dyadic(value):
    value = _fraction(value)
    denominator = value.denominator
    if denominator & (denominator - 1):
        raise ValueError(f'Non-dyadic trace entry: {value}')
    return {'numerator': str(value.numerator),
            'denominator_exponent': denominator.bit_length() - 1}


def _ints(values):
    return [int(value) for value in values]


def _label(generator):
    symbol = {'sign_flip': '(-1)', 'swap': 'X', 'hh': '(H tensor H)'}[generator['type']]
    return symbol + '_[' + ','.join(str(i) for i in generator['indices']) + ']'


class TraceRecorder:
    """An optional observer; no file is written until exact synthesis succeeds."""

    def __init__(self, original_matrix, *, num_qubits=None, output_dir=None):
        self.n = len(original_matrix)
        self.original = np.array(original_matrix, dtype=object, copy=True)
        self.identity = generate_identity_matrix(self.n)
        self.output_dir = Path(output_dir) if output_dir is not None else Path(__file__).parent / 'traces'
        self.matrix_ids = {}
        self.generator_ids = {}
        self.completed = []
        self.column = None
        self.phase = 'introduction'
        self.section = {'id': 'introduction', 'title': 'Original exact matrix'}
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        self.data = {
            'schema_version': '1.1.0',
            'trace_id': f'synthesis_{stamp}_{uuid4().hex[:8]}',
            'title': 'Exact dyadic synthesis',
            'provenance': {'kind': 'compiler', 'producer': 'dyadic_ring_exact_synthesis',
                           'note': 'Recorded from the existing algorithm without changing its generator choices or execution order.'},
            'conventions': {'profile': 'orthogonal_dyadic', 'action': 'left', 'index_base': 0,
                            'basis_order': 'Matrix rows/columns in ascending computational-basis index; Qiskit little-endian qubit convention.',
                            'circuit_time_order': 'earliest_first'},
            'problem': {'dimension': self.n, 'qubit_count': num_qubits,
                        'column_order': list(range(self.n)),
                        'reduction_strategy': 'integral_then_normalize'},
            'matrices': {}, 'states': {}, 'generators': {}, 'operations': [], 'events': [],
            'rules': {key: {'title': title, 'statement': statement, 'source_url': None}
                      for key, (title, statement) in RULES.items()},
            'verifications': [],
        }
        self.data['problem']['input_matrix_id'] = self._matrix(self.original)
        self.data['problem']['target_matrix_id'] = self._matrix(self.identity)
        self.current = self._state(self.original)
        self.data['problem']['initial_state_id'] = self.current
        self._event('input', {'state_id': self.current}, None,
                    'Begin with the supplied exact dyadic orthogonal matrix.')
        self._verification('input_orthogonality', self.original.T @ self.original, self.identity,
                           'The original matrix satisfies U^T U = I exactly.')

    def _matrix(self, matrix):
        # Immutable keys prevent later in-place synthesis writes changing snapshots.
        key = tuple(tuple(_fraction(value) for value in row) for row in matrix)
        if key not in self.matrix_ids:
            matrix_id = f'matrix_{len(self.matrix_ids):05d}'
            self.matrix_ids[key] = matrix_id
            self.data['matrices'][matrix_id] = [[_dyadic(value) for value in row] for row in key]
        return self.matrix_ids[key]

    def _state(self, matrix):
        focus = None
        if self.column is not None:
            values = [_fraction(row[self.column]) for row in matrix]
            # Exact observation of a supplied snapshot, never an algorithmic choice.
            lde = max(value.denominator.bit_length() - 1 for value in values)
            lifted = [value * (2 ** lde) for value in values]
            if any(value.denominator != 1 for value in lifted):
                raise ValueError('Snapshot column is not dyadic.')
            integers = [value.numerator for value in lifted]
            focus = {'column': self.column, 'target_row': self.column, 'lde': lde,
                     'scaled_vector': [str(value) for value in integers],
                     'residues_mod2': [value % 2 for value in integers],
                     'residues_mod4': [value % 4 for value in integers]}
        state_id = f'state_{len(self.data["states"]):05d}'
        self.data['states'][state_id] = {'matrix_id': self._matrix(matrix),
                                       'completed_columns': list(self.completed), 'focus': focus}
        return state_id

    def _event(self, kind, payload, rule, text, *, facts=(), hold=0.6):
        self.data['events'].append({
            'id': f'event_{len(self.data["events"]):05d}', 'type': kind,
            'section': dict(self.section), 'payload': payload,
            'narration': {'text': text, 'hold_seconds': hold},
            'explanation': {'rule_id': rule, 'summary': text,
                            'facts': [{'label': label, 'text': str(value)} for label, value in facts]},
        })

    def _verification(self, kind, left, right, statement):
        if not np.array_equal(left, right):
            raise ValueError(f'Cannot export a successful trace: {kind} failed.')
        check_id = 'verify_' + kind
        self.data['verifications'].append({
            'id': check_id, 'kind': kind, 'passed': True,
            'left_matrix_id': self._matrix(left), 'right_matrix_id': self._matrix(right),
            'statement': statement,
        })
        self._event('verification', {'verification_id': check_id}, 'verification', statement)

    def start_column(self, matrix, column, lde, *, phase):
        self.column, self.phase = int(column), phase
        self.section = {'id': f'{phase}_column_{column}',
                        'title': f'{"Reduce denominators in" if phase == "integral" else "Normalize"} column {column}'}
        self.current = self._state(matrix)
        actual = self.data['states'][self.current]['focus']['lde']
        if actual != int(lde):
            raise ValueError('Supplied compiler LDE disagrees with the exact snapshot.')
        self._event('column_start', {'state_id': self.current}, 'column',
                    f'{"Reduce denominators in" if phase == "integral" else "Normalize"} column {column}.')
        self._event('lde_analysis', {'state_id': self.current}, 'lde',
                    f'The active column has least denominator exponent {actual}.')

    def start_sweep(self, matrix, lde, scaled_column, odd_indices, groups, sign_indices):
        focus = self.data['states'][self.current]['focus']
        if focus['scaled_vector'] != [str(int(value)) for value in scaled_column]:
            raise ValueError('Supplied compiler integer lift disagrees with the snapshot.')
        self.batch_start, self.batch_position = self.current, len(self.data['operations'])
        self.batch_lde = int(lde)
        odd, signs = _ints(odd_indices), _ints(sign_indices)
        self._event('residue_analysis', {'state_id': self.current, 'modulus': 2,
                                        'indices': list(range(self.n))}, 'parity',
                    f'The compiler selected {len(odd)} odd coordinates.',
                    facts=[('Odd indices', odd), ('Selected quartets', [_ints(group) for group in groups])])
        for group in groups:
            indices = _ints(group)
            self._event('indices_selected', {'state_id': self.current, 'indices': indices,
                                            'purpose': 'The next quartet selected by the compiler.'},
                        'parity', f'The compiler groups rows {indices}.')
        self._event('residue_analysis', {'state_id': self.current, 'modulus': 4, 'indices': odd},
                    'signs', f'Normalize residue-three entries in rows {signs}.',
                    facts=[('Compiler sign choices', signs)])

    def operation(self, matrix, generator, *, role):
        # generator is the record that the compiler just appended; its matrix is
        # obtained using the project's existing generator-to-matrix function.
        indices = _ints(generator['indices'])
        key = (generator['type'], tuple(indices))
        if key not in self.generator_ids:
            generator_id = f'generator_{len(self.generator_ids):05d}'
            self.generator_ids[key] = generator_id
            self.data['generators'][generator_id] = {
                'kind': {'sign_flip': 'sign', 'swap': 'swap', 'hh': 'k'}[generator['type']],
                'indices': indices, 'matrix_id': self._matrix(generator_to_matrix(generator, self.n)),
                'label': _label(generator),
            }
        generator_id = self.generator_ids[key]
        rule = {'sign_correction': 'signs', 'mixing': 'mixing',
                'permutation': 'integral', 'terminal_sign': 'integral'}[role]
        op_id = f'operation_{len(self.data["operations"]):05d}'
        after = self._state(matrix)
        self.data['operations'].append({'id': op_id, 'generator_id': generator_id,
                                       'before_state_id': self.current, 'after_state_id': after,
                                       'role': role, 'rule_id': rule})
        self._event('generator_selected', {'operation_id': op_id}, rule,
                    f'The compiler selected {_label(generator)}.')
        self._event('sign_correction' if role == 'sign_correction' else 'generator_applied',
                    {'operation_id': op_id}, rule, f'Apply {_label(generator)} to the recorded rows.')
        self.current = after

    def finish_sweep(self, matrix, lde):
        actual = self.data['states'][self.current]['focus']['lde']
        if actual != int(lde) or self._matrix(matrix) != self.data['states'][self.current]['matrix_id']:
            raise ValueError('Sweep endpoint disagrees with the recorded operations.')
        if actual < self.batch_lde:
            self._event('lde_reduced', {'before_state_id': self.batch_start, 'after_state_id': self.current,
                                       'operation_ids': [op['id'] for op in self.data['operations'][self.batch_position:]]},
                        'lde', f'After this sweep the least denominator exponent drops from {self.batch_lde} to {actual}.')

    def column_integral(self, matrix, column):
        self.current = self._state(matrix)
        self._event('column_integral', {'state_id': self.current}, 'integral',
                    f'Column {column} is integral. Its final position and sign are handled in the normalization pass.')

    def column_complete(self, matrix, column):
        self.completed.append(int(column))
        self.current = self._state(matrix)
        self._event('column_complete', {'state_id': self.current, 'column': int(column)}, 'completion',
                    f'Column {column} now equals its target positive basis vector.')

    def finish(self, reduced_matrix, generator_list, synthesized_matrix):
        observed = [(self.data['generators'][op['generator_id']]['kind'],
                     self.data['generators'][op['generator_id']]['indices']) for op in self.data['operations']]
        expected = [({'sign_flip': 'sign', 'swap': 'swap', 'hh': 'k'}[gen['type']], _ints(gen['indices']))
                    for gen in generator_list]
        if observed != expected or self.completed != list(range(self.n)):
            raise ValueError('Trace is missing an operation or completed column.')
        self.column = None
        self.current = self._state(reduced_matrix)
        self.section = {'id': 'recovery', 'title': 'Recover and verify the original matrix'}
        self._verification('reduction_identity', reduced_matrix, self.identity,
                           'The recorded reduction ends at the exact identity matrix.')
        factors = [{'generator_id': op['generator_id'], 'inverse': True} for op in self.data['operations']]
        self.data['result'] = {
            'final_state_id': self.current,
            'reduction_operation_ids': [op['id'] for op in self.data['operations']],
            'recovered_factors': factors,
            'circuit': {'representation': 'basis_level', 'time_order': 'earliest_first',
                        'gates': [{'id': f'gate_{i:05d}', **factor,
                                   'label': self.data['generators'][factor['generator_id']]['label']}
                                  for i, factor in enumerate(reversed(factors))]},
        }
        self._event('recovery', {}, 'recovery',
                    'Recover the original matrix using inverse reduction factors; execute the circuit right to left in the written product.')
        self._verification('reconstruction', synthesized_matrix, self.original,
                           'The original matrix equals the synthesized matrix exactly.')
        self._event('complete', {'state_id': self.current}, None,
                    'The complete exact synthesis trace is ready for visualization.')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / (self.data['trace_id'] + '.json')
        temporary = destination.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        temporary.replace(destination)
        return destination.resolve()
