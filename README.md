# SuperApp Toolkit

A lightweight desktop toolkit built with `customtkinter` that bundles multiple creator utilities into a single app.

## Features
1. Duplicate Cleaner
   - Smart copy detection (e.g., `file (1).ext`), optional size verification, optional subfolder scan
   - Legacy prefix-match mode with configurable prefix length
   - Review results and delete duplicates in bulk
1. Quality Scaler
   - Image upscaling with presets (2x–4x) and fixed resolutions (480p–4K)
   - Video upscaling to fixed resolutions (480p–4K)
   - Batch processing with progress logs
1. Screen Recorder
   - Record a specific monitor at 480p/720p/1080p
   - Optional microphone/system audio capture
   - MP4 output with automatic audio+video muxing
1. Batch Renamer
   - Template-based renaming with tokens `{name}`, `{ext}`, `{n}` (supports `{n:03}` formatting)
   - Regex replace mode
   - Start/step numbering and conflict-aware preview

## Requirements
- Python 3.x
- Dependencies used by the tools (examples):
  - `customtkinter`, `opencv-python`, `moviepy`, `Pillow`, `mss`, `pyaudio`, `numpy`
  - `ffmpeg` must be available on PATH for muxing recordings

## Run
1. Activate your Python environment
1. Install dependencies
1. Launch via `run_app.sh` or `Launch_SuperApp.command`

## Notes
- Some features (screen recording audio muxing) depend on system tools like `ffmpeg`.
- Large video operations can take time; check the log panel for progress.
