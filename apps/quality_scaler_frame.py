"""Image/video upscale, compression, and trim utility."""

from __future__ import annotations

import os
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.theme import (
    COLOR_CARD_BG,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_H3,
    FONT_SMALL,
    GLYPH,
    RADIUS,
    RADIUS_SM,
    SPACE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from core.ui_helpers import (
    Card,
    FileDropList,
    GhostButton,
    PageHeader,
    PrimaryButton,
    StatusBadge,
    SuccessButton,
    human_size,
)


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg")

RESOLUTION_PRESETS: Dict[str, object] = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2K": (2560, 1440),
    "4K": (3840, 2160),
    "Scale ×2": "2x",
    "Scale ×3": "3x",
    "Scale ×4": "4x",
}

COMPRESSION_PRESETS = ["Web", "Social", "Archive"]
IMAGE_QUALITY = {"Web": 60, "Social": 75, "Archive": 88}
VIDEO_BITRATE = {"Web": "1200k", "Social": "2400k", "Archive": "4500k"}


class QualityScalerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.mode_var = ctk.StringVar(value="Image")
        self.operation_var = ctk.StringVar(value="Upscale")
        self.image_resolution_var = ctk.StringVar(value="Scale ×2")
        self.video_resolution_var = ctk.StringVar(value="1080p")
        self.image_format_var = ctk.StringVar(value=self._default_image_format())
        self.video_format_var = ctk.StringVar(value=self._default_video_format())
        self.compression_var = ctk.StringVar(value="Web")
        self.trim_start_var = ctk.StringVar(value="0")
        self.trim_end_var = ctk.StringVar(value="")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_ui()

    def _default_image_format(self):
        if self.app_state:
            return self.app_state.settings.get("preferred_image_format", "png")
        return "png"

    def _default_video_format(self):
        if self.app_state:
            return self.app_state.settings.get("preferred_video_format", "mp4")
        return "mp4"

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="Quality + Compressor",
            subtitle="Upscale, compress, and trim images/videos. Runs in the background task queue.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        # Mode + settings
        settings_card = Card(self, title="What should we do?", padding=SPACE_MD)
        settings_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = settings_card.body
        body.grid_columnconfigure((0, 1), weight=1)

        mode_col = ctk.CTkFrame(body, fg_color="transparent")
        mode_col.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_SM))
        mode_col.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(mode_col, text="Media type", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkSegmentedButton(
            mode_col, values=["Image", "Video"], variable=self.mode_var, command=self._on_mode_changed
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        op_col = ctk.CTkFrame(body, fg_color="transparent")
        op_col.grid(row=0, column=1, sticky="ew", padx=(SPACE_SM, 0))
        op_col.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(op_col, text="Operation", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkSegmentedButton(
            op_col,
            values=["Upscale", "Compress", "Trim"],
            variable=self.operation_var,
            command=self._on_operation_changed,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.params_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.params_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(SPACE_MD, 0))
        self.params_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._render_params()

        # Files + log
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        self.drop_list = FileDropList(
            content,
            on_add=self._add_files,
            on_add_folder=self._add_folder,
            on_clear=lambda: self.drop_list.clear(),
            empty_hint="Add media files to process.",
        )
        self.drop_list.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))

        log_card = Card(content, title="Activity", padding=SPACE_MD)
        log_card.grid(row=0, column=1, sticky="nsew", padx=(SPACE_SM, 0))
        log_card.body.grid_rowconfigure(1, weight=1)
        self.status = StatusBadge(log_card.body, status="Idle")
        self.status.grid(row=0, column=0, sticky="w")
        self.log_box = ctk.CTkTextbox(log_card.body, corner_radius=RADIUS_SM)
        self.log_box.grid(row=1, column=0, sticky="nsew", pady=(SPACE_SM, 0))
        self.log_box.configure(state="disabled")

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(SPACE_MD, 0))
        footer.grid_columnconfigure(0, weight=1)
        SuccessButton(footer, text=f"{GLYPH['play']}  Start", command=self.start_processing, width=160).grid(
            row=0, column=0, sticky="e"
        )

    # ------------------------------------------------------------------
    def _render_params(self):
        for child in self.params_frame.winfo_children():
            child.destroy()
        mode = self.mode_var.get()
        op = self.operation_var.get()

        if mode == "Image":
            self._dropdown(self.params_frame, 0, 0, "Resolution", list(RESOLUTION_PRESETS.keys()), self.image_resolution_var)
            self._dropdown(self.params_frame, 0, 1, "Output format", ["png", "jpg", "webp", "bmp"], self.image_format_var)
            if op == "Compress":
                self._dropdown(self.params_frame, 0, 2, "Compression preset", COMPRESSION_PRESETS, self.compression_var)
            return

        # Video
        self._dropdown(self.params_frame, 0, 0, "Resolution", ["480p", "720p", "1080p", "2K", "4K"], self.video_resolution_var)
        self._dropdown(self.params_frame, 0, 1, "Output format", ["mp4", "mov", "webm"], self.video_format_var)
        if op == "Compress":
            self._dropdown(self.params_frame, 0, 2, "Compression preset", COMPRESSION_PRESETS, self.compression_var)
        if op == "Trim":
            self._text_entry(self.params_frame, 1, 0, "Trim start (sec)", self.trim_start_var)
            self._text_entry(self.params_frame, 1, 1, "Trim end (sec)", self.trim_end_var, placeholder="leave blank for end")

    def _dropdown(self, parent, row, col, label, values, variable):
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.grid(row=row, column=col, sticky="ew", padx=SPACE_SM, pady=SPACE_SM)
        block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(block, text=label, text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkOptionMenu(block, values=values, variable=variable).grid(row=1, column=0, sticky="ew", pady=(2, 0))

    def _text_entry(self, parent, row, col, label, variable, placeholder=""):
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.grid(row=row, column=col, sticky="ew", padx=SPACE_SM, pady=SPACE_SM)
        block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(block, text=label, text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkEntry(block, textvariable=variable, placeholder_text=placeholder).grid(
            row=1, column=0, sticky="ew", pady=(2, 0)
        )

    def _on_mode_changed(self, _value):
        self._render_params()

    def _on_operation_changed(self, _value):
        self._render_params()

    # ------------------------------------------------------------------
    def _add_files(self):
        paths = filedialog.askopenfilenames()
        if paths:
            self.drop_list.add(paths)

    def _add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        accepted = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + AUDIO_EXTENSIONS
        entries = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in accepted:
                entries.append(path)
        self.drop_list.add(entries)

    def log(self, msg: str):
        entry = f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n"
        self.after(0, lambda text=entry: self._append_log(text))
        if self.app_state:
            self.app_state.log(msg)

    def _append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def start_processing(self):
        inputs = self.drop_list.paths()
        if not inputs:
            messagebox.showerror("Error", "Add at least one file first.")
            return
        initial_dir = self.app_state.settings.get("exports_folder") if self.app_state else None
        output_dir = filedialog.askdirectory(initialdir=initial_dir)
        if not output_dir:
            return
        os.makedirs(output_dir, exist_ok=True)

        self.status.set_status("Running")
        if self.app_state:
            self.app_state.submit_task(
                "Media Processor",
                f"{self.operation_var.get()} {len(inputs)} {self.mode_var.get().lower()} file(s)",
                self._process_loop,
                files=list(inputs),
                output_dir=output_dir,
            )
            self.log(f"Queued {self.operation_var.get().lower()} for {len(inputs)} file(s).")
        else:
            threading.Thread(
                target=self._process_loop, kwargs={"files": list(inputs), "output_dir": output_dir}, daemon=True
            ).start()

    def _process_loop(self, files, output_dir):
        mode = self.mode_var.get()
        operation = self.operation_var.get()
        errors = 0
        for path in files:
            self.log(f"Processing {os.path.basename(path)}…")
            try:
                if mode == "Image":
                    if operation == "Compress":
                        self._compress_image(path, output_dir)
                    else:
                        self._upscale_image(path, output_dir)
                else:
                    ext = os.path.splitext(path)[1].lower()
                    if operation == "Compress":
                        self._compress_video(path, output_dir)
                    elif operation == "Trim":
                        if ext in VIDEO_EXTENSIONS:
                            self._trim_video(path, output_dir)
                        elif ext in AUDIO_EXTENSIONS:
                            self._trim_audio(path, output_dir)
                        else:
                            raise ValueError("Trim only supports video and common audio files.")
                    else:
                        self._upscale_video(path, output_dir)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                self.log(f"Error on {os.path.basename(path)}: {exc}")

        self.after(0, lambda: self.status.set_status("Failed" if errors else "Completed"))
        summary = f"Finished {operation.lower()} — {len(files) - errors}/{len(files)} succeeded."
        self.log(summary)
        return summary

    # ------------------------------------------------------------------
    def _upscale_image(self, path, output_dir):
        import cv2  # defer optional import

        img = cv2.imread(path)
        if img is None:
            raise ValueError("Could not read image.")
        preset = RESOLUTION_PRESETS[self.image_resolution_var.get()]
        if isinstance(preset, str) and preset.endswith("x"):
            factor = int(preset[:-1])
            target = (img.shape[1] * factor, img.shape[0] * factor)
        else:
            target = preset
        resized = cv2.resize(img, target, interpolation=cv2.INTER_LANCZOS4)
        fmt = self.image_format_var.get()
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"up_{base}.{fmt}")
        cv2.imwrite(out, resized)
        self.log(self._size_summary(path, out))

    def _compress_image(self, path, output_dir):
        from PIL import Image  # defer

        quality = IMAGE_QUALITY[self.compression_var.get()]
        fmt = self.image_format_var.get()
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"cmp_{base}.{fmt}")
        with Image.open(path) as img:
            working = img.convert("RGB") if fmt in ("jpg", "jpeg", "webp") else img.copy()
            save_kwargs = {}
            if fmt in ("jpg", "jpeg", "webp"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
            working.save(out, "JPEG" if fmt in ("jpg", "jpeg") else fmt.upper(), **save_kwargs)
        self.log(self._size_summary(path, out))

    def _upscale_video(self, path, output_dir):
        from moviepy import VideoFileClip  # defer

        preset = RESOLUTION_PRESETS[self.video_resolution_var.get()]
        fmt = self.video_format_var.get()
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"up_{base}.{fmt}")
        clip = VideoFileClip(path)
        height = preset[1] if isinstance(preset, tuple) else int(clip.h * int(preset[:-1]))
        resized = clip.resized(height=height)
        resized.write_videofile(out, codec="libx264", logger=None)
        clip.close()
        self.log(self._size_summary(path, out))

    def _compress_video(self, path, output_dir):
        from moviepy import VideoFileClip  # defer

        bitrate = VIDEO_BITRATE[self.compression_var.get()]
        fmt = self.video_format_var.get()
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"cmp_{base}.{fmt}")
        clip = VideoFileClip(path)
        clip.write_videofile(out, codec="libx264", bitrate=bitrate, audio_codec="aac", logger=None)
        clip.close()
        self.log(self._size_summary(path, out))

    def _trim_video(self, path, output_dir):
        from moviepy import VideoFileClip

        clip = VideoFileClip(path)
        start = max(0.0, float(self.trim_start_var.get() or "0"))
        end = float(self.trim_end_var.get()) if self.trim_end_var.get().strip() else clip.duration
        fmt = self.video_format_var.get()
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"trim_{base}.{fmt}")
        clipped = clip.subclipped(start, min(end, clip.duration))
        clipped.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        clipped.close()
        clip.close()
        self.log(self._size_summary(path, out))

    def _trim_audio(self, path, output_dir):
        from moviepy import AudioFileClip

        clip = AudioFileClip(path)
        start = max(0.0, float(self.trim_start_var.get() or "0"))
        end = float(self.trim_end_var.get()) if self.trim_end_var.get().strip() else clip.duration
        ext = os.path.splitext(path)[1].lower()
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"trim_{base}{ext}")
        clipped = clip.subclipped(start, min(end, clip.duration))
        clipped.write_audiofile(out, logger=None)
        clipped.close()
        clip.close()
        self.log(self._size_summary(path, out))

    # ------------------------------------------------------------------
    def _size_summary(self, original, output):
        if not os.path.exists(output):
            return f"Saved {os.path.basename(output)}"
        before = os.path.getsize(original)
        after = os.path.getsize(output)
        delta = after - before
        sign = "+" if delta >= 0 else ""
        return (
            f"Saved {os.path.basename(output)}  |  "
            f"{human_size(before)} → {human_size(after)}  ({sign}{human_size(abs(delta))})"
        )
