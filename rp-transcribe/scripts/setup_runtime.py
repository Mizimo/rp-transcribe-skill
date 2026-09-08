#!/usr/bin/env python3
"""Install one backend into a self-contained, relocatable runtime directory."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import venv


def default_backend():
    return "mlx" if platform.system() == "Darwin" and platform.machine() == "arm64" else "faster"


def runtime_home():
    return Path(os.environ.get("RP_TRANSCRIBE_HOME", Path(__file__).resolve().parents[1] / ".runtime")).expanduser().resolve()


def configure_caches(home):
    # Override only this process and its children; keep downloads in one place.
    for name, folder in {"HF_HOME": "huggingface", "XDG_CACHE_HOME": "cache",
                         "TORCH_HOME": "torch", "NUMBA_CACHE_DIR": "numba",
                         "PIP_CACHE_DIR": "pip"}.items():
        os.environ[name] = str(home / folder)
    os.environ["HF_HUB_CACHE"] = str(home / "huggingface" / "hub")
    os.environ["HF_ASSETS_CACHE"] = str(home / "huggingface" / "assets")
    os.environ["HF_XET_CACHE"] = str(home / "huggingface" / "xet")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["mlx", "faster"], default=default_backend())
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python 3.10+ is required; Python 3.11 or 3.12 is recommended for new installs.")
    if not all(shutil.which(x) for x in ["ffmpeg", "ffprobe"]):
        parser.error("Install ffmpeg and ffprobe first; see references/deployment.md.")
    if args.backend == "mlx" and default_backend() != "mlx":
        parser.error("MLX backend requires an Apple Silicon Mac.")
    home = runtime_home()
    configure_caches(home)
    target = home / "venv"
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    package = "mlx-whisper==0.4.3" if args.backend == "mlx" else "faster-whisper>=1.2.1,<2"
    subprocess.run([str(python), "-m", "pip", "install", package], check=True)
    print(f"Runtime: {home}\nPython: {python}\nBackend: {args.backend}")
    print("Models download on the first run. Existing local models can be passed with --model.")


if __name__ == "__main__":
    main()
