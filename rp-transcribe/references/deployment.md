# Deployment

## Choose A Backend

- Apple Silicon macOS: `setup_runtime.py --backend mlx` (automatic on arm64 Mac).
  Uses `mlx-whisper==0.4.3`, matching the original working environment.
- Linux, Windows, or Intel Mac: `setup_runtime.py --backend faster` installs
  `faster-whisper>=1.2.1,<2`. CPU/int8 is the portable runtime default.
- NVIDIA CUDA: pass `--backend faster --device cuda --compute-type float16` to
  transcription. Install the GPU runtime required by the installed CTranslate2
  version. See the [upstream requirements](https://github.com/SYSTRAN/faster-whisper#gpu).
  CPU large-v3 can be slow. Do not silently reduce model size.

FFmpeg is needed for this workflow even though faster-whisper can decode audio
itself. Install FFmpeg using the platform package manager (for example
`brew install ffmpeg` on macOS or `sudo apt install ffmpeg` on Debian/Ubuntu).
Setup checks prerequisites before installing Python dependencies. It does not
modify system Python or install a system GPU driver. Python 3.11/3.12 avoids many
wheel-availability problems on a fresh machine.

## Execute

After setup, use `.runtime/venv/bin/python` (Windows:
`.runtime\venv\Scripts\python.exe`) relative to the skill directory. With a custom
`RP_TRANSCRIBE_HOME`, use its `venv` instead. Keep that variable set on every run.

```sh
RP_PYTHON="$SKILL_DIR/.runtime/venv/bin/python"
"$RP_PYTHON" "$SKILL_DIR/scripts/transcribe.py" "/path/to/RP16.mp4"
"$RP_PYTHON" "$SKILL_DIR/scripts/transcribe.py" "/path/to/RP16.mp4" --mp3-only
"$RP_PYTHON" "$SKILL_DIR/scripts/transcribe.py" "/path/to/RP16.mp3" \
  --start 600 --duration 90 --output-dir "/path/to/new-check-directory"
```

`SKILL_DIR` must be set to the installed skill directory. Quote paths with spaces.
Check-directory timestamps are offset to the source; keep checks separate from
final output. Input MP3 is reused when it is already at the requested full-length
output path, avoiding an unnecessary re-encode.

For existing installations, run the script with the existing environment's
Python and pass `--model /path/to/compatible/model`. MLX and CTranslate2 weights
are different formats; do not reuse one backend's weights with the other.
The existing runtime and model remain external, and deleting the skill does not
remove them. Large-v3 defaults are `mlx-community/whisper-large-v3-mlx` for MLX
and `large-v3` for faster-whisper. Upstream APIs:
[MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper).

## Failures And Resuming

- `No Metal device available`: some sandboxed/headless sessions cannot access
  the GPU. Use the host's normal permission mechanism to rerun with GPU access.
  Do not reinstall the model or silently fall back to another backend.
- If inference fails after MP3 extraction, rerun with that MP3 as input. Existing
  complete/partial text outputs are refused; inspect them and use a fresh output
  directory for a new attempt. The source and completed MP3 are retained.
- If an interrupted download or installation fails, rerun setup/inference with
  the same runtime home. Report the actual dependency/network error.
- Review JSON records the tail after the last returned segment, not a proven
  speech omission. Silence/music and missed speech require different checks.
- No transcribed text does not mean silence. Use audio analysis or playback
  before making claims about an empty interval.

## Storage And Cleanup

The runtime script directs its subprocess caches (pip, Hugging Face, Torch,
Numba, and XDG) into the selected runtime home without changing shell profiles.
All model/environment content is excluded from Git by `.gitignore`.
For uninstall, first stop active transcription jobs, inspect the exact runtime
directory, then move the skill and its owned runtime to trash. With a custom
runtime path or reused environment, inspect ownership separately. Never remove
an unrelated global cache or a shared model automatically.

Per-recording review artifacts stay beside outputs until the agent completes
review and translation. The agent then removes only explicitly identified run
artifacts. Final files are `<stem>.mp3`, `<stem>.txt`, and `<stem>.zh.txt`; all
other generated review/check files are temporary unless the user asks to keep them.
