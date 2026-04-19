"""Duplicate file cleaner."""

from __future__ import annotations

import hashlib
import os
import re
import threading
from collections import defaultdict
from typing import Dict, List, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.theme import (
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    COLOR_SUCCESS,
    FONT_BODY,
    FONT_SMALL,
    GLYPH,
    RADIUS,
    RADIUS_LG,
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
    human_size,
)


COPY_PATTERN = re.compile(r"^(.+?)\s*\((\d+)\)(\.[^.]+)$")


class DuplicateCleanerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.target_folder = ctk.StringVar(value=self._initial_folder())
        self.recursive = ctk.BooleanVar(value=True)
        self.mode_var = ctk.StringVar(value="Smart copy names")
        self.prefix_length = ctk.IntVar(value=10)
        self.min_bytes = ctk.IntVar(value=0)
        self.move_to_trash = ctk.BooleanVar(value=True)

        self._scan_thread: threading.Thread | None = None
        self._scan_cancel = threading.Event()
        self._duplicates: List[Tuple[str, str]] = []  # (path, reason)
        self._stats = {"scanned": 0, "duplicates": 0, "bytes": 0}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_ui()

    # ------------------------------------------------------------------
    def _initial_folder(self) -> str:
        if self.app_state:
            return self.app_state.settings.get("default_output_folder", "")
        return ""

    def _build_ui(self):
        PageHeader(
            self,
            title="Duplicate Cleaner",
            subtitle="Detect and remove duplicate files by name, hash, or shared prefix.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        # ---- Source / options card
        source_card = Card(self, title="Source & options", padding=SPACE_MD)
        source_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = source_card.body
        body.grid_columnconfigure(0, weight=1)

        FolderPicker(
            body,
            "Target folder",
            self.target_folder,
            helper="Scan all files in this folder (and optionally its subfolders).",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))

        options = ctk.CTkFrame(body, fg_color="transparent")
        options.grid(row=1, column=0, sticky="ew", pady=SPACE_SM)
        options.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            options, text="Detection mode", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w"
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.mode_toggle = ctk.CTkSegmentedButton(
            options,
            values=["Smart copy names", "Hash (exact match)", "Prefix + size"],
            variable=self.mode_var,
            command=self._on_mode_changed,
        )
        self.mode_toggle.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, SPACE_SM))

        ctk.CTkCheckBox(options, text="Scan subfolders", variable=self.recursive).grid(
            row=2, column=0, sticky="w", pady=SPACE_SM
        )
        ctk.CTkCheckBox(options, text="Move to system trash instead of deleting", variable=self.move_to_trash).grid(
            row=2, column=1, sticky="w", pady=SPACE_SM
        )

        self.prefix_frame = ctk.CTkFrame(options, fg_color="transparent")
        self.prefix_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=SPACE_SM)
        ctk.CTkLabel(self.prefix_frame, text="Prefix length").pack(side="left", padx=(0, SPACE_SM))
        ctk.CTkEntry(self.prefix_frame, textvariable=self.prefix_length, width=80).pack(side="left")
        ctk.CTkLabel(
            self.prefix_frame,
            text=f"{GLYPH['dot']} Matches files sharing the first N characters and size.",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_SMALL),
        ).pack(side="left", padx=SPACE)

        size_row = ctk.CTkFrame(options, fg_color="transparent")
        size_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=SPACE_SM)
        ctk.CTkLabel(size_row, text="Ignore files smaller than (bytes)").pack(side="left", padx=(0, SPACE_SM))
        ctk.CTkEntry(size_row, textvariable=self.min_bytes, width=100).pack(side="left")

        self._on_mode_changed(self.mode_var.get())

        # ---- Action bar
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        actions.grid_columnconfigure(0, weight=1)

        self.status_badge = StatusBadge(actions, status="Idle")
        self.status_badge.grid(row=0, column=0, sticky="w")

        self.scan_btn = PrimaryButton(actions, text=f"{GLYPH['search']}  Scan now", command=self.scan_files, width=160)
        self.scan_btn.grid(row=0, column=1, padx=(SPACE_SM, 0))

        self.cancel_btn = GhostButton(actions, text="Cancel", command=self._cancel_scan, width=100, state="disabled")
        self.cancel_btn.grid(row=0, column=2, padx=(SPACE_SM, 0))

        self.delete_btn = DangerButton(
            actions, text=f"{GLYPH['close']}  Remove duplicates", command=self.confirm_delete, width=200, state="disabled"
        )
        self.delete_btn.grid(row=0, column=3, padx=(SPACE_SM, 0))

        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=3, column=0, sticky="ew", pady=(0, SPACE_SM))
        self.progress.set(0)
        self.progress.grid_remove()

        # ---- Results list
        results_card = Card(self, title="Results", padding=SPACE_MD)
        results_card.grid(row=4, column=0, sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        results_card.body.grid_rowconfigure(1, weight=1)

        header_bar = ctk.CTkFrame(results_card.body, fg_color="transparent")
        header_bar.grid(row=0, column=0, sticky="ew")
        header_bar.grid_columnconfigure(0, weight=1)
        self.summary_label = ctk.CTkLabel(
            header_bar,
            text="No scan yet.",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_BODY),
            anchor="w",
        )
        self.summary_label.grid(row=0, column=0, sticky="w")

        self.results_scroll = ctk.CTkScrollableFrame(
            results_card.body, fg_color="transparent"
        )
        self.results_scroll.grid(row=1, column=0, sticky="nsew", pady=(SPACE_SM, 0))
        self.results_scroll.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    def _on_mode_changed(self, mode: str):
        is_prefix = mode == "Prefix + size"
        for child in self.prefix_frame.winfo_children():
            try:
                child.configure(state=("normal" if is_prefix else "disabled"))
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    def scan_files(self):
        folder = self.target_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Select a folder", "Please choose an existing folder before scanning.")
            return
        if self._scan_thread and self._scan_thread.is_alive():
            return

        if self.app_state:
            self.app_state.remember_folder(folder)

        self._duplicates.clear()
        self._stats = {"scanned": 0, "duplicates": 0, "bytes": 0}
        for child in self.results_scroll.winfo_children():
            child.destroy()

        self.progress.grid()
        self.progress.set(0)
        self.scan_btn.configure(state="disabled")
        self.delete_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status_badge.set_status("Running")
        self.summary_label.configure(text="Scanning…")

        self._scan_cancel = threading.Event()
        self._scan_thread = threading.Thread(target=self._scan_worker, args=(folder,), daemon=True)
        self._scan_thread.start()

    def _cancel_scan(self):
        self._scan_cancel.set()

    def _scan_worker(self, folder: str):
        mode = self.mode_var.get()
        min_bytes = max(0, self.min_bytes.get() or 0)
        try:
            all_files = list(self._iter_files(folder, min_bytes))
            total = len(all_files) or 1
            self._update_status(f"Indexed {len(all_files):,} files. Detecting duplicates…", progress=0.05)

            if mode == "Hash (exact match)":
                duplicates = self._detect_by_hash(all_files, total)
            elif mode == "Prefix + size":
                duplicates = self._detect_by_prefix(all_files, total)
            else:
                duplicates = self._detect_smart_copies(all_files, total)

            self._duplicates = duplicates
            self._stats["duplicates"] = len(duplicates)
            self._stats["bytes"] = sum(os.path.getsize(p) for p, _ in duplicates if os.path.exists(p))
            self._stats["scanned"] = len(all_files)
            self.after(0, self._finish_scan)
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda err=exc: self._scan_failed(err))

    # ------------------------------------------------------------------
    def _iter_files(self, folder: str, min_bytes: int):
        for root, _dirs, files in os.walk(folder):
            if not self.recursive.get() and root != folder:
                continue
            for name in files:
                if self._scan_cancel.is_set():
                    return
                full = os.path.join(root, name)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                if size < min_bytes:
                    continue
                yield full, size

    def _detect_smart_copies(self, files, total):
        paths_by_dir: Dict[str, set] = defaultdict(set)
        for path, _size in files:
            paths_by_dir[os.path.dirname(path)].add(os.path.basename(path))

        duplicates: List[Tuple[str, str]] = []
        for index, (path, _size) in enumerate(files):
            if self._scan_cancel.is_set():
                break
            name = os.path.basename(path)
            match = COPY_PATTERN.match(name)
            if not match:
                continue
            original = match.group(1).strip() + match.group(3)
            if original in paths_by_dir[os.path.dirname(path)]:
                reason = f"Copy of “{original}”"
                duplicates.append((path, reason))
            self._update_status(None, progress=0.05 + 0.9 * (index / total))
        return duplicates

    def _detect_by_hash(self, files, total):
        # Bucket by size first so we only hash likely candidates.
        by_size: Dict[int, List[str]] = defaultdict(list)
        for path, size in files:
            by_size[size].append(path)

        duplicates: List[Tuple[str, str]] = []
        processed = 0
        for size, paths in by_size.items():
            if self._scan_cancel.is_set():
                break
            if len(paths) < 2 or size == 0:
                processed += len(paths)
                self._update_status(None, progress=0.1 + 0.85 * (processed / total))
                continue
            digests: Dict[str, str] = {}
            for path in paths:
                if self._scan_cancel.is_set():
                    break
                digest = self._hash_file(path)
                if digest is None:
                    processed += 1
                    continue
                if digest in digests:
                    duplicates.append((path, f"Identical to {os.path.basename(digests[digest])}"))
                else:
                    digests[digest] = path
                processed += 1
                self._update_status(None, progress=0.1 + 0.85 * (processed / total))
        return duplicates

    def _detect_by_prefix(self, files, total):
        prefix = max(1, self.prefix_length.get() or 1)
        buckets: Dict[Tuple[str, int], List[str]] = defaultdict(list)
        for path, size in files:
            name = os.path.basename(path)
            buckets[(name[:prefix].lower(), size)].append(path)

        duplicates: List[Tuple[str, str]] = []
        processed = 0
        for key, paths in buckets.items():
            if self._scan_cancel.is_set():
                break
            if len(paths) > 1:
                paths.sort()
                for dup in paths[1:]:
                    duplicates.append((dup, f"Shares prefix with {os.path.basename(paths[0])}"))
            processed += len(paths)
            self._update_status(None, progress=0.1 + 0.85 * (processed / total))
        return duplicates

    def _hash_file(self, path: str):
        h = hashlib.sha1()
        try:
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            return None
        return h.hexdigest()

    # ------------------------------------------------------------------
    def _update_status(self, message, progress=None):
        def apply():
            if message:
                self.summary_label.configure(text=message)
            if progress is not None:
                self.progress.set(progress)

        self.after(0, apply)

    def _finish_scan(self):
        self.progress.set(1.0)
        self.progress.grid_remove()
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        cancelled = self._scan_cancel.is_set()
        if cancelled:
            self.status_badge.set_status("Cancelled")
            self.summary_label.configure(text="Scan cancelled.")
            return

        self.status_badge.set_status("Completed")
        scanned = self._stats["scanned"]
        dups = self._stats["duplicates"]
        size = self._stats["bytes"]
        self.summary_label.configure(
            text=f"Scanned {scanned:,} files — found {dups:,} duplicate{'' if dups == 1 else 's'} "
            f"using {human_size(size)}."
        )
        if self.app_state:
            self.app_state.log(
                f"Duplicate scan: {dups} duplicates totalling {human_size(size)} across {scanned} files."
            )
        self._render_results()
        self.delete_btn.configure(state="normal" if dups else "disabled")

    def _scan_failed(self, exc: Exception):
        self.progress.grid_remove()
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_badge.set_status("Failed")
        self.summary_label.configure(text=f"Scan failed: {exc}")
        messagebox.showerror("Scan failed", str(exc))

    def _render_results(self):
        for child in self.results_scroll.winfo_children():
            child.destroy()
        if not self._duplicates:
            ctk.CTkLabel(
                self.results_scroll,
                text="No duplicates detected.",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_BODY),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=SPACE_SM)
            return

        for idx, (path, reason) in enumerate(self._duplicates[:500]):
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            row = ctk.CTkFrame(self.results_scroll, fg_color=COLOR_SUBTLE_BG, corner_radius=RADIUS_SM)
            row.grid(row=idx, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row,
                text=f"{GLYPH['file']}  {os.path.basename(path)}",
                anchor="w",
                font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
            ).grid(row=0, column=0, sticky="ew", padx=SPACE, pady=(SPACE_SM, 0))
            ctk.CTkLabel(
                row,
                text=f"{reason}  ·  {human_size(size)}\n{path}",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
                anchor="w",
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=SPACE, pady=(0, SPACE_SM))
        if len(self._duplicates) > 500:
            ctk.CTkLabel(
                self.results_scroll,
                text=f"… and {len(self._duplicates) - 500:,} more files.",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
            ).grid(row=500, column=0, sticky="w", pady=SPACE_SM)

    # ------------------------------------------------------------------
    def confirm_delete(self):
        if not self._duplicates:
            return
        action = "move to Trash" if self.move_to_trash.get() else "permanently delete"
        if not messagebox.askyesno(
            "Confirm", f"{action.capitalize()} {len(self._duplicates)} file(s)?"
        ):
            return

        if self.app_state:
            self.app_state.submit_task(
                "Duplicate removal",
                f"{action.capitalize()} {len(self._duplicates)} files",
                self._run_delete,
                to_trash=self.move_to_trash.get(),
                paths=[p for p, _ in self._duplicates],
            )
        else:
            self._run_delete(to_trash=self.move_to_trash.get(), paths=[p for p, _ in self._duplicates])

    def _run_delete(self, to_trash: bool, paths: List[str]):
        deleted = 0
        errors: List[str] = []
        for path in paths:
            try:
                if to_trash:
                    try:
                        import send2trash as _trash

                        _trash.send2trash(path)
                    except Exception:
                        os.remove(path)
                else:
                    os.remove(path)
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{os.path.basename(path)}: {exc}")

        summary = f"Removed {deleted} file(s)."
        if errors:
            summary += f" {len(errors)} failed."
        if self.app_state:
            level = "success" if not errors else "warning"
            self.app_state.notify(summary, level=level)
        self.after(0, lambda: self._post_delete(deleted, errors))
        return summary

    def _post_delete(self, deleted, errors):
        messagebox.showinfo(
            "Done",
            f"Removed {deleted} file(s)."
            + (f"\n\n{len(errors)} could not be removed." if errors else ""),
        )
        self.delete_btn.configure(state="disabled")
        self.scan_files()
