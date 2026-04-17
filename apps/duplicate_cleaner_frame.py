import os
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Regex to match numbered copy patterns: "filename (1).ext", "filename (2).ext", etc.
COPY_PATTERN = re.compile(r'^(.+?)\s*\((\d+)\)(\.[^.]+)$')

class DuplicateCleanerFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Variables
        self.target_folder = ctk.StringVar()
        self.check_size = ctk.BooleanVar(value=True)
        self.recursive = ctk.BooleanVar(value=True)
        self.smart_detection = ctk.BooleanVar(value=True)
        self.match_count = ctk.IntVar(value=10)
        self.duplicates = []

        self.create_widgets()

    def create_widgets(self):
        # Header
        self.header = ctk.CTkLabel(self, text="File Duplicate Cleaner", font=ctk.CTkFont(size=24, weight="bold"))
        self.header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="n")

        # Folder Selection
        self.folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.folder_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.folder_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.folder_frame, text="Target Folder:").grid(row=0, column=0, padx=5)
        self.folder_entry = ctk.CTkEntry(self.folder_frame, textvariable=self.target_folder)
        self.folder_entry.grid(row=0, column=1, padx=10, sticky="ew")
        self.browse_btn = ctk.CTkButton(self.folder_frame, text="Browse", width=100, command=self.browse_folder)
        self.browse_btn.grid(row=0, column=2, padx=5)

        # Options Frame
        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.options_frame.grid_columnconfigure((0,1,2), weight=1)

        # Row 0: Basic Options
        self.smart_cb = ctk.CTkCheckBox(self.options_frame, text="Smart Copy Detection", variable=self.smart_detection)
        self.smart_cb.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.check_size_cb = ctk.CTkCheckBox(self.options_frame, text="Verify File Size", variable=self.check_size)
        self.check_size_cb.grid(row=0, column=1, padx=20, pady=10, sticky="w")
        
        self.recursive_cb = ctk.CTkCheckBox(self.options_frame, text="Scan Subfolders", variable=self.recursive)
        self.recursive_cb.grid(row=0, column=2, padx=20, pady=10, sticky="w")

        # Row 1: Advanced Prefix Setting
        self.prefix_frame = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        self.prefix_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10)
        
        ctk.CTkLabel(self.prefix_frame, text="Legacy Match (prefix chars):").pack(side="left", padx=(10, 5))
        self.match_entry = ctk.CTkEntry(self.prefix_frame, textvariable=self.match_count, width=60)
        self.match_entry.pack(side="left", padx=5)
        
        self.hint_label = ctk.CTkLabel(self.prefix_frame, text='(Set to 0 to disable prefix matching)', font=ctk.CTkFont(size=11), text_color="gray")
        self.hint_label.pack(side="left", padx=5)

        # Action Buttons
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure((0,1), weight=1)

        self.scan_btn = ctk.CTkButton(self.action_frame, text="Scan for Duplicates", height=40, command=self.scan_files)
        self.scan_btn.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.clean_btn = ctk.CTkButton(self.action_frame, text="Delete Duplicates", height=40, 
                                      fg_color="indianred", hover_color="darkred",
                                      command=self.confirm_delete, state=ctk.DISABLED)
        self.clean_btn.grid(row=0, column=1, padx=5, sticky="ew")

        # Results List
        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.results_frame.grid_rowconfigure(1, weight=1)

        self.results_label = ctk.CTkLabel(self.results_frame, text="Duplicates Found:", font=ctk.CTkFont(weight="bold"))
        self.results_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.results_list = ctk.CTkTextbox(self.results_frame)
        self.results_list.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.target_folder.set(folder)

    def scan_files(self):
        folder = self.target_folder.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Error", "Please select a valid folder.")
            return

        self.results_list.delete("1.0", "end")
        self.duplicates = []
        unique_dups = set()

        try:
            # 1. Run Smart Copy Detection if enabled
            if self.smart_detection.get():
                self.scan_numbered_copies(folder, unique_dups)

            # 2. Run Prefix Match (Legacy) if enabled
            if self.match_count.get() > 0:
                self.scan_prefix_match(folder, unique_dups)

            if self.duplicates:
                self.clean_btn.configure(state=ctk.NORMAL)
                total_size = sum(os.path.getsize(f) for f in self.duplicates if os.path.exists(f))
                size_mb = total_size / (1024 * 1024)
                if self.app_state:
                    self.app_state.log(f"Duplicate scan found {len(self.duplicates)} files ({size_mb:.1f} MB).")
                messagebox.showinfo("Scan Complete", 
                    f"Found {len(self.duplicates)} duplicates.\n"
                    f"Total size: {size_mb:.1f} MB")
            else:
                self.clean_btn.configure(state=ctk.DISABLED)
                messagebox.showinfo("Scan Complete", "No duplicates found.")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def scan_numbered_copies(self, folder, unique_dups):
        """Detect numbered copies: file (1).ext, etc."""
        all_files = {}
        for root, dirs, files in os.walk(folder):
            if not self.recursive.get() and root != folder:
                continue
            all_files[root] = set(files)

        for dir_path, filenames in all_files.items():
            for filename in sorted(filenames):
                match = COPY_PATTERN.match(filename)
                if match:
                    base_name = match.group(1).strip()
                    copy_num = match.group(2)
                    extension = match.group(3)
                    original_name = base_name + extension

                    if original_name in filenames:
                        dup_path = os.path.join(dir_path, filename)
                        if dup_path not in unique_dups:
                            unique_dups.add(dup_path)
                            self.duplicates.append(dup_path)
                            size_kb = os.path.getsize(dup_path) // 1024
                            self.results_list.insert("end", 
                                f"[SMART COPY #{copy_num}] {filename} ({size_kb} KB)\n"
                                f"   Original: {original_name}\n"
                                f"   Path: {dup_path}\n\n")

    def scan_prefix_match(self, folder, unique_dups):
        """Standard prefix-based duplicate detection."""
        file_map = {}
        match_n = self.match_count.get()

        for root, dirs, files in os.walk(folder):
            if not self.recursive.get() and root != folder:
                continue
            
            for filename in files:
                file_path = os.path.join(root, filename)
                if file_path in unique_dups: continue # Already found by smart scan

                try:
                    file_size = os.path.getsize(file_path)
                    prefix = filename[:match_n].lower()
                    key = (prefix, file_size) if self.check_size.get() else prefix
                    
                    if key not in file_map:
                        file_map[key] = []
                    file_map[key].append(file_path)
                except: continue

        for key, paths in file_map.items():
            if len(paths) > 1:
                paths.sort()
                for dup in paths[1:]:
                    if dup not in unique_dups:
                        unique_dups.add(dup)
                        self.duplicates.append(dup)
                        size_kb = os.path.getsize(dup) // 1024
                        self.results_list.insert("end", f"[PREFIX MATCH] {os.path.basename(dup)} ({size_kb} KB)\n   Path: {dup}\n\n")

    def confirm_delete(self):
        if messagebox.askyesno("Confirm", f"Delete {len(self.duplicates)} files?"):
            self.delete_files()

    def delete_files(self):
        count = 0
        for f in self.duplicates:
            try:
                os.remove(f)
                count += 1
            except: pass
        if self.app_state:
            self.app_state.notify(f"Duplicate cleaner deleted {count} files.")
        messagebox.showinfo("Done", f"Deleted {count} files.")
        self.scan_files()
