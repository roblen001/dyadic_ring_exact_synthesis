"""Restrained semantic palette and layout for a 16:9 mathematical explainer."""

BACKGROUND = "#111820"
PANEL = "#17222E"
BORDER = "#2C3C4D"
TEXT = "#E9F0F6"
MUTED = "#92A6B9"
BLUE = "#67B7EE"
GOLD = "#F0C76A"
GREEN = "#73D6AC"
RED = "#EF9090"
# Pango's generic families resolve to installed fonts on Windows, macOS, Linux.
FONT = "Sans"
MONO_FONT = "Monospace"

FRAME_WIDTH = 16
FRAME_HEIGHT = 9
LEFT_CENTER = (-4.02, 0.25, 0)
RIGHT_CENTER = (3.66, 0.25, 0)
LEFT_WIDTH = 7.02
RIGHT_WIDTH = 7.65
CONTENT_HEIGHT = 4.68
EXPLANATION_CENTER = (0, -3.24, 0)
EXPLANATION_WIDTH = 14.9
EXPLANATION_HEIGHT = 1.69
TRANSITION_SECONDS = 0.42

EVENT_TITLES = {
    "input": "The exact input",
    "column_start": "A column to reduce",
    "lde_analysis": "Clear the denominators",
    "residue_analysis": "Inspect the residue structure",
    "indices_selected": "The selected indices",
    "generator_selected": "The chosen generator",
    "sign_correction": "Apply the sign correction",
    "generator_applied": "Apply the generator",
    "lde_reduced": "The denominator exponent changes",
    "column_complete": "Column complete",
    "recovery": "Recover the circuit",
    "verification": "Check the exact result",
    "complete": "Synthesis complete",
}
