---
name: rp-transcribe
description: Convert local RP lesson videos or audio into MP3, a reviewed Japanese transcript, and a Traditional Chinese translation. Use for RP media processing or the same workflow on other local recordings.
---

# RP Transcribe

For a bare RP media path in an established RP workflow, produce MP3, reviewed
Japanese text, and Traditional Chinese text beside the input. Honor narrower
requests (MP3 only, transcript only, another language or output directory).
Locate a moved source before claiming it is missing. Do not fetch a Drive URL
or infer browser credentials from this local-file workflow.

## Runtime

Resolve this skill's directory as `SKILL_DIR`; never embed a particular user's
home directory. Read [deployment.md](references/deployment.md) for installation,
backend choice, reusing existing models, or GPU failures.

Use an existing compatible Python environment and model when available. Otherwise
run `python3 "$SKILL_DIR/scripts/setup_runtime.py"`. The default runtime is
`$SKILL_DIR/.runtime`; `RP_TRANSCRIBE_HOME` relocates all runtime-owned caches.
Use large-v3 by default. Do not silently replace it with turbo or a smaller model.

## Run

```sh
"$RP_PYTHON" "$SKILL_DIR/scripts/transcribe.py" "/absolute/path/RP16.mp4"
```

`RP_PYTHON` is the installed runtime's Python or an existing compatible Python.
The helper extracts MP3 at VBR quality 2 and creates `.txt`, `.raw.txt`,
`.segments.json`, and `.review.json`. Chinese translation is performed by the
agent after review, not by Whisper's English-only translation task.
`--mp3-only` skips inference. `--output-dir` changes the destination.
Existing outputs are refused; inspect them and choose a fresh directory for
rechecks. Never overwrite an edited transcript during a retry.

## Review And Translate

1. Read the entire transcript and review report. Inspect flagged segments using
   their start/end times. Raw segments remain in the JSON, including low-confidence
   speech. Out-of-bounds model timestamps are preserved and flagged, not treated
   as proof that audio was processed. The script removes only adjacent duplicate
   lines from the draft.
2. Check questionable music/quiet intervals and abrupt transitions. Use
   `--start SECONDS --duration SECONDS --output-dir CHECK_DIR` to independently
   transcribe a suspect interval. Segment timestamps refer to the original source.
   Prefer a newly created temporary directory for each check.
3. A progress bar ending below 100% is a reason to inspect the tail, not proof of
   truncation. An empty tail transcript proves neither silence nor completeness.
   Check audio levels or listen where needed. Do not claim the whole transcript
   is complete solely because a tail recheck is empty or reaches 100%.
4. Correct proper nouns only with sufficient evidence from the recording, visible
   slides, or authoritative references. Replay/retranscribe uncertain phrases;
   mark unresolved wording instead of inventing a plausible correction. Stock
   closings, `BGM`, and repeated tokens are review candidates, not unconditional
   deletion rules. Preserve real spoken closings and repeated speech.
5. Write `<stem>.zh.txt` in Traditional Chinese from the reviewed Japanese draft.
   Preserve meaning, order, omissions/uncertainty markers, and names. Do not add
   outside facts or manufacture speech/lyrics in music-only passages. A request
   for a form impression is separate from the transcript; do not submit a form
   unless asked.
6. Verify the MP3 duration (allow encoder padding), both text files, and the
   boundaries of checked excerpts. Report actual checks and remaining uncertainty.

## Cleanup And Delivery

After review and translation succeed, remove only this run's `.raw.txt`,
`.segments.json`, `.review.json`, and explicitly identified check files, unless
the user wants audit artifacts. Retain these on failure to support resuming.
Use exact paths from the current run; never use broad deletion globs or delete
the source, final MP3/text, shared runtime, or cached model as temporary output.

Deliver clickable absolute links to MP3, Japanese text, and Chinese text, along
with a short factual verification/cleanup note. Do not claim audio was listened
to when only automated recognition was used. Keep recordings and transcripts
out of the skill's Git repository.
