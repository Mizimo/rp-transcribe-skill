# RP Transcribe Skill

Portable skill for local lesson recordings: MP3 extraction, Japanese large-v3
transcription, evidence-based review, Traditional Chinese translation, and cleanup.
The scripts handle audio and recognition; the agent performs review and translation.

## Install On Another Machine

Authenticate GitHub first because this repository is private. Python 3.11 or 3.12
and `ffmpeg` / `ffprobe` on PATH are recommended.

```sh
gh repo clone Mizimo/rp-transcribe-skill
mkdir -p "$HOME/.codex/skills"
cp -R rp-transcribe-skill/rp-transcribe "$HOME/.codex/skills/rp-transcribe"
python3 "$HOME/.codex/skills/rp-transcribe/scripts/setup_runtime.py"
```

Use a fresh destination; the copy command is for first installation. For another
agent, copy the same `rp-transcribe/` directory into that agent's skill directory.
On Windows, use PowerShell `Copy-Item -Recurse` and the relevant agent's directory.
Start a new agent session and invoke `$rp-transcribe /absolute/path/RP16.mp4`.

The default runtime, models, and caches live together under `rp-transcribe/.runtime`.
Set `RP_TRANSCRIBE_HOME` before both setup and execution to move that storage.
Models download on first inference; they are several GB, and backend dependencies
also need disk space. Existing compatible models can be reused with `--model`.
Do not copy a virtual environment between operating systems or move it after
creation; rebuild the environment at its new path.

See [deployment details](rp-transcribe/references/deployment.md) for backend options,
existing-runtime usage, storage cleanup, and GPU troubleshooting.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

Tests exercise real FFmpeg extraction, no-overwrite behavior, excerpt timestamps,
review flags, failure recovery, and backend adapters with mocked inference. They
do not download models. Real inference must be verified on the target hardware.
Recordings, transcripts, models, environments, and credentials are not included.
