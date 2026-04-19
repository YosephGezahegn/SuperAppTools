"""1-click screen recorder with audio, countdown, pause, and timer."""

from __future__ import annotations

import datetime
import os
import subprocess
import threading
import time
import wave

import customtkinter as ctk
from tkinter import messagebox

from core.theme import (
    COLOR_CARD_BG,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_H2,
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
    DangerButton,
    FolderPicker,
    GhostButton,
    PageHeader,
    PrimaryButton,
    StatusBadge,
    SuccessButton,
)


class ScreenRecorderFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        default_folder = os.path.expanduser("~/Documents/SuperApp/Recordings")
        if self.app_state:
            default_folder = self.app_state.settings.get("recordings_folder", default_folder)

        self.default_folder = ctk.StringVar(value=default_folder)
        self.resolution = ctk.StringVar(value="1080p")
        self.selected_screen = ctk.StringVar()
        self.selected_audio = ctk.StringVar()
        self.countdown_var = ctk.IntVar(value=3)
        self.fps_var = ctk.IntVar(value=20)
        self.audio_level_var = ctk.DoubleVar(value=0)
        self.timer_var = ctk.StringVar(value="00:00:00")

        self.is_recording = False
        self.is_paused = False
        self._record_start = 0.0
        self._paused_time_accum = 0.0
        self._pause_started = 0.0

        self._lazy_initialize()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_ui()
        self._tick_timer()

    def _lazy_initialize(self):
        try:
            import mss

            self.sct = mss.mss()
            self.monitors = self.sct.monitors
        except Exception:  # noqa: BLE001
            self.sct = None
            self.monitors = []

        try:
            import pyaudio

            self.pyaudio_module = pyaudio
            self.audio = pyaudio.PyAudio()
            self.audio_devices = self._get_audio_devices()
        except Exception:  # noqa: BLE001
            self.pyaudio_module = None
            self.audio = None
            self.audio_devices = ["None"]

    def _get_audio_devices(self):
        devices = ["None"]
        if not self.audio:
            return devices
        try:
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if info.get("maxInputChannels") > 0:
                    devices.append(f"{i}: {info.get('name')}")
        except Exception:  # noqa: BLE001
            pass
        return devices

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="Screen Recorder",
            subtitle="Capture a monitor with optional audio. Output is muxed to MP4 with ffmpeg.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        config_card = Card(self, title="Configuration", padding=SPACE_MD)
        config_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = config_card.body
        body.grid_columnconfigure(0, weight=1)

        FolderPicker(body, "Save folder", self.default_folder).grid(
            row=0, column=0, sticky="ew", pady=(0, SPACE_SM)
        )

        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.grid(row=1, column=0, sticky="ew", pady=SPACE_SM)
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        screen_options = []
        if self.monitors:
            screen_options = [
                f"Screen {i} ({self.monitors[i]['width']}x{self.monitors[i]['height']})"
                for i in range(1, len(self.monitors))
            ]
        if not screen_options:
            screen_options = ["Primary"]
        if not self.selected_screen.get():
            self.selected_screen.set(screen_options[0])

        self._dropdown(grid, 0, 0, "Screen", screen_options, self.selected_screen)
        self._dropdown(grid, 0, 1, "Resolution", ["480p", "720p", "1080p"], self.resolution)
        self._dropdown(grid, 0, 2, "Audio input", self.audio_devices, self.selected_audio)
        if self.audio_devices:
            self.selected_audio.set(self.audio_devices[0])
        self._numeric(grid, 0, 3, "FPS", self.fps_var)
        self._numeric(grid, 1, 0, "Countdown (sec)", self.countdown_var)

        # Status card with timer
        status_card = Card(self, title="Preview", padding=SPACE_MD)
        status_card.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = status_card.body
        body.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        self.status_badge = StatusBadge(top, status="Idle")
        self.status_badge.grid(row=0, column=0, sticky="w")
        self.timer_label = ctk.CTkLabel(
            top,
            textvariable=self.timer_var,
            font=ctk.CTkFont(size=FONT_DISPLAY, weight="bold"),
        )
        self.timer_label.grid(row=0, column=1, sticky="e")

        audio_row = ctk.CTkFrame(body, fg_color="transparent")
        audio_row.grid(row=1, column=0, sticky="ew", pady=(SPACE_SM, 0))
        audio_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(audio_row, text=f"{GLYPH['dot']}  Mic level", text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=0, sticky="w", padx=(0, SPACE_SM)
        )
        self.audio_meter = ctk.CTkProgressBar(audio_row, variable=self.audio_level_var, height=8)
        self.audio_meter.grid(row=0, column=1, sticky="ew")
        self.audio_meter.set(0)

        # Buttons
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", pady=(0, SPACE_LG))
        actions.grid_columnconfigure(0, weight=1)

        self.record_btn = SuccessButton(
            actions, text=f"{GLYPH['recorder']}  Start recording", command=self.toggle_recording, height=48, width=240
        )
        self.record_btn.grid(row=0, column=1, padx=SPACE_SM)

        self.pause_btn = GhostButton(
            actions, text=f"{GLYPH['pause']}  Pause", command=self.toggle_pause, width=140, state="disabled"
        )
        self.pause_btn.grid(row=0, column=2, padx=SPACE_SM)

    def _dropdown(self, parent, row, col, label, values, variable):
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.grid(row=row, column=col, sticky="ew", padx=SPACE_SM, pady=SPACE_SM)
        block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(block, text=label, text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkOptionMenu(block, values=values, variable=variable).grid(row=1, column=0, sticky="ew", pady=(2, 0))

    def _numeric(self, parent, row, col, label, variable):
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.grid(row=row, column=col, sticky="ew", padx=SPACE_SM, pady=SPACE_SM)
        block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(block, text=label, text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkEntry(block, textvariable=variable).grid(row=1, column=0, sticky="ew", pady=(2, 0))

    # ------------------------------------------------------------------
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if not self.sct:
            messagebox.showerror("Missing dependency", "mss is required for screen capture. Install it with pip.")
            return
        save_dir = self.default_folder.get()
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not create directory: {exc}")
            return

        res = self.resolution.get()
        target_map = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080)}
        self.target_size = target_map.get(res, (1920, 1080))
        self.fps = max(5, int(self.fps_var.get() or 20))

        try:
            screen_idx = int(self.selected_screen.get().split(" ")[1])
        except Exception:  # noqa: BLE001
            screen_idx = 1
        self.monitor = self.monitors[screen_idx] if self.monitors and screen_idx < len(self.monitors) else None
        if not self.monitor:
            messagebox.showerror("No monitor", "Could not find an available monitor.")
            return

        audio_idx = None
        if self.selected_audio.get() != "None" and ":" in self.selected_audio.get():
            try:
                audio_idx = int(self.selected_audio.get().split(":")[0])
            except Exception:  # noqa: BLE001
                audio_idx = None

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.video_filename = os.path.join(save_dir, f"recording_{timestamp}.avi")
        self.audio_filename = os.path.join(save_dir, f"recording_{timestamp}.wav")
        self.final_filename = os.path.join(save_dir, f"recording_{timestamp}.mp4")

        # Countdown
        countdown = max(0, int(self.countdown_var.get()))
        self.status_badge.set_status("Queued")
        for remaining in range(countdown, 0, -1):
            self.status_badge.configure(text=f"Starts in {remaining}…")
            self.update_idletasks()
            time.sleep(1)

        self.is_recording = True
        self.is_paused = False
        self._record_start = time.time()
        self._paused_time_accum = 0.0

        self.record_btn.configure(
            text=f"{GLYPH['stop']}  Stop recording",
            fg_color=COLOR_DANGER,
            hover_color=("#B91C1C", "#DC2626"),
        )
        self.pause_btn.configure(state="normal", text=f"{GLYPH['pause']}  Pause")
        self.status_badge.set_status("Running")
        if self.app_state:
            self.app_state.log(f"Recording started: {self.final_filename}")

        self.video_thread = threading.Thread(target=self._record_video, args=(self.monitor, self.video_filename), daemon=True)
        self.video_thread.start()

        self.audio_thread = None
        if audio_idx is not None and self.audio:
            self.audio_thread = threading.Thread(
                target=self._record_audio, args=(audio_idx, self.audio_filename), daemon=True
            )
            self.audio_thread.start()

    def stop_recording(self):
        self.is_recording = False
        self.record_btn.configure(text="Processing…", state="disabled")
        self.pause_btn.configure(state="disabled")
        self.status_badge.set_status("Queued")
        threading.Thread(target=self._finish_recording, daemon=True).start()

    def toggle_pause(self):
        if not self.is_recording:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self._pause_started = time.time()
            self.pause_btn.configure(text=f"{GLYPH['play']}  Resume")
            self.status_badge.set_status("Cancelled")
            self.status_badge.configure(text="Paused")
        else:
            self._paused_time_accum += time.time() - self._pause_started
            self.pause_btn.configure(text=f"{GLYPH['pause']}  Pause")
            self.status_badge.set_status("Running")

    def _record_video(self, monitor, filename):
        import cv2  # defer
        import numpy as np

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(filename, fourcc, self.fps, self.target_size)
        delay = 1.0 / self.fps
        while self.is_recording:
            if self.is_paused:
                time.sleep(0.1)
                continue
            start = time.time()
            img = np.array(self.sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            frame = cv2.resize(frame, self.target_size)
            out.write(frame)
            elapsed = time.time() - start
            if delay - elapsed > 0:
                time.sleep(delay - elapsed)
        out.release()

    def _record_audio(self, device_idx, filename):
        import numpy as np

        CHUNK = 1024
        FORMAT = self.pyaudio_module.paInt16
        CHANNELS = 1
        RATE = 44100
        try:
            info = self.audio.get_device_info_by_index(device_idx)
            if int(info.get("maxInputChannels", 0)) >= 2:
                CHANNELS = 2
        except Exception:  # noqa: BLE001
            pass

        try:
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device_idx,
                frames_per_buffer=CHUNK,
            )
            frames = []
            while self.is_recording:
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                    level = min(1.0, float(np.frombuffer(data, dtype=np.int16).std()) / 4000)
                    self.after(0, lambda value=level: self.audio_level_var.set(value))
                except Exception:  # noqa: BLE001
                    pass
            stream.stop_stream()
            stream.close()

            with wave.open(filename, "wb") as waveFile:
                waveFile.setnchannels(CHANNELS)
                waveFile.setsampwidth(self.audio.get_sample_size(FORMAT))
                waveFile.setframerate(RATE)
                waveFile.writeframes(b"".join(frames))
        except Exception as exc:  # noqa: BLE001
            if self.app_state:
                self.app_state.log(f"Audio recording failed: {exc}")

    def _finish_recording(self):
        try:
            if getattr(self, "video_thread", None):
                self.video_thread.join(timeout=10)
            if getattr(self, "audio_thread", None):
                self.audio_thread.join(timeout=10)

            if os.path.exists(self.audio_filename):
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", self.video_filename, "-i", self.audio_filename,
                        "-c:v", "copy", "-c:a", "aac", self.final_filename,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if os.path.exists(self.final_filename):
                    for f in (self.video_filename, self.audio_filename):
                        try:
                            os.remove(f)
                        except OSError:
                            pass
            else:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", self.video_filename, "-c:v", "copy", self.final_filename],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if os.path.exists(self.final_filename):
                    try:
                        os.remove(self.video_filename)
                    except OSError:
                        pass
        except Exception as exc:  # noqa: BLE001
            if self.app_state:
                self.app_state.log(f"Muxing failed: {exc}")
        finally:
            self.after(0, self._reset_gui)

    def _reset_gui(self):
        self.record_btn.configure(
            text=f"{GLYPH['recorder']}  Start recording",
            state="normal",
            fg_color=("#059669", "#10B981"),
            hover_color=("#047857", "#059669"),
        )
        self.pause_btn.configure(text=f"{GLYPH['pause']}  Pause", state="disabled")
        self.audio_meter.set(0)
        self.status_badge.set_status("Completed")
        self.timer_var.set("00:00:00")
        if self.app_state:
            self.app_state.notify(f"Recording saved: {self.final_filename}", level="success")

    # ------------------------------------------------------------------
    def _tick_timer(self):
        if self.is_recording and not self.is_paused:
            elapsed = time.time() - self._record_start - self._paused_time_accum
            hours, rem = divmod(int(max(0, elapsed)), 3600)
            minutes, seconds = divmod(rem, 60)
            self.timer_var.set(f"{hours:02}:{minutes:02}:{seconds:02}")
        self.after(500, self._tick_timer)
