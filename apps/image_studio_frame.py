import os
import re
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

import customtkinter as ctk
from tkinter import Canvas, filedialog, messagebox
from PIL import Image, ImageEnhance, ImageFilter, ImageGrab, ImageOps, ImageTk

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


SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif")
THUMBNAIL_SIZE = (80, 80)
CANVAS_PADDING = 24


class ImageStudioFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.all_paths = []
        self.filtered_paths = []
        self.selected_path = None

        self.original_image = None
        self.preview_image = None
        self.tk_preview = None
        self.current_zoom = 1.0

        self.format_filter = ctk.StringVar(value="All")
        self.search_var = ctk.StringVar(value="")
        self.folder_scope = ctk.StringVar(value="Current Folder")
        self.brightness = ctk.DoubleVar(value=1.0)
        self.contrast = ctk.DoubleVar(value=1.0)
        self.blur = ctk.DoubleVar(value=0.0)
        self.crop_mode = False
        self.crop_points = []
        self.lasso_lines = []
        self.lasso_preview = None
        self.current_bbox = None

        self.create_widgets()

    def create_widgets(self):
        ctk.CTkLabel(self, text="Image Studio", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(20, 10), sticky="n"
        )

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        toolbar.grid_columnconfigure(6, weight=1)

        ctk.CTkButton(toolbar, text="Add Files", command=self.add_files).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Add Folder", command=self.add_folder).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Download URL", command=self.download_image).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Capture Screen", command=self.capture_screen).grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Export", fg_color="green", command=self.export_image).grid(row=0, column=4, padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Reset", fg_color="gray", command=self.reset_edits).grid(row=0, column=5, padx=5, pady=5)

        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(body, width=300)
        sidebar.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)

        filters = ctk.CTkFrame(sidebar)
        filters.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        filters.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(filters, text="Search").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.search_entry = ctk.CTkEntry(filters, textvariable=self.search_var, placeholder_text="filename contains...")
        self.search_entry.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda _e: self.apply_filters())

        ctk.CTkLabel(filters, text="Format").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkOptionMenu(
            filters,
            values=["All", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"],
            variable=self.format_filter,
            command=lambda _v: self.apply_filters(),
        ).grid(row=1, column=1, padx=6, pady=6, sticky="ew")

        ctk.CTkLabel(filters, text="Folder Scope").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkOptionMenu(
            filters,
            values=["Current Folder", "Include Subfolders"],
            variable=self.folder_scope,
        ).grid(row=2, column=1, padx=6, pady=6, sticky="ew")

        ctk.CTkButton(filters, text="Clear Filters", fg_color="gray", command=self.clear_filters).grid(
            row=3, column=0, columnspan=2, padx=6, pady=6, sticky="ew"
        )

        self.summary_label = ctk.CTkLabel(sidebar, text="No images loaded", anchor="w")
        self.summary_label.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")

        self.list_frame = ctk.CTkScrollableFrame(sidebar)
        self.list_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.list_frame.grid_columnconfigure(1, weight=1)
        self.list_buttons = []
        self.list_thumbs = []
        self._bind_list_navigation(self.list_frame)
        self._bind_wheel_recursive(self.list_frame)

        viewer = ctk.CTkFrame(body)
        viewer.grid(row=0, column=1, sticky="nsew")
        viewer.grid_columnconfigure(0, weight=1)
        viewer.grid_rowconfigure(0, weight=1)
        viewer.grid_rowconfigure(1, weight=0)

        self.canvas = Canvas(viewer, bg="#111111", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self.render_preview())
        self.canvas.bind("<MouseWheel>", self.handle_zoom)
        self.canvas.bind("<Button-4>", self.handle_zoom)
        self.canvas.bind("<Button-5>", self.handle_zoom)

        info_panel = ctk.CTkFrame(viewer)
        info_panel.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        info_panel.grid_columnconfigure((0, 1, 2), weight=1)

        editor = ctk.CTkFrame(info_panel)
        editor.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        editor.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(editor, text="Brightness").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkSlider(editor, from_=0.5, to=1.5, variable=self.brightness, command=self.on_adjustment_change).grid(
            row=0, column=1, padx=8, pady=6, sticky="ew"
        )
        ctk.CTkLabel(editor, text="Contrast").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkSlider(editor, from_=0.5, to=1.5, variable=self.contrast, command=self.on_adjustment_change).grid(
            row=1, column=1, padx=8, pady=6, sticky="ew"
        )
        ctk.CTkLabel(editor, text="Blur").grid(row=2, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkSlider(editor, from_=0, to=8, variable=self.blur, command=self.on_adjustment_change).grid(
            row=2, column=1, padx=8, pady=6, sticky="ew"
        )
        ctk.CTkButton(editor, text="Rotate Left", command=lambda: self.rotate_image(-90)).grid(
            row=3, column=0, padx=8, pady=6, sticky="ew"
        )
        ctk.CTkButton(editor, text="Rotate Right", command=lambda: self.rotate_image(90)).grid(
            row=3, column=1, padx=8, pady=6, sticky="ew"
        )
        ctk.CTkButton(editor, text="Flip H", command=lambda: self.flip_image("h")).grid(
            row=4, column=0, padx=8, pady=6, sticky="ew"
        )
        ctk.CTkButton(editor, text="Flip V", command=lambda: self.flip_image("v")).grid(
            row=4, column=1, padx=8, pady=6, sticky="ew"
        )
        self.freehand_btn = ctk.CTkButton(editor, text="Freehand Tool", command=self.toggle_crop_mode)
        self.freehand_btn.grid(
            row=5, column=0, padx=8, pady=6, sticky="ew"
        )
        self.apply_crop_btn = ctk.CTkButton(editor, text="Apply Crop", fg_color="green", state="disabled", command=self.apply_lasso_crop)
        self.apply_crop_btn.grid(
            row=5, column=1, padx=8, pady=6, sticky="ew"
        )

        meta = ctk.CTkFrame(info_panel)
        meta.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        meta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(meta, text="Metadata", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=8, pady=(8, 4), sticky="w"
        )
        self.metadata_box = ctk.CTkTextbox(meta, height=170)
        self.metadata_box.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        ctk.CTkButton(meta, text="Remove Metadata", fg_color="indianred", command=self.clear_metadata).grid(
            row=2, column=0, padx=8, pady=(4, 8), sticky="ew"
        )

        ocr = ctk.CTkFrame(info_panel)
        ocr.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        ocr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ocr, text="OCR", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=8, pady=(8, 4), sticky="w")
        ctk.CTkButton(ocr, text="Extract Text", command=self.extract_text).grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        self.ocr_box = ctk.CTkTextbox(ocr, height=120)
        self.ocr_box.grid(row=2, column=0, padx=8, pady=4, sticky="nsew")
        ctk.CTkButton(ocr, text="Copy Text", fg_color="gray", command=self.copy_ocr_text).grid(
            row=3, column=0, padx=8, pady=4, sticky="ew"
        )
        ctk.CTkButton(ocr, text="Save OCR", command=self.save_ocr_text).grid(
            row=4, column=0, padx=8, pady=(4, 8), sticky="ew"
        )

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif")])
        self._add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        paths = []
        recursive = self.folder_scope.get() == "Include Subfolders"
        if recursive:
            for root, _, filenames in os.walk(folder):
                for filename in filenames:
                    if filename.lower().endswith(SUPPORTED_EXTS):
                        paths.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(folder):
                path = os.path.join(folder, filename)
                if os.path.isfile(path) and filename.lower().endswith(SUPPORTED_EXTS):
                    paths.append(path)
        self._add_paths(paths)

    def _add_paths(self, paths):
        added = 0
        for path in paths:
            if path not in self.all_paths and os.path.isfile(path):
                self.all_paths.append(path)
                added += 1
        if added and self.app_state:
            self.app_state.log(f"Image Studio added {added} image(s).")
        self.apply_filters()

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

        self.filtered_paths = sorted(filtered, key=lambda item: os.path.basename(item).lower())
        self.summary_label.configure(text=f"{len(self.filtered_paths)} image(s)")
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

        for index, path in enumerate(self.filtered_paths):
            thumb_label = ctk.CTkLabel(self.list_frame, text="", width=80)
            thumb_label.grid(row=index, column=0, padx=(4, 8), pady=4)
            self._set_thumbnail(thumb_label, path)
            self._bind_list_navigation(thumb_label)
            self._bind_wheel_recursive(thumb_label)
            thumb_label.bind("<Button-1>", lambda _e, p=path: self.select_path_and_focus(p))

            button = ctk.CTkButton(
                self.list_frame,
                text=os.path.basename(path),
                anchor="w",
                fg_color="#1F6AA5" if path == self.selected_path else "#151515",
                command=lambda p=path: self.select_path_and_focus(p),
            )
            button.grid(row=index, column=1, padx=(0, 4), pady=4, sticky="ew")
            self.list_buttons.append((path, button))
            self._bind_list_navigation(button)
            self._bind_wheel_recursive(button)

    def _set_thumbnail(self, label, path):
        try:
            with Image.open(path) as image:
                thumb = ImageOps.exif_transpose(image).convert("RGBA")
                thumb.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
                ctk_thumb = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
            label.configure(image=ctk_thumb, text="")
            label.image = ctk_thumb
            self.list_thumbs.append(ctk_thumb)
        except Exception:
            label.configure(text="No preview")

    def select_path(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            with Image.open(path) as image:
                self.original_image = ImageOps.exif_transpose(image).convert("RGBA")
            self.selected_path = path
            self.current_zoom = 1.0
            self.reset_adjustment_controls()
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
            button.configure(fg_color="#1F6AA5" if path == self.selected_path else "#151515")

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
            target_index = 0
        else:
            current_index = self.filtered_paths.index(self.selected_path)
            target_index = min(max(current_index + step, 0), len(self.filtered_paths) - 1)
        self.select_path(self.filtered_paths[target_index])
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
            raw_delta = getattr(event, "delta", 0)
            if raw_delta == 0:
                return "break"
            if abs(raw_delta) >= 120:
                delta = int(-raw_delta / 120)
            else:
                delta = -1 if raw_delta > 0 else 1

        canvas.yview_scroll(delta, "units")
        return "break"

    def scroll_selected_into_view(self):
        canvas = getattr(self.list_frame, "_parent_canvas", None)
        if canvas is None or not self.filtered_paths or self.selected_path not in self.filtered_paths:
            return
        try:
            index = self.filtered_paths.index(self.selected_path)
            fraction = index / max(1, len(self.filtered_paths))
            canvas.yview_moveto(min(max(fraction, 0.0), 1.0))
        except Exception:
            pass

    def render_preview(self):
        self.canvas.delete("all")
        if self.preview_image is None:
            return

        canvas_width = max(200, self.canvas.winfo_width())
        canvas_height = max(200, self.canvas.winfo_height())
        available_width = max(1, canvas_width - (CANVAS_PADDING * 2))
        available_height = max(1, canvas_height - (CANVAS_PADDING * 2))

        display = self.preview_image.copy()
        fit_ratio = min(available_width / display.width, available_height / display.height, 1.0)
        scale = max(0.1, fit_ratio * self.current_zoom)
        size = (max(1, int(display.width * scale)), max(1, int(display.height * scale)))
        resized = display.resize(size, Image.LANCZOS)

        self.tk_preview = ImageTk.PhotoImage(resized)
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.tk_preview, anchor="center")

        if self.crop_points:
            self.redraw_lasso()

    def toggle_crop_mode(self):
        self.crop_mode = not self.crop_mode
        if self.crop_mode:
            self.freehand_btn.configure(fg_color="#1F6AA5")
            self.canvas.configure(cursor="cross")
            self.canvas.bind("<Button-1>", self.on_lasso_click)
            self.canvas.bind("<B1-Motion>", self.draw_lasso_freehand)
            self.canvas.bind("<Motion>", self.preview_lasso_straight)
            self.canvas.bind("<Double-Button-1>", self.end_lasso)
            self.canvas.bind("<Button-3>", self.end_lasso)
            self.master.bind("<Escape>", lambda _e: self.toggle_crop_mode())
            if self.app_state:
                self.app_state.notify("Freehand Tool active. Click for straight lines, drag for freehand. Right-click or Double-click to finish. ESC to cancel.")
        else:
            self.freehand_btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            self.canvas.configure(cursor="")
            self.canvas.unbind("<Button-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.unbind("<Motion>")
            self.canvas.unbind("<Double-Button-1>")
            self.canvas.unbind("<Button-3>")
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
        # Stop preview if selection is already finalized/closed
        if self.apply_crop_btn.cget("state") == "normal":
            if self.lasso_preview:
                self.canvas.delete(self.lasso_preview)
                self.lasso_preview = None
            return

        if self.lasso_preview:
            self.canvas.delete(self.lasso_preview)
        
        # We need current canvas coords of the last point
        last_ix, last_iy = self.crop_points[-1]
        last_cx, last_cy = self._image_to_canvas(last_ix, last_iy)
        self.lasso_preview = self.canvas.create_line(last_cx, last_cy, event.x, event.y, fill="#00ffff", width=1, dash=(2, 2))

    def end_lasso(self, event=None):
        if len(self.crop_points) < 3:
            return
        # Close path visually (it's already closed in logic by just being a list of points)
        self.apply_crop_btn.configure(state="normal")
        self.render_preview()

    def _canvas_to_image(self, cx, cy):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        available_width = max(1, canvas_width - (CANVAS_PADDING * 2))
        available_height = max(1, canvas_height - (CANVAS_PADDING * 2))
        display = self.preview_image
        fit_ratio = min(available_width / display.width, available_height / display.height, 1.0)
        scale = max(0.01, fit_ratio * self.current_zoom)
        orig_w, orig_h = self.original_image.size
        cx_rel = cx - (canvas_width // 2)
        cy_rel = cy - (canvas_height // 2)
        ix = (cx_rel / scale) + (orig_w / 2)
        iy = (cy_rel / scale) + (orig_h / 2)
        return ix, iy

    def _image_to_canvas(self, ix, iy):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        available_width = max(1, canvas_width - (CANVAS_PADDING * 2))
        available_height = max(1, canvas_height - (CANVAS_PADDING * 2))
        display = self.preview_image
        fit_ratio = min(available_width / display.width, available_height / display.height, 1.0)
        scale = max(0.01, fit_ratio * self.current_zoom)
        orig_w, orig_h = self.original_image.size
        ix_rel = ix - (orig_w / 2)
        iy_rel = iy - (orig_h / 2)
        cx = (ix_rel * scale) + (canvas_width // 2)
        cy = (iy_rel * scale) + (canvas_height // 2)
        return cx, cy

    def redraw_lasso(self):
        self.lasso_lines = []
        if len(self.crop_points) < 2:
            return
        
        canvas_pts = [self._image_to_canvas(ix, iy) for ix, iy in self.crop_points]
        
        for i in range(len(canvas_pts) - 1):
            p1 = canvas_pts[i]
            p2 = canvas_pts[i+1]
            line = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#00ffff", width=2, dash=(4, 4))
            self.lasso_lines.append(line)
        
        # If stabilized (Apply btn active), close the loop
        if self.apply_crop_btn.cget("state") == "normal":
            p1 = canvas_pts[-1]
            p2 = canvas_pts[0]
            line = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#00ff00", width=2, dash=(4, 4))
            self.lasso_lines.append(line)

    def apply_lasso_crop(self):
        if not self.original_image or len(self.crop_points) < 3:
            return
        from PIL import ImageDraw
        
        # points are already in image coords
        mask = Image.new("L", self.original_image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(self.crop_points, outline=1, fill=255)

        # Apply mask
        result = Image.new("RGBA", self.original_image.size, (0, 0, 0, 0))
        result.paste(self.original_image, mask=mask)

        # Crop to bounding box
        bbox = mask.getbbox()
        if bbox:
            result = result.crop(bbox)
            self.original_image = result
            self.toggle_crop_mode() # Turn off crop mode after apply
            self.reset_adjustment_controls()
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

    def handle_zoom(self, event):
        if self.preview_image is None or self.crop_mode:
            return
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            self.current_zoom *= 0.9
        else:
            self.current_zoom *= 1.1
        self.current_zoom = min(max(self.current_zoom, 0.2), 5.0)
        self.render_preview()

    def reset_adjustment_controls(self):
        self.brightness.set(1.0)
        self.contrast.set(1.0)
        self.blur.set(0.0)

    def on_adjustment_change(self, _value=None):
        if self.original_image is None:
            return
        image = self.original_image.copy()
        image = ImageEnhance.Brightness(image).enhance(self.brightness.get())
        image = ImageEnhance.Contrast(image).enhance(self.contrast.get())
        if self.blur.get() > 0:
            image = image.filter(ImageFilter.GaussianBlur(radius=self.blur.get()))
        self.preview_image = image
        self.render_preview()

    def rotate_image(self, degrees):
        if self.original_image is None:
            return
        self.original_image = self.original_image.rotate(degrees, expand=True)
        self.on_adjustment_change()

    def flip_image(self, axis):
        if self.original_image is None:
            return
        if axis == "h":
            self.original_image = self.original_image.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            self.original_image = self.original_image.transpose(Image.FLIP_TOP_BOTTOM)
        self.on_adjustment_change()

    def reset_edits(self):
        if not self.selected_path:
            return
        self.select_path(self.selected_path)

    def export_image(self):
        if self.preview_image is None or not self.selected_path:
            return
        fmt = self._prompt("Export", "Format (png, jpg, webp, bmp, tiff, pdf):")
        if not fmt:
            return
        fmt = fmt.lower().strip(".")
        if fmt not in {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"}:
            messagebox.showerror("Error", "Unsupported format.")
            return

        initial_dir = None
        if self.app_state:
            initial_dir = self.app_state.settings.get("exports_folder")
        output_dir = filedialog.askdirectory(initialdir=initial_dir)
        if not output_dir:
            return

        base_name = os.path.splitext(os.path.basename(self.selected_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}_export.{fmt}")
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
            self.app_state.notify(f"Image exported: {os.path.basename(output_path)}")
        else:
            messagebox.showinfo("Done", f"Saved: {output_path}")

    def load_metadata(self):
        self.metadata_box.delete("1.0", "end")
        if not self.selected_path:
            return
        try:
            with Image.open(self.selected_path) as image:
                stat = os.stat(self.selected_path)
                self.metadata_box.insert("end", f"Name: {os.path.basename(self.selected_path)}\n")
                self.metadata_box.insert("end", f"Path: {self.selected_path}\n")
                self.metadata_box.insert("end", f"Size: {image.width} x {image.height}\n")
                self.metadata_box.insert("end", f"Mode: {image.mode}\n")
                self.metadata_box.insert("end", f"File Size: {stat.st_size / 1024:.1f} KB\n")
                self.metadata_box.insert(
                    "end",
                    f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n",
                )
                exif = image.getexif()
                self.metadata_box.insert("end", f"EXIF Tags: {len(exif) if exif else 0}\n")
        except Exception as exc:
            self.metadata_box.insert("end", f"Metadata error: {exc}")

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
            self.app_state.notify("OCR text copied to clipboard.")

    def save_ocr_text(self):
        text = self.ocr_box.get("1.0", "end").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            file.write(text)
        if self.app_state:
            self.app_state.notify(f"OCR saved: {os.path.basename(path)}")

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
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                with open(path, "wb") as file:
                    file.write(response.content)
            else:
                with urllib.request.urlopen(url, timeout=15) as stream:
                    payload = stream.read()
                with open(path, "wb") as file:
                    file.write(payload)
        except Exception as exc:
            messagebox.showerror("Error", f"Download failed: {exc}")
            return

        self._add_paths([path])
        self.select_path(path)

    def _prompt(self, title, message):
        dialog = ctk.CTkInputDialog(text=message, title=title)
        return dialog.get_input()
