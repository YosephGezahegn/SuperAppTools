"""SuperApp — entry point and application shell."""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Tuple

import customtkinter as ctk

from apps.backup_snapshot_frame import BackupSnapshotFrame
from apps.batch_renamer_frame import BatchRenamerFrame
from apps.dashboard_frame import DashboardFrame
from apps.duplicate_cleaner_frame import DuplicateCleanerFrame
from apps.file_organizer_frame import FileOrganizerFrame
from apps.image_studio_frame import ImageStudioFrame
from apps.quality_scaler_frame import QualityScalerFrame
from apps.screen_recorder_frame import ScreenRecorderFrame
from apps.settings_frame import SettingsFrame
from apps.task_queue_frame import TaskQueueFrame
from core.app_state import AppState
from core.theme import (
    ACCENT_PALETTES,
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DIVIDER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    FONT_BODY,
    FONT_H2,
    FONT_H3,
    FONT_SMALL,
    GLYPH,
    RADIUS,
    RADIUS_LG,
    RADIUS_SM,
    SIDEBAR_WIDTH,
    SPACE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    STATUS_BAR_HEIGHT,
    WINDOW_DEFAULT,
    WINDOW_MIN,
    ThemeContext,
)
from core.ui_helpers import GhostButton, ToastManager


# Navigation catalog: (frame_id, label, description, group, glyph, frame_class)
NAV_ITEMS: List[Tuple[str, str, str, str, str, type]] = [
    ("dashboard", "Dashboard", "Overview and quick actions", "Workspace", GLYPH["dashboard"], DashboardFrame),
    ("cleaner", "Duplicate Cleaner", "Find and remove duplicate files", "Files", GLYPH["cleaner"], DuplicateCleanerFrame),
    ("renamer", "Batch Renamer", "Template- and regex-based renaming", "Files", GLYPH["renamer"], BatchRenamerFrame),
    ("organizer", "File Organizer", "Sort files into folders by rules", "Files", GLYPH["organizer"], FileOrganizerFrame),
    ("snapshot", "Backup Snapshot", "Snapshot folders and restore on demand", "Files", GLYPH["snapshot"], BackupSnapshotFrame),
    ("scaler", "Quality + Compressor", "Upscale, compress, and trim media", "Media", GLYPH["scaler"], QualityScalerFrame),
    ("image_studio", "Image Studio", "Viewer, editor, OCR, and metadata", "Media", GLYPH["image_studio"], ImageStudioFrame),
    ("recorder", "Screen Recorder", "Capture your screen with audio", "Media", GLYPH["recorder"], ScreenRecorderFrame),
    ("tasks", "Task Queue", "Background jobs and log history", "System", GLYPH["tasks"], TaskQueueFrame),
    ("settings", "Settings", "Theme, accent color, and preferences", "System", GLYPH["settings"], SettingsFrame),
]


class SuperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.app_state = AppState()
        self.theme = ThemeContext(accent=self.app_state.settings.get("accent", "Blue"))

        ctk.set_appearance_mode(self.app_state.settings.get("theme", "Dark"))
        ctk.set_default_color_theme("blue")

        self.title("SuperApp — Creator Toolkit")
        self.geometry(f"{WINDOW_DEFAULT[0]}x{WINDOW_DEFAULT[1]}")
        self.minsize(*WINDOW_MIN)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.frames: Dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.nav_labels: Dict[str, str] = {frame_id: label for frame_id, label, *_ in NAV_ITEMS}
        self.active_frame_id = ""

        self._build_sidebar()
        self._build_container()
        self._build_status_bar()

        self._init_frames()
        self._load_plugins()

        self.toasts = ToastManager(self, self.app_state)
        self.app_state.subscribe("notifications", self._on_notification_status)
        self.app_state.subscribe("tasks", self._on_tasks_update)
        self.app_state.subscribe("settings", self._on_settings_update)

        self._bind_shortcuts()

        initial = self.app_state.settings.get("last_frame") or "dashboard"
        if initial not in self.frames:
            initial = "dashboard"
        self.show_frame(initial)
        self._refresh_nav_accent()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=COLOR_SUBTLE_BG)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_LG, SPACE))
        brand.grid_columnconfigure(1, weight=1)

        logo_mark = ctk.CTkLabel(
            brand,
            text="◆",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.theme.primary,
        )
        logo_mark.grid(row=0, column=0, sticky="w")
        self._logo_mark = logo_mark

        ctk.CTkLabel(
            brand,
            text="SuperApp",
            font=ctk.CTkFont(size=FONT_H2, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, padx=(SPACE_SM, 0), sticky="w")
        ctk.CTkLabel(
            brand,
            text="Creator Toolkit",
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLOR_MUTED,
            anchor="w",
        ).grid(row=1, column=1, padx=(SPACE_SM, 0), sticky="w")

        # Command palette trigger
        palette_btn = GhostButton(
            self.sidebar,
            text=f"{GLYPH['search']}   Search tools…   ⌘K",
            command=self.open_command_palette,
        )
        palette_btn.grid(row=1, column=0, padx=SPACE_MD, pady=(0, SPACE), sticky="ew")

        # Scrollable nav list
        self.nav_scroll = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLOR_DIVIDER,
        )
        self.nav_scroll.grid(row=2, column=0, sticky="nsew", padx=SPACE_SM, pady=0)
        self.nav_scroll.grid_columnconfigure(0, weight=1)

        # Footer
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=SPACE_MD, pady=SPACE_MD)
        footer.grid_columnconfigure(0, weight=1)

        self.theme_toggle = GhostButton(
            footer,
            text=self._theme_button_text(),
            command=self.toggle_theme,
        )
        self.theme_toggle.grid(row=0, column=0, sticky="ew")

    def _build_nav_sections(self):
        for child in self.nav_scroll.winfo_children():
            child.destroy()
        self.nav_buttons.clear()

        groups: Dict[str, List[Tuple[str, str, str]]] = {}
        for frame_id, label, _desc, group, glyph, _cls in NAV_ITEMS:
            groups.setdefault(group, []).append((frame_id, label, glyph))

        row = 0
        for group_name, entries in groups.items():
            ctk.CTkLabel(
                self.nav_scroll,
                text=group_name.upper(),
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
                anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=SPACE, pady=(SPACE_SM, 2))
            row += 1
            for frame_id, label, glyph in entries:
                self._add_nav_button(row, frame_id, label, glyph)
                row += 1

        # Plugin nav rendered later (after _init_frames) but fall back if empty
        if getattr(self, "_plugin_entries", None):
            ctk.CTkLabel(
                self.nav_scroll,
                text="PLUGINS",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
                anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=SPACE, pady=(SPACE_SM, 2))
            row += 1
            for frame_id, label in self._plugin_entries:
                self._add_nav_button(row, frame_id, label, GLYPH["plugin"])
                row += 1

    def _add_nav_button(self, row: int, frame_id: str, label: str, glyph: str):
        btn = ctk.CTkButton(
            self.nav_scroll,
            text=f"  {glyph}   {label}",
            anchor="w",
            height=34,
            corner_radius=RADIUS,
            fg_color="transparent",
            hover_color=COLOR_CARD_BG,
            text_color=("#111827", "#E5E7EB"),
            font=ctk.CTkFont(size=FONT_BODY),
            command=lambda key=frame_id: self.show_frame(key),
        )
        btn.grid(row=row, column=0, padx=SPACE_SM, pady=1, sticky="ew")
        self.nav_buttons[frame_id] = btn

    def _build_container(self):
        self.container = ctk.CTkFrame(self, fg_color=("#F9FAFB", "#161618"), corner_radius=0)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, height=STATUS_BAR_HEIGHT, fg_color=COLOR_SUBTLE_BG)
        self.status_bar.grid(row=1, column=1, sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text=f"{GLYPH['dot']}  Ready",
            anchor="w",
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLOR_MUTED,
        )
        self.status_label.grid(row=0, column=0, padx=SPACE_MD, pady=SPACE_SM, sticky="w")

        self.queue_indicator = ctk.CTkLabel(
            self.status_bar,
            text="",
            anchor="e",
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLOR_MUTED,
        )
        self.queue_indicator.grid(row=0, column=1, padx=SPACE_MD, pady=SPACE_SM, sticky="e")

        self.accent_indicator = ctk.CTkLabel(
            self.status_bar,
            text=f"Accent · {self.theme.accent}",
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLOR_MUTED,
        )
        self.accent_indicator.grid(row=0, column=2, padx=(SPACE_SM, SPACE_MD), pady=SPACE_SM, sticky="e")

    # ------------------------------------------------------------------
    # Frame loading
    # ------------------------------------------------------------------
    def _init_frames(self):
        self._plugin_entries: List[Tuple[str, str]] = []
        self._build_nav_sections()
        for frame_id, _label, _desc, _group, _glyph, frame_cls in NAV_ITEMS:
            try:
                self.frames[frame_id] = frame_cls(self.container, app_state=self.app_state)
            except Exception as exc:  # noqa: BLE001
                self.app_state.log(f"Failed to initialise frame {frame_id}: {exc}")
                self.frames[frame_id] = self._build_error_frame(frame_id, exc)

    def _load_plugins(self):
        for plugin in self.app_state.load_plugins():
            try:
                frame = plugin.build_frame(self.container, self.app_state)
                self.frames[plugin.plugin_id] = frame
                self._plugin_entries.append((plugin.plugin_id, plugin.button_text))
                self.nav_labels[plugin.plugin_id] = plugin.button_text
            except Exception as exc:  # noqa: BLE001
                self.app_state.log(f"Plugin {plugin.plugin_id} failed: {exc}")
        self._build_nav_sections()

    def _build_error_frame(self, frame_id: str, exc: Exception):
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkLabel(
            frame,
            text=f"Couldn't load {frame_id}:\n{exc}",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_BODY),
            justify="left",
        ).pack(padx=SPACE_LG, pady=SPACE_LG)
        return frame

    # ------------------------------------------------------------------
    # Navigation + theming
    # ------------------------------------------------------------------
    def show_frame(self, name: str):
        if name not in self.frames:
            return
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[name].grid(row=0, column=0, sticky="nsew", padx=SPACE_LG, pady=SPACE_LG)
        self.active_frame_id = name
        self._refresh_nav_accent()
        self.app_state.settings["last_frame"] = name
        try:
            self.app_state.save_settings()
        except Exception:  # noqa: BLE001
            pass

    def _refresh_nav_accent(self):
        for frame_id, btn in self.nav_buttons.items():
            if frame_id == self.active_frame_id:
                btn.configure(fg_color=self.theme.soft, text_color=self.theme.primary)
            else:
                btn.configure(fg_color="transparent", text_color=("#111827", "#E5E7EB"))
        self._logo_mark.configure(text_color=self.theme.primary)
        self.accent_indicator.configure(text=f"Accent · {self.theme.accent}")

    def apply_accent(self, accent: str):
        if accent not in ACCENT_PALETTES:
            accent = "Blue"
        self.theme.accent = accent
        self.app_state.settings["accent"] = accent
        self.app_state.save_settings()
        self._refresh_nav_accent()
        self.app_state.emit("accent_changed", accent)

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        target = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(target)
        self.app_state.settings["theme"] = target
        self.app_state.save_settings()
        self.theme_toggle.configure(text=self._theme_button_text())

    def _theme_button_text(self):
        mode = ctk.get_appearance_mode()
        symbol = "☾" if mode == "Dark" else "☀"
        return f"  {symbol}   Appearance · {mode}"

    # ------------------------------------------------------------------
    # Command palette
    # ------------------------------------------------------------------
    def open_command_palette(self, *_):
        if getattr(self, "_palette", None) and self._palette.winfo_exists():
            self._palette.focus_set()
            return
        self._palette = CommandPalette(self, nav_items=NAV_ITEMS, on_select=self.show_frame)

    # ------------------------------------------------------------------
    # Status bar callbacks
    # ------------------------------------------------------------------
    def _on_notification_status(self, message: str, _level: str = "info"):
        self.after(0, lambda: self.status_label.configure(text=f"{GLYPH['dot']}  {message}"))

    def _on_tasks_update(self, tasks):
        running = sum(1 for t in tasks if t.status == "Running")
        queued = sum(1 for t in tasks if t.status == "Queued")
        if running or queued:
            text = f"{GLYPH['clock']}  {running} running · {queued} queued"
        else:
            completed = sum(1 for t in tasks if t.status == "Completed")
            text = f"{GLYPH['check']}  {completed} task{'s' if completed != 1 else ''} complete"
        self.after(0, lambda: self.queue_indicator.configure(text=text))

    def _on_settings_update(self, settings):
        accent = settings.get("accent", "Blue")
        if accent != self.theme.accent:
            self.theme.accent = accent
            self._refresh_nav_accent()

    # ------------------------------------------------------------------
    # Shortcuts + lifecycle
    # ------------------------------------------------------------------
    def _bind_shortcuts(self):
        self.bind_all("<Command-k>", self.open_command_palette)
        self.bind_all("<Control-k>", self.open_command_palette)
        self.bind_all("<Command-1>", lambda e: self.show_frame("dashboard"))
        self.bind_all("<Command-,>", lambda e: self.show_frame("settings"))
        self.bind_all("<Control-comma>", lambda e: self.show_frame("settings"))
        self.bind_all("<Command-l>", lambda e: self.toggle_theme())
        self.bind_all("<Control-l>", lambda e: self.toggle_theme())

    def _on_close(self):
        try:
            self.app_state.shutdown()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()


class CommandPalette(ctk.CTkToplevel):
    """A lightweight fuzzy-search launcher inspired by modern editors."""

    def __init__(self, master: SuperApp, nav_items, on_select):
        super().__init__(master)
        self.title("Command Palette")
        self.geometry("520x420")
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        self.configure(fg_color=("#FFFFFF", "#1E1E21"))
        self._nav_items = nav_items
        self._on_select = on_select
        self._results: List[tuple] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.query_var = tk.StringVar()
        self.query_var.trace_add("write", lambda *_: self._refresh())

        entry = ctk.CTkEntry(
            self,
            textvariable=self.query_var,
            placeholder_text="Search tools, frames, or settings…",
            corner_radius=RADIUS,
            height=42,
        )
        entry.grid(row=0, column=0, padx=SPACE_MD, pady=SPACE_MD, sticky="ew")
        entry.focus_set()
        entry.bind("<Return>", self._activate_selection)
        entry.bind("<Down>", self._move_down)
        entry.bind("<Up>", self._move_up)
        entry.bind("<Escape>", lambda e: self.destroy())

        self.results_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results_frame.grid(row=1, column=0, padx=SPACE_MD, pady=(0, SPACE_MD), sticky="nsew")
        self.results_frame.grid_columnconfigure(0, weight=1)

        self._selected_index = 0
        self._refresh()

    def _refresh(self):
        query = self.query_var.get().strip().lower()
        results = []
        for frame_id, label, desc, group, glyph, _cls in self._nav_items:
            haystack = f"{label} {desc} {group}".lower()
            if not query or query in haystack:
                results.append((frame_id, label, desc, group, glyph))
        self._results = results
        self._selected_index = 0
        self._render_results()

    def _render_results(self):
        for child in self.results_frame.winfo_children():
            child.destroy()
        if not self._results:
            ctk.CTkLabel(
                self.results_frame,
                text="No matches",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_BODY),
            ).grid(row=0, column=0, padx=SPACE, pady=SPACE_MD)
            return
        for idx, (frame_id, label, desc, group, glyph) in enumerate(self._results):
            selected = idx == self._selected_index
            row = ctk.CTkFrame(
                self.results_frame,
                fg_color=COLOR_CARD_BG if selected else "transparent",
                corner_radius=RADIUS_SM,
            )
            row.grid(row=idx, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                row, text=glyph, width=28, font=ctk.CTkFont(size=FONT_H3, weight="bold")
            ).grid(row=0, column=0, rowspan=2, padx=(SPACE_SM, SPACE), pady=SPACE_SM)
            ctk.CTkLabel(
                row, text=label, font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w"
            ).grid(row=0, column=1, sticky="ew", pady=(SPACE_SM, 0))
            ctk.CTkLabel(
                row,
                text=f"{group}  ·  {desc}",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_SMALL),
                anchor="w",
            ).grid(row=1, column=1, sticky="ew", pady=(0, SPACE_SM))
            row.bind("<Button-1>", lambda _e, key=frame_id: self._pick(key))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda _e, key=frame_id: self._pick(key))

    def _pick(self, frame_id: str):
        self.destroy()
        self._on_select(frame_id)

    def _activate_selection(self, _event=None):
        if not self._results:
            return
        frame_id = self._results[self._selected_index][0]
        self._pick(frame_id)

    def _move_down(self, _event=None):
        if self._results:
            self._selected_index = (self._selected_index + 1) % len(self._results)
            self._render_results()
        return "break"

    def _move_up(self, _event=None):
        if self._results:
            self._selected_index = (self._selected_index - 1) % len(self._results)
            self._render_results()
        return "break"


if __name__ == "__main__":
    app = SuperApp()
    app.mainloop()
