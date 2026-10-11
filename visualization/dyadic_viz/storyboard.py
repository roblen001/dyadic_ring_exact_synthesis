"""Export supplied events and voiceover cues without importing Manim."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import textwrap


def build_storyboard(trace: dict) -> dict:
    """Prepare a literal storyboard from an already validated trace.

    Timing is intentionally absent until Manim measures the rendered animations.
    Hold times alone are not video timestamps.
    """
    operations = {op["id"]: op for op in trace["operations"]}
    current = trace["problem"]["initial_state_id"]
    applied = []
    events = []
    for event in trace["events"]:
        item = deepcopy(event)
        before = current
        payload = event["payload"]
        if event["type"] in ("generator_applied", "sign_correction"):
            operation = operations[payload["operation_id"]]
            before = operation["before_state_id"]
            current = operation["after_state_id"]
            applied.append(operation["id"])
        elif "state_id" in payload:
            current = payload["state_id"]
        elif event["type"] == "lde_reduced":
            current = payload["after_state_id"]
        elif event["type"] == "recovery":
            current = trace["result"]["final_state_id"]
        item["before_state_id"] = before
        item["after_state_id"] = current
        item["applied_operation_ids"] = list(applied)
        events.append(item)
    return {
        "schema_version": trace['schema_version'], "trace_id": trace["trace_id"],
        "title": trace["title"], "provenance": deepcopy(trace["provenance"]),
        "rules": deepcopy(trace["rules"]),
        "timing_status": "unrendered", "events": events,
    }


def attach_timeline(storyboard: dict, timeline: dict) -> dict:
    """Attach actual renderer timings, refusing an unrelated or partial render."""
    if timeline["trace_id"] != storyboard["trace_id"]:
        raise ValueError("Timeline belongs to a different trace")
    expected = [event["id"] for event in storyboard["events"]]
    observed = [event["id"] for event in timeline["events"]]
    if expected != observed:
        raise ValueError("Timeline event sequence does not match the storyboard")
    result = deepcopy(storyboard)
    previous_end = 0.0
    for event, timing in zip(result["events"], timeline["events"]):
        start, end = timing["start_seconds"], timing["end_seconds"]
        if start < previous_end - 1e-6 or end <= start:
            raise ValueError(f"Invalid rendered timing for {event['id']}")
        event["timing"] = {"start_seconds": start, "end_seconds": end}
        previous_end = end
    result["timing_status"] = "rendered"
    result["duration_seconds"] = timeline["duration_seconds"]
    result["sections"] = deepcopy(timeline["sections"])
    return result


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_narration(path: Path, storyboard: dict) -> None:
    lines = [f"# {storyboard['title']}", "", "Voiceover script supplied by the trace.", ""]
    if storyboard["timing_status"] == "unrendered":
        lines += ["Timestamps will be added after rendering; holds exclude animation time.", ""]
    section = None
    for event in storyboard["events"]:
        if event["section"]["id"] != section:
            section = event["section"]["id"]
            lines += [f"## {event['section']['title']}", ""]
        cue = event["id"] + " / " + event["type"]
        if "timing" in event:
            cue += f" / {event['timing']['start_seconds']:.2f}–{event['timing']['end_seconds']:.2f}s"
        lines += [f"### {cue}", "", event["narration"]["text"], "",
                  f"Hold after animations: {event['narration']['hold_seconds']:g}s.", ""]
        explanation = event["explanation"]
        lines += ["Editor notes (kept off-screen):", "", explanation["summary"], ""]
        rule = storyboard.get("rules", {}).get(explanation["rule_id"])
        if rule:
            lines += [f"Rule: {rule['title']}. {rule['statement']}", ""]
        for fact in explanation["facts"]:
            lines += [f"- {fact['label']}: {fact['text']}"]
        lines += [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def write_captions(path: Path, storyboard: dict) -> None:
    """Draft SRT aligned to event spans, for subsequent human voiceover editing."""
    if storyboard["timing_status"] != "rendered":
        raise ValueError("Captions require actual rendered timestamps")
    cues = []
    for event in storyboard["events"]:
        # Keep literal words; split long narration over sequential two-line cues.
        lines = textwrap.wrap(event["narration"]["text"], 42, break_long_words=False,
                              break_on_hyphens=False)
        chunks = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        start, end = event["timing"]["start_seconds"], event["timing"]["end_seconds"]
        weights = [len(chunk) for chunk in chunks]
        weight_sum = sum(weights)
        cursor = start
        for i, (chunk, weight) in enumerate(zip(chunks, weights)):
            next_cursor = end if i == len(chunks) - 1 else cursor + (end - start) * weight / weight_sum
            cues += [str(len(cues) // 4 + 1),
                     f"{_timestamp(cursor)} --> {_timestamp(next_cursor)}", chunk, ""]
            cursor = next_cursor
    path.write_text("\n".join(cues) + "\n", encoding="utf-8")
