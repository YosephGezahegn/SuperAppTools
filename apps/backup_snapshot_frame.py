"""Folder snapshot + restore tool."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import List

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.theme import (
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_SMALL,
    GLYPH,
    RADIUS_SM,
    SPACE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from core.ui_helpers import (
    Card,
    FolderPicker,
    GhostButton,
    PageHeader,
    PrimaryButton,
    StatusBadge,
    SuccessButton,
    human_size,
)


class BackupSnapshotFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.source_var = ctk.StringVar()
        self.snapshot_root_var = ctk.StringVar(value=self._snapshot_root())
        self.selected_snapshot_var = ctk.StringVar()
        self.include_files_var = ctk.BooleanVar(value=True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_ui()
        self._refresh_snapshots()

    def _snapshot_root(self):
        if self.app_state:
            return self.app_state.settings.get("snapshots_folder", "")
        return ""

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="Backup Snapshot",
            subtitle="Create timestamped snapshots of a folder — with or without the underlying files.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        # Create
        create_card = Card(self, title="Create snapshot", padding=SPACE_MD)
        create_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = create_card.body
        body.grid_columnconfigure(0, weight=1)
        FolderPicker(body, "Source folder", self.source_var).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        FolderPicker(body, "Snapshot store", self.snapshot_root_var).grid(row=1, column=0, sticky="ew", pady=SPACE_SM)
        ctk.CTkCheckBox(
            body, text="Copy files into the snapshot store (disables restore if off)", variable=self.include_files_var
        ).grid(row=2, column=0, sticky="w", pady=(SPACE_SM, 0))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", pady=(SPACE_MD, 0))
        actions.grid_columnconfigure(0, weight=1)
        self.status = StatusBadge(actions, status="Idle")
        self.status.grid(row=0, column=0, sticky="w")
        PrimaryButton(actions, text=f"{GLYPH['add']}  Create snapshot", command=self.create_snapshot, width=200).grid(
            row=0, column=1
        )

        # Restore
        restore_card = Card(self, title="Restore snapshot", padding=SPACE_MD)
        restore_card.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = restore_card.body
        body.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(body, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        controls.grid_columnconfigure(0, weight=1)
        self.snapshot_menu = ctk.CTkOptionMenu(
            controls, values=["No snapshots found"], variable=self.selected_snapshot_var, command=lambda _: self._refresh_manifest_display()
        )
        self.snapshot_menu.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_SM))
        GhostButton(controls, text=f"{GLYPH['refresh']}  Refresh", command=self._refresh_snapshots, width=120).grid(row=0, column=1)

        self.manifest_box = ctk.CTkTextbox(body, corner_radius=RADIUS_SM, height=140)
        self.manifest_box.grid(row=1, column=0, sticky="ew")
        self.manifest_box.configure(state="disabled")

        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", pady=(SPACE_SM, 0))
        action_row.grid_columnconfigure(0, weight=1)
        SuccessButton(action_row, text=f"{GLYPH['play']}  Restore to folder", command=self.restore_snapshot, width=200).grid(
            row=0, column=1
        )

    # ------------------------------------------------------------------
    def _refresh_snapshots(self):
        root = self.snapshot_root_var.get().strip()
        if root:
            os.makedirs(root, exist_ok=True)
        items = []
        if root and os.path.isdir(root):
            items = [name for name in sorted(os.listdir(root), reverse=True) if os.path.isdir(os.path.join(root, name))]
        if not items:
            items = ["No snapshots found"]
        self.snapshot_menu.configure(values=items)
        self.selected_snapshot_var.set(items[0])
        self._refresh_manifest_display()

    def _refresh_manifest_display(self):
        self.manifest_box.configure(state="normal")
        self.manifest_box.delete("1.0", "end")
        name = self.selected_snapshot_var.get()
        root = self.snapshot_root_var.get().strip()
        manifest_path = os.path.join(root, name, "manifest.json") if root else ""
        if not manifest_path or not os.path.exists(manifest_path):
            self.manifest_box.insert("end", "Select a snapshot to inspect its manifest.")
        else:
            try:
                with open(manifest_path, "r", encoding="utf-8") as file:
                    manifest = json.load(file)
                total = len(manifest.get("files", []))
                total_size = sum(f.get("size", 0) for f in manifest.get("files", []))
                self.manifest_box.insert(
                    "end",
                    f"Source: {manifest.get('source', '—')}\n"
                    f"Created: {manifest.get('created_at', '—')}\n"
                    f"Files included: {manifest.get('include_files')}\n"
                    f"Entries: {total}\n"
                    f"Total payload: {human_size(total_size)}\n",
                )
            except Exception as exc:  # noqa: BLE001
                self.manifest_box.insert("end", f"Could not read manifest: {exc}")
        self.manifest_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def create_snapshot(self):
        source = self.source_var.get().strip()
        root = self.snapshot_root_var.get().strip()
        if not source or not os.path.isdir(source):
            messagebox.showerror("Error", "Choose a valid source folder.")
            return
        if not root:
            messagebox.showerror("Error", "Choose a snapshot store.")
            return
        os.makedirs(root, exist_ok=True)

        self.status.set_status("Running")
        if self.app_state:
            self.app_state.remember_folder(source)
            self.app_state.submit_task(
                "Backup Snapshot",
                f"Snapshot {os.path.basename(source)}",
                self._build_snapshot,
                source=source,
                root=root,
                include_files=self.include_files_var.get(),
            )
        else:
            self._build_snapshot(source=source, root=root, include_files=self.include_files_var.get())

        self.after(400, self._refresh_snapshots)

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
        for current, _dirs, files in os.walk(source):
            for filename in files:
                full = os.path.join(current, filename)
                rel = os.path.relpath(full, source)
                try:
                    size = os.path.getsize(full)
                    modified = os.path.getmtime(full)
                except OSError:
                    continue
                manifest["files"].append({"relative_path": rel, "size": size, "modified": modified})
                if include_files:
                    dest = os.path.join(payload_dir, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    try:
                        shutil.copy2(full, dest)
                    except OSError:
                        pass

        with open(os.path.join(snapshot_dir, "manifest.json"), "w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)

        if self.app_state:
            self.app_state.notify(f"Snapshot created at {snapshot_dir}", level="success")
        self.after(0, lambda: self.status.set_status("Completed"))
        return snapshot_dir

    # ------------------------------------------------------------------
    def restore_snapshot(self):
        name = self.selected_snapshot_var.get()
        root = self.snapshot_root_var.get().strip()
        snapshot_dir = os.path.join(root, name)
        manifest_path = os.path.join(snapshot_dir, "manifest.json")
        if name == "No snapshots found" or not os.path.exists(manifest_path):
            messagebox.showerror("Error", "Choose a valid snapshot first.")
            return
        restore_dir = filedialog.askdirectory()
        if not restore_dir:
            return

        if self.app_state:
            self.app_state.submit_task(
                "Restore Snapshot",
                f"Restore {name}",
                self._restore_task,
                snapshot_dir=snapshot_dir,
                restore_dir=restore_dir,
            )
        else:
            self._restore_task(snapshot_dir=snapshot_dir, restore_dir=restore_dir)

    def _restore_task(self, snapshot_dir, restore_dir):
        manifest_path = os.path.join(snapshot_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = json.load(file)

        copied = 0
        payload_dir = os.path.join(snapshot_dir, "files")
        if manifest.get("include_files") and os.path.isdir(payload_dir):
            for item in manifest.get("files", []):
                rel = item["relative_path"]
                source = os.path.join(payload_dir, rel)
                target = os.path.join(restore_dir, rel)
                if os.path.exists(source):
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    try:
                        shutil.copy2(source, target)
                        copied += 1
                    except OSError:
                        pass
        else:
            report = os.path.join(restore_dir, "snapshot_restore_report.json")
            with open(report, "w", encoding="utf-8") as file:
                json.dump(manifest, file, indent=2)
            copied = len(manifest.get("files", []))

        if self.app_state:
            self.app_state.notify(f"Restored {copied} entry(ies) to {restore_dir}", level="success")
        return f"Restored {copied} entries."
