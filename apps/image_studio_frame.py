import os
import re
import threading
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

import customtkinter as ctk
from tkinter import Canvas, filedialog, messagebox
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageGrab, ImageOps, ImageTk

try:
    import requests
except Exception:
    requests = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import piexif
except Exception:
    piexif = None

from core.theme import (
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
)
from core.ui_helpers import Card, GhostButton, PageHeader, PrimaryButton

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif")
THUMBNAIL_SIZE = (64, 64)
CANVAS_PADDING = 16
SIDEBAR_W = 210
CONTROLS_W = 260


class _Section(ctk.CTkFrame):
    """Collapsible labeled section for the right controls panel."""

    def __init__(self, master, title: str, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._expanded = True

        header = ctk.CTkFrame(self, fg_color=COLOR_SUBTLE_BG, corner_radius=RADIUS_SM)
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        header.grid_columnconfigure(0, weight=1)
        self._toggle_lbl = ctk.CTkLabel(
            header,
            text=f"▾  {title}",
            font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
            anchor="w",
        )
        self._toggle_lbl.grid(row=0, column=0, sticky="ew", padx=SPACE_SM, pady=4)
        header.bind("<Button-1>", self._toggle)
        self._toggle_lbl.bind("<Button-1>", self._toggle)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="ew")
        self.body.grid_columnconfigure(0, weight=1)

    def _toggle(self, _e=None):
        self._expanded = not self._expanded
        title_text = self._toggle_lbl.cget("text")
        if self._expanded:
            self._toggle_lbl.configure(text=title_text.replace("▸", "▾"))
            self.body.grid()
        else:
            self._toggle_lbl.configure(text=title_text.replace("▾", "▸"))
            self.body.grid_remove()


def _slider_row(parent, label: str, variable: ctk.DoubleVar, from_: float, to: float,
                command=None, row: int = 0, fmt: str = ".2f") -> ctk.CTkLabel:
    parent.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=FONT_SMALL), anchor="w",
                 text_color=COLOR_MUTED, width=70).grid(row=row, column=0, sticky="w",
                                                         padx=(0, SPACE_SM), pady=2)
    val_lbl = ctk.CTkLabel(parent, text=f"{variable.get():{fmt}}", width=40,
                           font=ctk.CTkFont(size=FONT_SMALL), text_color=COLOR_MUTED)
    val_lbl.grid(row=row, column=2, sticky="e", padx=(SPACE_SM, 0), pady=2)

    def _on_change(v):
        val_lbl.configure(text=f"{float(v):{fmt}}")
        if command:
            command(v)

    ctk.CTkSlider(parent, from_=from_, to=to, variable=variable,
                  command=_on_change, height=14).grid(row=row, column=1, sticky="ew", pady=2)
    return val_lbl


class ImageStudioFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.all_paths: list = []
        self.filtered_paths: list = []
        self.selected_path: str | None = None
        self.original_image = None
        self.preview_image = None
        self.tk_preview = None
        self.current_zoom = 1.0
        self._thumb_generation = 0

        # Filter vars
        self.format_filter = ctk.StringVar(value="All")
        self.search_var = ctk.StringVar(value="")
        self.folder_scope = ctk.StringVar(value="Current Folder")

        # Adjustment vars
        self.brightness = ctk.DoubleVar(value=1.0)
        self.contrast = ctk.DoubleVar(value=1.0)
        self.saturation = ctk.DoubleVar(value=1.0)
        self.blur = ctk.DoubleVar(value=0.0)
        self.flip_h_pct = ctk.DoubleVar(value=0.0)
        self.flip_v_pct = ctk.DoubleVar(value=0.0)

        # Crop / lasso state
        self.crop_mode = False
        self.crop_points: list = []
        self.lasso_lines: list = []
        self.lasso_preview = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_sidebar()
        self._build_canvas()
        self._build_controls()

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=SPACE_MD, pady=(SPACE_MD, SPACE_SM))
        header.grid_columnconfigure(5, weight=1)

        PageHeader(header, title="Image Studio",
                   subtitle="View, edit, annotate, and export images.").grid(
            row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=5, sticky="e")

        btns = [
            (f"{GLYPH['add']}  Add Files", self.add_files, None),
            (f"{GLYPH['add']}  Add Folder", self.add_folder, None),
            (f"{GLYPH['download']}  URL", self.download_image, None),
            (f"{GLYPH['camera']}  Screen", self.capture_screen, None),
            ("Export", self.export_image, "#1a7f4b"),
            ("Reset", self.reset_edits, "#555555"),
        ]
        for i, (label, cmd, color) in enumerate(btns):
            kw = {"fg_color": color} if color else {}
            ctk.CTkButton(btn_frame, text=label, command=cmd, width=110,
                          height=30, font=ctk.CTkFont(size=FONT_SMALL), **kw).grid(
                row=0, column=i, padx=(0, SPACE_SM))

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=SIDEBAR_W, corner_radius=RADIUS)
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(SPACE_MD, SPACE_SM), pady=(0, SPACE_MD))
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(3, weight=1)
        sidebar.grid_propagate(False)

        # Search
        ctk.CTkEntry(sidebar, textvariable=self.search_var,
                     placeholder_text=f"{GLYPH['search']}  Search…",
                     corner_radius=RADIUS, height=30,
                     font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=0, sticky="ew", padx=SPACE_SM, pady=(SPACE_SM, 4))
        self.search_var.trace_add("write", lambda *_: self.apply_filters())

        # Format + scope row
        filter_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", padx=SPACE_SM, pady=(0, 4))
        filter_row.grid_columnconfigure(0, weight=1)
        filter_row.grid_columnconfigure(1, weight=1)
        ctk.CTkOptionMenu(filter_row,
                          values=["All", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"],
                          variable=self.format_filter,
                          command=lambda _v: self.apply_filters(),
                          height=28, font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkOptionMenu(filter_row,
                          values=["Current Folder", "Include Subfolders"],
                          variable=self.folder_scope,
                          height=28, font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=1, sticky="ew", padx=(2, 0))

        self.summary_label = ctk.CTkLabel(sidebar, text="No images loaded",
                                          anchor="w", text_color=COLOR_MUTED,
                                          font=ctk.CTkFont(size=FONT_SMALL))
        self.summary_label.grid(row=2, column=0, sticky="ew", padx=SPACE_SM, pady=(0, 4))

        self.list_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent", corner_radius=0)
        self.list_frame.grid(row=3, column=0, sticky="nsew", padx=2, pady=(0, SPACE_SM))
        self.list_frame.grid_columnconfigure(1, weight=1)
        self.list_buttons: list = []
        self.list_thumbs: list = []
        self._bind_list_navigation(self.list_frame)
        self._bind_wheel_recursive(self.list_frame)

    def _build_canvas(self):
        canvas_frame = ctk.CTkFrame(self, corner_radius=RADIUS, fg_color="#0d0d0d")
        canvas_frame.grid(row=1, column=1, sticky="nsew", padx=SPACE_SM, pady=(0, SPACE_MD))
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)

        self.canvas = Canvas(canvas_frame, bg="#0d0d0d", highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self.render_preview())
        self.canvas.bind("<MouseWheel>", self.handle_zoom)
        self.canvas.bind("<Button-4>", self.handle_zoom)
        self.canvas.bind("<Button-5>", self.handle_zoom)

        # Zoom indicator
        self.zoom_label = ctk.CTkLabel(canvas_frame, text="100%",
                                       font=ctk.CTkFont(size=FONT_SMALL),
                                       text_color="#444444", fg_color="transparent")
        self.zoom_label.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-6)

    def _build_controls(self):
        controls_outer = ctk.CTkScrollableFrame(self, width=CONTROLS_W,
                                                corner_radius=RADIUS, fg_color="transparent")
        controls_outer.grid(row=1, column=2, sticky="nsew",
                            padx=(SPACE_SM, SPACE_MD), pady=(0, SPACE_MD))
        controls_outer.grid_columnconfigure(0, weight=1)
        controls_outer.grid_propagate(False)

        row = 0

        # ── Adjustments ──────────────────────────────────────────────
        adj = _Section(controls_outer, "Adjustments")
        adj.grid(row=row, column=0, sticky="ew", pady=(0, SPACE_SM))
        row += 1
        b = adj.body
        b.grid_columnconfigure(1, weight=1)
        _slider_row(b, "Brightness", self.brightness, 0.2, 2.0, self.on_adjustment_change, 0)
        _slider_row(b, "Contrast", self.contrast, 0.2, 2.0, self.on_adjustment_change, 1)
        _slider_row(b, "Saturation", self.saturation, 0.0, 2.0, self.on_adjustment_change, 2)
        _slider_row(b, "Blur", self.blur, 0.0, 10.0, self.on_adjustment_change, 3)

        # ── Transform ────────────────────────────────────────────────
        tfm = _Section(controls_outer, "Transform")
        tfm.grid(row=row, column=0, sticky="ew", pady=(0, SPACE_SM))
        row += 1
        b = tfm.body
        b.grid_columnconfigure(1, weight=1)

        rotate_row = ctk.CTkFrame(b, fg_color="transparent")
        rotate_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, SPACE_SM))
        rotate_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(rotate_row, text="↺  Left 90°",
                      command=lambda: self.rotate_image(-90),
                      height=28, font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(rotate_row, text="↻  Right 90°",
                      command=lambda: self.rotate_image(90),
                      height=28, font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=1, sticky="ew", padx=(2, 0))

        _slider_row(b, "Flip H %", self.flip_h_pct, 0.0, 100.0,
                    self.on_adjustment_change, 1, ".0f")
        _slider_row(b, "Flip V %", self.flip_v_pct, 0.0, 100.0,
                    self.on_adjustment_change, 2, ".0f")

        reset_flip_row = ctk.CTkFrame(b, fg_color="transparent")
        reset_flip_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(SPACE_SM, 0))
        reset_flip_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(reset_flip_row, text="Reset Flip H",
                      command=lambda: (self.flip_h_pct.set(0), self.on_adjustment_change()),
                      height=26, font=ctk.CTkFont(size=FONT_SMALL),
                      fg_color="#3a3a3a").grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(reset_flip_row, text="Reset Flip V",
                      command=lambda: (self.flip_v_pct.set(0), self.on_adjustment_change()),
                      height=26, font=ctk.CTkFont(size=FONT_SMALL),
                      fg_color="#3a3a3a").grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # ── Freehand / Crop ──────────────────────────────────────────
        crop_sec = _Section(controls_outer, "Freehand Crop")
        crop_sec.grid(row=row, column=0, sticky="ew", pady=(0, SPACE_SM))
        row += 1
        b = crop_sec.body
        b.grid_columnconfigure((0, 1), weight=1)
        self.freehand_btn = ctk.CTkButton(b, text="✏  Start",
                                          command=self.toggle_crop_mode,
                                          height=28, font=ctk.CTkFont(size=FONT_SMALL))
        self.freehand_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2), pady=(0, SPACE_SM))
        self.apply_crop_btn = ctk.CTkButton(b, text="✓  Apply",
                                            fg_color="#1a7f4b", state="disabled",
                                            command=self.apply_lasso_crop,
                                            height=28, font=ctk.CTkFont(size=FONT_SMALL))
        self.apply_crop_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=(0, SPACE_SM))
        ctk.CTkLabel(b, text="Click = straight lines  •  Drag = freehand\nRight-click or double-click to close",
                     text_color=COLOR_MUTED, font=ctk.CTkFont(size=10), justify="left",
                     anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew")

        # ── Metadata ─────────────────────────────────────────────────
        meta_sec = _Section(controls_outer, "Metadata")
        meta_sec.grid(row=row, column=0, sticky="ew", pady=(0, SPACE_SM))
        row += 1
        b = meta_sec.body
        b.grid_columnconfigure(0, weight=1)
        self.metadata_box = ctk.CTkTextbox(b, height=120, corner_radius=RADIUS_SM,
                                           font=ctk.CTkFont(size=10))
        self.metadata_box.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        ctk.CTkButton(b, text="Remove Metadata", fg_color="#7a2a2a",
                      command=self.clear_metadata, height=26,
                      font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=1, column=0, sticky="ew", pady=(0, SPACE_SM))

        # ── OCR ──────────────────────────────────────────────────────
        ocr_sec = _Section(controls_outer, "OCR")
        ocr_sec.grid(row=row, column=0, sticky="ew", pady=(0, SPACE_SM))
        row += 1
        b = ocr_sec.body
        b.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(b, text="Extract Text", command=self.extract_text,
                      height=28, font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        self.ocr_box = ctk.CTkTextbox(b, height=100, corner_radius=RADIUS_SM,
                                      font=ctk.CTkFont(size=10))
        self.ocr_box.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_SM))

        ocr_btns = ctk.CTkFrame(b, fg_color="transparent")
        ocr_btns.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_SM))
        ocr_btns.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(ocr_btns, text="Copy", fg_color="#3a3a3a",
                      command=self.copy_ocr_text, height=26,
                      font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(ocr_btns, text="Save", fg_color="#3a3a3a",
                      command=self.save_ocr_text, height=26,
                      font=ctk.CTkFont(size=FONT_SMALL)).grid(
            row=0, column=1, sticky="ew", padx=(2, 0))

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def add_files(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif")])
        self._add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        recursive = self.folder_scope.get() == "Include Subfolders"
        paths = []
        if recursive:
            for root, _, filenames in os.walk(folder):
                for fn in filenames:
                    if fn.lower().endswith(SUPPORTED_EXTS):
                        paths.append(os.path.join(root, fn))
        else:
            for fn in os.listdir(folder):
                p = os.path.join(folder, fn)
                if os.path.isfile(p) and fn.lower().endswith(SUPPORTED_EXTS):
                    paths.append(p)
        self._add_paths(paths)
        if self.app_state:
            self.app_state.remember_folder(folder)

    def _add_paths(self, paths):
        added = sum(1 for p in paths
                    if p not in self.all_paths and os.path.isfile(p)
                    and not self.all_paths.append(p))
        if added and self.app_state:
            self.app_state.log(f"Image Studio: added {added} image(s).")
        self.apply_filters()

    # ------------------------------------------------------------------
    # Filtering & list rendering
    # ------------------------------------------------------------------

    def apply_filters(self):
        search = self.search_var.get().strip().lower()
        fmt = self.format_filter.get().lower()
        filtered = []
        for path in self.all_paths:
            if not os.path.exists(path):
                continue
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            name = os.path.basename(path).lower()
            if fmt != "all" and ext != fmt:
                continue
            if search and search not in name:
                continue
            filtered.append(path)

        self.filtered_paths = sorted(filtered, key=lambda p: os.path.basename(p).lower())
        n = len(self.filtered_paths)
        self.summary_label.configure(text=f"{n} image{'s' if n != 1 else ''}")
        self.render_list()

        if self.filtered_paths:
            if self.selected_path not in self.filtered_paths:
                self.select_path(self.filtered_paths[0])
            else:
                self.highlight_selected()
        else:
            self.selected_path = None
            self.original_image = None
            self.preview_image = None
            self.canvas.delete("all")
            self.metadata_box.delete("1.0", "end")
            self.ocr_box.delete("1.0", "end")

    def clear_filters(self):
        self.search_var.set("")
        self.format_filter.set("All")
        self.apply_filters()

    def render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.list_buttons = []
        self.list_thumbs = []

        self._thumb_generation += 1
        current_gen = self._thumb_generation
        pending: list = []

        for index, path in enumerate(self.filtered_paths):
            thumb_label = ctk.CTkLabel(self.list_frame, text="·", width=THUMBNAIL_SIZE[0],
                                       height=THUMBNAIL_SIZE[1], text_color="#444")
            thumb_label.grid(row=index, column=0, padx=(4, 6), pady=3)
            self._bind_list_navigation(thumb_label)
            self._bind_wheel_recursive(thumb_label)
            thumb_label.bind("<Button-1>", lambda _e, p=path: self.select_path_and_focus(p))
            pending.append((path, thumb_label))

            button = ctk.CTkButton(
                self.list_frame,
                text=os.path.basename(path),
                anchor="w",
                height=THUMBNAIL_SIZE[1],
                fg_color=COLOR_SUBTLE_BG if path == self.selected_path else "transparent",
                hover_color=COLOR_SUBTLE_BG,
                font=ctk.CTkFont(size=FONT_SMALL),
                command=lambda p=path: self.select_path_and_focus(p),
            )
            button.grid(row=index, column=1, padx=(0, 4), pady=3, sticky="ew")
            self.list_buttons.append((path, button))
            self._bind_list_navigation(button)
            self._bind_wheel_recursive(button)

        threading.Thread(
            target=self._load_thumbs_thread,
            args=(current_gen, pending),
            daemon=True,
        ).start()

    def _load_thumbs_thread(self, gen: int, items: list):
        for path, label in items:
            if self._thumb_generation != gen:
                return
            try:
                with Image.open(path) as img:
                    thumb = ImageOps.exif_transpose(img).convert("RGBA")
                    thumb.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
                    ctk_thumb = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
            except Exception:
                ctk_thumb = None
            if self._thumb_generation != gen:
                return

            def _apply(lbl=label, image=ctk_thumb):
                if image:
                    lbl.configure(image=image, text="")
                    lbl.image = image
                    self.list_thumbs.append(image)
                else:
                    lbl.configure(text="?")

            self.after(0, _apply)

    # ------------------------------------------------------------------
    # Selection & highlighting
    # ------------------------------------------------------------------

    def select_path(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            with Image.open(path) as image:
                self.original_image = ImageOps.exif_transpose(image).convert("RGBA")
            self.selected_path = path
            self.current_zoom = 1.0
            self._reset_adjustment_vars()
            self.preview_image = self.original_image.copy()
            self.render_preview()
            self.load_metadata()
            self.highlight_selected()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open image: {exc}")

    def select_path_and_focus(self, path):
        self.select_path(path)
        self.focus_selected_button()

    def highlight_selected(self):
        for path, button in self.list_buttons:
            button.configure(
                fg_color=COLOR_SUBTLE_BG if path == self.selected_path else "transparent")

    def focus_selected_button(self):
        for path, button in self.list_buttons:
            if path == self.selected_path:
                try:
                    button.focus_set()
                except Exception:
                    pass
                self.scroll_selected_into_view()
                break

    def _bind_list_navigation(self, widget):
        widget.bind("<Up>", self.on_list_up)
        widget.bind("<Down>", self.on_list_down)

    def _bind_wheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self.on_list_mousewheel, add="+")
        widget.bind("<Button-4>", self.on_list_mousewheel, add="+")
        widget.bind("<Button-5>", self.on_list_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child)

    def on_list_up(self, event=None):
        self.move_selection(-1)
        return "break"

    def on_list_down(self, event=None):
        self.move_selection(1)
        return "break"

    def move_selection(self, step):
        if not self.filtered_paths:
            return
        if self.selected_path not in self.filtered_paths:
            idx = 0
        else:
            idx = min(max(self.filtered_paths.index(self.selected_path) + step, 0),
                      len(self.filtered_paths) - 1)
        self.select_path(self.filtered_paths[idx])
        self.focus_selected_button()

    def on_list_mousewheel(self, event):
        canvas = getattr(self.list_frame, "_parent_canvas", None)
        if canvas is None:
            return None
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            raw = getattr(event, "delta", 0)
            if raw == 0:
                return "break"
            delta = int(-raw / 120) if abs(raw) >= 120 else (-1 if raw > 0 else 1)
        canvas.yview_scroll(delta, "units")
        return "break"

    def scroll_selected_into_view(self):
        canvas = getattr(self.list_frame, "_parent_canvas", None)
        if canvas is None or not self.filtered_paths or self.selected_path not in self.filtered_paths:
            return
        try:
            fraction = self.filtered_paths.index(self.selected_path) / max(1, len(self.filtered_paths))
            canvas.yview_moveto(min(max(fraction, 0.0), 1.0))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Canvas rendering
    # ------------------------------------------------------------------

    def render_preview(self):
        self.canvas.delete("all")
        if self.preview_image is None:
            return

        cw = max(200, self.canvas.winfo_width())
        ch = max(200, self.canvas.winfo_height())
        avail_w = max(1, cw - CANVAS_PADDING * 2)
        avail_h = max(1, ch - CANVAS_PADDING * 2)

        display = self.preview_image.copy()
        scale = max(0.05, min(avail_w / display.width, avail_h / display.height, 1.0) * self.current_zoom)
        size = (max(1, int(display.width * scale)), max(1, int(display.height * scale)))
        resized = display.resize(size, Image.LANCZOS)

        self.tk_preview = ImageTk.PhotoImage(resized)
        self.canvas.create_image(cw // 2, ch // 2, image=self.tk_preview, anchor="center")

        pct = int(self.current_zoom * 100)
        self.zoom_label.configure(text=f"{pct}%")

        if self.crop_points:
            self.redraw_lasso()

    def handle_zoom(self, event):
        if self.preview_image is None or self.crop_mode:
            return
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            self.current_zoom *= 0.9
        else:
            self.current_zoom *= 1.1
        self.current_zoom = min(max(self.current_zoom, 0.1), 8.0)
        self.render_preview()

    # ------------------------------------------------------------------
    # Adjustments
    # ------------------------------------------------------------------

    def _reset_adjustment_vars(self):
        self.brightness.set(1.0)
        self.contrast.set(1.0)
        self.saturation.set(1.0)
        self.blur.set(0.0)
        self.flip_h_pct.set(0.0)
        self.flip_v_pct.set(0.0)

    def on_adjustment_change(self, _value=None):
        if self.original_image is None:
            return
        img = self.original_image.copy()
        img = ImageEnhance.Brightness(img).enhance(self.brightness.get())
        img = ImageEnhance.Contrast(img).enhance(self.contrast.get())
        img = ImageEnhance.Color(img).enhance(self.saturation.get())
        if self.blur.get() > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=self.blur.get()))

        # Flip H percentage: blend original ↔ horizontally flipped
        h_pct = self.flip_h_pct.get() / 100.0
        if h_pct > 0:
            flipped_h = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            img = Image.blend(img, flipped_h, h_pct)

        # Flip V percentage: blend original ↔ vertically flipped
        v_pct = self.flip_v_pct.get() / 100.0
        if v_pct > 0:
            flipped_v = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            img = Image.blend(img, flipped_v, v_pct)

        self.preview_image = img
        self.render_preview()

    def rotate_image(self, degrees):
        if self.original_image is None:
            return
        self.original_image = self.original_image.rotate(degrees, expand=True)
        self.on_adjustment_change()

    def reset_edits(self):
        if not self.selected_path:
            return
        self.select_path(self.selected_path)

    # ------------------------------------------------------------------
    # Freehand / lasso crop
    # ------------------------------------------------------------------

    def toggle_crop_mode(self):
        self.crop_mode = not self.crop_mode
        if self.crop_mode:
            self.freehand_btn.configure(text="✕  Cancel", fg_color="#7a2a2a")
            self.canvas.configure(cursor="cross")
            self.canvas.bind("<Button-1>", self.on_lasso_click)
            self.canvas.bind("<B1-Motion>", self.draw_lasso_freehand)
            self.canvas.bind("<Motion>", self.preview_lasso_straight)
            self.canvas.bind("<Double-Button-1>", self.end_lasso)
            self.canvas.bind("<Button-3>", self.end_lasso)
            self.master.bind("<Escape>", lambda _e: self.toggle_crop_mode())
            if self.app_state:
                self.app_state.notify("Freehand active. Click = straight, drag = freehand. Right-click or double-click to finish.")
        else:
            self.freehand_btn.configure(text="✏  Start", fg_color=["#3B8ED0", "#1F6AA5"])
            self.canvas.configure(cursor="")
            for event in ("<Button-1>", "<B1-Motion>", "<Motion>", "<Double-Button-1>", "<Button-3>"):
                self.canvas.unbind(event)
            self.master.unbind("<Escape>")
            self.clear_lasso()

    def on_lasso_click(self, event):
        if not self.original_image:
            return
        ix, iy = self._canvas_to_image(event.x, event.y)
        if not self.crop_points:
            self.crop_points = [(ix, iy)]
            self.apply_crop_btn.configure(state="disabled")
        else:
            self.crop_points.append((ix, iy))
            self.render_preview()

    def draw_lasso_freehand(self, event):
        if not self.original_image:
            return
        ix, iy = self._canvas_to_image(event.x, event.y)
        if not self.crop_points:
            self.crop_points = [(ix, iy)]
            return
        last_ix, last_iy = self.crop_points[-1]
        if abs(last_ix - ix) > 1 or abs(last_iy - iy) > 1:
            self.crop_points.append((ix, iy))
            self.render_preview()

    def preview_lasso_straight(self, event):
        if not self.crop_points or not self.crop_mode:
            return
        if self.apply_crop_btn.cget("state") == "normal":
            if self.lasso_preview:
                self.canvas.delete(self.lasso_preview)
                self.lasso_preview = None
            return
        if self.lasso_preview:
            self.canvas.delete(self.lasso_preview)
        last_cx, last_cy = self._image_to_canvas(*self.crop_points[-1])
        self.lasso_preview = self.canvas.create_line(
            last_cx, last_cy, event.x, event.y, fill="#00ffcc", width=1, dash=(3, 3))

    def end_lasso(self, event=None):
        if len(self.crop_points) < 3:
            return
        self.apply_crop_btn.configure(state="normal")
        self.render_preview()

    def _canvas_to_image(self, cx, cy):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        aw, ah = max(1, cw - CANVAS_PADDING * 2), max(1, ch - CANVAS_PADDING * 2)
        scale = max(0.01, min(aw / self.preview_image.width,
                              ah / self.preview_image.height, 1.0) * self.current_zoom)
        ow, oh = self.original_image.size
        return (cx - cw // 2) / scale + ow / 2, (cy - ch // 2) / scale + oh / 2

    def _image_to_canvas(self, ix, iy):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        aw, ah = max(1, cw - CANVAS_PADDING * 2), max(1, ch - CANVAS_PADDING * 2)
        scale = max(0.01, min(aw / self.preview_image.width,
                              ah / self.preview_image.height, 1.0) * self.current_zoom)
        ow, oh = self.original_image.size
        return (ix - ow / 2) * scale + cw // 2, (iy - oh / 2) * scale + ch // 2

    def redraw_lasso(self):
        self.lasso_lines = []
        if len(self.crop_points) < 2:
            return
        pts = [self._image_to_canvas(ix, iy) for ix, iy in self.crop_points]
        for i in range(len(pts) - 1):
            self.lasso_lines.append(self.canvas.create_line(
                *pts[i], *pts[i + 1], fill="#00ffcc", width=2, dash=(4, 4)))
        if self.apply_crop_btn.cget("state") == "normal":
            self.lasso_lines.append(self.canvas.create_line(
                *pts[-1], *pts[0], fill="#00ff88", width=2, dash=(4, 4)))

    def apply_lasso_crop(self):
        if not self.original_image or len(self.crop_points) < 3:
            return
        from PIL import ImageDraw
        mask = Image.new("L", self.original_image.size, 0)
        ImageDraw.Draw(mask).polygon(self.crop_points, outline=1, fill=255)
        result = Image.new("RGBA", self.original_image.size, (0, 0, 0, 0))
        result.paste(self.original_image, mask=mask)
        bbox = mask.getbbox()
        if bbox:
            self.original_image = result.crop(bbox)
            self.toggle_crop_mode()
            self._reset_adjustment_vars()
            self.preview_image = self.original_image.copy()
            self.render_preview()
            if self.app_state:
                self.app_state.notify("Image cropped to freehand selection.")
        else:
            messagebox.showwarning("Warning", "Selection is empty.")

    def clear_lasso(self):
        if self.lasso_preview:
            self.canvas.delete(self.lasso_preview)
            self.lasso_preview = None
        for line in self.lasso_lines:
            self.canvas.delete(line)
        self.lasso_lines = []
        self.crop_points = []
        self.apply_crop_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_image(self):
        if self.preview_image is None or not self.selected_path:
            return
        fmt = self._prompt("Export Format", "Format (png, jpg, webp, bmp, tiff, pdf):")
        if not fmt:
            return
        fmt = fmt.lower().strip(".")
        if fmt not in {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"}:
            messagebox.showerror("Error", "Unsupported format.")
            return
        initial_dir = self.app_state.settings.get("exports_folder") if self.app_state else None
        output_dir = filedialog.askdirectory(initialdir=initial_dir)
        if not output_dir:
            return
        base = os.path.splitext(os.path.basename(self.selected_path))[0]
        output_path = os.path.join(output_dir, f"{base}_export.{fmt}")
        try:
            image = self.preview_image
            if fmt == "pdf":
                image.convert("RGB").save(output_path, "PDF")
            elif fmt in {"jpg", "jpeg"}:
                image.convert("RGB").save(output_path, "JPEG", quality=92)
            else:
                image.save(output_path, fmt.upper())
        except Exception as exc:
            messagebox.showerror("Error", f"Export failed: {exc}")
            return
        if self.app_state:
            self.app_state.notify(f"Exported: {os.path.basename(output_path)}")
        else:
            messagebox.showinfo("Done", f"Saved: {output_path}")

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def load_metadata(self):
        self.metadata_box.delete("1.0", "end")
        if not self.selected_path:
            return
        try:
            with Image.open(self.selected_path) as image:
                stat = os.stat(self.selected_path)
                lines = [
                    f"Name: {os.path.basename(self.selected_path)}",
                    f"Dimensions: {image.width} × {image.height}",
                    f"Mode: {image.mode}",
                    f"File size: {stat.st_size / 1024:.1f} KB",
                    f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')}",
                    f"EXIF tags: {len(image.getexif()) if image.getexif() else 0}",
                ]
                self.metadata_box.insert("end", "\n".join(lines))
        except Exception as exc:
            self.metadata_box.insert("end", f"Error: {exc}")

    def clear_metadata(self):
        if not self.selected_path:
            return
        ext = os.path.splitext(self.selected_path)[1].lower()
        try:
            if ext in {".jpg", ".jpeg"} and piexif:
                piexif.remove(self.selected_path)
            else:
                with Image.open(self.selected_path) as image:
                    clean = Image.new(image.mode, image.size)
                    clean.putdata(list(image.getdata()))
                    clean.save(self.selected_path)
        except Exception as exc:
            messagebox.showerror("Error", f"Metadata cleanup failed: {exc}")
            return
        self.load_metadata()
        if self.app_state:
            self.app_state.notify(f"Metadata removed: {os.path.basename(self.selected_path)}")

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------

    def extract_text(self):
        if self.preview_image is None:
            return
        if not pytesseract:
            messagebox.showerror("Error", "pytesseract is not installed.")
            return
        try:
            text = pytesseract.image_to_string(self.preview_image.convert("RGB")).strip()
        except Exception as exc:
            messagebox.showerror("Error", f"OCR failed: {exc}")
            return
        self.ocr_box.delete("1.0", "end")
        self.ocr_box.insert("end", text)

    def copy_ocr_text(self):
        text = self.ocr_box.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        if self.app_state:
            self.app_state.notify("OCR text copied.")

    def save_ocr_text(self):
        text = self.ocr_box.get("1.0", "end").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        if self.app_state:
            self.app_state.notify(f"OCR saved: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Screen capture / URL download
    # ------------------------------------------------------------------

    def capture_screen(self):
        try:
            image = ImageGrab.grab()
        except Exception as exc:
            messagebox.showerror("Error", f"Screen capture failed: {exc}")
            return
        save_dir = filedialog.askdirectory()
        if not save_dir:
            return
        path = os.path.join(save_dir, f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        image.save(path)
        self._add_paths([path])
        self.select_path(path)
        if self.app_state:
            self.app_state.notify(f"Screenshot captured: {os.path.basename(path)}")

    def download_image(self):
        url = self._prompt("Image URL", "Paste image URL:")
        if not url:
            return
        save_dir = filedialog.askdirectory()
        if not save_dir:
            return
        try:
            filename = os.path.basename(urlparse(url).path) or "downloaded_image"
            filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
            path = os.path.join(save_dir, filename)
            if requests:
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
            else:
                with urllib.request.urlopen(url, timeout=15) as s:
                    payload = s.read()
                with open(path, "wb") as f:
                    f.write(payload)
        except Exception as exc:
            messagebox.showerror("Error", f"Download failed: {exc}")
            return
        self._add_paths([path])
        self.select_path(path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prompt(self, title, message):
        return ctk.CTkInputDialog(text=message, title=title).get_input()
