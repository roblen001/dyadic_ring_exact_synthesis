"""Semantic event handlers and presentation state, independent of synthesis.

An event handler only reads supplied state, operation, generator, and explanation
records. Matrix comparisons below identify changed cells for a visual highlight;
they do not choose operations or manufacture proof statements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from manim import DOWN, LEFT, RIGHT, FadeIn, FadeOut, ReplacementTransform, VGroup

from dyadic_viz import theme as T
from dyadic_viz.components import (
    Card, CircuitView, ExplanationPanel, GeneratorView, MatrixView, StatusBar,
    VectorTable, VerificationView, fit, label, message_card, text_block,
    viewport_indices, wrap_lines,
)


@dataclass
class RenderContext:
    scene: object
    trace: dict
    state_id: str | None = None
    matrix: MatrixView | None = None
    right: object | None = None
    status: StatusBar | None = None
    heading: object | None = None
    explanation: ExplanationPanel | None = None
    highlight: VGroup | None = None
    applied: list[str] = field(default_factory=list)
    explanation_pages: list = field(default_factory=list)
    displayed_details: set = field(default_factory=set)
    pending_details: list = field(default_factory=list)

    def __post_init__(self):
        self.operations = {op["id"]: op for op in self.trace["operations"]}
        self.verifications = {item["id"]: item for item in self.trace["verifications"]}

    def replace(self, attribute: str, new, *, animate: bool = True):
        previous = getattr(self, attribute)
        if animate:
            if previous is None:
                self.scene.play(FadeIn(new), run_time=T.TRANSITION_SECONDS)
            elif attribute != "matrix":
                self.scene.play(FadeOut(previous), FadeIn(new), run_time=T.TRANSITION_SECONDS)
            else:
                self.scene.play(ReplacementTransform(previous, new), run_time=T.TRANSITION_SECONDS)
        else:
            if previous is not None:
                self.scene.remove(previous)
            self.scene.add(new)
        setattr(self, attribute, new)

    def begin_event(self, event: dict, number: int, count: int):
        self.pending_details = []
        if self.highlight is not None:
            self.scene.remove(self.highlight)
            self.highlight = None
        title = fit(label(T.EVENT_TITLES[event["type"]], 32), 10.7)
        title.move_to([-7.43, 4.03, 0], aligned_edge=LEFT)
        section = label(event["section"]["title"], 17, T.MUTED)
        long_section = section.width > 3.8
        if long_section:
            section = label("Trace section", 17, T.MUTED)
        section.move_to([7.43, 4.04, 0], aligned_edge=RIGHT)
        self.replace("heading", VGroup(title, section))
        self.explanation_pages = ExplanationPanel.pages(event, self.trace["rules"])
        if long_section:
            section_lines = wrap_lines(event["section"]["title"], T.EXPLANATION_WIDTH - 0.65, 23)
            self.explanation_pages.extend(("Section", section_lines[i:i + 2])
                                          for i in range(0, len(section_lines), 2))
        page_title, lines = self.explanation_pages[0]
        self.replace("explanation", ExplanationPanel(page_title, lines, 1, len(self.explanation_pages)))
        if hasattr(self, "footer"):
            self.scene.remove(self.footer)
        provenance = self.trace["provenance"]["kind"].upper()
        footer = f"{provenance} TRACE  ·  {self.trace['trace_id']}  ·  EVENT {number}/{count}"
        self.footer = fit(label(footer, 14, T.MUTED), 14.8).move_to([0, -4.30, 0])
        self.scene.add(self.footer)

    def finish_event(self, event: dict):
        saved_right = self.right
        if any(tuple(detail) not in self.displayed_details for detail in self.pending_details):
            self.show_exact_details(self.pending_details)
            if saved_right is not None:
                self.show_right(saved_right)
        pages = self.explanation_pages
        # The trace's hold is a minimum. Paging additionally protects readability.
        narration_seconds = len(event["narration"]["text"].split()) / 2.6
        requested = max(float(event["narration"]["hold_seconds"]), narration_seconds)
        for index, (title, lines) in enumerate(pages):
            if index:
                self.replace("explanation", ExplanationPanel(title, lines, index + 1, len(pages)))
            reading_seconds = len(" ".join(lines).split()) / 3.0
            self.scene.wait(max(1.1, requested / len(pages), reading_seconds))

    def state(self, state_id: str) -> dict:
        return self.trace["states"][state_id]

    def values(self, state_id: str) -> list:
        return self.trace["matrices"][self.state(state_id)["matrix_id"]]

    def set_state(self, state_id: str, support=(), *, changed_from: str | None = None,
                  title: str = "U · exact current matrix"):
        state = self.state(state_id)
        focus = state["focus"]
        matrix = MatrixView(self.values(state_id), focus=None if focus is None else focus["column"],
                            support=support, completed=state["completed_columns"], title=title)
        matrix.move_to(T.LEFT_CENTER)
        self.pending_details.extend(matrix.exact_details)
        self.replace("matrix", matrix)
        self.state_id = state_id
        status = StatusBar(state, self.trace["problem"]["dimension"],
                           len(self.applied), len(self.trace["operations"]))
        self.replace("status", status)
        if changed_from is not None:
            before, after = self.values(changed_from), self.values(state_id)
            changed = [(r, c) for r, c in matrix.entries if before[r][c] != after[r][c]]
            self.show_highlight(entries=changed)

    def show_highlight(self, **kwargs):
        if self.highlight is not None:
            self.scene.remove(self.highlight)
        self.highlight = self.matrix.highlights(**kwargs)
        if len(self.highlight):
            self.scene.play(FadeIn(self.highlight), run_time=0.28)

    def show_right(self, card):
        card.move_to(T.RIGHT_CENTER)
        self.replace("right", card)

    def show_text_pages(self, title: str, text: str, *, accent=T.BLUE,
                        lines_per_page: int = 7):
        lines = wrap_lines(text, T.RIGHT_WIDTH - 0.8, 24)
        pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
        for i, page in enumerate(pages):
            caption = title + (f" · {i + 1}/{len(pages)}" if len(pages) > 1 else "")
            self.show_right(message_card(caption, page, accent))
            if i + 1 < len(pages):
                self.scene.wait(max(1.5, len(" ".join(page).split()) / 3))

    def show_exact_details(self, details):
        for name, value in details:
            key = (name, value)
            if key in self.displayed_details:
                continue
            self.displayed_details.add(key)
            self.show_text_pages(f"Exact value · {name}", value, accent=T.GOLD)
            self.scene.wait(1.6)

    def show_vector(self, state_id: str, *, modulus=None, selected=()):
        focus = self.state(state_id)["focus"]
        dimension = self.trace["problem"]["dimension"]
        groups = [list(range(i, min(i + 6, dimension))) for i in range(0, dimension, 6)]
        selected_set = set(selected)
        # Show the trace-selected indices first while still eventually showing all rows.
        if selected_set:
            groups.sort(key=lambda group: not bool(selected_set.intersection(group)))
        for number, indices in enumerate(groups, 1):
            card = VectorTable(focus, indices, modulus=modulus, selected=selected,
                               page=number, pages=len(groups))
            self.show_right(card)
            if number < len(groups):
                self.scene.wait(1.8)
            if card.exact_details:
                self.show_exact_details(card.exact_details)
                self.show_right(card)

    def show_generator(self, operation: dict, *, applying=False):
        generator = self.trace["generators"][operation["generator_id"]]
        if label(generator["label"], 25).width > 6.8:
            self.show_text_pages("Generator label supplied by the trace", generator["label"], accent=T.GOLD)
            self.scene.wait(1.5)
        card = GeneratorView(generator, self.trace["matrices"][generator["matrix_id"]],
                             applying=applying)
        self.show_right(card)
        return generator


def input_event(context: RenderContext, event: dict):
    context.set_state(event["payload"]["state_id"], title="U · original input")
    problem = context.trace["problem"]
    qubits = problem["qubit_count"]
    context.show_text_pages("The synthesis problem", "\n".join([
        context.trace["title"],
        f"Dimension: {problem['dimension']}",
        "Basis-level matrix" if qubits is None else f"Qubits: {qubits}",
        context.trace["conventions"]["basis_order"],
        context.trace["provenance"]["note"],
    ]))
    context.show_exact_details(context.matrix.exact_details)


def column_start(context: RenderContext, event: dict):
    state_id = event["payload"]["state_id"]
    context.set_state(state_id)
    focus = context.state(state_id)["focus"]
    context.show_highlight(columns=[focus["column"]], color=T.BLUE)
    context.show_right(message_card("Current target", [
        f"column {focus['column']}  →  e{focus['target_row']}",
        f"Least denominator exponent: {focus['lde']}",
    ]))


def lde_analysis(context: RenderContext, event: dict):
    state_id = event["payload"]["state_id"]
    context.set_state(state_id)
    context.show_vector(state_id)


def residue_analysis(context: RenderContext, event: dict):
    payload = event["payload"]
    context.set_state(payload["state_id"], payload["indices"])
    context.show_highlight(rows=payload["indices"])
    context.show_vector(payload["state_id"], modulus=payload["modulus"], selected=payload["indices"])


def indices_selected(context: RenderContext, event: dict):
    payload = event["payload"]
    # Keep every selected index visible across pages even if there are more than six.
    indices = payload["indices"]
    for start in range(0, max(1, len(indices)), 5):
        group = indices[start:start + 5]
        context.set_state(payload["state_id"], group)
        context.show_highlight(rows=group)
        context.show_text_pages("Selection supplied by the trace", "\n".join([
            "Indices: " + ", ".join(map(str, group)), payload["purpose"],
        ]), accent=T.GOLD)
        if start + 5 < len(indices):
            context.scene.wait(1.7)


def generator_selected(context: RenderContext, event: dict):
    operation = context.operations[event["payload"]["operation_id"]]
    generator = context.trace["generators"][operation["generator_id"]]
    context.set_state(operation["before_state_id"], generator["indices"])
    context.show_highlight(rows=generator["indices"])
    context.show_generator(operation)


def apply_generator(context: RenderContext, event: dict):
    operation = context.operations[event["payload"]["operation_id"]]
    generator = context.show_generator(operation, applying=True)
    context.set_state(operation["before_state_id"], generator["indices"], title="U · before left multiplication")
    context.show_highlight(rows=generator["indices"])
    context.scene.wait(0.6)
    context.applied.append(operation["id"])
    context.set_state(operation["after_state_id"], generator["indices"],
                      changed_from=operation["before_state_id"], title="G U · changed entries in gold")
    context.show_exact_details(context.matrix.exact_details)


def lde_reduced(context: RenderContext, event: dict):
    payload = event["payload"]
    before = context.state(payload["before_state_id"])["focus"]
    after = context.state(payload["after_state_id"])["focus"]
    context.set_state(payload["after_state_id"])
    transition = label(f"{before['lde']}   →   {after['lde']}", 64, T.GOLD)
    subtitle = label("Least denominator exponent", 24, T.MUTED)
    batch = label(f"Recorded batch: {len(payload['operation_ids'])} operation(s)", 21, T.TEXT)
    body = VGroup(transition, subtitle, batch).arrange(DOWN, buff=0.36)
    context.show_right(Card("LDE before and after the supplied batch", body,
                            T.RIGHT_WIDTH, T.CONTENT_HEIGHT, T.GOLD))


def column_complete(context: RenderContext, event: dict):
    payload = event["payload"]
    context.set_state(payload["state_id"])
    context.show_highlight(columns=[payload["column"]], color=T.GREEN)
    context.show_right(message_card("Column complete", [
        f"column {payload['column']}  =  e{payload['column']}",
        f"{len(context.state(payload['state_id'])['completed_columns'])} columns recorded complete",
    ], T.GREEN))


def recovery(context: RenderContext, event: dict):
    result = context.trace["result"]
    context.set_state(result["final_state_id"], title="Reduced matrix · identity")
    generators = context.trace["generators"]
    chronological = [
        f"{number}. {generators[context.operations[operation_id]['generator_id']]['label']}"
        for number, operation_id in enumerate(result["reduction_operation_ids"], 1)
    ]
    context.show_text_pages("Reduction applications · chronological order", "\n".join(chronological) or "No applications.", accent=T.BLUE)
    context.scene.wait(max(1.5, min(5, len(chronological) * 0.5)))
    factors = result["recovered_factors"]
    product = "U = " + (" · ".join(f"({generators[item['generator_id']]['label']})⁻¹" for item in factors) or "I")
    context.show_text_pages("Recovered matrix product · written left to right", product, accent=T.GOLD)
    context.scene.wait(max(1.8, min(6, len(factors) * 0.6)))
    gates = result["circuit"]["gates"]
    dimension = context.trace["problem"]["dimension"]
    # At most four time positions per view. A support union larger than six gets
    # multiple explicitly labelled basis viewports, with no gate omitted.
    for start in range(0, max(1, len(gates)), 4):
        batch = gates[start:start + 4]
        support = list(dict.fromkeys(row for gate in batch
                                    for row in generators[gate["generator_id"]]["indices"]))
        row_pages = [support[i:i + 6] for i in range(0, len(support), 6)] or [viewport_indices(dimension)]
        if dimension <= 6:
            row_pages = [list(range(dimension))]
        for rows in row_pages:
            context.show_right(CircuitView(batch, generators, dimension, start, len(gates), sorted(rows)))
            context.scene.wait(max(1.7, len(batch) * 0.5))
        for offset, gate in enumerate(batch):
            # Full labels and supports stay readable even when circuit glyphs are compact.
            generator = generators[gate["generator_id"]]
            context.show_text_pages(f"Circuit gate {start + offset + 1}/{len(gates)} · inverse", "\n".join([
                gate["label"], "Basis indices: " + ", ".join(map(str, generator["indices"])),
            ]), accent=T.GOLD)
            context.scene.wait(1.0)
        # Return to the visual circuit for the event's voiceover hold.
        context.show_right(CircuitView(batch, generators, dimension, start, len(gates), sorted(row_pages[-1])))


def verification(context: RenderContext, event: dict):
    check = context.verifications[event["payload"]["verification_id"]]
    lines = wrap_lines(check["statement"], 6.8, 23)
    pages = [lines[i:i + 5] for i in range(0, len(lines), 5)]
    for i, page in enumerate(pages):
        context.show_right(VerificationView(check, page, i + 1, len(pages)))
        if i + 1 < len(pages):
            context.scene.wait(max(1.5, len(" ".join(page).split()) / 3))


def complete(context: RenderContext, event: dict):
    context.set_state(event["payload"]["state_id"], title="Final reduced matrix · identity")
    context.show_right(message_card("Exact synthesis verified", [
        f"{context.trace['problem']['dimension']} columns complete",
        f"{len(context.trace['operations'])} generator applications",
        "Input orthogonality   PASS",
        "Reduction to identity   PASS",
        "Reconstruction   PASS",
    ], T.GREEN))


HANDLERS: dict[str, Callable] = {
    "input": input_event,
    "column_start": column_start,
    "lde_analysis": lde_analysis,
    "residue_analysis": residue_analysis,
    "indices_selected": indices_selected,
    "generator_selected": generator_selected,
    "sign_correction": apply_generator,
    "generator_applied": apply_generator,
    "lde_reduced": lde_reduced,
    "column_complete": column_complete,
    "recovery": recovery,
    "verification": verification,
    "complete": complete,
}
