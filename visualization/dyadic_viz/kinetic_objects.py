"""Unboxed, independently animatable mathematical objects for Manim.

Computer Modern glyphs come from Matplotlib's local mathtext renderer.  Its
SVG paths give us genuine mathematical typography without a TeX installation.
The objects in this module format supplied values; they perform no synthesis.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
from typing import Iterable, Mapping
import xml.etree.ElementTree as ET

from manim import (
    BLUE, DOWN, GOLD, GREEN, LEFT, ORANGE, PURPLE, RED, RIGHT, TEAL, UP,
    WHITE, Line, SVGMobject, Text, VGroup,
)


_CACHE_DIR = Path(__file__).resolve().parent.parent / "build" / "mathtext-cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_CACHE_DIR / "mplconfig"))

import matplotlib  # noqa: E402  (the writable cache is configured first)
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.mathtext import math_to_image  # noqa: E402


ROW_COLORS = [BLUE, TEAL, GOLD, RED, PURPLE, GREEN, ORANGE]


def generator_symbol(generator: Mapping, inverse: bool = False) -> str:
    """Mathematical gate notation, with ordered matrix-basis support."""
    symbol = {'sign': r'(-1)', 'swap': 'X', 'k': r'(H\otimes H)'}[generator['kind']]
    support = ','.join(str(index) for index in generator['indices'])
    return rf'{symbol}_{{[{support}]}}' + ('^{-1}' if inverse else '')


def row_color(index: int):
    """Use the same color whenever a global row reappears on screen."""
    return ROW_COLORS[index % len(ROW_COLORS)]


def _integer_text(value: object) -> str:
    text = str(value)
    if not re.fullmatch(r"-?\d+", text):
        raise ValueError(f"Expected an exact integer, received {text!r}")
    return text


def dyadic_expr(value: Mapping[str, object] | str | int) -> str:
    """Represent a supplied exact value as mathtext, without float conversion."""
    if not isinstance(value, Mapping):
        return _integer_text(value)
    numerator = _integer_text(value["numerator"])
    exponent = value["denominator_exponent"]
    if not isinstance(exponent, int) or isinstance(exponent, bool) or exponent < 0:
        raise ValueError("A dyadic denominator exponent must be a nonnegative integer")
    if exponent == 0:
        return numerator
    denominator = str(2 ** exponent) if exponent <= 12 else rf"2^{{{exponent}}}"
    sign = "-" if numerator.startswith("-") else ""
    magnitude = numerator[1:] if sign else numerator
    return sign + rf"\frac{{{magnitude}}}{{{denominator}}}"


@lru_cache(maxsize=2048)
def _math_template(expr: str) -> SVGMobject:
    # A version in the hash avoids retaining old SVG styling after a renderer
    # change.  The disk cache is also useful across separate Manim processes.
    digest = hashlib.sha256(("cm-path-v2:" + expr).encode("utf-8")).hexdigest()
    target = _CACHE_DIR / f"{digest}.svg"
    if not target.exists():
        temporary = target.with_name(f"{digest}.{os.getpid()}.tmp.svg")
        with matplotlib.rc_context({
            "mathtext.fontset": "cm",
            "font.family": "serif",
            "svg.fonttype": "path",
            "savefig.transparent": True,
        }):
            math_to_image(
                f"${expr}$", temporary,
                prop=FontProperties(size=32, math_fontfamily="cm"),
                format="svg", color="white",
            )
        # Matplotlib emits a transparent figure-sized patch.  Remove it before
        # Manim recolors the glyphs, so it can never become a filled rectangle.
        tree = ET.parse(temporary)
        root = tree.getroot()
        for parent in root.iter():
            for child in list(parent):
                if child.attrib.get("id") == "patch_1":
                    parent.remove(child)
        tree.write(temporary, encoding="utf-8", xml_declaration=True)
        os.replace(temporary, target)
    return SVGMobject(str(target), fill_opacity=1, stroke_width=0)


def math_token(expr: str, color=WHITE, height: float = 0.55) -> SVGMobject:
    """Return fresh editable glyph paths for a supported mathtext expression.

    ``expr`` omits dollar delimiters.  Fractions, exponents, subscripts, Greek
    letters, italic variables, and row sums use ordinary mathtext syntax.
    """
    if height <= 0:
        raise ValueError("Math token height must be positive")
    result = _math_template(expr).copy().set_color(color)
    if result.height:
        result.scale_to_fit_height(height)
    return result


def _open_brackets(width: float, height: float) -> VGroup:
    x = width / 2 + 0.18
    y = height / 2 + 0.16
    hook = 0.17
    left = VGroup(
        Line([-x + hook, y, 0], [-x, y, 0]),
        Line([-x, y, 0], [-x, -y, 0]),
        Line([-x, -y, 0], [-x + hook, -y, 0]),
    )
    right = VGroup(
        Line([x - hook, y, 0], [x, y, 0]),
        Line([x, y, 0], [x, -y, 0]),
        Line([x, -y, 0], [x - hook, -y, 0]),
    )
    return VGroup(left, right).set_stroke(WHITE, width=2)


class BareMatrix(VGroup):
    """Entries keyed by their original global indices, plus open brackets."""

    def __init__(self, values, row_ids=None, col_ids=None,
                 entry_height: float = 0.48, h_buff: float = 0.9,
                 v_buff: float = 0.85):
        self.row_ids = list(range(len(values))) if row_ids is None else list(row_ids)
        self.col_ids = (list(range(len(values[0]))) if col_ids is None else list(col_ids))
        if not self.row_ids or not self.col_ids:
            raise ValueError("A displayed matrix must contain at least one row and column")
        self.entries = {
            (row, col): math_token(dyadic_expr(values[row][col]), height=entry_height)
            for row in self.row_ids for col in self.col_ids
        }
        # Expand a column for a wide exact integer; never replace digits with
        # decimals or ellipses.  The caller can then fit the complete group.
        widths = [max(h_buff, max(self.entries[row, col].width for row in self.row_ids)
                      + 0.3) for col in self.col_ids]
        heights = [max(v_buff, max(self.entries[row, col].height for col in self.col_ids)
                       + 0.22) for row in self.row_ids]
        x_positions = []
        cursor = -sum(widths) / 2
        for width in widths:
            x_positions.append(cursor + width / 2)
            cursor += width
        y_positions = []
        cursor = sum(heights) / 2
        for height in heights:
            y_positions.append(cursor - height / 2)
            cursor -= height
        for i, row in enumerate(self.row_ids):
            for j, col in enumerate(self.col_ids):
                self.entries[row, col].move_to([x_positions[j], y_positions[i], 0])
        entries_group = VGroup(*self.entries.values())
        # The centering offset also centers matrices whose column widths vary.
        entries_group.move_to([0, 0, 0])
        self.brackets = _open_brackets(entries_group.width, entries_group.height)
        super().__init__(entries_group, self.brackets)


def bare_matrix(values, row_ids=None, col_ids=None, entry_height: float = 0.48,
                h_buff: float = 0.9, v_buff: float = 0.85) -> BareMatrix:
    return BareMatrix(values, row_ids, col_ids, entry_height, h_buff, v_buff)


class BareVector(VGroup):
    """A column vector whose individual entries can move into another object."""

    def __init__(self, values, indices=None, entry_height: float = 0.65,
                 v_buff: float = 0.9):
        self.indices = list(range(len(values))) if indices is None else list(indices)
        if not self.indices:
            raise ValueError("A displayed vector must contain at least one entry")
        self.entries = {
            index: math_token(dyadic_expr(values[index]), height=entry_height)
            for index in self.indices
        }
        spacing = max(v_buff, entry_height + 0.22)
        for i, index in enumerate(self.indices):
            self.entries[index].move_to([0, (len(self.indices) - 1) * spacing / 2 - i * spacing, 0])
        entries_group = VGroup(*self.entries.values())
        self.brackets = _open_brackets(entries_group.width, entries_group.height)
        super().__init__(entries_group, self.brackets)


def bare_vector(values, indices=None, entry_height: float = 0.65,
                v_buff: float = 0.9) -> BareVector:
    return BareVector(values, indices, entry_height, v_buff)


@lru_cache(maxsize=512)
def _caption_template(text: str, font_size: float) -> Text:
    return Text(text, font="Sans", font_size=font_size, color=WHITE)


def caption(text: str, width: float = 12, font_size: float = 28, color=WHITE) -> VGroup:
    """Wrap supplied prose into a small, centered group with no frame."""
    lines = []
    for paragraph in str(text).splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if line and _caption_template(candidate, font_size).width > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line or " ")
    result = VGroup(*(
        _caption_template(line, font_size).copy().set_color(color) for line in lines
    )).arrange(DOWN, buff=0.14)
    if result.width > width:
        result.scale_to_fit_width(width)
    return result
