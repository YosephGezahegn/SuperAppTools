import json
import os
import shutil
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox


class BackupSnapshotFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.source_var = ctk.StringVar()
        self.snapshot_root_var = ctk.StringVar(value=self._snapshot_root())
        self.selected_snapshot_var = ctk.StringVar()
        self.include_files_var = ctk.BooleanVar(value=True)

        self.create_widgets()

    def _snapshot_root(self):
        if self.app_state:
            return self.app_state.settings.get("snapshots_folder", "")
        return ""

    def create_widgets(self):
        ctk.CTkLabel(self, text="Backup Snapshot", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(20, 10), sticky="n"
        )

        top = ctk.CTkFrame(self)
        top.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        self._folder_row(top, 0, "Source Folder", self.source_var)
        self._folder_row(top, 1, "Snapshot Store", self.snapshot_root_var)

        ctk.CTkCheckBox(top, text="Copy files into snapshot store", variable=self.include_files_var).grid(
            row=2, column=1, padx=10, pady=(0, 10), sticky="w"
        )

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        ctk.CTkButton(controls, text="Create Snapshot", command=self.create_snapshot).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Refresh Snapshots", fg_color="gray", command=self.refresh_snapshot_menu).pack(
            side="left", padx=5
        )
        ctk.CTkButton(controls, text="Restore Snapshot", fg_color="green", command=self.restore_snapshot).pack(
            side="right", padx=5
        )

        self.snapshot_menu = ctk.CTkOptionMenu(self, values=["No snapshots found"], variable=self.selected_snapshot_var)
        self.snapshot_menu.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")

        self.log_box = ctk.CTkTextbox(self)
        self.log_box.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)

        self.refresh_snapshot_menu()

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

    def refresh_snapshot_menu(self):
        root = self.snapshot_root_var.get().strip()
        os.makedirs(root, exist_ok=True)
        items = [name for name in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, name))]
        if not items:
            items = ["No snapshots found"]
        self.snapshot_menu.configure(values=items)
        self.selected_snapshot_var.set(items[0])

    def create_snapshot(self):
        source = self.source_var.get().strip()
        root = self.snapshot_root_var.get().strip()
        if not source or not os.path.isdir(source):
            messagebox.showerror("Error", "Choose a valid source folder.")
            return
        os.makedirs(root, exist_ok=True)

        if self.app_state:
            self.app_state.submit_task(
                "Backup Snapshot",
                f"Snapshot {os.path.basename(source)}",
                self._build_snapshot,
                source=source,
                root=root,
                include_files=self.include_files_var.get(),
            )
        else:
            self._build_snapshot(source, root, self.include_files_var.get())
        self.refresh_snapshot_menu()

    def _build_snapshot(self, source, root, include_files):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = os.path.join(root, f"snapshot_{stamp}")
        payload_dir = os.path.join(snapshot_dir, "files")
        os.makedirs(snapshot_dir, exist_ok=True)
        if include_files:
            os.makedirs(payload_dir, exist_ok=True)

        manifest = {
            "source": source,
            "created_at": datetime.now().isoformat(),
            "include_files": include_files,
            "files": [],
        }

        for current_root, _, filenames in os.walk(source):
            for filename in filenames:
                full_path = os.path.join(current_root, filename)
                rel_path = os.path.relpath(full_path, source)
                item = {
                    "relative_path": rel_path,
                    "size": os.path.getsize(full_path),
                    "modified": os.path.getmtime(full_path),
                }
                manifest["files"].append(item)
                if include_files:
                    dest = os.path.join(payload_dir, rel_path)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(full_path, dest)

        with open(os.path.join(snapshot_dir, "manifest.json"), "w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)

        if self.app_state:
            self.app_state.notify(f"Snapshot created: {snapshot_dir}")
        return snapshot_dir

    def restore_snapshot(self):
        snapshot_name = self.selected_snapshot_var.get()
        root = self.snapshot_root_var.get().strip()
        snapshot_dir = os.path.join(root, snapshot_name)
        manifest_path = os.path.join(snapshot_dir, "manifest.json")

        if snapshot_name == "No snapshots found" or not os.path.exists(manifest_path):
            messagebox.showerror("Error", "Choose a valid snapshot.")
            return

        restore_dir = filedialog.askdirectory()
        if not restore_dir:
            return

        if self.app_state:
            self.app_state.submit_task(
                "Restore Snapshot",
                f"Restore {snapshot_name}",
                self._restore_snapshot_task,
                snapshot_dir=snapshot_dir,
                restore_dir=restore_dir,
            )
        else:
            self._restore_snapshot_task(snapshot_dir, restore_dir)

    def _restore_snapshot_task(self, snapshot_dir, restore_dir):
        manifest_path = os.path.join(snapshot_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = json.load(file)

        copied = 0
        payload_dir = os.path.join(snapshot_dir, "files")
        if manifest.get("include_files") and os.path.isdir(payload_dir):
            for item in manifest.get("files", []):
                rel_path = item["relative_path"]
                source = os.path.join(payload_dir, rel_path)
                target = os.path.join(restore_dir, rel_path)
                if os.path.exists(source):
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copy2(source, target)
                    copied += 1
        else:
            report_path = os.path.join(restore_dir, "snapshot_restore_report.json")
            with open(report_path, "w", encoding="utf-8") as file:
                json.dump(manifest, file, indent=2)
            copied = len(manifest.get("files", []))

        if self.app_state:
            self.app_state.notify(f"Snapshot restored into {restore_dir}")
        return f"Restored {copied} files."
