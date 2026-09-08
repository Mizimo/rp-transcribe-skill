import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "rp-transcribe" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import transcribe as workflow


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rp-skill-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "RP sample.v1.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=3", "-c:a", "aac", str(self.source)], check=True)

    def run_cli(self, *args):
        with patch.object(sys, "argv", ["transcribe.py", str(self.source), *map(str, args)]):
            workflow.main()

    def test_conversion_preserves_source_and_refuses_overwrite(self):
        original = self.source.read_bytes()
        self.run_cli("--mp3-only")
        mp3 = self.source.with_suffix(".mp3")
        self.assertAlmostEqual(workflow.probe(mp3), 3, delta=0.1)
        audio = mp3.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_cli("--mp3-only")
        self.assertEqual(mp3.read_bytes(), audio)
        self.assertEqual(self.source.read_bytes(), original)

    def test_review_preserves_possible_real_closing_and_flags_low_confidence(self):
        segments = [{"start": 0, "end": 1, "text": "ご視聴ありがとうございました。", "no_speech_prob": 0.9},
                    {"start": 1, "end": 2, "text": "ご視聴ありがとうございました。"}]
        raw, draft, flags = workflow.review_segments(segments, 60)
        self.assertEqual(len(raw), 2)
        self.assertEqual(len(draft), 1)
        self.assertEqual(flags[0]["start"], 60)
        self.assertIn("high_no_speech_probability", flags[0]["reasons"])
        self.assertIn("adjacent_duplicate_removed_from_draft", flags[1]["reasons"])

    def test_excerpt_evidence_offsets_and_no_automatic_translation(self):
        segments = [{"start": 0.1, "end": 0.8, "text": "音楽です。"}]
        with patch.object(workflow, "infer", return_value=(segments, "ja", "test-model")):
            self.run_cli("--start", "1", "--duration", "1")
        prefix = self.root / self.source.stem
        evidence = json.loads(Path(str(prefix) + ".segments.json").read_text())
        report = json.loads(Path(str(prefix) + ".review.json").read_text())
        self.assertAlmostEqual(evidence[0]["start"], 1.1)
        self.assertAlmostEqual(report["untranscribed_tail_seconds"], 0.2)
        self.assertFalse(Path(str(prefix) + ".zh.txt").exists())

    def test_existing_translation_blocks_work_before_extraction(self):
        self.source.with_suffix(".zh.txt").write_text("reviewed translation")
        with self.assertRaises(SystemExit):
            self.run_cli()
        self.assertFalse(self.source.with_suffix(".mp3").exists())

    def test_inference_failure_keeps_mp3_for_retry(self):
        with patch.object(workflow, "infer", side_effect=RuntimeError("GPU unavailable")):
            with self.assertRaises(RuntimeError):
                self.run_cli()
        audio = self.source.with_suffix(".mp3")
        before = audio.read_bytes()
        self.source = audio
        with patch.object(workflow, "infer", return_value=([], "ja", "test-model")):
            self.run_cli()
        self.assertEqual(before, audio.read_bytes())
        report = json.loads(audio.with_suffix(".review.json").read_text())
        self.assertGreater(report["untranscribed_tail_seconds"], 2.9)

    def test_invalid_excerpt_produces_no_output(self):
        with self.assertRaises(SystemExit):
            self.run_cli("--start", "9")
        self.assertFalse(self.source.with_suffix(".mp3").exists())

    def test_model_timestamp_overrun_is_preserved_and_flagged(self):
        segments = [{"start": 30, "end": 59.98, "text": "ご視聴ありがとうございました。"}]
        raw, draft, flags = workflow.review_segments(segments, offset=16, duration=45)
        self.assertIn("timestamp_out_of_bounds", flags[0]["reasons"])
        self.assertAlmostEqual(flags[0]["end"], 75.98)
        self.assertEqual(raw, draft)

    def test_faster_adapter_consumes_lazy_segments(self):
        segment = types.SimpleNamespace(start=0, end=1, text="speech", no_speech_prob=0,
                                        avg_logprob=-0.1, compression_ratio=1)
        class Engine:
            def __init__(self, *args, **kwargs):
                pass
            def transcribe(self, *args, **kwargs):
                return iter([segment]), types.SimpleNamespace(language="ja")
        args = types.SimpleNamespace(backend="faster", model=None, language="ja", device="cpu", compute_type="int8")
        with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=Engine)}), patch.dict("os.environ"):
            result, language, model = workflow.infer(self.source, args, self.root)
        self.assertEqual(result[0]["text"], "speech")
        self.assertEqual(language, "ja")
        self.assertEqual(model, "large-v3")


if __name__ == "__main__":
    unittest.main()
