"""Thin trace-to-Manim entry point, invoked by visualize_process.py.

Environment: DYADIC_TRACE_PATH is required; DYADIC_TIMELINE_PATH optionally
receives measured scene timestamps. No synthesis/compiler module is imported.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from manim import Scene, config

from dyadic_viz.kinetic_stage import HANDLERS, KineticContext
from dyadic_viz.trace import load_trace
from dyadic_viz.validation import validate_trace
from dyadic_viz.presentation import build_presentation
from dyadic_viz.presentation_scene import summary, formula, compact_recovery


config.frame_width = 16
config.frame_height = 9
config.background_color = "#000000"


class TraceScene(Scene):
    """Validate, dispatch semantic events, and record actual render timings."""

    def construct(self):
        path = os.environ.get("DYADIC_TRACE_PATH")
        if not path:
            raise ValueError("DYADIC_TRACE_PATH must point to a valid synthesis trace JSON file.")
        trace = load_trace(Path(path))
        validate_trace(trace)
        recipe_path = os.environ.get('DYADIC_PRESENTATION_PATH')
        recipe = json.loads(Path(recipe_path).read_text(encoding='utf-8')) if recipe_path else {}
        mode = os.environ.get('DYADIC_PRESENTATION_MODE', 'compact')
        board = build_presentation(trace, mode=mode, recipe=recipe)
        events = board['events']
        context = KineticContext(self, trace)
        timeline = {"trace_id": trace["trace_id"], "duration_seconds": 0,
                    "events": [], "sections": []}
        current_section = None
        for number, event in enumerate(events, 1):
            print(f"Event {number}/{len(events)}: {event['type']} "
                  f"[{event['section']['id']}]", flush=True)
            start = float(self.time)
            section = event["section"]
            if section["id"] != current_section:
                if timeline["sections"]:
                    timeline["sections"][-1]["end_seconds"] = start
                # Manim reuses this name in section filenames. Contract IDs are
                # portable filename components; human titles can contain ':'.
                self.next_section(name=section["id"])
                timeline["sections"].append({"id": section["id"], "title": section["title"],
                                             "start_seconds": start, "end_seconds": start})
                current_section = section["id"]
            context.begin_event(event, number, len(events))
            if event['type'] == 'presentation_summary':
                summary(context, event)
            elif event['type'] == 'presentation_formula':
                formula(context, event)
            elif event['type'] == 'recovery' and mode == 'compact' and len(trace['operations']) > 12:
                compact_recovery(context, event)
            else:
                HANDLERS[event["type"]](context, event)
            if event['type'] != 'presentation_formula':
                context.finish_event(event)
            end = float(self.time)
            timeline["events"].append({"id": event["id"], "type": event["type"],
                                       "section_id": section["id"], "start_seconds": start,
                                       "end_seconds": end, "duration_seconds": end - start,
                                       "source_event_ids": event['source_event_ids']})
        timeline["duration_seconds"] = float(self.time)
        if timeline["sections"]:
            timeline["sections"][-1]["end_seconds"] = float(self.time)
        output = os.environ.get("DYADIC_TIMELINE_PATH")
        if output:
            destination = Path(output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(timeline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
