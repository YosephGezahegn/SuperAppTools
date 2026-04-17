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
   - Image and video compression presets for `Web`, `Social`, and `Archive`
   - Quick video/audio trim support with start/end times
   - Batch processing with progress logs and output size summaries
1. Screen Recorder
   - Record a specific monitor at 480p/720p/1080p
   - Optional microphone/system audio capture
   - MP4 output with automatic audio+video muxing
   - Countdown start, pause/resume, and mic level meter
1. Batch Renamer
   - Template-based renaming with tokens `{name}`, `{ext}`, `{n}` (supports `{n:03}` formatting)
   - Regex replace mode
   - Start/step numbering, folder import, and conflict-aware preview
1. Image Studio
   - Image viewer with list, thumbnails, large view, and full screen
   - One-click full-screen capture import
   - Zoom and pan interactions
   - Basic edits (rotate, flip, brightness, contrast, blur) and export to multiple formats (including PDF)
   - Download images from URLs
   - View, edit, and remove metadata (JPEG editing/removal works best with `piexif`)
   - OCR text extraction with copy/save actions (requires `pytesseract`)
1. File Organizer
   - Sort files by type, date, or size
   - Move or copy into organized folder structures
   - Dry-run preview before changes
1. Backup Snapshot
   - Create folder snapshots with manifest files
   - Optionally copy source files into the snapshot store for restore
   - Restore snapshots into a chosen folder
1. Global Settings
   - Default output folders, preferred formats, theme, and worker settings
1. Task Queue + History
   - Background job queue for long-running tools
   - Re-run completed tasks and inspect results/errors
1. Notifications + Logs
   - Shared status bar notifications
   - Centralized rolling logs in the task history view
1. Plugin System
   - Drop new Python plugins into the `plugins/` folder
   - Register tools without changing the main app shell

## Requirements
- Python 3.x
- Dependencies used by the tools (examples):
  - `customtkinter`, `opencv-python`, `moviepy`, `Pillow`, `mss`, `pyaudio`, `numpy`, `requests`
  - Optional: `pytesseract`, `piexif`
  - `ffmpeg` must be available on PATH for muxing recordings

## Run
1. Activate your Python environment
1. Install dependencies
1. Launch via `run_app.sh` or `Launch_SuperApp.command`

## Notes
- Some features (screen recording audio muxing) depend on system tools like `ffmpeg`.
- Large video operations can take time; check the log panel for progress.
