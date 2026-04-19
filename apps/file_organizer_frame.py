"""File organizer — sort a folder into structured subfolders."""

from __future__ import annotations

import os
import shutil
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple

import customtkinter as ctk
from tkinter import messagebox

from core.theme import (
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_H3,
    FONT_SMALL,
    GLYPH,
    RADIUS_SM,
    SPACE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    STATUS_COLORS,
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


TYPE_MAP: Dict[str, set] = {
    "Images": {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".heic", ".svg"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".m4v"},
    "Audio": {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg", ".opus"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".pptx", ".odt", ".rtf"},
    "Code": {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".rb", ".sh"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Design": {".psd", ".ai", ".fig", ".sketch", ".xd", ".afphoto", ".afdesign"},
}


class FileOrganizerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state
        self.preview_rows: List[Tuple[str, str, str]] = []

        self.source_var = ctk.StringVar()
        self.destination_var = ctk.StringVar(value=self._default_destination())
        self.mode_var = ctk.StringVar(value="Move")
        self.strategy_var = ctk.StringVar(value="Type")
        self.dry_run_var = ctk.BooleanVar(value=True)
        self.include_subfolders_var = ctk.BooleanVar(value=False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_ui()

    def _default_destination(self):
        if self.app_state:
            return self.app_state.settings.get("organized_folder", "")
        return ""

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="File Organizer",
            subtitle="Automatically sort a messy folder by type, date, or size. Always dry-run first.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        # Config card
        settings_card = Card(self, title="Rules", padding=SPACE_MD)
        settings_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = settings_card.body
        body.grid_columnconfigure(0, weight=1)

        FolderPicker(body, "Source folder", self.source_var).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        FolderPicker(body, "Destination root", self.destination_var).grid(
            row=1, column=0, sticky="ew", pady=SPACE_SM
        )

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", pady=SPACE_SM)
        row.grid_columnconfigure((0, 1), weight=1)

        sort_col = ctk.CTkFrame(row, fg_color="transparent")
        sort_col.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_SM))
        sort_col.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sort_col, text="Sort strategy", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkSegmentedButton(sort_col, values=["Type", "Date", "Size", "Extension"], variable=self.strategy_var).grid(
            row=1, column=0, sticky="ew", pady=(4, 0)
        )

        action_col = ctk.CTkFrame(row, fg_color="transparent")
        action_col.grid(row=0, column=1, sticky="ew", padx=(SPACE_SM, 0))
        action_col.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(action_col, text="Action", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkSegmentedButton(action_col, values=["Move", "Copy"], variable=self.mode_var).grid(
            row=1, column=0, sticky="ew", pady=(4, 0)
        )

        toggles = ctk.CTkFrame(body, fg_color="transparent")
        toggles.grid(row=3, column=0, sticky="ew", pady=(SPACE_SM, 0))
        ctk.CTkCheckBox(toggles, text="Dry-run (preview only)", variable=self.dry_run_var).pack(side="left")
        ctk.CTkCheckBox(toggles, text="Include subfolders", variable=self.include_subfolders_var).pack(
            side="left", padx=SPACE_MD
        )

        # Action buttons
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        actions.grid_columnconfigure(0, weight=1)
        self.status = StatusBadge(actions, status="Idle")
        self.status.grid(row=0, column=0, sticky="w")
        PrimaryButton(actions, text="Preview rules", command=self.preview_plan, width=150).grid(
            row=0, column=1, padx=(SPACE_SM, 0)
        )
        SuccessButton(actions, text=f"{GLYPH['play']}  Run organizer", command=self.run_organizer, width=170).grid(
            row=0, column=2, padx=(SPACE_SM, 0)
        )

        # Preview + stats split
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=3, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=2)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        preview_card = Card(content, title="Plan", padding=SPACE_MD)
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))
        preview_card.body.grid_rowconfigure(0, weight=1)
        self.preview_box = ctk.CTkTextbox(preview_card.body, corner_radius=RADIUS_SM)
        self.preview_box.grid(row=0, column=0, sticky="nsew")
        self.preview_box.insert("0.0", "Nothing previewed yet.")
        self.preview_box.configure(state="disabled")

        stats_card = Card(content, title="Buckets", padding=SPACE_MD)
        stats_card.grid(row=0, column=1, sticky="nsew", padx=(SPACE_SM, 0))
        stats_card.body.grid_rowconfigure(1, weight=1)
        self.stats_body = ctk.CTkScrollableFrame(stats_card.body, fg_color="transparent")
        self.stats_body.grid(row=0, column=0, sticky="nsew")
        self.stats_body.grid_columnconfigure(0, weight=1)
        self._render_stats(Counter())

    # ------------------------------------------------------------------
    def build_plan(self):
        source = self.source_var.get().strip()
        destination = self.destination_var.get().strip()
        if not source or not os.path.isdir(source):
            raise ValueError("Choose a valid source folder.")
        if not destination:
            raise ValueError("Choose a destination folder.")

        plan: List[Tuple[str, str, str]] = []
        iterator = self._walk_source(source) if self.include_subfolders_var.get() else self._direct_source(source)
        for source_path in iterator:
            bucket = self._resolve_bucket(source_path)
            target_dir = os.path.join(destination, bucket)
            target_path = os.path.join(target_dir, os.path.basename(source_path))
            plan.append((source_path, target_dir, target_path))
        return plan

    def _direct_source(self, source):
        for entry in sorted(os.listdir(source)):
            full = os.path.join(source, entry)
            if os.path.isfile(full):
                yield full

    def _walk_source(self, source):
        for root, _dirs, files in os.walk(source):
            for name in sorted(files):
                yield os.path.join(root, name)

    def _resolve_bucket(self, path: str) -> str:
        strategy = self.strategy_var.get()
        if strategy == "Date":
            stamp = datetime.fromtimestamp(os.path.getmtime(path))
            return os.path.join(str(stamp.year), f"{stamp.month:02d}-{stamp.strftime('%b')}")
        if strategy == "Size":
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb < 1:
                return "Tiny (under 1 MB)"
            if size_mb < 10:
                return "Small (under 10 MB)"
            if size_mb < 100:
                return "Medium (under 100 MB)"
            return "Large (100 MB+)"
        ext = os.path.splitext(path)[1].lower()
        if strategy == "Extension":
            return ext.lstrip(".") or "No Extension"
        for bucket, extensions in TYPE_MAP.items():
            if ext in extensions:
                return bucket
        return "Other"

    # ------------------------------------------------------------------
    def preview_plan(self):
        try:
            self.preview_rows = self.build_plan()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        if self.app_state:
            self.app_state.remember_folder(self.source_var.get().strip())

        self.status.set_status("Completed" if self.preview_rows else "Idle")
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert(
            "end",
            f"Strategy: {self.strategy_var.get()}   ·   Action: {self.mode_var.get()}\n"
            f"Total: {len(self.preview_rows)} file(s)\n\n",
        )
        counter: Counter = Counter()
        for source, target_dir, target in self.preview_rows[:500]:
            bucket = os.path.relpath(target_dir, self.destination_var.get().strip())
            counter[bucket] += 1
            self.preview_box.insert("end", f"{os.path.basename(source)}  →  {bucket}/{os.path.basename(target)}\n")
        if len(self.preview_rows) > 500:
            self.preview_box.insert("end", f"\n… and {len(self.preview_rows) - 500} more files.")
        self.preview_box.configure(state="disabled")

        # full counter for stats panel
        full_counter: Counter = Counter()
        for _source, target_dir, _target in self.preview_rows:
            bucket = os.path.relpath(target_dir, self.destination_var.get().strip())
            full_counter[bucket] += 1
        self._render_stats(full_counter)

    def _render_stats(self, counter: Counter):
        for child in self.stats_body.winfo_children():
            child.destroy()
        if not counter:
            ctk.CTkLabel(
                self.stats_body,
                text="Preview to see the distribution.",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_BODY),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            return
        total = sum(counter.values()) or 1
        for idx, (bucket, count) in enumerate(counter.most_common()):
            frame = ctk.CTkFrame(self.stats_body, fg_color=COLOR_SUBTLE_BG, corner_radius=RADIUS_SM)
            frame.grid(row=idx, column=0, sticky="ew", pady=2)
            frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                frame,
                text=bucket,
                font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=SPACE, pady=(SPACE_SM, 0))
            ctk.CTkLabel(
                frame,
                text=f"{count} files ({count / total:.0%})",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
                anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=SPACE, pady=(0, SPACE_SM))
            bar = ctk.CTkProgressBar(frame, height=4)
            bar.grid(row=2, column=0, sticky="ew", padx=SPACE, pady=(0, SPACE_SM))
            bar.set(count / total)

    # ------------------------------------------------------------------
    def run_organizer(self):
        self.preview_plan()
        if not self.preview_rows:
            messagebox.showinfo("Nothing to do", "No files found in the source.")
            return
        if self.dry_run_var.get():
            messagebox.showinfo(
                "Dry run complete", f"{len(self.preview_rows)} moves prepared. Uncheck dry-run to execute."
            )
            return
        if not messagebox.askyesno("Confirm", f"{self.mode_var.get()} {len(self.preview_rows)} files?"):
            return

        if self.app_state:
            self.app_state.submit_task(
                "File Organizer",
                f"{self.mode_var.get()} files by {self.strategy_var.get().lower()}",
                self._execute_plan,
                plan=list(self.preview_rows),
                action=self.mode_var.get(),
            )
        else:
            self._execute_plan(plan=list(self.preview_rows), action=self.mode_var.get())

    def _execute_plan(self, plan, action):
        moved = 0
        bytes_moved = 0
        for source_path, target_dir, target_path in plan:
            os.makedirs(target_dir, exist_ok=True)
            final_target = self._unique_target(target_path)
            size = os.path.getsize(source_path) if os.path.exists(source_path) else 0
            if action == "Copy":
                shutil.copy2(source_path, final_target)
            else:
                shutil.move(source_path, final_target)
            moved += 1
            bytes_moved += size

        summary = f"{action}d {moved} files ({human_size(bytes_moved)})."
        if self.app_state:
            self.app_state.notify(summary, level="success")
        return summary

    def _unique_target(self, path: str) -> str:
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            candidate = f"{base}_{counter}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
