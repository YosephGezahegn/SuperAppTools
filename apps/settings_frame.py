import os
import customtkinter as ctk
from tkinter import filedialog
from core.app_state import _default_settings


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.grid_columnconfigure(0, weight=1)

        self.theme_var = ctk.StringVar(value=self._setting("theme", "Dark"))
        self.output_var = ctk.StringVar(value=self._setting("default_output_folder", ""))
        self.recordings_var = ctk.StringVar(value=self._setting("recordings_folder", ""))
        self.exports_var = ctk.StringVar(value=self._setting("exports_folder", ""))
        self.organized_var = ctk.StringVar(value=self._setting("organized_folder", ""))
        self.snapshots_var = ctk.StringVar(value=self._setting("snapshots_folder", ""))
        self.image_format_var = ctk.StringVar(value=self._setting("preferred_image_format", "png"))
        self.video_format_var = ctk.StringVar(value=self._setting("preferred_video_format", "mp4"))
        self.max_workers_var = ctk.StringVar(value=str(self._setting("max_workers", 2)))

        self.create_widgets()

    def _setting(self, key, fallback):
        if not self.app_state:
            return fallback
        return self.app_state.settings.get(key, fallback)

    def create_widgets(self):
        ctk.CTkLabel(self, text="Global Settings", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(20, 10), sticky="n"
        )

        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        self._folder_row(form, 0, "Default Output", self.output_var)
        self._folder_row(form, 1, "Recordings Folder", self.recordings_var)
        self._folder_row(form, 2, "Exports Folder", self.exports_var)
        self._folder_row(form, 3, "Organized Folder", self.organized_var)
        self._folder_row(form, 4, "Snapshots Folder", self.snapshots_var)

        ctk.CTkLabel(form, text="Theme").grid(row=5, column=0, padx=10, pady=10, sticky="w")
        self.theme_menu = ctk.CTkOptionMenu(form, values=["Dark", "Light", "System"], variable=self.theme_var)
        self.theme_menu.grid(row=5, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(form, text="Preferred Image Format").grid(row=6, column=0, padx=10, pady=10, sticky="w")
        self.image_menu = ctk.CTkOptionMenu(
            form, values=["png", "jpg", "webp", "bmp", "tiff"], variable=self.image_format_var
        )
        self.image_menu.grid(row=6, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(form, text="Preferred Video Format").grid(row=7, column=0, padx=10, pady=10, sticky="w")
        self.video_menu = ctk.CTkOptionMenu(form, values=["mp4", "mov", "webm"], variable=self.video_format_var)
        self.video_menu.grid(row=7, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(form, text="Task Workers").grid(row=8, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(form, textvariable=self.max_workers_var).grid(row=8, column=1, padx=10, pady=10, sticky="ew")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkButton(footer, text="Reset Defaults", fg_color="gray", command=self.reset_defaults).pack(
            side="left", padx=5, pady=5
        )
        ctk.CTkButton(footer, text="Save Settings", fg_color="green", command=self.save_settings).pack(
            side="right", padx=5, pady=5
        )

    def _folder_row(self, parent, row, label, variable):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(parent, textvariable=variable).grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(parent, text="Browse", width=90, command=lambda v=variable: self.pick_folder(v)).grid(
            row=row, column=2, padx=10, pady=10
        )

    def pick_folder(self, variable):
        path = filedialog.askdirectory()
        if path:
            variable.set(path)

    def reset_defaults(self):
        if not self.app_state:
            return
        defaults = _default_settings()
        self.output_var.set(defaults.get("default_output_folder", ""))
        self.recordings_var.set(defaults.get("recordings_folder", ""))
        self.exports_var.set(defaults.get("exports_folder", ""))
        self.organized_var.set(defaults.get("organized_folder", ""))
        self.snapshots_var.set(defaults.get("snapshots_folder", ""))
        self.theme_var.set(defaults.get("theme", "Dark"))
        self.image_format_var.set(defaults.get("preferred_image_format", "png"))
        self.video_format_var.set(defaults.get("preferred_video_format", "mp4"))
        self.max_workers_var.set(str(defaults.get("max_workers", 2)))

    def save_settings(self):
        if not self.app_state:
            return
        updates = {
            "theme": self.theme_var.get(),
            "default_output_folder": self.output_var.get().strip(),
            "recordings_folder": self.recordings_var.get().strip(),
            "exports_folder": self.exports_var.get().strip(),
            "organized_folder": self.organized_var.get().strip(),
            "snapshots_folder": self.snapshots_var.get().strip(),
            "preferred_image_format": self.image_format_var.get().strip(),
            "preferred_video_format": self.video_format_var.get().strip(),
            "max_workers": max(1, int(self.max_workers_var.get() or "1")),
        }
        for path_key in [
            "default_output_folder",
            "recordings_folder",
            "exports_folder",
            "organized_folder",
            "snapshots_folder",
        ]:
            path = updates[path_key]
            if path:
                os.makedirs(path, exist_ok=True)
        self.app_state.update_settings(updates)
        ctk.set_appearance_mode(updates["theme"])
