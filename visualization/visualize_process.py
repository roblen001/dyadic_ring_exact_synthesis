"""Validate a compiler trace, export its script, and render its Manim animation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from dyadic_viz.trace import load_trace
from dyadic_viz.validation import TraceValidationError, validate_trace
from dyadic_viz.storyboard import (
    attach_timeline, build_storyboard, write_captions, write_json, write_narration,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="JSON matching schema/synthesis-trace.schema.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true", help="Exact checks only; no Manim required")
    mode.add_argument("--storyboard-only", action="store_true", help="Export explanation/script without video")
    parser.add_argument("--quality", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args(argv)
    try:
        trace_path = args.trace.resolve()
        trace = load_trace(trace_path)
        report = validate_trace(trace)
        print(f"Validated: dimension {report.dimension}, {report.operation_count} operations, "
              f"{report.event_count} events. Exact arithmetic checks passed.")
        for warning in report.warnings:
            print(f"Note: {warning}")
        if args.validate_only:
            return 0
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        name = trace["trace_id"]
        storyboard = build_storyboard(trace)
        storyboard_path = output / f"{name}.storyboard.json"
        narration_path = output / f"{name}.narration.md"
        write_json(storyboard_path, storyboard)
        write_narration(narration_path, storyboard)
        if args.storyboard_only:
            print(f"Storyboard: {storyboard_path}\nNarration: {narration_path}")
            return 0
        if importlib.util.find_spec("manim") is None:
            raise RuntimeError("Manim is not installed in this Python environment. "
                               "Run python -m pip install -r requirements.txt.")
        media_root = output / ".manim"
        media_root.mkdir(exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=media_root))
        # Render an immutable copy so edits to the compiler output during a render cannot change it.
        frozen_trace = run_dir / "trace.json"
        write_json(frozen_trace, trace)
        timeline_path = run_dir / "timeline.json"
        env = dict(os.environ)
        env["DYADIC_TRACE_PATH"] = str(frozen_trace)
        env["DYADIC_TIMELINE_PATH"] = str(timeline_path)
        project = Path(__file__).resolve().parent
        env["PYTHONPATH"] = str(project) + os.pathsep + env.get("PYTHONPATH", "")
        quality = {"low": "l", "medium": "m", "high": "h"}[args.quality]
        command = [sys.executable, "-m", "manim", "-q", quality, "--renderer", "cairo",
                   "--format", "mp4", "--save_sections", "--disable_caching",
                   "--progress_bar", "none", "-v", "WARNING", "--media_dir", str(run_dir),
                   "--output_file", name, str(project / "dyadic_viz" / "render_scene.py"), "TraceScene"]
        print(f"Rendering {args.quality} quality. Media and section clips: {run_dir}", flush=True)
        completed = subprocess.run(command, env=env, cwd=project, check=False)
        if completed.returncode:
            raise RuntimeError(f"Manim exited with status {completed.returncode}. "
                               f"The storyboard is preserved at {storyboard_path}.")
        videos = [p for p in run_dir.rglob(f"{name}.mp4") if p.parent.name != "sections"]
        if len(videos) != 1 or not timeline_path.is_file():
            raise RuntimeError("Render did not produce exactly one movie and an event timeline")
        storyboard = attach_timeline(storyboard, json.loads(timeline_path.read_text(encoding="utf-8")))
        movie_path = output / f"{name}.mp4"
        shutil.copy2(videos[0], movie_path)
        write_json(storyboard_path, storyboard)
        write_narration(narration_path, storyboard)
        captions_path = output / f"{name}.srt"
        write_captions(captions_path, storyboard)
        shutil.copy2(timeline_path, output / f"{name}.timeline.json")
        shutil.copy2(frozen_trace, output / f"{name}.trace.json")
        write_json(output / f"{name}.manifest.json", {
            "trace_id": name, "source": str(trace_path),
            "rendered_trace_sha256": hashlib.sha256(frozen_trace.read_bytes()).hexdigest(),
            "movie": str(movie_path), "storyboard": str(storyboard_path),
            "narration": str(narration_path), "captions": str(captions_path),
            "section_media_directory": str(run_dir), "quality": args.quality,
            "duration_seconds": storyboard["duration_seconds"],
        })
        print(f"Movie: {movie_path}\nNarration: {narration_path}\nCaptions: {captions_path}")
        return 0
    except (TraceValidationError, ValueError, OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
