"""Task queue + activity log viewer."""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List

import customtkinter as ctk

from core.theme import (
    COLOR_CARD_BG,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_H3,
    FONT_SMALL,
    GLYPH,
    RADIUS,
    RADIUS_SM,
    SPACE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    STATUS_COLORS,
)
from core.ui_helpers import (
    Card,
    DangerButton,
    GhostButton,
    KeyValueGrid,
    PageHeader,
    PrimaryButton,
    StatusBadge,
)


FILTERS = ["All", "Queued", "Running", "Completed", "Failed", "Cancelled"]


class TaskQueueFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state
        self.task_map: Dict[int, object] = {}
        self.selected_task_id: int | None = None

        self.filter_var = ctk.StringVar(value="All")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_tasks())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_ui()

        if self.app_state:
            self.app_state.subscribe("tasks", self._on_tasks)
            self.app_state.subscribe("logs", self._on_log)
            self._on_tasks(self.app_state.task_history)
            for entry in self.app_state.log_entries[-200:]:
                self._append_log(entry)

    # ------------------------------------------------------------------
    def _build_ui(self):
        PageHeader(
            self,
            title="Task Queue",
            subtitle="Background jobs, history, and live log output. Cancel or rerun any task.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # Left: task list
        left = Card(content, title="Tasks", padding=SPACE_MD)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))
        body = left.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        search_row = ctk.CTkFrame(body, fg_color="transparent")
        search_row.grid(row=0, column=0, sticky="ew")
        search_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            search_row,
            textvariable=self.search_var,
            placeholder_text=f"{GLYPH['search']}  Search tasks…",
            corner_radius=RADIUS,
        ).grid(row=0, column=0, sticky="ew")

        filter_row = ctk.CTkSegmentedButton(
            body,
            values=FILTERS,
            variable=self.filter_var,
            command=lambda _v: self._refresh_tasks(),
        )
        filter_row.grid(row=1, column=0, sticky="ew", pady=(SPACE_SM, SPACE_SM))

        self.task_panel = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self.task_panel.grid(row=2, column=0, sticky="nsew")
        self.task_panel.grid_columnconfigure(0, weight=1)

        # Right: details + log
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(SPACE_SM, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        detail_card = Card(right, title="Task details", padding=SPACE_MD)
        detail_card.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        detail_card.body.grid_columnconfigure(0, weight=1)
        self.detail_grid = KeyValueGrid(detail_card.body)
        self.detail_grid.grid(row=0, column=0, sticky="ew")
        self.detail_empty = ctk.CTkLabel(
            detail_card.body,
            text="Select a task to see its metadata.",
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.detail_empty.grid(row=1, column=0, sticky="ew", pady=(SPACE_SM, 0))
        self.detail_actions = ctk.CTkFrame(detail_card.body, fg_color="transparent")
        self.detail_actions.grid(row=2, column=0, sticky="ew", pady=(SPACE_SM, 0))
        self.rerun_btn = PrimaryButton(self.detail_actions, text="Rerun", command=self._rerun_selected, width=120)
        self.cancel_btn = DangerButton(self.detail_actions, text="Cancel", command=self._cancel_selected, width=120)
        self.rerun_btn.pack(side="right", padx=(SPACE_SM, 0))
        self.cancel_btn.pack(side="right")
        self._toggle_action_buttons(False)

        log_card = Card(right, title="Activity log", padding=SPACE_MD)
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.body.grid_columnconfigure(0, weight=1)
        log_card.body.grid_rowconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(log_card.body, corner_radius=RADIUS_SM)
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

        controls = ctk.CTkFrame(log_card.body, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(SPACE_SM, 0))
        GhostButton(controls, text="Clear log view", command=self._clear_log).pack(side="right")

    # ------------------------------------------------------------------
    def _toggle_action_buttons(self, visible: bool):
        if visible:
            self.rerun_btn.pack(side="right", padx=(SPACE_SM, 0))
            self.cancel_btn.pack(side="right")
        else:
            self.rerun_btn.pack_forget()
            self.cancel_btn.pack_forget()

    def _filtered_tasks(self, tasks):
        keyword = self.search_var.get().strip().lower()
        target_status = self.filter_var.get()
        results = []
        for task in tasks:
            if target_status != "All" and task.status != target_status:
                continue
            haystack = f"{task.name} {task.description} {task.status}".lower()
            if keyword and keyword not in haystack:
                continue
            results.append(task)
        return results

    def _on_tasks(self, tasks):
        self.after(0, lambda snap=list(tasks): self._refresh_tasks(snap))

    def _refresh_tasks(self, snapshot=None):
        if snapshot is None and self.app_state:
            snapshot = list(self.app_state.task_history)
        snapshot = snapshot or []
        tasks = self._filtered_tasks(snapshot)
        for child in self.task_panel.winfo_children():
            child.destroy()
        self.task_map.clear()

        if not tasks:
            ctk.CTkLabel(
                self.task_panel,
                text="No tasks match the filters.",
                text_color=COLOR_MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", pady=SPACE_SM)
        else:
            for row, task in enumerate(tasks):
                self._render_task_row(row, task)
                self.task_map[task.task_id] = task

        if self.selected_task_id in self.task_map:
            self._show_task(self.task_map[self.selected_task_id])
        else:
            self.detail_grid.clear()
            self.detail_empty.grid()
            self._toggle_action_buttons(False)

    def _render_task_row(self, row: int, task):
        selected = self.selected_task_id == task.task_id
        frame = ctk.CTkFrame(
            self.task_panel,
            fg_color=COLOR_SUBTLE_BG if selected else "transparent",
            corner_radius=RADIUS_SM,
        )
        frame.grid(row=row, column=0, sticky="ew", pady=2)
        frame.grid_columnconfigure(1, weight=1)

        color = STATUS_COLORS.get(task.status, COLOR_MUTED)
        ctk.CTkLabel(
            frame, text="●", text_color=color, font=ctk.CTkFont(size=14, weight="bold"), width=16
        ).grid(row=0, column=0, rowspan=2, padx=(SPACE_SM, SPACE_SM), pady=SPACE_SM)
        ctk.CTkLabel(
            frame,
            text=f"#{task.task_id} · {task.name}",
            font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", pady=(SPACE_SM, 0))
        ctk.CTkLabel(
            frame,
            text=f"{task.status} · {task.description or '—'}",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_SMALL),
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", pady=(0, SPACE_SM))
        frame.bind("<Button-1>", lambda _e, t=task: self._show_task(t))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda _e, t=task: self._show_task(t))

        if task.status == "Running" and task.progress > 0:
            bar = ctk.CTkProgressBar(frame, height=4)
            bar.grid(row=2, column=1, sticky="ew", padx=(0, SPACE_SM), pady=(0, SPACE_SM))
            bar.set(task.progress)

    def _show_task(self, task):
        self.selected_task_id = task.task_id
        self.detail_grid.clear()
        self.detail_empty.grid_remove()
        self.detail_grid.add("ID", f"#{task.task_id}")
        self.detail_grid.add("Name", task.name)
        self.detail_grid.add("Description", task.description or "—")
        self.detail_grid.add("Status", task.status)
        self.detail_grid.add("Created", task.created_at)
        self.detail_grid.add("Started", task.started_at or "—")
        self.detail_grid.add("Completed", task.completed_at or "—")
        if task.duration_seconds is not None:
            self.detail_grid.add("Duration", f"{task.duration_seconds:.2f}s")
        if task.result:
            self.detail_grid.add("Result", task.result)
        if task.error:
            self.detail_grid.add("Error", task.error)
        self._toggle_action_buttons(True)

    def _rerun_selected(self):
        if self.app_state and self.selected_task_id is not None:
            self.app_state.rerun_task(self.selected_task_id)

    def _cancel_selected(self):
        if self.app_state and self.selected_task_id is not None:
            self.app_state.cancel_task(self.selected_task_id)

    # ------------------------------------------------------------------
    def _on_log(self, latest_entry: str, _all_entries: List[str]):
        self.after(0, lambda text=latest_entry: self._append_log(text))

    def _append_log(self, entry: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", entry + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
