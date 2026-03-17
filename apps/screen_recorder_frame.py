import os
import time
import datetime
import threading
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox
import cv2
import mss
import numpy as np
import pyaudio
import wave

class ScreenRecorderFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.grid_columnconfigure(0, weight=1)

        # Variables
        self.default_folder = ctk.StringVar(value=os.path.expanduser("~/Documents/1.Recs"))
        self.resolution = ctk.StringVar(value="1080p")
        self.selected_screen = ctk.StringVar()
        self.selected_audio = ctk.StringVar()
        self.is_recording = False
        
        # Audio / Video objects
        self.sct = mss.mss()
        self.monitors = self.sct.monitors
        
        try:
            self.audio = pyaudio.PyAudio()
            self.audio_devices = self.get_audio_devices()
        except Exception as e:
            print("PyAudio warning:", e)
            self.audio = None
            self.audio_devices = ["None"]
            
        self.fps = 20.0
        
        self.create_widgets()
        
    def get_audio_devices(self):
        devices = []
        try:
            for i in range(self.audio.get_device_count()):
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info.get('maxInputChannels') > 0:
                    devices.append(f"{i}: {dev_info.get('name')}")
        except:
            pass
        return devices if devices else ["None"]
        
    def create_widgets(self):
        # Header
        self.header = ctk.CTkLabel(self, text="1-Click Screen Recorder", font=ctk.CTkFont(size=24, weight="bold"))
        self.header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="n")

        # Config Frame
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.config_frame.grid_columnconfigure(1, weight=1)
        
        # Output Folder
        ctk.CTkLabel(self.config_frame, text="Save Folder:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.folder_entry = ctk.CTkEntry(self.config_frame, textvariable=self.default_folder)
        self.folder_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.browse_btn = ctk.CTkButton(self.config_frame, text="Browse", width=80, command=self.browse_folder)
        self.browse_btn.grid(row=0, column=2, padx=10, pady=10)

        # Monitor Selection
        ctk.CTkLabel(self.config_frame, text="Select Screen:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        screen_options = [f"Screen {i} ({self.monitors[i]['width']}x{self.monitors[i]['height']})" for i in range(1, len(self.monitors))]
        if not screen_options: screen_options = ["Primary"]
        self.screen_menu = ctk.CTkOptionMenu(self.config_frame, variable=self.selected_screen, values=screen_options)
        self.screen_menu.grid(row=1, column=1, padx=10, pady=10, sticky="ew", columnspan=2)
        if screen_options: self.selected_screen.set(screen_options[0])
        
        # Audio Input Selection
        ctk.CTkLabel(self.config_frame, text="Voice/Audio Input:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.audio_menu = ctk.CTkOptionMenu(self.config_frame, variable=self.selected_audio, values=self.audio_devices)
        self.audio_menu.grid(row=2, column=1, padx=10, pady=10, sticky="ew", columnspan=2)
        if self.audio_devices: self.selected_audio.set(self.audio_devices[0])

        # Resolution Selection
        ctk.CTkLabel(self.config_frame, text="Resolution:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.res_menu = ctk.CTkOptionMenu(self.config_frame, variable=self.resolution, values=["480p", "720p", "1080p"])
        self.res_menu.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        
        # Action Button
        self.record_btn = ctk.CTkButton(self, text="Start Recording", font=ctk.CTkFont(size=18, weight="bold"), height=50, command=self.toggle_recording, fg_color="#28a745", hover_color="#218838")
        self.record_btn.grid(row=2, column=0, padx=20, pady=30, sticky="ew")

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=14))
        self.status_label.grid(row=3, column=0, padx=20, pady=10)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.default_folder.set(folder)

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        save_dir = self.default_folder.get()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create directory: {e}")
                return

        # Determine target resolution
        res = self.resolution.get()
        if res == "480p":
            self.target_size = (854, 480)
        elif res == "720p":
            self.target_size = (1280, 720)
        else:
            self.target_size = (1920, 1080)

        # Get screen index
        try:
            screen_idx = int(self.selected_screen.get().split(" ")[1])
        except:
            screen_idx = 1
            
        self.monitor = self.monitors[screen_idx]

        # Get audio index
        audio_idx = None
        if self.selected_audio.get() != "None" and ":" in self.selected_audio.get():
            try:
                audio_idx = int(self.selected_audio.get().split(":")[0])
            except:
                pass

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.video_filename = os.path.join(save_dir, f"recording_{timestamp}.avi")
        self.audio_filename = os.path.join(save_dir, f"recording_{timestamp}.wav")
        self.final_filename = os.path.join(save_dir, f"recording_{timestamp}.mp4")

        self.is_recording = True
        self.record_btn.configure(text="Stop Recording", fg_color="#dc3545", hover_color="#c82333")
        self.status_label.configure(text="Recording...")

        # Start threads
        self.video_thread = threading.Thread(target=self.record_video, args=(self.monitor, self.video_filename))
        self.video_thread.start()

        self.audio_thread = None
        if audio_idx is not None and self.audio:
            self.audio_thread = threading.Thread(target=self.record_audio, args=(audio_idx, self.audio_filename))
            self.audio_thread.start()
            
    def stop_recording(self):
        self.is_recording = False
        self.record_btn.configure(text="Processing...", state="disabled", fg_color="gray")
        self.status_label.configure(text="Saving and processing media...")
        
        # We wait for threads in a separate thread to keep GUI responsive
        threading.Thread(target=self.finish_recording).start()

    def record_video(self, monitor, filename):
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(filename, fourcc, self.fps, self.target_size)
        delay = 1.0 / self.fps
        
        while self.is_recording:
            start_time = time.time()
            img = np.array(self.sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            frame = cv2.resize(frame, self.target_size)
            out.write(frame)
            
            elapsed = time.time() - start_time
            if delay - elapsed > 0:
                time.sleep(delay - elapsed)
                
        out.release()

    def record_audio(self, device_idx, filename):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        
        try:
            dev_info = self.audio.get_device_info_by_index(device_idx)
            max_channels = int(dev_info.get('maxInputChannels'))
            if max_channels >= 2:
                CHANNELS = 2
        except:
            pass

        try:
            stream = self.audio.open(format=FORMAT,
                                     channels=CHANNELS,
                                     rate=RATE,
                                     input=True,
                                     input_device_index=device_idx,
                                     frames_per_buffer=CHUNK)
                                     
            frames = []
            while self.is_recording:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                except:
                    pass
                    
            stream.stop_stream()
            stream.close()
            
            waveFile = wave.open(filename, 'wb')
            waveFile.setnchannels(CHANNELS)
            waveFile.setsampwidth(self.audio.get_sample_size(FORMAT))
            waveFile.setframerate(RATE)
            waveFile.writeframes(b''.join(frames))
            waveFile.close()
        except Exception as e:
            print(f"Audio recording failed: {e}")

    def finish_recording(self):
        self.video_thread.join()
        if self.audio_thread:
            self.audio_thread.join()
            
        if os.path.exists(self.audio_filename):
            try:
                subprocess.run(['ffmpeg', '-y', '-i', self.video_filename, '-i', self.audio_filename, '-c:v', 'copy', '-c:a', 'aac', self.final_filename], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(self.final_filename):
                    os.remove(self.video_filename)
                    os.remove(self.audio_filename)
            except Exception as e:
                print(f"FFmpeg muxing failed: {e}")
        else:
            try:
                subprocess.run(['ffmpeg', '-y', '-i', self.video_filename, '-c:v', 'copy', self.final_filename], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(self.final_filename):
                    os.remove(self.video_filename)
            except:
                pass

        self.after(0, self.reset_gui)
        
    def reset_gui(self):
        self.record_btn.configure(text="Start Recording", state="normal", fg_color="#28a745", hover_color="#218838")
        self.status_label.configure(text=f"Recording saved to {self.default_folder.get()}")
