import json
from pathlib import Path
import tempfile
import unittest

from dyadic_viz.trace import load_trace
from dyadic_viz.storyboard import build_storyboard, attach_timeline, write_captions, write_narration

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthesis_trace.json"


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.trace = load_trace(FIXTURE)
        self.board = build_storyboard(self.trace)

    def test_only_apply_events_extend_prefix(self):
        previous = 0
        for event in self.board["events"]:
            count = len(event["applied_operation_ids"])
            self.assertEqual(count - previous, int(event["type"] in ("sign_correction", "generator_applied")))
            previous = count
        self.assertEqual(previous, 4)

    def test_no_guessed_timestamps(self):
        self.assertEqual(self.board["timing_status"], "unrendered")
        self.assertTrue(all("timing" not in event for event in self.board["events"]))

    def test_measured_captions_keep_all_narration(self):
        timeline = {"trace_id": self.trace["trace_id"], "duration_seconds": 320,
                    "sections": [], "events": [
                        {"id": e["id"], "start_seconds": 10 * i, "end_seconds": 10 * (i + 1)}
                        for i, e in enumerate(self.trace["events"])]}
        rendered = attach_timeline(self.board, timeline)
        with tempfile.TemporaryDirectory() as folder:
            srt, script = Path(folder) / "captions.srt", Path(folder) / "narration.md"
            write_captions(srt, rendered)
            write_narration(script, rendered)
            lines = srt.read_text(encoding="utf-8").splitlines()
            text = " ".join(line for line in lines if line and not line.isdigit() and " --> " not in line)
            self.assertEqual(text, " ".join(e["narration"]["text"] for e in self.trace["events"]))
            self.assertIn("00:05:20,000", srt.read_text(encoding="utf-8"))
            self.assertIn("0.00–10.00s", script.read_text(encoding="utf-8"))

    def test_reject_mismatched_timeline(self):
        with self.assertRaisesRegex(ValueError, "event sequence"):
            attach_timeline(self.board, {"trace_id": self.trace["trace_id"], "events": []})


if __name__ == "__main__":
    unittest.main()
