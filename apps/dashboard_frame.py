"""Dashboard / home frame for SuperApp."""

from __future__ import annotations

from datetime import datetime
from typing import List

import customtkinter as ctk

from core.theme import (
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_H1,
    FONT_H2,
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
    STATUS_COLORS,
)
from core.ui_helpers import Card, GhostButton, PageHeader, PrimaryButton


QUICK_ACTIONS = [
    ("cleaner", "Duplicate Cleaner", "Reclaim space from duplicated files.", GLYPH["cleaner"]),
    ("renamer", "Batch Renamer", "Template- or regex-rename in seconds.", GLYPH["renamer"]),
    ("scaler", "Quality + Compressor", "Upscale, compress, trim media.", GLYPH["scaler"]),
    ("organizer", "File Organizer", "Sort a messy folder by type, date, size.", GLYPH["organizer"]),
    ("recorder", "Screen Recorder", "Capture screen + audio to MP4.", GLYPH["recorder"]),
    ("image_studio", "Image Studio", "View, edit, OCR, and export images.", GLYPH["image_studio"]),
]


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 5:
        return "Working late"
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_header()
        self._build_stats()
        self._build_quick_actions()
        self._build_recent_columns()

        if self.app_state:
            self.app_state.subscribe("tasks", self._refresh_tasks)
            self.app_state.subscribe("settings", lambda _settings: self._refresh_recent())
            self._refresh_tasks(self.app_state.task_history)
            self._refresh_recent()

    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = f"{_greeting()} — welcome back"
        subtitle = (
            "Pick a tool below or press ⌘K (Ctrl+K) to search. "
            "All background jobs run in the Task Queue while you keep working."
        )
        PageHeader(header, title=title, subtitle=subtitle).grid(row=0, column=0, sticky="ew")

        buttons = ctk.CTkFrame(header, fg_color="transparent")
        buttons.grid(row=0, column=1, sticky="e")
        PrimaryButton(
            buttons,
            text=f"{GLYPH['search']}  Command palette",
            width=180,
            command=lambda: self._activate_palette(),
        ).pack(side="right")

    def _activate_palette(self):
        top = self.winfo_toplevel()
        if hasattr(top, "open_command_palette"):
            top.open_command_palette()

    # ------------------------------------------------------------------
    def _build_stats(self):
        stats_row = ctk.CTkFrame(self, fg_color="transparent")
        stats_row.grid(row=1, column=0, sticky="ew", pady=(SPACE_LG, SPACE_MD))
        for col in range(4):
            stats_row.grid_columnconfigure(col, weight=1, uniform="stats")

        self._stat_cards = {}
        for col, (key, label, glyph) in enumerate(
            [
                ("Queued", "Queued", GLYPH["clock"]),
                ("Running", "Running", GLYPH["play"]),
                ("Completed", "Completed", GLYPH["check"]),
                ("Failed", "Failed", GLYPH["warn"]),
            ]
        ):
            card = Card(stats_row, padding=SPACE_MD)
            card.grid(row=0, column=col, sticky="nsew", padx=SPACE_SM)
            body = card.body
            body.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                body,
                text=f"{glyph}  {label}",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            value = ctk.CTkLabel(
                body,
                text="0",
                font=ctk.CTkFont(size=FONT_DISPLAY, weight="bold"),
                text_color=STATUS_COLORS.get(key, COLOR_MUTED),
                anchor="w",
            )
            value.grid(row=1, column=0, sticky="w", pady=(SPACE_SM, 0))
            self._stat_cards[key] = value

    # ------------------------------------------------------------------
    def _build_quick_actions(self):
        card = Card(self, title="Quick actions", padding=SPACE_MD)
        card.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        body = card.body
        for col in range(3):
            body.grid_columnconfigure(col, weight=1, uniform="qa")

        for i, (frame_id, label, desc, glyph) in enumerate(QUICK_ACTIONS):
            row, col = divmod(i, 3)
            tile = ctk.CTkFrame(
                body,
                fg_color=COLOR_SUBTLE_BG,
                corner_radius=RADIUS_LG,
            )
            tile.grid(row=row, column=col, padx=SPACE_SM, pady=SPACE_SM, sticky="nsew")
            tile.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                tile,
                text=glyph,
                font=ctk.CTkFont(size=22, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, padx=SPACE_MD, pady=(SPACE_MD, 0), sticky="w")
            ctk.CTkLabel(
                tile,
                text=label,
                font=ctk.CTkFont(size=FONT_H3, weight="bold"),
                anchor="w",
            ).grid(row=1, column=0, padx=SPACE_MD, pady=(SPACE_SM, 0), sticky="w")
            ctk.CTkLabel(
                tile,
                text=desc,
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
                anchor="w",
                justify="left",
                wraplength=260,
            ).grid(row=2, column=0, padx=SPACE_MD, pady=(2, SPACE_SM), sticky="w")

            open_btn = GhostButton(
                tile,
                text=f"Open  {GLYPH['arrow']}",
                command=lambda key=frame_id: self._navigate(key),
                height=30,
            )
            open_btn.grid(row=3, column=0, padx=SPACE_MD, pady=(0, SPACE_MD), sticky="w")

    def _navigate(self, frame_id: str):
        top = self.winfo_toplevel()
        if hasattr(top, "show_frame"):
            top.show_frame(frame_id)

    # ------------------------------------------------------------------
    def _build_recent_columns(self):
        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.grid(row=3, column=0, sticky="nsew")
        columns.grid_columnconfigure((0, 1), weight=1)
        columns.grid_rowconfigure(0, weight=1)

        # Recent tasks
        self.tasks_card = Card(columns, title="Recent tasks", padding=SPACE_MD)
        self.tasks_card.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))
        self.tasks_card.body.grid_rowconfigure(0, weight=1)
        self.tasks_body = ctk.CTkFrame(self.tasks_card.body, fg_color="transparent")
        self.tasks_body.grid(row=0, column=0, sticky="nsew")
        self.tasks_body.grid_columnconfigure(0, weight=1)

        # Recent folders + shortcuts
        self.side_card = Card(columns, title="Recent folders & tips", padding=SPACE_MD)
        self.side_card.grid(row=0, column=1, sticky="nsew", padx=(SPACE_SM, 0))
        self.side_card.body.grid_rowconfigure(1, weight=1)
        self.recent_body = ctk.CTkFrame(self.side_card.body, fg_color="transparent")
        self.recent_body.grid(row=0, column=0, sticky="nsew")
        self.recent_body.grid_columnconfigure(0, weight=1)

        tips = ctk.CTkFrame(self.side_card.body, fg_color="transparent")
        tips.grid(row=1, column=0, sticky="ew", pady=(SPACE_MD, 0))
        for label in (
            f"{GLYPH['dot']}  ⌘K / Ctrl+K — open the command palette",
            f"{GLYPH['dot']}  ⌘L / Ctrl+L — toggle light/dark",
            f"{GLYPH['dot']}  ⌘, / Ctrl+,  — open Settings",
            f"{GLYPH['dot']}  Drop a folder path into any input",
        ):
            ctk.CTkLabel(
                tips,
                text=label,
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
                anchor="w",
            ).pack(anchor="w", pady=2)

    # ------------------------------------------------------------------
    def _refresh_tasks(self, tasks: List):
        self.after(0, lambda snapshot=list(tasks[:6]): self._render_tasks(snapshot))

    def _render_tasks(self, tasks):
        if self.app_state:
            counts = self.app_state.task_stats()
            for key, label_widget in self._stat_cards.items():
                label_widget.configure(text=str(counts.get(key, 0)))

        for child in self.tasks_body.winfo_children():
            child.destroy()

        if not tasks:
            ctk.CTkLabel(
                self.tasks_body,
                text="No tasks yet. Actions from any tool will queue up here.",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_BODY),
                anchor="w",
                justify="left",
            ).grid(row=0, column=0, sticky="w", pady=SPACE_SM)
            return

        for row_idx, task in enumerate(tasks):
            row = ctk.CTkFrame(self.tasks_body, fg_color=COLOR_SUBTLE_BG, corner_radius=RADIUS_SM)
            row.grid(row=row_idx, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)

            color = STATUS_COLORS.get(task.status, COLOR_MUTED)
            ctk.CTkLabel(row, text="●", text_color=color, font=ctk.CTkFont(size=14, weight="bold"), width=18).grid(
                row=0, column=0, rowspan=2, padx=(SPACE, SPACE_SM), pady=SPACE_SM
            )
            ctk.CTkLabel(
                row,
                text=f"#{task.task_id} · {task.name}",
                font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, sticky="ew", pady=(SPACE_SM, 0))
            ctk.CTkLabel(
                row,
                text=f"{task.status} · {task.description or '—'}",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
                anchor="w",
            ).grid(row=1, column=1, sticky="ew", pady=(0, SPACE_SM))

        ctk.CTkButton(
            self.tasks_body,
            text=f"Open Task Queue  {GLYPH['arrow']}",
            fg_color="transparent",
            hover_color=COLOR_SUBTLE_BG,
            anchor="w",
            command=lambda: self._navigate("tasks"),
        ).grid(row=len(tasks), column=0, sticky="ew", pady=(SPACE_SM, 0))

    # ------------------------------------------------------------------
    def _refresh_recent(self):
        for child in self.recent_body.winfo_children():
            child.destroy()

        recents = []
        if self.app_state:
            recents = self.app_state.settings.get("recent_folders", [])

        if not recents:
            ctk.CTkLabel(
                self.recent_body,
                text="Folders you browse to will appear here.",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_BODY),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=SPACE_SM)
            return

        for idx, path in enumerate(recents[:6]):
            row = ctk.CTkFrame(self.recent_body, fg_color=COLOR_SUBTLE_BG, corner_radius=RADIUS_SM)
            row.grid(row=idx, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row,
                text=f"{GLYPH['folder']}  {path}",
                anchor="w",
                font=ctk.CTkFont(size=FONT_BODY),
            ).grid(row=0, column=0, sticky="ew", padx=SPACE, pady=SPACE_SM)
