#!/usr/bin/env python3
"""Extract MP3 and produce Japanese draft text plus timestamped review evidence."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from setup_runtime import configure_caches, default_backend, runtime_home

SUSPECT = {"ご視聴ありがとうございました", "おやすみなさい", "お疲れ様でした", "BGM", "me"}


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                             "-of", "json", str(path)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    if not any(s["codec_type"] == "audio" for s in data["streams"]):
        raise ValueError("Source contains no audio stream.")
    duration = float(data["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Source has no positive finite duration.")
    return duration


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive finite number.")
    return number


def nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("Expected a nonnegative finite number.")
    return number


def write_new(path, text):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def review_segments(segments, offset=0, duration=None):
    raw, cleaned, flags = [], [], []
    for segment in segments:
        text = " ".join(segment.get("text", "").split())
        if not text:
            continue
        raw.append(text)
        reasons = []
        if (segment["start"] < 0 or segment["end"] < segment["start"] or
                (duration is not None and segment["end"] > duration + 0.1)):
            reasons.append("timestamp_out_of_bounds")
        if text.rstrip("。.!！") in SUSPECT:
            reasons.append("possible_stock_hallucination")
        tokens = text.split()
        if len(tokens) > 1 and len(set(tokens)) == 1:
            reasons.append("repeated_token")
        if segment.get("no_speech_prob", 0) > 0.6:
            reasons.append("high_no_speech_probability")
        if segment.get("avg_logprob", 0) < -1:
            reasons.append("low_log_probability")
        if cleaned and cleaned[-1] == text:
            reasons.append("adjacent_duplicate_removed_from_draft")
        else:
            cleaned.append(text)
        if reasons:
            flags.append({"start": segment["start"] + offset,
                          "end": segment["end"] + offset, "text": text, "reasons": reasons})
    return raw, cleaned, flags


def infer(audio, args, home):
    configure_caches(home)
    options = dict(language=args.language, condition_on_previous_text=False,
                   no_speech_threshold=0.6, logprob_threshold=-1.0,
                   compression_ratio_threshold=2.4, task="transcribe")
    if args.backend == "mlx":
        import mlx_whisper
        model = args.model or "mlx-community/whisper-large-v3-mlx"
        result = mlx_whisper.transcribe(str(audio), path_or_hf_repo=model, verbose=False, **options)
        segments, language = result["segments"], result.get("language")
    else:
        from faster_whisper import WhisperModel
        model = args.model or "large-v3"
        engine = WhisperModel(model, device=args.device, compute_type=args.compute_type,
                              download_root=str(home / "models"))
        stream, info = engine.transcribe(str(audio), vad_filter=False, **options)
        segments = []
        for segment in stream:
            segments.append({key: getattr(segment, key) for key in
                             ["start", "end", "text", "no_speech_prob", "avg_logprob", "compression_ratio"]})
            print(f"Transcribed through {segment.end:.1f}s", flush=True)
        language = info.language
    return segments, language, model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--backend", choices=["mlx", "faster"], default=default_backend())
    parser.add_argument("--model", help="Backend-compatible local model directory or model identifier")
    parser.add_argument("--language", default="ja")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="cpu",
                        help="faster-whisper only; CPU is the portable default")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper only")
    parser.add_argument("--mp3-only", action="store_true")
    parser.add_argument("--start", type=nonnegative, default=0.0)
    parser.add_argument("--duration", type=positive)
    args = parser.parse_args()
    source = args.input.expanduser().resolve(strict=True)
    if not all(shutil.which(x) for x in ["ffmpeg", "ffprobe"]):
        parser.error("ffmpeg and ffprobe are required.")
    source_duration = probe(source)
    if args.start >= source_duration:
        parser.error("--start is beyond the source duration.")
    duration = min(args.duration or source_duration, source_duration - args.start)
    out = (args.output_dir or source.parent).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    outputs = {name: out / f"{source.stem}{suffix}" for name, suffix in
               {"mp3": ".mp3", "text": ".txt", "raw": ".raw.txt",
                "segments": ".segments.json", "review": ".review.json"}.items()}
    reuse_input = source == outputs["mp3"] and source.suffix.lower() == ".mp3" and not args.start and args.duration is None
    targets = [outputs["mp3"]] if args.mp3_only else list(outputs.values()) + [out / f"{source.stem}.zh.txt"]
    for target in targets:
        if target == outputs["mp3"] and reuse_input:
            continue
        if target.exists() or target.is_symlink():
            parser.error(f"Refusing to overwrite: {target}. Use a fresh --output-dir.")
    if args.model and Path(args.model).expanduser().is_dir():
        args.model = str(Path(args.model).expanduser().resolve())
    if not reuse_input:
        with tempfile.TemporaryDirectory(prefix="rp-transcribe-", dir=out) as temp:
            staging = Path(temp) / "audio.mp3"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                            "-ss", str(args.start), "-i", str(source), "-t", str(duration),
                            "-map", "0:a:0", "-vn", "-codec:a", "libmp3lame", "-q:a", "2", str(staging)], check=True)
            # Exclusive creation also protects against a concurrent run publishing first.
            with outputs["mp3"].open("xb") as dest, staging.open("rb") as src:
                shutil.copyfileobj(src, dest)
    audio_duration = probe(outputs["mp3"])
    if abs(audio_duration - duration) > 0.5:
        raise ValueError(f"Unexpected audio duration: {audio_duration} vs {duration}")
    print(f"MP3: {outputs['mp3']} ({audio_duration:.2f}s)", flush=True)
    if args.mp3_only:
        return
    segments, language, model = infer(outputs["mp3"], args, runtime_home())
    raw, cleaned, flags = review_segments(segments, args.start, duration)
    evidence = [{"start": s["start"] + args.start, "end": s["end"] + args.start,
                 "text": s["text"], "no_speech_prob": s.get("no_speech_prob"),
                 "avg_logprob": s.get("avg_logprob")} for s in segments]
    report = {"source": str(source), "source_duration": source_duration, "start": args.start,
              "duration": duration, "audio_duration": audio_duration, "backend": args.backend,
              "model": model, "language": language, "raw_lines": len(raw), "draft_lines": len(cleaned),
              "untranscribed_tail_seconds": max(0, duration - max((s["end"] for s in segments), default=0)),
              "flags": flags, "status": "needs_agent_review_and_translation"}
    write_new(outputs["raw"], "\n".join(raw) + ("\n" if raw else ""))
    write_new(outputs["segments"], json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    write_new(outputs["review"], json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    write_new(outputs["text"], "\n".join(cleaned) + ("\n" if cleaned else ""))
    print(f"Draft: {outputs['text']}\nReview: {outputs['review']}", flush=True)
    print("Agent review and Chinese translation remain; preserve review files until those finish.")


if __name__ == "__main__":
    main()
