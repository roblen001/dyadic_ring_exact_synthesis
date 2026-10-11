"""Animate a supplied four-level matrix action as moving mathematical objects.

The trace owns the operation, all coefficients, and the result.  This module
only substitutes those exact values into its row products; it neither chooses
generators nor derives denominator or residue claims.
"""
from __future__ import annotations

from manim import (
    DOWN, LEFT, PI, RIGHT, UP, WHITE, YELLOW, FadeIn, FadeOut,
    Indicate, LaggedStart, Line, ReplacementTransform, TransformFromCopy,
    VGroup, smooth,
)

from dyadic_viz.kinetic_objects import (
    bare_matrix, bare_vector, dyadic_expr, math_token, row_color, generator_symbol,
)


def _supplied_caption(trace: dict, operation: dict) -> str:
    for event in trace.get("events", []):
        if (event.get("type") == "generator_applied"
                and event.get("payload", {}).get("operation_id") == operation["id"]):
            return event.get("narration", {}).get("text", "")
    return ""


def _row_expression(values: list, coefficients: list, indices: list[int]):
    """Build a factor and individually movable source-value terms.

    The public trace validator requires the canonical half-integer K block.
    Keep this assertion local too so a standalone caller cannot accidentally
    render a different matrix using the shared one-half notation.
    """
    if any(abs(int(c["numerator"])) != 1 or c["denominator_exponent"] != 1
           for c in coefficients):
        raise ValueError("The K arithmetic beat requires supplied coefficients ±1/2")

    factor = math_token(r"\frac{1}{2}", height=0.64)
    opening = math_token("(", height=0.88)
    closing = math_token(")", height=0.88)
    pieces = [factor, opening]
    targets = {}
    term_groups = []
    for number, (index, coefficient) in enumerate(zip(indices, coefficients)):
        sign = "-" if int(coefficient["numerator"]) < 0 else "+"
        sign_object = None
        if number or sign == "-":
            sign_object = math_token(sign, color=WHITE, height=0.24)
            # A standalone minus has almost no height.  Setting its height
            # like a plus sign would produce an enormous horizontal bar.
            if sign == "-":
                sign_object.scale_to_fit_width(0.25)
            pieces.append(sign_object)
        expr = dyadic_expr(values[index])
        if int(values[index]["numerator"]) < 0:
            expr = "(" + expr + ")"
        target = math_token(expr, color=row_color(index), height=0.62)
        targets[index] = target
        pieces.append(target)
        term_groups.append(VGroup(*([sign_object] if sign_object is not None else []), target))
    pieces.append(closing)
    expression = VGroup(*pieces).arrange(RIGHT, buff=0.17)
    if expression.width > 6.0:
        expression.scale_to_fit_width(6.0)
    expression.move_to([0, -0.65, 0])
    scaffold = VGroup(*(piece for piece in pieces if piece not in targets.values()))
    return expression, scaffold, targets, term_groups, VGroup(factor, opening, closing)


def animate_k(scene, trace: dict, operation: dict, caption_callback):
    """Perform one supplied K operation and return ``(objects, output_vector)``.

    The returned group contains only persistent visible stage objects.  Its
    output vector can be detached or transformed by the next mathematical
    beat.  Non-support coordinates are deliberately absent from this close-up;
    the full supplied matrix action is retained by the owning scene.
    """
    generator = trace["generators"][operation["generator_id"]]
    if generator["kind"] != "k":
        raise ValueError("animate_k needs a supplied K generator")
    indices = list(generator["indices"])
    if len(indices) != 4:
        raise ValueError("The K arithmetic close-up needs four ordered indices")
    before = trace["states"][operation["before_state_id"]]
    after = trace["states"][operation["after_state_id"]]
    column = before["focus"]["column"]
    before_values = [row[column] for row in trace["matrices"][before["matrix_id"]]]
    after_values = [row[column] for row in trace["matrices"][after["matrix_id"]]]
    coefficients = trace["matrices"][generator["matrix_id"]]

    source = bare_vector(before_values, indices=indices).move_to([-5.2, 0.3, 0])
    output = bare_vector(after_values, indices=indices).move_to([5.1, 0.3, 0])
    for index in indices:
        source.entries[index].set_color(row_color(index))
        output.entries[index].set_color(row_color(index)).set_opacity(0)

    matrix = bare_matrix(coefficients, row_ids=indices, col_ids=indices,
                         entry_height=0.40, h_buff=0.72, v_buff=0.63)
    matrix.move_to([0, 2.15, 0])
    symbol = generator_symbol(generator)
    matrix_name = math_token(symbol, color=YELLOW, height=0.48).next_to(matrix, UP, buff=0.17)
    source_name = math_token("v", height=0.52).next_to(source, UP, buff=0.35)
    output_name = math_token(symbol + 'v', height=0.52)
    if output_name.width > 4.6:
        output_name.scale_to_fit_width(4.6)
    output_name.next_to(output, UP, buff=0.35)
    persistent = VGroup(source, output, matrix, matrix_name, source_name, output_name)
    if trace['problem']['dimension'] > 4 or indices != list(range(4)):
        # A close-up is explicitly indexed so an arbitrary embedding cannot be
        # mistaken for the entire ambient vector or a different support order.
        support = math_token('(' + ','.join(str(i) for i in indices) + ')', height=.35)
        support.next_to(matrix, RIGHT, buff=.25)
        persistent.add(support)

    supplied_caption = _supplied_caption(trace, operation)
    if supplied_caption:
        caption_callback(supplied_caption)
    scene.play(FadeIn(source, shift=0.2 * RIGHT), FadeIn(source_name),
               FadeIn(matrix, shift=0.2 * DOWN), FadeIn(matrix_name),
               FadeIn(output.brackets), FadeIn(output_name), run_time=0.9)
    # Add the complete output group after its brackets enter.  Its entry
    # children stay invisible until each exact row result arrives.
    scene.add(persistent)
    scene.wait(0.35)

    previous_rule = None
    for number, row in enumerate(indices):
        row_entries = VGroup(*(matrix.entries[row, col] for col in indices))
        underline = Line(row_entries.get_left() + 0.13 * LEFT + 0.20 * DOWN,
                         row_entries.get_right() + 0.13 * RIGHT + 0.20 * DOWN,
                         color=row_color(row), stroke_width=3)
        if previous_rule is None:
            scene.play(FadeIn(underline), *(entry.animate.set_color(row_color(row)) for entry in row_entries),
                       run_time=0.35)
        else:
            scene.play(ReplacementTransform(previous_rule, underline),
                       *(entry.animate.set_color(row_color(row)) for entry in row_entries), run_time=0.25)
        previous_rule = underline

        expression, scaffold, destinations, terms, framing = _row_expression(
            before_values, [coefficients[row][col] for col in indices], indices)
        expression_members = tuple(expression.get_family())
        scene.play(FadeIn(scaffold), run_time=0.2)
        # A source copy follows an arc into its signed term.  The four row
        # colors remain stable even when the value changes in later beats.
        flights = [TransformFromCopy(source.entries[index], destinations[index],
                                     path_arc=(-0.32 + 0.17 * j) * PI)
                   for j, index in enumerate(indices)]
        scene.play(LaggedStart(*flights, lag_ratio=0.16),
                   run_time=1.15 if number == 0 else 0.85)
        scene.add(expression)
        scene.wait(0.45 if number == 0 else 0.2)

        # A zero sum physically contracts its opposing contributions before
        # becoming the exact supplied zero.  No intermediate numeric claim is
        # synthesized, so this also works when cancellation is not pairwise.
        if int(after_values[row]["numerator"]) == 0:
            center = expression.get_center()
            scene.play(*(
                term.animate.move_to(center + (term.get_center() - center) * 0.38)
                for term in terms
            ), FadeOut(framing), run_time=0.48, rate_func=smooth)
            equation_body = VGroup(*terms)
        else:
            equation_body = expression

        result = output.entries[row].copy().set_opacity(1)
        scene.play(ReplacementTransform(equation_body, result, path_arc=-0.13 * PI),
                   run_time=0.7 if number == 0 else 0.55)
        output.entries[row].set_opacity(1)
        scene.remove(result, expression, scaffold, framing, *expression_members, *terms)
        # Consolidate after the moving sum is removed.  This keeps Cairo's
        # static frame cache coherent across animations of nested entries.
        scene.add(persistent)
        scene.play(Indicate(output.entries[row], color=row_color(row), scale_factor=1.12),
                   run_time=0.4)
        scene.wait(0.22)

    scene.play(FadeOut(previous_rule), run_time=0.25)
    scene.wait(0.5)
    return persistent, output
