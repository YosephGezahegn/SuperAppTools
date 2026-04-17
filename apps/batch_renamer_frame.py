import os
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox


class BatchRenamerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # State
        self.input_files = []
        self.mode_var = ctk.StringVar(value="Template")
        self.keep_ext = ctk.BooleanVar(value=True)
        self.start_num = ctk.IntVar(value=1)
        self.step_num = ctk.IntVar(value=1)

        self.create_widgets()

    def create_widgets(self):
        # Header
        self.header = ctk.CTkLabel(self, text="Batch Renamer", font=ctk.CTkFont(size=24, weight="bold"))
        self.header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="n")

        # Mode switch
        self.mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.mode_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        self.mode_switch = ctk.CTkSegmentedButton(
            self.mode_frame,
            values=["Template", "Regex"],
            variable=self.mode_var,
            command=self.toggle_mode,
        )
        self.mode_switch.pack(fill="x")

        # Settings
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Template settings
        self.template_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.template_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.template_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(self.template_frame, text="Template:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.template_entry = ctk.CTkEntry(self.template_frame)
        self.template_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        self.template_entry.insert(0, "{name}_{n:03}{ext}")

        self.keep_ext_cb = ctk.CTkCheckBox(self.template_frame, text="Keep Extension", variable=self.keep_ext)
        self.keep_ext_cb.grid(row=0, column=2, padx=5, pady=8, sticky="w")

        ctk.CTkLabel(self.template_frame, text="Start #:").grid(row=1, column=0, padx=5, pady=8, sticky="w")
        self.start_entry = ctk.CTkEntry(self.template_frame, textvariable=self.start_num, width=80)
        self.start_entry.grid(row=1, column=1, padx=5, pady=8, sticky="w")

        ctk.CTkLabel(self.template_frame, text="Step:").grid(row=1, column=2, padx=5, pady=8, sticky="w")
        self.step_entry = ctk.CTkEntry(self.template_frame, textvariable=self.step_num, width=80)
        self.step_entry.grid(row=1, column=2, padx=55, pady=8, sticky="w")

        self.template_hint = ctk.CTkLabel(
            self.template_frame,
            text="Tokens: {name} {ext} {n} (supports {n:03})",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.template_hint.grid(row=2, column=0, columnspan=3, padx=5, pady=(0, 8), sticky="w")

        # Regex settings
        self.regex_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.regex_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(self.regex_frame, text="Pattern:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.regex_pattern = ctk.CTkEntry(self.regex_frame)
        self.regex_pattern.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        ctk.CTkLabel(self.regex_frame, text="Replace:").grid(row=1, column=0, padx=5, pady=8, sticky="w")
        self.regex_replace = ctk.CTkEntry(self.regex_frame)
        self.regex_replace.grid(row=1, column=1, padx=5, pady=8, sticky="ew")

        self.toggle_mode("Template")

        # Content
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.content_frame.grid_columnconfigure((0, 1), weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.file_list = ctk.CTkTextbox(self.content_frame)
        self.file_list.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.file_list.insert("0.0", "--- Input Files ---\n")

        self.preview_list = ctk.CTkTextbox(self.content_frame)
        self.preview_list.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.preview_list.insert("0.0", "--- Preview ---\n")

        # Footer actions
        self.footer = ctk.CTkFrame(self)
        self.footer.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.add_btn = ctk.CTkButton(self.footer, text="Add Files", command=self.add_files)
        self.add_btn.pack(side="left", padx=5, pady=5)

        self.add_folder_btn = ctk.CTkButton(self.footer, text="Add Folder", command=self.add_folder)
        self.add_folder_btn.pack(side="left", padx=5, pady=5)

        self.clear_btn = ctk.CTkButton(self.footer, text="Clear", fg_color="gray", command=self.clear_files)
        self.clear_btn.pack(side="left", padx=5, pady=5)

        self.preview_btn = ctk.CTkButton(self.footer, text="Preview", command=self.preview_rename)
        self.preview_btn.pack(side="right", padx=5, pady=5)

        self.rename_btn = ctk.CTkButton(self.footer, text="Rename", fg_color="green", command=self.apply_rename, state=ctk.DISABLED)
        self.rename_btn.pack(side="right", padx=5, pady=5)

    def toggle_mode(self, mode):
        if mode == "Template":
            self.regex_frame.grid_forget()
            self.template_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        else:
            self.template_frame.grid_forget()
            self.regex_frame.grid(row=0, column=0, columnspan=3, sticky="ew")

    def add_files(self):
        files = filedialog.askopenfilenames()
        for f in files:
            if f not in self.input_files:
                self.input_files.append(f)
                self.file_list.insert("end", f"{os.path.basename(f)}\n")
        self.rename_btn.configure(state=ctk.DISABLED)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and path not in self.input_files:
                self.input_files.append(path)
                self.file_list.insert("end", f"{os.path.basename(path)}\n")
        self.rename_btn.configure(state=ctk.DISABLED)

    def clear_files(self):
        self.input_files = []
        self.file_list.delete("1.0", "end")
        self.file_list.insert("0.0", "--- Input Files ---\n")
        self.preview_list.delete("1.0", "end")
        self.preview_list.insert("0.0", "--- Preview ---\n")
        self.rename_btn.configure(state=ctk.DISABLED)

    def _build_new_name(self, path, index):
        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        if self.mode_var.get() == "Template":
            template = self.template_entry.get().strip()
            n = self.start_num.get() + (index * self.step_num.get())
            try:
                new_name = template.format(name=name, ext=ext, n=n)
            except Exception as e:
                raise ValueError(f"Template error: {e}")
            if self.keep_ext.get() and "{ext}" not in template:
                new_name += ext
        else:
            pattern = self.regex_pattern.get()
            repl = self.regex_replace.get()
            try:
                new_name = re.sub(pattern, repl, name)
            except Exception as e:
                raise ValueError(f"Regex error: {e}")
            if self.keep_ext.get():
                new_name += ext
        return new_name

    def preview_rename(self):
        if not self.input_files:
            messagebox.showerror("Error", "Please add files first.")
            return

        self.preview_list.delete("1.0", "end")
        self.preview_list.insert("0.0", "--- Preview ---\n")

        try:
            preview = self._build_preview()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            self.rename_btn.configure(state=ctk.DISABLED)
            return

        if preview["conflicts"]:
            self.preview_list.insert("end", "Conflicts detected:\n")
            for item in preview["conflicts"]:
                self.preview_list.insert("end", f"  {item}\n")
            self.rename_btn.configure(state=ctk.DISABLED)
            return

        for old, new in preview["pairs"]:
            self.preview_list.insert("end", f"{os.path.basename(old)}  ->  {new}\n")

        self.rename_btn.configure(state=ctk.NORMAL)

    def _build_preview(self):
        pairs = []
        new_names = []
        conflicts = []

        for i, path in enumerate(self.input_files):
            new_name = self._build_new_name(path, i)
            pairs.append((path, new_name))
            new_names.append(new_name)

        # Detect duplicates in target names
        seen = set()
        for name in new_names:
            if name in seen:
                conflicts.append(f"Duplicate target name: {name}")
            seen.add(name)

        # Detect collisions with existing files
        for old, new in pairs:
            target = os.path.join(os.path.dirname(old), new)
            if os.path.exists(target) and target != old:
                conflicts.append(f"Exists already: {new}")

        return {"pairs": pairs, "conflicts": conflicts}

    def apply_rename(self):
        if not self.input_files:
            return

        try:
            preview = self._build_preview()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        if preview["conflicts"]:
            messagebox.showerror("Error", "Conflicts found. Fix and preview again.")
            return

        if not messagebox.askyesno("Confirm", f"Rename {len(preview['pairs'])} files?"):
            return

        errors = 0
        for old, new in preview["pairs"]:
            target = os.path.join(os.path.dirname(old), new)
            try:
                os.rename(old, target)
            except Exception:
                errors += 1

        if errors:
            messagebox.showwarning("Done", f"Renamed with {errors} errors.")
        else:
            messagebox.showinfo("Done", "All files renamed successfully.")
            if self.app_state:
                self.app_state.notify(f"Batch rename finished: {len(preview['pairs'])} files.")

        self.clear_files()
