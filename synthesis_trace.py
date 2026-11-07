"""Small, optional hooks between synthesis and the visualization recorder.

This module has no visualization dependencies. Disabled tracing uses stateless
no-op methods; enabled hooks snapshot the live compiler state synchronously.
Only pass values the compiler already calculated: copies, formatting and proof
checks belong in the recorder, not in hook arguments.
"""


class NullTrace:
    """Accept hooks without reading compiler state or importing the recorder."""

    __slots__ = ()

    def bind(self, matrix, generator_list):
        return self

    def start_column(self, column, lde, *, phase="integral"):
        pass

    def start_sweep(self, lde, scaled_column, odd_indices, groups, sign_indices):
        pass

    def sign_correction(self):
        pass

    def mixing(self):
        pass

    def permutation(self):
        pass

    def terminal_sign(self):
        pass

    def finish_sweep(self, lde):
        pass

    def column_integral(self, column):
        pass

    def column_complete(self, column):
        pass

    def finish(self, reduced_matrix, generator_list, synthesized_matrix):
        return None


NO_TRACE = NullTrace()


class SynthesisTrace:
    """Adapt a recorder to short hooks bound to one synthesis run.

    Matrix and generator-list references are bound at compiler entry. Each hook
    immediately calls the recorder, which freezes the current state before the
    compiler's next in-place change. No algorithmic decisions are made here.
    """

    def __init__(self, recorder):
        self._recorder = recorder

    def bind(self, matrix, generator_list):
        self._matrix = matrix
        self._generators = generator_list
        return self

    def start_column(self, column, lde, *, phase="integral"):
        self._recorder.start_column(self._matrix, column, lde, phase=phase)

    def start_sweep(self, lde, scaled_column, odd_indices, groups, sign_indices):
        self._recorder.start_sweep(
            self._matrix, lde, scaled_column, odd_indices, groups, sign_indices,
        )

    def _operation(self, role):
        self._recorder.operation(self._matrix, self._generators[-1], role=role)

    def sign_correction(self):
        self._operation("sign_correction")

    def mixing(self):
        self._operation("mixing")

    def permutation(self):
        self._operation("permutation")

    def terminal_sign(self):
        self._operation("terminal_sign")

    def finish_sweep(self, lde):
        self._recorder.finish_sweep(self._matrix, lde)

    def column_integral(self, column):
        self._recorder.column_integral(self._matrix, column)

    def column_complete(self, column):
        self._recorder.column_complete(self._matrix, column)

    def finish(self, reduced_matrix, generator_list, synthesized_matrix):
        """Save only after the caller has verified exact reconstruction."""
        print("[Trace] Finalizing and saving the visualization trace...", flush=True)
        path = self._recorder.finish(reduced_matrix, generator_list, synthesized_matrix)
        print(f"Visualization trace saved to: {path}", flush=True)
        return path


def bind_trace(trace, matrix, generator_list):
    """Accept an optional hook object or an existing raw TraceRecorder."""
    if trace is None:
        return NO_TRACE
    if not isinstance(trace, (NullTrace, SynthesisTrace)):
        trace = SynthesisTrace(trace)
    return trace.bind(matrix, generator_list)


def create_trace(original_matrix, *, enabled, num_qubits=None, output_dir=None):
    """Choose recording once; disabled setup does not inspect the matrix."""
    print(f"[Trace] Recording is {'enabled' if enabled else 'disabled'}.", flush=True)
    if not enabled:
        return NO_TRACE

    from visualization.trace_recorder import TraceRecorder

    return SynthesisTrace(TraceRecorder(
        original_matrix, num_qubits=num_qubits, output_dir=output_dir,
    ))
