"""Settings frame with accent picker, folder config, and preferences."""

from __future__ import annotations

import os

import customtkinter as ctk
from tkinter import messagebox

from core.app_state import _default_settings
from core.theme import (
    ACCENT_PALETTES,
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_H3,
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
    FolderPicker,
    GhostButton,
    PageHeader,
    PrimaryButton,
)


FOLDER_FIELDS = [
    ("default_output_folder", "Default output", "Where exports go by default."),
    ("recordings_folder", "Recordings", "Used by the Screen Recorder."),
    ("exports_folder", "Media exports", "Used by Quality + Compressor and Image Studio."),
    ("organized_folder", "Organized files", "Destination for File Organizer runs."),
    ("snapshots_folder", "Snapshots", "Backup Snapshot stores archives here."),
]


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.theme_var = ctk.StringVar(value=self._setting("theme", "Dark"))
        self.accent_var = ctk.StringVar(value=self._setting("accent", "Blue"))
        self.image_format_var = ctk.StringVar(value=self._setting("preferred_image_format", "png"))
        self.video_format_var = ctk.StringVar(value=self._setting("preferred_video_format", "mp4"))
        self.max_workers_var = ctk.StringVar(value=str(self._setting("max_workers", 2)))
        self.confirm_var = ctk.BooleanVar(value=self._setting("confirm_destructive", True))
        self.toast_var = ctk.BooleanVar(value=self._setting("enable_toasts", True))

        self.folder_vars = {
            key: ctk.StringVar(value=self._setting(key, ""))
            for key, _label, _helper in FOLDER_FIELDS
        }

        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _setting(self, key, fallback):
        if not self.app_state:
            return fallback
        return self.app_state.settings.get(key, fallback)

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="Settings",
            subtitle="Appearance, preferred formats, working folders, and safety options.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        # Appearance
        appearance_card = Card(self, title="Appearance", padding=SPACE_MD)
        appearance_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = appearance_card.body
        body.grid_columnconfigure(0, weight=1)

        mode_row = ctk.CTkFrame(body, fg_color="transparent")
        mode_row.grid(row=0, column=0, sticky="ew")
        mode_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            mode_row, text="Theme", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), width=120, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkSegmentedButton(
            mode_row,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            command=self._on_theme_change,
        ).grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            body, text="Accent color", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w"
        ).grid(row=1, column=0, sticky="w", pady=(SPACE_MD, SPACE_SM))

        swatch_row = ctk.CTkFrame(body, fg_color="transparent")
        swatch_row.grid(row=2, column=0, sticky="ew")
        self._swatch_widgets = {}
        for idx, name in enumerate(ACCENT_PALETTES.keys()):
            self._swatch_widgets[name] = self._make_swatch(swatch_row, name)
            self._swatch_widgets[name].grid(row=0, column=idx, padx=(0, SPACE_SM))
        self._refresh_swatches()

        # Preferences
        prefs_card = Card(self, title="Preferences", padding=SPACE_MD)
        prefs_card.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = prefs_card.body
        body.grid_columnconfigure(1, weight=1)

        self._option_row(body, 0, "Preferred image format", self.image_format_var, ["png", "jpg", "jpeg", "webp", "bmp", "tiff"])
        self._option_row(body, 1, "Preferred video format", self.video_format_var, ["mp4", "mov", "webm", "avi"])
        self._entry_row(body, 2, "Task workers (parallel jobs)", self.max_workers_var)

        ctk.CTkCheckBox(
            body,
            text="Confirm before destructive actions (delete, overwrite)",
            variable=self.confirm_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(SPACE_SM, 0))
        ctk.CTkCheckBox(
            body, text="Show toast notifications", variable=self.toast_var
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(SPACE_SM, 0))

        # Folders
        folders_card = Card(self, title="Working folders", padding=SPACE_MD)
        folders_card.grid(row=3, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = folders_card.body
        body.grid_columnconfigure(0, weight=1)

        for row_idx, (key, label, helper) in enumerate(FOLDER_FIELDS):
            FolderPicker(body, label, self.folder_vars[key], helper=helper).grid(
                row=row_idx, column=0, sticky="ew", pady=SPACE_SM
            )

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(0, SPACE_MD))
        footer.grid_columnconfigure(0, weight=1)

        GhostButton(footer, text=f"{GLYPH['refresh']}  Reset to defaults", command=self.reset_defaults).grid(
            row=0, column=0, sticky="w"
        )
        PrimaryButton(footer, text=f"{GLYPH['check']}  Save settings", command=self.save_settings, width=160).grid(
            row=0, column=1, sticky="e"
        )

    # ------------------------------------------------------------------
    def _option_row(self, parent, row, label, variable, values):
        ctk.CTkLabel(parent, text=label, width=160, anchor="w").grid(row=row, column=0, sticky="w", pady=SPACE_SM)
        ctk.CTkOptionMenu(parent, values=values, variable=variable).grid(row=row, column=1, sticky="ew", pady=SPACE_SM)

    def _entry_row(self, parent, row, label, variable):
        ctk.CTkLabel(parent, text=label, width=160, anchor="w").grid(row=row, column=0, sticky="w", pady=SPACE_SM)
        ctk.CTkEntry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=SPACE_SM)

    def _make_swatch(self, parent, name: str):
        palette = ACCENT_PALETTES[name]
        container = ctk.CTkFrame(parent, fg_color="transparent")
        dot = ctk.CTkButton(
            container,
            text="",
            width=42,
            height=42,
            corner_radius=21,
            fg_color=palette["primary"],
            hover_color=palette["primary_hover"],
            command=lambda n=name: self._pick_accent(n),
        )
        dot.grid(row=0, column=0)
        label = ctk.CTkLabel(
            container,
            text=name,
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLOR_MUTED,
        )
        label.grid(row=1, column=0, pady=(SPACE_SM, 0))
        container._dot = dot  # noqa: SLF001
        container._label = label  # noqa: SLF001
        return container

    def _refresh_swatches(self):
        active = self.accent_var.get()
        for name, widget in self._swatch_widgets.items():
            if name == active:
                widget._label.configure(text_color=("#111827", "#E5E7EB"), font=ctk.CTkFont(size=FONT_SMALL, weight="bold"))
                widget._dot.configure(border_width=3, border_color=("#111827", "#E5E7EB"))
            else:
                widget._label.configure(text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL))
                widget._dot.configure(border_width=0)

    def _pick_accent(self, name: str):
        self.accent_var.set(name)
        self._refresh_swatches()
        top = self.winfo_toplevel()
        if hasattr(top, "apply_accent"):
            top.apply_accent(name)

    def _on_theme_change(self, value: str):
        ctk.set_appearance_mode(value)
        if self.app_state:
            self.app_state.settings["theme"] = value
            self.app_state.save_settings()

    # ------------------------------------------------------------------
    def save_settings(self):
        if not self.app_state:
            return
        try:
            workers = max(1, int(self.max_workers_var.get() or "1"))
        except ValueError:
            messagebox.showerror("Invalid", "Worker count must be a whole number.")
            return

        updates = {
            "theme": self.theme_var.get(),
            "accent": self.accent_var.get(),
            "preferred_image_format": self.image_format_var.get().strip(),
            "preferred_video_format": self.video_format_var.get().strip(),
            "max_workers": workers,
            "confirm_destructive": bool(self.confirm_var.get()),
            "enable_toasts": bool(self.toast_var.get()),
        }
        for key, _label, _helper in FOLDER_FIELDS:
            value = self.folder_vars[key].get().strip()
            updates[key] = value
            if value:
                try:
                    os.makedirs(value, exist_ok=True)
                except OSError:
                    pass
        self.app_state.update_settings(updates)
        ctk.set_appearance_mode(updates["theme"])
        top = self.winfo_toplevel()
        if hasattr(top, "apply_accent"):
            top.apply_accent(updates["accent"])

    def reset_defaults(self):
        defaults = _default_settings()
        for key in ("theme", "accent", "preferred_image_format", "preferred_video_format", "max_workers"):
            value = defaults.get(key, "")
            var = getattr(self, f"{key.split('_')[0]}_var", None)
            if var is None:
                continue
        # Apply individual vars
        self.theme_var.set(defaults.get("theme", "Dark"))
        self.accent_var.set(defaults.get("accent", "Blue"))
        self.image_format_var.set(defaults.get("preferred_image_format", "png"))
        self.video_format_var.set(defaults.get("preferred_video_format", "mp4"))
        self.max_workers_var.set(str(defaults.get("max_workers", 2)))
        self.confirm_var.set(defaults.get("confirm_destructive", True))
        self.toast_var.set(defaults.get("enable_toasts", True))
        for key, _label, _helper in FOLDER_FIELDS:
            self.folder_vars[key].set(defaults.get(key, ""))
        self._refresh_swatches()
