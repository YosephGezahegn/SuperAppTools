# SuperApp

A modern desktop toolkit built with Python + customtkinter. Ships as a single window with a sidebar navigator, background task queue, and a growing collection of file/media utilities.

---

## Features

| Tool | What it does |
|---|---|
| **Dashboard** | Quick-action tiles, live task stats, recent folders |
| **Duplicate Cleaner** | Find dupes by smart copy-names, SHA-1 hash, or prefix+size — move to Trash or delete |
| **File Organizer** | Sort files into type-based (or extension-based) subfolders; stats panel shows per-bucket progress |
| **Batch Renamer** | Template, Regex, or Case modes with token chips, undo history, live preview |
| **Quality Scaler** | Bulk resize images and transcode videos; drop-zone input, per-file progress |
| **Image Studio** | Crop, rotate, flip, adjust brightness/contrast/saturation, export |
| **Screen Recorder** | Capture screen + optional audio; live timer, configurable FPS |
| **Backup Snapshot** | Timestamped folder snapshots with optional file copy; manifest preview; one-click restore |
| **Task Queue** | Searchable history of every background job; cancel, rerun, activity log |
| **Settings** | Accent palette, dark/light/system theme, toast toggle |

---

## Getting started

```bash
# 1 — Install dependencies
pip install -r requirements.txt

# 2 — Run
python main_app.py
```

Optional heavy dependencies (screen recorder audio, GPU video ops) are imported lazily — the app starts without them and surfaces a warning only when you use the relevant feature.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl + K` | Open command palette |
| `Cmd/Ctrl + L` | Jump to Task Queue |
| `Cmd/Ctrl + ,` | Open Settings |
| `Cmd/Ctrl + 1` | Go to Dashboard |

---

## Accent colors

Six built-in palettes (Blue, Violet, Emerald, Rose, Amber, Slate) switchable from **Settings → Appearance**. The accent tints sidebar highlights, buttons, and status badges live — no restart needed.

---

## Architecture

```
SuperApp/
├── main_app.py          # Window, sidebar, command palette, keyboard bindings
├── core/
│   ├── theme.py         # Design tokens: spacing, typography, radii, palettes, glyphs
│   ├── ui_helpers.py    # Shared widgets: Card, Toast, FolderPicker, PrimaryButton …
│   └── app_state.py     # Global state, pub/sub, task queue, settings persistence
├── apps/
│   ├── dashboard_frame.py
│   ├── duplicate_cleaner_frame.py
│   ├── file_organizer_frame.py
│   ├── batch_renamer_frame.py
│   ├── quality_scaler_frame.py
│   ├── image_studio_frame.py
│   ├── screen_recorder_frame.py
│   ├── backup_snapshot_frame.py
│   ├── task_queue_frame.py
│   └── settings_frame.py
└── plugins/             # Drop-in plugin frames (see Plugin SDK below)
```

### Plugin SDK

Place a `.py` file in the `plugins/` folder. It must export a `CTkFrame` subclass named `PluginFrame` with the signature:

```python
class PluginFrame(ctk.CTkFrame):
    NAME = "My Plugin"          # sidebar label
    DESCRIPTION = "One liner"   # command palette subtitle

    def __init__(self, master, app_state=None, **kwargs): ...
```

SuperApp discovers it at startup and adds it to the **Plugins** sidebar group automatically.

---

## Requirements

See [`requirements.txt`](requirements.txt). Core runtime needs only `customtkinter` and `Pillow`. All other dependencies are optional and loaded on demand.
