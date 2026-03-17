import os
import threading
import time
from datetime import datetime
import cv2
import customtkinter as ctk
from PIL import Image
from moviepy import VideoFileClip
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
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # Variables
        self.input_files = []
        self.output_dir = ""
        self.processing = False
        self.stop_requested = False

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
        self.img_format_option.set("png")

        self.vid_settings_frame = ctk.CTkFrame(self.settings_container, fg_color="transparent")
        ctk.CTkLabel(self.vid_settings_frame, text="Video Res:").grid(row=0, column=0, padx=5, pady=10)
        self.vid_res_option = ctk.CTkOptionMenu(self.vid_settings_frame, values=[k for k in RESOLUTION_PRESETS.keys() if "Scale" not in k])
        self.vid_res_option.grid(row=0, column=1, padx=5, pady=10)
        self.vid_res_option.set("1080p")

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

    def toggle_mode(self, mode):
        if mode == "Image":
            self.vid_settings_frame.grid_forget()
            self.img_settings_frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        else:
            self.img_settings_frame.grid_forget()
            self.vid_settings_frame.grid(row=0, column=0, columnspan=4, sticky="ew")

    def log(self, msg):
        self.log_box.insert("end", f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        self.log_box.see("end")

    def add_files(self):
        files = filedialog.askopenfilenames()
        for f in files:
            if f not in self.input_files:
                self.input_files.append(f)
                self.file_list.insert("end", f"{os.path.basename(f)}\n")

    def start_processing(self):
        if not self.input_files: return
        self.output_dir = filedialog.askdirectory()
        if not self.output_dir: return
        
        self.processing = True
        self.start_btn.configure(text="STOP", fg_color="red")
        threading.Thread(target=self.process_loop, daemon=True).start()

    def process_loop(self):
        mode = self.mode_var.get()
        res = RESOLUTION_PRESETS[self.img_res_option.get() if mode == "Image" else self.vid_res_option.get()]
        fmt = self.img_format_option.get() if mode == "Image" else "mp4"

        for file_path in self.input_files:
            if not self.processing: break
            self.log(f"Processing {os.path.basename(file_path)}...")
            try:
                if mode == "Image": self.process_image(file_path, res, fmt)
                else: self.process_video(file_path, res, "mp4")
            except Exception as e:
                self.log(f"Error: {e}")

        self.processing = False
        self.start_btn.configure(text="START", fg_color="green")
        messagebox.showinfo("Done", "Processing complete")

    def process_image(self, path, res, fmt):
        img = cv2.imread(path)
        if isinstance(res, str) and res.endswith("x"):
            f = int(res[:-1])
            target = (img.shape[1]*f, img.shape[0]*f)
        else: target = res
        resized = cv2.resize(img, target, interpolation=cv2.INTER_LANCZOS4)
        out = os.path.join(self.output_dir, f"up_{os.path.basename(path)}.{fmt}")
        cv2.imwrite(out, resized)

    def process_video(self, path, res, fmt):
        clip = VideoFileClip(path)
        h = res[1] if isinstance(res, tuple) else clip.h * int(res[:-1])
        resized = clip.resized(height=h)
        out = os.path.join(self.output_dir, f"up_{os.path.basename(path)}")
        resized.write_videofile(out, codec="libx264")
        clip.close()
