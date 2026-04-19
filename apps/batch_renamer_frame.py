"""Batch file renamer with template, regex, and case modes + undo history."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import List, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.theme import (
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_SMALL,
    GLYPH,
    RADIUS_LG,
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
)


TOKEN_HINTS = [
    ("{name}", "Original name without extension"),
    ("{ext}", "Original extension including dot"),
    ("{n}", "Sequence number"),
    ("{n:03}", "Padded sequence (leading zeros)"),
    ("{parent}", "Parent folder name"),
    ("{date}", "Current date YYYY-MM-DD"),
    ("{size}", "File size in KB"),
]


class BatchRenamerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.mode_var = ctk.StringVar(value="Template")
        self.case_var = ctk.StringVar(value="Keep")
        self.keep_ext = ctk.BooleanVar(value=True)
        self.start_num = ctk.IntVar(value=1)
        self.step_num = ctk.IntVar(value=1)
        self._undo_stack: List[List[Tuple[str, str]]] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="Batch Renamer",
            subtitle="Rename files with templates, regex, or case rules — preview before committing, and undo any batch.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        settings_card = Card(self, title="Rules", padding=SPACE_MD)
        settings_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = settings_card.body
        body.grid_columnconfigure(0, weight=1)

        self.mode_toggle = ctk.CTkSegmentedButton(
            body,
            values=["Template", "Regex", "Case"],
            variable=self.mode_var,
            command=self._on_mode_change,
        )
        self.mode_toggle.grid(row=0, column=0, sticky="ew")

        self.template_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.regex_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.case_frame = ctk.CTkFrame(body, fg_color="transparent")

        self._build_template_frame()
        self._build_regex_frame()
        self._build_case_frame()

        options = ctk.CTkFrame(body, fg_color="transparent")
        options.grid(row=2, column=0, sticky="ew", pady=(SPACE_MD, 0))
        options.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkCheckBox(options, text="Keep original extension", variable=self.keep_ext).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(options, text="Start #").grid(row=0, column=1, sticky="e", padx=(0, SPACE_SM))
        ctk.CTkEntry(options, textvariable=self.start_num, width=80).grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(options, text="Step").grid(row=0, column=3, sticky="e", padx=(0, SPACE_SM))
        ctk.CTkEntry(options, textvariable=self.step_num, width=80).grid(row=0, column=3, padx=(50, 0), sticky="w")

        # Files + preview
        self.grid_rowconfigure(2, weight=1)
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.drop_list = FileDropList(
            content,
            on_add=self._add_files,
            on_add_folder=self._add_folder,
            on_clear=self._clear,
            empty_hint="Add files or a folder to get started.",
        )
        self.drop_list.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))

        preview_card = Card(content, title="Preview", padding=SPACE_MD)
        preview_card.grid(row=0, column=1, sticky="nsew", padx=(SPACE_SM, 0))
        preview_card.body.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(preview_card.body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        self.preview_status = StatusBadge(head, status="Idle")
        self.preview_status.grid(row=0, column=0, sticky="w")

        self.preview_box = ctk.CTkTextbox(preview_card.body, corner_radius=RADIUS_SM)
        self.preview_box.grid(row=1, column=0, sticky="nsew", pady=(SPACE_SM, 0))
        self.preview_box.configure(state="disabled")

        # Footer actions
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(SPACE_MD, 0))
        footer.grid_columnconfigure(0, weight=1)

        self.undo_btn = GhostButton(footer, text=f"{GLYPH['refresh']}  Undo last rename", command=self.undo_last, width=200)
        self.undo_btn.grid(row=0, column=0, sticky="w")
        self.undo_btn.configure(state="disabled")

        PrimaryButton(footer, text="Preview", command=self.refresh_preview, width=140).grid(
            row=0, column=1, padx=(SPACE_SM, 0)
        )
        self.apply_btn = SuccessButton(footer, text="Apply rename", command=self.apply_rename, width=160, state="disabled")
        self.apply_btn.grid(row=0, column=2, padx=(SPACE_SM, 0))

        self._on_mode_change("Template")

    def _build_template_frame(self):
        frame = self.template_frame
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Template", font=ctk.CTkFont(size=FONT_BODY, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, SPACE_SM)
        )
        self.template_entry = ctk.CTkEntry(frame)
        self.template_entry.grid(row=0, column=1, sticky="ew", pady=(SPACE_SM, SPACE_SM))
        self.template_entry.insert(0, "{name}_{n:03}{ext}")

        # Token chip hints
        chip_row = ctk.CTkFrame(frame, fg_color="transparent")
        chip_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(
            chip_row, text="Tokens  ", text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL)
        ).pack(side="left")
        for token, tip in TOKEN_HINTS:
            chip = ctk.CTkButton(
                chip_row,
                text=token,
                font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
                fg_color=COLOR_SUBTLE_BG,
                hover_color=("#E5E7EB", "#2C2C31"),
                text_color=("#111827", "#E5E7EB"),
                corner_radius=RADIUS_SM,
                height=24,
                width=0,
                command=lambda t=token: self._insert_token(t),
            )
            chip.pack(side="left", padx=2)

    def _insert_token(self, token: str):
        if self.mode_var.get() != "Template":
            return
        try:
            self.template_entry.insert("insert", token)
        except Exception:  # noqa: BLE001
            pass

    def _build_regex_frame(self):
        frame = self.regex_frame
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Pattern").grid(row=0, column=0, sticky="w", padx=(0, SPACE_SM), pady=SPACE_SM)
        self.regex_pattern = ctk.CTkEntry(frame)
        self.regex_pattern.grid(row=0, column=1, sticky="ew", pady=SPACE_SM)
        ctk.CTkLabel(frame, text="Replace").grid(row=1, column=0, sticky="w", padx=(0, SPACE_SM), pady=SPACE_SM)
        self.regex_replace = ctk.CTkEntry(frame)
        self.regex_replace.grid(row=1, column=1, sticky="ew", pady=SPACE_SM)
        ctk.CTkLabel(
            frame,
            text="Use regular expressions. Back-references like \\1 are supported.",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_SMALL),
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, SPACE_SM))

    def _build_case_frame(self):
        frame = self.case_frame
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame,
            text="Change file-name casing in place.",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_SMALL),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(SPACE_SM, SPACE_SM))
        ctk.CTkSegmentedButton(
            frame,
            values=["Keep", "lower", "UPPER", "Title", "snake_case", "kebab-case"],
            variable=self.case_var,
        ).grid(row=1, column=0, sticky="ew")

    def _on_mode_change(self, mode: str):
        for f in (self.template_frame, self.regex_frame, self.case_frame):
            f.grid_forget()
        target = {"Template": self.template_frame, "Regex": self.regex_frame, "Case": self.case_frame}[mode]
        target.grid(row=1, column=0, sticky="ew", pady=(SPACE_SM, 0))

    # ------------------------------------------------------------------
    def _add_files(self):
        paths = filedialog.askopenfilenames()
        if paths:
            self.drop_list.add(paths)
            self.apply_btn.configure(state="disabled")

    def _add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        if self.app_state:
            self.app_state.remember_folder(folder)
        entries = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                entries.append(path)
        self.drop_list.add(entries)
        self.apply_btn.configure(state="disabled")

    def _clear(self):
        self.drop_list.clear()
        self._set_preview_text("")
        self.preview_status.set_status("Idle")
        self.apply_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    def _build_new_name(self, path: str, index: int) -> str:
        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        parent = os.path.basename(os.path.dirname(path))
        mode = self.mode_var.get()

        if mode == "Template":
            template = self.template_entry.get().strip()
            n = self.start_num.get() + (index * self.step_num.get())
            try:
                size_kb = max(1, int(os.path.getsize(path) / 1024))
            except OSError:
                size_kb = 0
            context = {
                "name": name,
                "ext": ext,
                "n": n,
                "parent": parent,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "size": size_kb,
            }
            try:
                new_name = template.format(**context)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Template error: {exc}") from exc
            if self.keep_ext.get() and "{ext}" not in template:
                new_name += ext
            return new_name

        if mode == "Regex":
            pattern = self.regex_pattern.get()
            repl = self.regex_replace.get()
            try:
                new_name = re.sub(pattern, repl, name)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Regex error: {exc}") from exc
            return new_name + (ext if self.keep_ext.get() else "")

        # Case mode
        style = self.case_var.get()
        transformed = name
        if style == "lower":
            transformed = name.lower()
        elif style == "UPPER":
            transformed = name.upper()
        elif style == "Title":
            transformed = name.title()
        elif style == "snake_case":
            transformed = re.sub(r"[\s\-]+", "_", name).lower()
        elif style == "kebab-case":
            transformed = re.sub(r"[\s_]+", "-", name).lower()
        return transformed + (ext if self.keep_ext.get() else "")

    # ------------------------------------------------------------------
    def refresh_preview(self):
        inputs = self.drop_list.paths()
        if not inputs:
            messagebox.showerror("Error", "Add files first.")
            return

        try:
            pairs, conflicts = self._compute_pairs(inputs)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            self.apply_btn.configure(state="disabled")
            return

        if conflicts:
            self.preview_status.set_status("Failed")
            lines = ["Conflicts prevent renaming:\n"] + [f"  · {c}" for c in conflicts]
            self._set_preview_text("\n".join(lines))
            self.apply_btn.configure(state="disabled")
            return

        self.preview_status.set_status("Completed")
        lines = [f"{os.path.basename(old)}  →  {new}" for old, new in pairs]
        self._set_preview_text("\n".join(lines))
        self.apply_btn.configure(state="normal")

    def _compute_pairs(self, inputs: List[str]):
        pairs = []
        targets = {}
        conflicts: List[str] = []
        for i, path in enumerate(inputs):
            new = self._build_new_name(path, i)
            target = os.path.join(os.path.dirname(path), new)
            pairs.append((path, new))
            if target in targets:
                conflicts.append(f"Duplicate target name: {new}")
            targets[target] = path
            if os.path.exists(target) and target != path:
                conflicts.append(f"Already exists: {new}")
        return pairs, conflicts

    def _set_preview_text(self, text: str):
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        if text:
            self.preview_box.insert("end", text)
        self.preview_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def apply_rename(self):
        inputs = self.drop_list.paths()
        if not inputs:
            return
        try:
            pairs, conflicts = self._compute_pairs(inputs)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        if conflicts:
            messagebox.showerror("Error", "Conflicts still present — preview again.")
            return
        if not messagebox.askyesno("Confirm", f"Rename {len(pairs)} file(s)?"):
            return

        performed: List[Tuple[str, str]] = []
        errors = 0
        for old, new in pairs:
            target = os.path.join(os.path.dirname(old), new)
            try:
                os.rename(old, target)
                performed.append((old, target))
            except Exception:  # noqa: BLE001
                errors += 1

        if performed:
            self._undo_stack.append(performed)
            self.undo_btn.configure(state="normal")

        if self.app_state:
            level = "success" if not errors else "warning"
            self.app_state.notify(
                f"Renamed {len(performed)} file(s)." + (f" {errors} failed." if errors else ""), level=level
            )
        messagebox.showinfo(
            "Done", f"Renamed {len(performed)} file(s)." + (f" {errors} could not be renamed." if errors else "")
        )
        # Update list to new paths
        self.drop_list.set_paths([target for _old, target in performed])
        self.apply_btn.configure(state="disabled")
        self._set_preview_text("")
        self.preview_status.set_status("Idle")

    def undo_last(self):
        if not self._undo_stack:
            return
        last_batch = self._undo_stack.pop()
        restored = 0
        errors = 0
        for old, new in last_batch:
            try:
                os.rename(new, old)
                restored += 1
            except Exception:  # noqa: BLE001
                errors += 1
        if self.app_state:
            level = "success" if not errors else "warning"
            self.app_state.notify(f"Undid rename — restored {restored} file(s).", level=level)
        if not self._undo_stack:
            self.undo_btn.configure(state="disabled")
        self.drop_list.set_paths([old for old, _new in last_batch])
