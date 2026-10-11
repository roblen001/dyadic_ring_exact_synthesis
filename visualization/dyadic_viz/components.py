"""Reusable Manim views. All numbers and explanations come from the trace.

These components do formatting and viewport selection, never synthesis. In
particular, the integer lifts, LDEs, residues, and gate order are supplied data.
Plain Pango Text is used throughout; TeX is neither invoked nor required.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from manim import (
    DOWN, LEFT, RIGHT, UP, Line, RoundedRectangle,
    SurroundingRectangle, Text, VGroup,
)

from dyadic_viz import theme as T


@lru_cache(maxsize=512)
def _label_template(text: str, size: float) -> Text:
    # Keep pristine templates: constructing repeated matrix numerals should not
    # repeatedly parse the same SVG paths. Callers only ever receive copies.
    return Text(text, font=T.FONT, font_size=size, color=T.TEXT)


def label(text: object, size: float = 24, color: str = T.TEXT, **kwargs) -> Text:
    """Literal, non-markup text: trace content is never interpreted as code."""
    if kwargs:
        return Text(str(text), font=T.FONT, font_size=size, color=color, **kwargs)
    return _label_template(str(text), size).copy().set_color(color)


def fit(mobject, width: float, height: float | None = None):
    factor = min(1, width / max(mobject.width, 0.001))
    if height is not None:
        factor = min(factor, height / max(mobject.height, 0.001))
    return mobject.scale(factor)


@lru_cache(maxsize=4096)
def _text_width(value: str, size: float) -> float:
    return _label_template(value or " ", size).width


def wrap_lines(value: str, width: float, size: float = 24) -> list[str]:
    """Wrap without truncation, with a hard-word fallback for long integers."""
    output: list[str] = []
    # Measure cached words, not every successively longer sentence prefix.
    # A small margin accommodates side bearings; text_block applies the final
    # exact fit. Long indivisible tokens still use exact Pango measurements.
    space_width = max(0.02, _text_width("x x", size) - _text_width("xx", size))
    target_width = width * 0.96
    for paragraph in value.splitlines() or [""]:
        current = ""
        current_width = 0.0
        for word in paragraph.split():
            proposed = f"{current} {word}" if current else word
            word_width = _text_width(word, size)
            proposed_width = current_width + (space_width if current else 0) + word_width
            if proposed_width <= target_width:
                current = proposed
                current_width = proposed_width
                continue
            if current:
                output.append(current)
                current = ""
            # Break a long uninterrupted token only at a visual line boundary.
            while _text_width(word, size) > width:
                lo, hi = 1, len(word)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if _text_width(word[:mid], size) <= width:
                        lo = mid
                    else:
                        hi = mid - 1
                output.append(word[:lo])
                word = word[lo:]
            current = word
            current_width = _text_width(word, size)
        if current:
            output.append(current)
        elif not paragraph.strip():
            output.append("")
    return output or [""]


def text_block(lines: Iterable[str], width: float, size: float = 24,
               color: str = T.TEXT, gap: float = 0.13) -> VGroup:
    group = VGroup(*(label(line or " ", size, color) for line in lines))
    group.arrange(DOWN, aligned_edge=LEFT, buff=gap)
    return fit(group, width)


class Card(VGroup):
    def __init__(self, title: str, body, width: float, height: float,
                 accent: str = T.BLUE):
        frame = RoundedRectangle(width=width, height=height, corner_radius=0.12,
                                 stroke_color=T.BORDER, stroke_width=1,
                                 fill_color=T.PANEL, fill_opacity=1)
        heading = fit(label(title, 21, accent), width - 0.55)
        heading.move_to(frame.get_corner(UP + LEFT) + RIGHT * 0.27 + DOWN * 0.30,
                        aligned_edge=LEFT)
        fit(body, width - 0.6, height - 0.98)
        body.move_to(frame.get_center() + DOWN * 0.20)
        self.body = body
        super().__init__(frame, heading, body)


class ExactDyadic(VGroup):
    """An exact integer or stacked fraction; large denominators stay as 2^k."""
    def __init__(self, value: dict, size: float = 25, color: str = T.TEXT):
        numerator = value["numerator"]
        exponent = value["denominator_exponent"]
        if exponent == 0:
            super().__init__(label(numerator, size, color))
            return
        denominator = str(2 ** exponent) if exponent <= 12 else f"2^{exponent}"
        top = label(numerator, size * 0.80, color)
        bottom = label(denominator, size * 0.80, color)
        length = max(top.width, bottom.width) + 0.08
        bar = Line(LEFT * length / 2, RIGHT * length / 2,
                   stroke_color=color, stroke_width=1.25)
        top.next_to(bar, UP, buff=0.055)
        bottom.next_to(bar, DOWN, buff=0.055)
        super().__init__(top, bar, bottom)


def viewport_indices(dimension: int, preferred: Iterable[int] = (),
                     limit: int = 6) -> list[int]:
    """Keep focus/support visible and retain original global index labels."""
    chosen = list(dict.fromkeys(preferred))[:limit]
    chosen.extend(i for i in range(dimension) if i not in chosen)
    return sorted(chosen[:limit])


class MatrixView(VGroup):
    """Readable matrix viewport; never squeezes an entire large matrix down."""
    def __init__(self, values: list, *, focus: int | None = None,
                 support: Iterable[int] = (), completed: Iterable[int] = (),
                 row_indices: list[int] | None = None,
                 column_indices: list[int] | None = None,
                 title: str = "U · exact matrix", width: float = T.LEFT_WIDTH,
                 height: float = T.CONTENT_HEIGHT):
        dimension = len(values)
        support = list(support)
        preferred = support + ([] if focus is None else [focus])
        self.rows = row_indices if row_indices is not None else viewport_indices(dimension, preferred)
        self.columns = column_indices if column_indices is not None else viewport_indices(
            dimension, [] if focus is None else [focus])
        self.entries: dict[tuple[int, int], VGroup] = {}
        self.exact_details: list[tuple[str, str]] = []
        table = VGroup()
        nx, ny = len(self.columns), len(self.rows)
        dx = min(0.92, (width - 1.15) / max(1, nx))
        dy = min(0.69, (height - 1.2) / max(1, ny))
        x0, y0 = -(nx - 1) * dx / 2, (ny - 1) * dy / 2
        completed_set = set(completed)
        for j, column in enumerate(self.columns):
            color = T.GREEN if column in completed_set else T.MUTED
            table.add(label(f"c{column}", 14, color).move_to(
                [x0 + j * dx, y0 + dy * 0.77, 0]))
        for i, row in enumerate(self.rows):
            table.add(label(f"r{row}", 14, T.GOLD if row in support else T.MUTED).move_to(
                [x0 - dx * 0.86, y0 - i * dy, 0]))
            for j, column in enumerate(self.columns):
                value = values[row][column]
                if len(value["numerator"]) > 7 or len(str(value["denominator_exponent"])) > 6:
                    token = f"#{len(self.exact_details) + 1}"
                    exponent = value["denominator_exponent"]
                    rendered = value["numerator"] if exponent == 0 else (
                        f"({value['numerator']}) / 2^{exponent}")
                    self.exact_details.append((f"{token} = entry [{row}, {column}]", rendered))
                    entry = VGroup(label(token, 22, T.GOLD))
                else:
                    color = T.GREEN if column in completed_set else T.TEXT
                    entry = ExactDyadic(value, 25, color)
                fit(entry, dx * 0.76, dy * 0.75)
                entry.move_to([x0 + j * dx, y0 - i * dy, 0])
                self.entries[row, column] = entry
                table.add(entry)
        left = x0 - dx * 0.58
        right = x0 + (nx - 1) * dx + dx * 0.58
        top, bottom = y0 + dy * 0.48, y0 - (ny - 1) * dy - dy * 0.48
        for x, direction in ((left, 1), (right, -1)):
            table.add(Line([x, bottom, 0], [x, top, 0], color=T.MUTED),
                      Line([x, top, 0], [x + direction * 0.12, top, 0], color=T.MUTED),
                      Line([x, bottom, 0], [x + direction * 0.12, bottom, 0], color=T.MUTED))
        if focus in self.columns:
            cells = VGroup(*(self.entries[r, focus] for r in self.rows))
            glow = SurroundingRectangle(cells, buff=0.14, color=T.BLUE,
                                        fill_color=T.BLUE, fill_opacity=0.07, stroke_width=1.5)
            table.add_to_back(glow)
        scope = f"{dimension} × {dimension} · global row / column indices"
        if len(self.rows) < dimension or len(self.columns) < dimension:
            scope = f"Viewport: {len(self.rows)} × {len(self.columns)} of {dimension} × {dimension} · omitted entries not shown"
        if self.exact_details:
            scope += "\nNumbered entries have exact-value detail pages."
        note = text_block(wrap_lines(scope, width - 0.65, 14), width - 0.65, 14, T.MUTED)
        body = VGroup(table, note).arrange(DOWN, buff=0.22)
        self.card = Card(title, body, width, height)
        super().__init__(self.card)

    def highlights(self, *, rows: Iterable[int] = (), columns: Iterable[int] = (),
                   entries: Iterable[tuple[int, int]] = (), color: str = T.GOLD) -> VGroup:
        result = VGroup()
        for row in rows:
            cells = [v for (r, _), v in self.entries.items() if r == row]
            if cells:
                result.add(SurroundingRectangle(VGroup(*cells), buff=0.10,
                                                color=color, stroke_width=1.8))
        for column in columns:
            cells = [v for (_, c), v in self.entries.items() if c == column]
            if cells:
                result.add(SurroundingRectangle(VGroup(*cells), buff=0.10,
                                                color=color, stroke_width=1.8))
        for key in entries:
            if key in self.entries:
                result.add(SurroundingRectangle(self.entries[key], buff=0.075,
                                                color=color, stroke_width=1.5,
                                                fill_color=color, fill_opacity=0.10))
        return result


class StatusBar(VGroup):
    def __init__(self, state: dict, dimension: int, operation_count: int, total: int):
        focus = state["focus"]
        active = "No active column" if focus is None else f"Column {focus['column']} → e{focus['target_row']}"
        lde = "LDE —" if focus is None else f"LDE  {focus['lde']}"
        pieces = VGroup(label(active, 22, T.BLUE), label(lde, 24, T.GOLD),
                        label(f"{len(state['completed_columns'])}/{dimension} columns complete", 20, T.GREEN),
                        label(f"{operation_count}/{total} operations", 19, T.MUTED))
        pieces.arrange(RIGHT, buff=0.75)
        fit(pieces, 14.8)
        super().__init__(pieces)
        self.move_to([0, 3.10, 0])


class VectorTable(Card):
    def __init__(self, focus: dict, indices: list[int], *, modulus: int | None = None,
                 selected: Iterable[int] = (), page: int = 1, pages: int = 1):
        columns = ["row", f"2^{focus['lde']} · U[row,{focus['column']}]", "mod 2", "mod 4"]
        widths = [0.75, 3.60, 1.02, 1.02]
        centers = [-2.86, -0.685, 1.625, 2.645]
        heading = VGroup(*(fit(label(value, 17, T.MUTED), w).move_to([x, 1.3, 0])
                           for value, w, x in zip(columns, widths, centers)))
        lines = VGroup(heading)
        selected_set = set(selected)
        self.exact_details: list[tuple[str, str]] = []
        for k, index in enumerate(indices):
            y = 0.76 - k * 0.47
            integer = focus["scaled_vector"][index]
            if len(integer) > 18:
                token = f"#{len(self.exact_details) + 1}"
                self.exact_details.append((f"{token} = scaled vector row {index}", integer))
                integer = token
            texts = [str(index), integer, str(focus["residues_mod2"][index]), str(focus["residues_mod4"][index])]
            color = T.GOLD if index in selected_set else T.TEXT
            for number, (value, width, x) in enumerate(zip(texts, widths, centers)):
                entry_color = color if number < 2 else (T.GOLD if modulus == (2 if number == 2 else 4) else T.MUTED)
                lines.add(fit(label(value, 23, entry_color), width).move_to([x, y, 0]))
        footer = label(f"Exact supplied integer lift · rows {indices[0]}–{indices[-1]} · page {page}/{pages}", 15, T.MUTED)
        footer.move_to([0, -2.18, 0])
        lines.add(footer)
        title = "Integer lift and residues" if modulus is None else f"Residue view · modulus {modulus}"
        super().__init__(title, lines, T.RIGHT_WIDTH, T.CONTENT_HEIGHT)


class GeneratorView(Card):
    def __init__(self, generator: dict, values: list, *, applying: bool = False):
        indices = generator["indices"]
        matrix = MatrixView(values, row_indices=indices, column_indices=indices,
                            title="G · supplied support block", width=6.5, height=2.7)
        name = label(generator["label"], 25, T.GOLD)
        if name.width > 6.8:
            name = label(f"G · {generator['kind']} generator", 25, T.GOLD)
        support = fit(label(f"Ordered indices: {', '.join(map(str, indices))}", 18, T.MUTED), 6.7)
        formula = label("U  →  G U" if applying else "Chosen action: left multiplication", 25, T.BLUE)
        group = VGroup(name, support, matrix, formula).arrange(DOWN, buff=0.12)
        self.exact_details = matrix.exact_details
        super().__init__("Apply this generator" if applying else "Generator selected by the trace",
                         group, T.RIGHT_WIDTH, T.CONTENT_HEIGHT, T.GOLD)


class ExplanationPanel(Card):
    @staticmethod
    def pages(event: dict, rules: dict) -> list[tuple[str, list[str]]]:
        explanation = event["explanation"]
        rule_id = explanation["rule_id"]
        blocks: list[tuple[str, str]] = []
        if explanation["summary"]:
            blocks.append(("Trace explanation", explanation["summary"]))
        if rule_id is not None:
            rule = rules[rule_id]
            blocks.append((rule["title"], rule["statement"]))
        blocks.extend((fact["label"], fact["text"]) for fact in explanation["facts"])
        output = []
        for title, value in blocks:
            # Heading also wraps/paginates as literal content when unusually long.
            if _text_width(title, 20) > T.EXPLANATION_WIDTH - 0.6:
                value, title = title + "\n" + value, "Trace explanation"
            lines = wrap_lines(value, T.EXPLANATION_WIDTH - 0.65, 23)
            for start in range(0, len(lines), 2):
                output.append((title, lines[start:start + 2]))
        return output or [("Trace explanation", [""])]

    def __init__(self, title: str, lines: list[str], page: int, pages: int):
        if pages > 1:
            title = f"{title}  ·  {page}/{pages}"
        body = text_block(lines, T.EXPLANATION_WIDTH - 0.65, 23)
        super().__init__(title, body, T.EXPLANATION_WIDTH, T.EXPLANATION_HEIGHT, T.MUTED)
        self.move_to(T.EXPLANATION_CENTER)


def message_card(title: str, lines: list[str], accent: str = T.BLUE) -> Card:
    body = text_block(lines, T.RIGHT_WIDTH - 0.7, 27)
    return Card(title, body, T.RIGHT_WIDTH, T.CONTENT_HEIGHT, accent)


class CircuitView(Card):
    """Basis-level circuit in the explicit trace-provided temporal order."""
    def __init__(self, gates: list[dict], generators: dict, dimension: int,
                 start: int, total: int, rows: list[int]):
        body = VGroup()
        dy = 0.47
        top = (len(rows) - 1) * dy / 2
        y_by_row = {row: top - k * dy for k, row in enumerate(rows)}
        for row, y in y_by_row.items():
            body.add(label(f"|{row}>", 20, T.MUTED).move_to([-2.98, y, 0]),
                     Line([-2.52, y, 0], [3.02, y, 0], color=T.BORDER, stroke_width=2))
        gate_dx = min(1.15, 5.1 / max(1, len(gates)))
        left = -2.03
        for offset, gate in enumerate(gates):
            generator = generators[gate["generator_id"]]
            x = left + offset * gate_dx
            affected = [r for r in generator["indices"] if r in y_by_row]
            if affected:
                ys = [y_by_row[r] for r in affected]
                body.add(Line([x, min(ys), 0], [x, max(ys) + 0.001, 0], color=T.GOLD))
                for row in affected:
                    box = RoundedRectangle(width=0.40, height=0.31, corner_radius=0.045,
                                           stroke_color=T.GOLD, stroke_width=1.2,
                                           fill_color=T.PANEL, fill_opacity=1)
                    box.move_to([x, y_by_row[row], 0])
                    symbol = {"sign": "−", "swap": "×", "k": "K"}[generator["kind"]]
                    body.add(box, label(symbol, 17, T.GOLD).move_to(box))
            caption = label(str(start + offset + 1), 17, T.BLUE)
            caption.move_to([x, top + 0.47, 0])
            body.add(caption)
        order = label("time →    supplied chronological order", 19, T.BLUE)
        order.move_to([0, -top - 0.65, 0])
        scope = f"Gates {start + 1}–{start + len(gates)} of {total} · inverse factors"
        if not gates:
            scope = "Empty circuit · no generator applications"
        body.add(order, label(scope, 16, T.MUTED).next_to(order, DOWN, buff=0.17))
        if len(rows) < dimension:
            body.add(label(f"Basis viewport: {len(rows)} of {dimension} levels", 15, T.MUTED).next_to(order, DOWN, buff=0.50))
        super().__init__("Basis-level circuit · each numbered gate is an inverse", body,
                         T.RIGHT_WIDTH, T.CONTENT_HEIGHT, T.GOLD)


class VerificationView(Card):
    def __init__(self, verification: dict, lines: list[str], page: int = 1, pages: int = 1):
        passed = verification["passed"]
        status = label("PASS" if passed else "FAIL", 45, T.GREEN if passed else T.RED)
        statement = text_block(lines, 6.8, 23)
        witnesses = [f"Left witness: {verification['left_matrix_id']}",
                     f"Right witness: {verification['right_matrix_id']}"]
        if any(_text_width(value, 17) > 6.8 for value in witnesses):
            witnesses = ["Exact witness matrices are recorded in the trace."]
        witness = text_block(witnesses, 6.8, 17, T.MUTED)
        body = VGroup(status, statement, witness).arrange(DOWN, buff=0.30)
        title = verification["kind"].replace("_", " ").capitalize()
        if pages > 1:
            title += f" · {page}/{pages}"
        super().__init__(title, body, T.RIGHT_WIDTH, T.CONTENT_HEIGHT, T.GREEN)
