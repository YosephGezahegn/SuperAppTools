import customtkinter as ctk
from apps.duplicate_cleaner_frame import DuplicateCleanerFrame
from apps.quality_scaler_frame import QualityScalerFrame
from apps.screen_recorder_frame import ScreenRecorderFrame
class SuperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Antigravity Toolkit - Super App")
        self.geometry("1100x750")

        # Set appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Configure layout (2x1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar Frame
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="TOOLKIT v1.0", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Nav Buttons
        self.btn_cleaner = ctk.CTkButton(self.sidebar, text="Duplicate Cleaner", 
                                        fg_color="transparent", border_width=1,
                                        command=self.show_cleaner)
        self.btn_cleaner.grid(row=1, column=0, padx=20, pady=10)

        self.btn_scaler = ctk.CTkButton(self.sidebar, text="Quality Scaler", 
                                       fg_color="transparent", border_width=1,
                                       command=self.show_scaler)
        self.btn_scaler.grid(row=2, column=0, padx=20, pady=10)

        self.btn_recorder = ctk.CTkButton(self.sidebar, text="Screen Recorder", 
                                       fg_color="transparent", border_width=1,
                                       command=self.show_recorder)
        self.btn_recorder.grid(row=3, column=0, padx=20, pady=10)
        # Container for sub-apps
        self.container = ctk.CTkFrame(self, corner_radius=15)
        self.container.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # Initialize Frames
        self.frames = {}
        self.frames["cleaner"] = DuplicateCleanerFrame(self.container)
        self.frames["scaler"] = QualityScalerFrame(self.container)
        self.frames["recorder"] = ScreenRecorderFrame(self.container)
        
        # Show first app by default
        self.show_cleaner()

    def show_cleaner(self):
        self.active_frame("cleaner")
        self.btn_cleaner.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.btn_scaler.configure(fg_color="transparent")
        self.btn_recorder.configure(fg_color="transparent")

    def show_scaler(self):
        self.active_frame("scaler")
        self.btn_scaler.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.btn_cleaner.configure(fg_color="transparent")
        self.btn_recorder.configure(fg_color="transparent")

    def show_recorder(self):
        self.active_frame("recorder")
        self.btn_recorder.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.btn_cleaner.configure(fg_color="transparent")
        self.btn_scaler.configure(fg_color="transparent")

    def active_frame(self, name):
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[name].grid(row=0, column=0, sticky="nsew")

if __name__ == "__main__":
    app = SuperApp()
    app.mainloop()
