import os
import threading
from datetime import datetime
import cv2
import customtkinter as ctk
from PIL import Image
from moviepy import AudioFileClip, VideoFileClip
from tkinter import filedialog, messagebox

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv')
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')

RESOLUTION_PRESETS = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2K": (2560, 1440),
    "4K": (3840, 2160),
    "Scale X2": "2x",
    "Scale X3": "3x",
    "Scale X4": "4x"
}

class QualityScalerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state

        # Variables
        self.input_files = []
        self.output_dir = ""
        self.processing = False
        self.stop_requested = False
        self.operation_var = ctk.StringVar(value="Upscale")
        self.compression_preset = ctk.StringVar(value="Web")
        self.trim_start_var = ctk.StringVar(value="0")
        self.trim_end_var = ctk.StringVar(value="")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.create_widgets()

    def create_widgets(self):
        # Mode Toggler
        self.mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.mode_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        
        self.mode_var = ctk.StringVar(value="Image")
        self.mode_switch = ctk.CTkSegmentedButton(self.mode_frame, values=["Image", "Video"], 
                                                 variable=self.mode_var, command=self.toggle_mode)
        self.mode_switch.pack(pady=10, padx=10, fill="x")

        self.operation_switch = ctk.CTkSegmentedButton(
            self.mode_frame,
            values=["Upscale", "Compress", "Trim"],
            variable=self.operation_var,
            command=lambda _v: self.toggle_mode(self.mode_var.get()),
        )
        self.operation_switch.pack(pady=(0, 10), padx=10, fill="x")

        # Settings
        self.settings_container = ctk.CTkFrame(self)
        self.settings_container.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.settings_container.grid_columnconfigure((0,1,2,3), weight=1)

        self.img_settings_frame = ctk.CTkFrame(self.settings_container, fg_color="transparent")
        self.img_settings_frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        self.img_settings_frame.grid_columnconfigure((0,1,2,3), weight=1)

        ctk.CTkLabel(self.img_settings_frame, text="Image Res:").grid(row=0, column=0, padx=5, pady=10)
        self.img_res_option = ctk.CTkOptionMenu(self.img_settings_frame, values=list(RESOLUTION_PRESETS.keys()))
        self.img_res_option.grid(row=0, column=1, padx=5, pady=10)
        self.img_res_option.set("Scale X2")

        ctk.CTkLabel(self.img_settings_frame, text="Format:").grid(row=0, column=2, padx=5, pady=10)
        self.img_format_option = ctk.CTkOptionMenu(self.img_settings_frame, values=["png", "jpg", "webp", "bmp"])
        self.img_format_option.grid(row=0, column=3, padx=5, pady=10)
        self.img_format_option.set(self._default_image_format())

        ctk.CTkLabel(self.img_settings_frame, text="Compression Preset:").grid(row=1, column=0, padx=5, pady=10)
        self.img_compress_option = ctk.CTkOptionMenu(
            self.img_settings_frame, values=["Web", "Social", "Archive"], variable=self.compression_preset
        )
        self.img_compress_option.grid(row=1, column=1, padx=5, pady=10)

        self.vid_settings_frame = ctk.CTkFrame(self.settings_container, fg_color="transparent")
        ctk.CTkLabel(self.vid_settings_frame, text="Video Res:").grid(row=0, column=0, padx=5, pady=10)
        self.vid_res_option = ctk.CTkOptionMenu(self.vid_settings_frame, values=[k for k in RESOLUTION_PRESETS.keys() if "Scale" not in k])
        self.vid_res_option.grid(row=0, column=1, padx=5, pady=10)
        self.vid_res_option.set("1080p")

        ctk.CTkLabel(self.vid_settings_frame, text="Compression Preset:").grid(row=0, column=2, padx=5, pady=10)
        self.vid_compress_option = ctk.CTkOptionMenu(
            self.vid_settings_frame, values=["Web", "Social", "Archive"], variable=self.compression_preset
        )
        self.vid_compress_option.grid(row=0, column=3, padx=5, pady=10)

        ctk.CTkLabel(self.vid_settings_frame, text="Trim Start (sec):").grid(row=1, column=0, padx=5, pady=10)
        ctk.CTkEntry(self.vid_settings_frame, textvariable=self.trim_start_var).grid(row=1, column=1, padx=5, pady=10)
        ctk.CTkLabel(self.vid_settings_frame, text="Trim End (sec):").grid(row=1, column=2, padx=5, pady=10)
        ctk.CTkEntry(self.vid_settings_frame, textvariable=self.trim_end_var).grid(row=1, column=3, padx=5, pady=10)

        # File List & Logs
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=2)
        self.content_frame.grid_columnconfigure(1, weight=3)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.file_list = ctk.CTkTextbox(self.content_frame)
        self.file_list.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.file_list.insert("0.0", "--- Input Files ---\n")

        self.log_box = ctk.CTkTextbox(self.content_frame)
        self.log_box.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.log_box.insert("0.0", "System Log Started...\n")

        # Footer Actions
        self.footer = ctk.CTkFrame(self)
        self.footer.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        
        self.add_btn = ctk.CTkButton(self.footer, text="Add Files", command=self.add_files)
        self.add_btn.pack(side="left", padx=10, pady=10)
        
        self.start_btn = ctk.CTkButton(self.footer, text="START", font=ctk.CTkFont(weight="bold"), 
                                      fg_color="green", command=self.start_processing)
        self.start_btn.pack(side="right", padx=10, pady=10)

        self.toggle_mode("Image")

    def _default_image_format(self):
        if self.app_state:
            return self.app_state.settings.get("preferred_image_format", "png")
        return "png"

    def toggle_mode(self, mode):
        if mode == "Image":
            self.vid_settings_frame.grid_forget()
            self.img_settings_frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        else:
            self.img_settings_frame.grid_forget()
            self.vid_settings_frame.grid(row=0, column=0, columnspan=4, sticky="ew")

    def log(self, msg):
        entry = f"{datetime.now().strftime('%H:%M:%S')} {msg}\n"
        self.after(0, lambda text=entry: self._append_log(text))
        if self.app_state:
            self.app_state.log(msg)

    def _append_log(self, text):
        self.log_box.insert("end", text)
        self.log_box.see("end")

    def add_files(self):
        files = filedialog.askopenfilenames()
        for f in files:
            if f not in self.input_files:
                self.input_files.append(f)
                self.file_list.insert("end", f"{os.path.basename(f)}\n")

    def start_processing(self):
        if not self.input_files: return
        initial_dir = self.app_state.settings.get("exports_folder") if self.app_state else None
        self.output_dir = filedialog.askdirectory(initialdir=initial_dir)
        if not self.output_dir: return

        if self.app_state:
            self.app_state.submit_task(
                "Media Processor",
                f"{self.operation_var.get()} {self.mode_var.get().lower()} files",
                self.process_loop,
                output_dir=self.output_dir,
            )
            self.log(f"Queued {self.operation_var.get().lower()} job for {len(self.input_files)} files.")
        else:
            self.processing = True
            self.start_btn.configure(text="STOP", fg_color="red")
            threading.Thread(target=self.process_loop, kwargs={"output_dir": self.output_dir}, daemon=True).start()

    def process_loop(self, output_dir=None):
        mode = self.mode_var.get()
        operation = self.operation_var.get()
        res = RESOLUTION_PRESETS[self.img_res_option.get() if mode == "Image" else self.vid_res_option.get()]
        fmt = self.img_format_option.get() if mode == "Image" else self._default_video_format()
        output_dir = output_dir or self.output_dir

        for file_path in self.input_files:
            if not self.processing and not self.app_state:
                break
            self.log(f"Processing {os.path.basename(file_path)}...")
            try:
                if mode == "Image":
                    if operation == "Compress":
                        self.compress_image(file_path, fmt, output_dir)
                    else:
                        self.process_image(file_path, res, fmt, output_dir)
                else:
                    if operation == "Compress":
                        self.compress_video(file_path, output_dir)
                    elif operation == "Trim":
                        self.trim_media(file_path, output_dir)
                    else:
                        self.process_video(file_path, res, self._default_video_format(), output_dir)
            except Exception as e:
                self.log(f"Error: {e}")

        self.processing = False
        if not self.app_state:
            self.start_btn.configure(text="START", fg_color="green")
            messagebox.showinfo("Done", "Processing complete")
        return "Processing complete"

    def _default_video_format(self):
        if self.app_state:
            return self.app_state.settings.get("preferred_video_format", "mp4")
        return "mp4"

    def process_image(self, path, res, fmt, output_dir):
        img = cv2.imread(path)
        if isinstance(res, str) and res.endswith("x"):
            f = int(res[:-1])
            target = (img.shape[1]*f, img.shape[0]*f)
        else: target = res
        resized = cv2.resize(img, target, interpolation=cv2.INTER_LANCZOS4)
        base_name = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"up_{base_name}.{fmt}")
        cv2.imwrite(out, resized)
        self.log(self._size_summary(path, out))

    def compress_image(self, path, fmt, output_dir):
        preset_quality = {"Web": 60, "Social": 75, "Archive": 88}[self.compression_preset.get()]
        base_name = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"cmp_{base_name}.{fmt}")
        with Image.open(path) as img:
            working = img.convert("RGB") if fmt in ("jpg", "jpeg", "webp") else img.copy()
            save_kwargs = {}
            if fmt in ("jpg", "jpeg", "webp"):
                save_kwargs["quality"] = preset_quality
                save_kwargs["optimize"] = True
            working.save(out, "JPEG" if fmt in ("jpg", "jpeg") else fmt.upper(), **save_kwargs)
        self.log(self._size_summary(path, out))

    def process_video(self, path, res, fmt, output_dir):
        clip = VideoFileClip(path)
        h = res[1] if isinstance(res, tuple) else clip.h * int(res[:-1])
        resized = clip.resized(height=h)
        base_name = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"up_{base_name}.{fmt}")
        resized.write_videofile(out, codec="libx264", logger=None)
        clip.close()
        self.log(self._size_summary(path, out))

    def compress_video(self, path, output_dir):
        preset_bitrates = {"Web": "1200k", "Social": "2400k", "Archive": "4500k"}
        bitrate = preset_bitrates[self.compression_preset.get()]
        clip = VideoFileClip(path)
        base_name = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(output_dir, f"cmp_{base_name}.{self._default_video_format()}")
        clip.write_videofile(out, codec="libx264", bitrate=bitrate, audio_codec="aac", logger=None)
        clip.close()
        self.log(self._size_summary(path, out))

    def trim_media(self, path, output_dir):
        start = max(0.0, float(self.trim_start_var.get() or "0"))
        end_raw = self.trim_end_var.get().strip()
        ext = os.path.splitext(path)[1].lower()
        base_name = os.path.splitext(os.path.basename(path))[0]

        if ext in VIDEO_EXTENSIONS:
            clip = VideoFileClip(path)
            end = float(end_raw) if end_raw else clip.duration
            clipped = clip.subclipped(start, min(end, clip.duration))
            out = os.path.join(output_dir, f"trim_{base_name}.{self._default_video_format()}")
            clipped.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
            clipped.close()
            clip.close()
        elif ext in (".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"):
            clip = AudioFileClip(path)
            end = float(end_raw) if end_raw else clip.duration
            clipped = clip.subclipped(start, min(end, clip.duration))
            out = os.path.join(output_dir, f"trim_{base_name}{ext}")
            clipped.write_audiofile(out, logger=None)
            clipped.close()
            clip.close()
        else:
            raise ValueError("Trim is supported for video and common audio files only.")

        self.log(self._size_summary(path, out))

    def _size_summary(self, original, output):
        if not os.path.exists(output):
            return f"Saved {os.path.basename(output)}"
        before = os.path.getsize(original)
        after = os.path.getsize(output)
        delta = after - before
        sign = "+" if delta >= 0 else ""
        return (
            f"Saved {os.path.basename(output)} | "
            f"{before / 1024:.1f} KB -> {after / 1024:.1f} KB ({sign}{delta / 1024:.1f} KB)"
        )
