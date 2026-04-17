import customtkinter as ctk
from core.app_state import AppState
from apps.duplicate_cleaner_frame import DuplicateCleanerFrame
from apps.quality_scaler_frame import QualityScalerFrame
from apps.screen_recorder_frame import ScreenRecorderFrame
from apps.batch_renamer_frame import BatchRenamerFrame
from apps.image_studio_frame import ImageStudioFrame
from apps.file_organizer_frame import FileOrganizerFrame
from apps.backup_snapshot_frame import BackupSnapshotFrame
from apps.settings_frame import SettingsFrame
from apps.task_queue_frame import TaskQueueFrame


class SuperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.app_state = AppState()

        self.title("Antigravity Toolkit - Super App")
        self.geometry("1320x820")

        # Set appearance
        ctk.set_appearance_mode(self.app_state.settings.get("theme", "Dark"))
        ctk.set_default_color_theme("blue")

        # Configure layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # Sidebar Frame
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(20, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="TOOLKIT v1.0", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Nav Buttons
        self.nav_buttons = {}
        nav_items = [
            ("cleaner", "Duplicate Cleaner", DuplicateCleanerFrame),
            ("renamer", "Batch Renamer", BatchRenamerFrame),
            ("scaler", "Quality + Compressor", QualityScalerFrame),
            ("image_studio", "Image Studio", ImageStudioFrame),
            ("organizer", "File Organizer", FileOrganizerFrame),
            ("snapshot", "Backup Snapshot", BackupSnapshotFrame),
            ("recorder", "Screen Recorder", ScreenRecorderFrame),
            ("tasks", "Task Queue", TaskQueueFrame),
            ("settings", "Settings", SettingsFrame),
        ]

        self.container = ctk.CTkFrame(self, corner_radius=15)
        self.container.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        for row_index, (frame_id, label, frame_cls) in enumerate(nav_items, start=1):
            self.add_nav_button(row_index, frame_id, label)
            self.frames[frame_id] = frame_cls(self.container, app_state=self.app_state)

        # Load plugin tools last
        plugin_row = len(nav_items) + 1
        for plugin in self.app_state.load_plugins():
            self.add_nav_button(plugin_row, plugin.plugin_id, plugin.button_text)
            self.frames[plugin.plugin_id] = plugin.build_frame(self.container, self.app_state)
            plugin_row += 1

        # Container for sub-apps
        self.status_bar = ctk.CTkFrame(self, height=42)
        self.status_bar.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready")
        self.status_label.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.app_state.subscribe("notifications", self.handle_notification)

        # Show first app by default
        self.show_cleaner()

    def add_nav_button(self, row, frame_id, label):
        button = ctk.CTkButton(
            self.sidebar,
            text=label,
            fg_color="transparent",
            border_width=1,
            command=lambda key=frame_id: self.show_frame(key),
        )
        button.grid(row=row, column=0, padx=20, pady=8, sticky="ew")
        self.nav_buttons[frame_id] = button

    def show_frame(self, name):
        self.active_frame(name)
        for frame_id, button in self.nav_buttons.items():
            button.configure(fg_color=["#3B8ED0", "#1F6AA5"] if frame_id == name else "transparent")

    def show_cleaner(self):
        self.show_frame("cleaner")

    def show_scaler(self):
        self.show_frame("scaler")

    def show_recorder(self):
        self.show_frame("recorder")

    def show_renamer(self):
        self.show_frame("renamer")

    def show_image_studio(self):
        self.show_frame("image_studio")

    def active_frame(self, name):
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[name].grid(row=0, column=0, sticky="nsew")

    def handle_notification(self, message):
        self.after(0, lambda: self.status_label.configure(text=message))

    def destroy(self):
        try:
            self.app_state.shutdown()
        except Exception:
            pass
        super().destroy()

if __name__ == "__main__":
    app = SuperApp()
    app.mainloop()
