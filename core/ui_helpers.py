"""Reusable UI primitives for SuperApp frames.

Provides:
    * PageHeader      - consistent title + subtitle banner
    * Card            - rounded container with optional heading
    * FolderPicker    - labelled entry + browse button
    * FilePicker      - labelled entry + browse button (files)
    * FileDropList    - scrollable chip list with drag/drop style UX
    * Toast           - transient notification manager
    * StatusBadge     - coloured pill reflecting a status string
    * PrimaryButton / DangerButton / GhostButton / SuccessButton
    * Divider         - thin horizontal rule
    * KeyValueGrid    - two-column key/value rows
"""

import os
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Iterable, List, Optional

import customtkinter as ctk

from core.theme import (
    COLOR_CARD_BG,
    COLOR_CARD_BORDER,
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_DIVIDER,
    COLOR_MUTED,
    COLOR_SUBTLE_BG,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    FONT_BODY,
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


# ---------------------------------------------------------------------------
# Headers / layout chrome
# ---------------------------------------------------------------------------


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=FONT_H1, weight="bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_BODY),
            anchor="w",
            justify="left",
        )
        if subtitle:
            self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def set_subtitle(self, text: str):
        self.subtitle_label.configure(text=text)
        if text:
            self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        else:
            self.subtitle_label.grid_forget()


class Card(ctk.CTkFrame):
    """A rounded, bordered container with consistent padding."""

    def __init__(self, master, title: str = "", padding: int = SPACE_MD, **kwargs):
        kwargs.setdefault("fg_color", COLOR_CARD_BG)
        kwargs.setdefault("border_color", COLOR_CARD_BORDER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("corner_radius", RADIUS_LG)
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._padding = padding
        self._title_row = 0

        if title:
            self.title_label = ctk.CTkLabel(
                self,
                text=title,
                font=ctk.CTkFont(size=FONT_H3, weight="bold"),
                anchor="w",
            )
            self.title_label.grid(
                row=0, column=0, padx=padding, pady=(padding, SPACE_SM), sticky="ew"
            )
            self._title_row = 1

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(
            row=self._title_row,
            column=0,
            padx=padding,
            pady=(0 if title else padding, padding),
            sticky="nsew",
        )
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(self._title_row, weight=1)


class Divider(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=1, fg_color=COLOR_DIVIDER, **kwargs)


class StatusBadge(ctk.CTkLabel):
    def __init__(self, master, status: str = "Queued", **kwargs):
        color = STATUS_COLORS.get(status, COLOR_MUTED)
        super().__init__(
            master,
            text=status,
            fg_color=color,
            text_color=("#FFFFFF", "#FFFFFF"),
            corner_radius=RADIUS_SM,
            padx=SPACE_SM,
            pady=2,
            font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
            **kwargs,
        )

    def set_status(self, status: str):
        self.configure(text=status, fg_color=STATUS_COLORS.get(status, COLOR_MUTED))


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------


def _make_button(master, text, command, fg, hover, **kwargs):
    kwargs.setdefault("corner_radius", RADIUS)
    kwargs.setdefault("height", 36)
    kwargs.setdefault("font", ctk.CTkFont(size=FONT_BODY, weight="bold"))
    return ctk.CTkButton(
        master, text=text, command=command, fg_color=fg, hover_color=hover, **kwargs
    )


def PrimaryButton(master, text, command=None, **kwargs):
    return _make_button(master, text, command, ("#2F7DD8", "#1F6AA5"), ("#256AB8", "#185784"), **kwargs)


def DangerButton(master, text, command=None, **kwargs):
    return _make_button(master, text, command, COLOR_DANGER, COLOR_DANGER_HOVER, **kwargs)


def SuccessButton(master, text, command=None, **kwargs):
    return _make_button(master, text, command, COLOR_SUCCESS, COLOR_SUCCESS_HOVER, **kwargs)


def GhostButton(master, text, command=None, **kwargs):
    kwargs.setdefault("corner_radius", RADIUS)
    kwargs.setdefault("height", 36)
    kwargs.setdefault("font", ctk.CTkFont(size=FONT_BODY))
    kwargs.setdefault("border_width", 1)
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        fg_color="transparent",
        hover_color=COLOR_SUBTLE_BG,
        text_color=("#111827", "#E5E7EB"),
        border_color=COLOR_CARD_BORDER,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Folder / file pickers
# ---------------------------------------------------------------------------


class FolderPicker(ctk.CTkFrame):
    def __init__(self, master, label: str, variable: ctk.StringVar, *, helper: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.variable = variable

        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.entry = ctk.CTkEntry(self, textvariable=variable, corner_radius=RADIUS)
        self.entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        browse = GhostButton(self, text=f"{GLYPH['folder']}  Browse", command=self._browse, width=110)
        browse.grid(row=1, column=2, sticky="e", padx=(SPACE_SM, 0), pady=(4, 0))

        if helper:
            ctk.CTkLabel(
                self, text=helper, text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL), anchor="w"
            ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))

    def _browse(self):
        start = self.variable.get() if self.variable.get() and os.path.isdir(self.variable.get()) else None
        path = filedialog.askdirectory(initialdir=start)
        if path:
            self.variable.set(path)


class FilePicker(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label: str,
        variable: ctk.StringVar,
        filetypes: Optional[list] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.variable = variable
        self.filetypes = filetypes or [("All files", "*.*")]

        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.entry = ctk.CTkEntry(self, textvariable=variable, corner_radius=RADIUS)
        self.entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        GhostButton(self, text=f"{GLYPH['file']}  Browse", command=self._browse, width=110).grid(
            row=1, column=2, sticky="e", padx=(SPACE_SM, 0), pady=(4, 0)
        )

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=self.filetypes)
        if path:
            self.variable.set(path)


# ---------------------------------------------------------------------------
# Scrollable chip list for file/path collections
# ---------------------------------------------------------------------------


class FileDropList(ctk.CTkFrame):
    """A scrollable, virtualized list for file paths with remove buttons."""

    def __init__(
        self,
        master,
        on_add: Optional[Callable[[], None]] = None,
        on_add_folder: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        empty_hint: str = "No files yet. Click Add Files to get started.",
        **kwargs,
    ):
        kwargs.setdefault("fg_color", COLOR_SUBTLE_BG)
        kwargs.setdefault("corner_radius", RADIUS_LG)
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.empty_hint = empty_hint
        self._paths: List[str] = []

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=SPACE, pady=(SPACE, 0))
        header.grid_columnconfigure(3, weight=1)
        self.count_label = ctk.CTkLabel(
            header, text="0 files", font=ctk.CTkFont(size=FONT_BODY, weight="bold"), anchor="w"
        )
        self.count_label.grid(row=0, column=0, sticky="w")

        col = 1
        if on_add:
            GhostButton(header, text=f"{GLYPH['add']} Files", command=on_add, width=90).grid(
                row=0, column=col, padx=(SPACE_SM, 0)
            )
            col += 1
        if on_add_folder:
            GhostButton(header, text=f"{GLYPH['folder']} Folder", command=on_add_folder, width=90).grid(
                row=0, column=col, padx=(SPACE_SM, 0)
            )
            col += 1
        if on_clear:
            GhostButton(header, text=f"{GLYPH['refresh']} Clear", command=on_clear, width=90).grid(
                row=0, column=col + 1, sticky="e"
            )

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=SPACE, pady=SPACE)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self.scroll,
            text=self.empty_hint,
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_BODY),
            anchor="w",
            justify="left",
        )
        self._empty_label.grid(row=0, column=0, sticky="ew", pady=SPACE_SM)

    # Public API
    def paths(self) -> List[str]:
        return list(self._paths)

    def set_paths(self, paths: Iterable[str]):
        self._paths = list(paths)
        self._render()

    def add(self, paths: Iterable[str]):
        added = 0
        for p in paths:
            if p and p not in self._paths:
                self._paths.append(p)
                added += 1
        if added:
            self._render()
        return added

    def remove(self, path: str):
        if path in self._paths:
            self._paths.remove(path)
            self._render()

    def clear(self):
        self._paths.clear()
        self._render()

    def _render(self):
        for child in self.scroll.winfo_children():
            child.destroy()
        if not self._paths:
            self._empty_label = ctk.CTkLabel(
                self.scroll,
                text=self.empty_hint,
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(size=FONT_BODY),
                anchor="w",
                justify="left",
            )
            self._empty_label.grid(row=0, column=0, sticky="ew", pady=SPACE_SM)
        else:
            for i, path in enumerate(self._paths):
                row = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD_BG, corner_radius=RADIUS_SM)
                row.grid(row=i, column=0, sticky="ew", pady=2)
                row.grid_columnconfigure(0, weight=1)

                display = os.path.basename(path) or path
                label = ctk.CTkLabel(
                    row,
                    text=f"{GLYPH['file']}  {display}",
                    font=ctk.CTkFont(size=FONT_BODY),
                    anchor="w",
                )
                label.grid(row=0, column=0, sticky="ew", padx=SPACE, pady=SPACE_SM)

                path_label = ctk.CTkLabel(
                    row,
                    text=path,
                    text_color=COLOR_MUTED,
                    font=ctk.CTkFont(size=FONT_SMALL),
                    anchor="w",
                )
                path_label.grid(row=1, column=0, sticky="ew", padx=SPACE, pady=(0, SPACE_SM))

                remove = ctk.CTkButton(
                    row,
                    text=GLYPH["close"],
                    width=28,
                    height=28,
                    fg_color="transparent",
                    hover_color=COLOR_SUBTLE_BG,
                    text_color=COLOR_MUTED,
                    command=lambda p=path: self.remove(p),
                )
                remove.grid(row=0, column=1, rowspan=2, padx=(0, SPACE_SM))
        self.count_label.configure(text=f"{len(self._paths)} file{'s' if len(self._paths) != 1 else ''}")


# ---------------------------------------------------------------------------
# Toast notifications (stackable, auto-dismiss)
# ---------------------------------------------------------------------------


class Toast(ctk.CTkFrame):
    LEVEL_COLORS = {
        "info": COLOR_SUCCESS,
        "success": COLOR_SUCCESS,
        "warning": ("#D97706", "#F59E0B"),
        "error": COLOR_DANGER,
    }

    def __init__(self, master, message: str, level: str = "info", on_close=None):
        color = self.LEVEL_COLORS.get(level, COLOR_SUCCESS)
        super().__init__(master, fg_color=color, corner_radius=RADIUS)
        self._on_close = on_close

        glyph = {
            "info": GLYPH["info"],
            "success": GLYPH["check"],
            "warning": GLYPH["warn"],
            "error": GLYPH["close"],
        }.get(level, GLYPH["info"])

        ctk.CTkLabel(
            self,
            text=glyph,
            font=ctk.CTkFont(size=FONT_H3, weight="bold"),
            text_color=("#FFFFFF", "#FFFFFF"),
            width=24,
        ).grid(row=0, column=0, padx=(SPACE, 0), pady=SPACE_SM)
        ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=FONT_BODY),
            text_color=("#FFFFFF", "#FFFFFF"),
            wraplength=280,
            justify="left",
            anchor="w",
        ).grid(row=0, column=1, padx=SPACE, pady=SPACE_SM, sticky="w")
        ctk.CTkButton(
            self,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=("#00000022", "#FFFFFF22"),
            text_color=("#FFFFFF", "#FFFFFF"),
            command=self.dismiss,
        ).grid(row=0, column=2, padx=(0, SPACE_SM), pady=SPACE_SM)

    def dismiss(self):
        try:
            if self._on_close:
                self._on_close(self)
            self.destroy()
        except Exception:
            pass


class ToastManager:
    """Stacks toasts in the bottom-right corner of the owning window."""

    def __init__(self, root: tk.Misc, app_state=None):
        self.root = root
        self._toasts: List[Toast] = []
        self._container: Optional[ctk.CTkFrame] = None
        if app_state:
            app_state.subscribe("notifications", self._on_notification)

    def _ensure_container(self):
        if self._container and self._container.winfo_exists():
            return
        self._container = ctk.CTkFrame(self.root, fg_color="transparent")
        self._container.place(relx=1.0, rely=1.0, x=-SPACE_LG, y=-SPACE_LG, anchor="se")

    def _on_notification(self, message: str, level: str = "info"):
        self.root.after(0, lambda: self.push(message, level))

    def push(self, message: str, level: str = "info", timeout_ms: int = 4200):
        self._ensure_container()
        toast = Toast(self._container, message=message, level=level, on_close=self._remove)
        toast.pack(anchor="e", pady=(0, SPACE_SM), fill="x")
        self._toasts.append(toast)
        self.root.after(timeout_ms, toast.dismiss)

    def _remove(self, toast: Toast):
        if toast in self._toasts:
            self._toasts.remove(toast)


# ---------------------------------------------------------------------------
# Key/value grid helper
# ---------------------------------------------------------------------------


class KeyValueGrid(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self._row = 0

    def add(self, key: str, value: str):
        ctk.CTkLabel(
            self, text=key, text_color=COLOR_MUTED, font=ctk.CTkFont(size=FONT_SMALL), anchor="w"
        ).grid(row=self._row, column=0, padx=(0, SPACE), pady=2, sticky="w")
        value_label = ctk.CTkLabel(
            self, text=value, font=ctk.CTkFont(size=FONT_BODY), anchor="w", justify="left"
        )
        value_label.grid(row=self._row, column=1, pady=2, sticky="ew")
        self._row += 1
        return value_label

    def clear(self):
        for child in self.winfo_children():
            child.destroy()
        self._row = 0


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"
