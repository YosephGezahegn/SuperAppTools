import os
import shutil
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox


TYPE_MAP = {
    "Images": {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    "Audio": {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".pptx"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
}


class FileOrganizerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state
        self.preview_rows = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.source_var = ctk.StringVar()
        self.destination_var = ctk.StringVar(value=self._default_destination())
        self.mode_var = ctk.StringVar(value="Move")
        self.strategy_var = ctk.StringVar(value="Type")
        self.dry_run_var = ctk.BooleanVar(value=True)

        self.create_widgets()

    def _default_destination(self):
        if self.app_state:
            return self.app_state.settings.get("organized_folder", "")
        return ""

    def create_widgets(self):
        ctk.CTkLabel(self, text="File Organizer", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(20, 10), sticky="n"
        )

        settings = ctk.CTkFrame(self)
        settings.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        settings.grid_columnconfigure(1, weight=1)

        self._folder_row(settings, 0, "Source Folder", self.source_var)
        self._folder_row(settings, 1, "Destination Root", self.destination_var)

        ctk.CTkLabel(settings, text="Sort Strategy").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkOptionMenu(settings, values=["Type", "Date", "Size"], variable=self.strategy_var).grid(
            row=2, column=1, padx=10, pady=10, sticky="ew"
        )

        ctk.CTkLabel(settings, text="Action").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkOptionMenu(settings, values=["Move", "Copy"], variable=self.mode_var).grid(
            row=3, column=1, padx=10, pady=10, sticky="ew"
        )

        ctk.CTkCheckBox(settings, text="Dry-run preview only", variable=self.dry_run_var).grid(
            row=4, column=1, padx=10, pady=(0, 10), sticky="w"
        )

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        ctk.CTkButton(footer, text="Preview Rules", command=self.preview_plan).pack(side="left", padx=5)
        ctk.CTkButton(footer, text="Run Organizer", fg_color="green", command=self.run_organizer).pack(
            side="right", padx=5
        )

        self.preview_box = ctk.CTkTextbox(self)
        self.preview_box.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.preview_box.insert("0.0", "Preview will appear here.\n")

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

    def build_plan(self):
        source = self.source_var.get().strip()
        destination = self.destination_var.get().strip()
        if not source or not os.path.isdir(source):
            raise ValueError("Please choose a valid source folder.")
        if not destination:
            raise ValueError("Please choose a destination folder.")

        plan = []
        for entry in sorted(os.listdir(source)):
            source_path = os.path.join(source, entry)
            if not os.path.isfile(source_path):
                continue
            target_folder = self._resolve_bucket(source_path)
            target_dir = os.path.join(destination, target_folder)
            target_path = os.path.join(target_dir, entry)
            plan.append((source_path, target_dir, target_path))
        return plan

    def _resolve_bucket(self, path):
        strategy = self.strategy_var.get()
        if strategy == "Date":
            stamp = datetime.fromtimestamp(os.path.getmtime(path))
            return os.path.join(str(stamp.year), f"{stamp.month:02d}")
        if strategy == "Size":
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb < 10:
                return "Small Files"
            if size_mb < 100:
                return "Medium Files"
            return "Large Files"

        ext = os.path.splitext(path)[1].lower()
        for bucket, extensions in TYPE_MAP.items():
            if ext in extensions:
                return bucket
        return "Other"

    def preview_plan(self):
        try:
            self.preview_rows = self.build_plan()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("end", f"Strategy: {self.strategy_var.get()} | Action: {self.mode_var.get()}\n\n")
        for source_path, target_dir, target_path in self.preview_rows[:300]:
            self.preview_box.insert("end", f"{os.path.basename(source_path)}\n  -> {target_dir}\n  => {target_path}\n\n")
        if len(self.preview_rows) > 300:
            self.preview_box.insert("end", f"...and {len(self.preview_rows) - 300} more files.\n")

    def run_organizer(self):
        self.preview_plan()
        if not self.preview_rows:
            return
        if self.dry_run_var.get():
            messagebox.showinfo("Dry Run", f"Prepared {len(self.preview_rows)} file moves/copies.")
            return

        if not messagebox.askyesno("Confirm", f"{self.mode_var.get()} {len(self.preview_rows)} files?"):
            return

        if self.app_state:
            self.app_state.submit_task(
                "File Organizer",
                f"{self.mode_var.get()} files by {self.strategy_var.get().lower()}",
                self._execute_plan,
                plan=self.preview_rows,
                action=self.mode_var.get(),
            )
        else:
            self._execute_plan(self.preview_rows, self.mode_var.get())

    def _execute_plan(self, plan, action):
        moved = 0
        for source_path, target_dir, target_path in plan:
            os.makedirs(target_dir, exist_ok=True)
            final_target = self._unique_target(target_path)
            if action == "Copy":
                shutil.copy2(source_path, final_target)
            else:
                shutil.move(source_path, final_target)
            moved += 1

        if self.app_state:
            self.app_state.notify(f"File Organizer finished: {moved} files processed.")
        return f"Processed {moved} files."

    def _unique_target(self, path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            candidate = f"{base}_{counter}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
