import importlib.util
import json
import os
import queue
import threading
import traceback
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


def _default_settings() -> Dict[str, Any]:
    home = os.path.expanduser("~")
    return {
        "theme": "Dark",
        "default_output_folder": os.path.join(home, "Documents", "SuperApp"),
        "recordings_folder": os.path.join(home, "Documents", "SuperApp", "Recordings"),
        "exports_folder": os.path.join(home, "Documents", "SuperApp", "Exports"),
        "organized_folder": os.path.join(home, "Documents", "SuperApp", "Organized"),
        "snapshots_folder": os.path.join(home, "Documents", "SuperApp", "Snapshots"),
        "preferred_image_format": "png",
        "preferred_video_format": "mp4",
        "max_workers": 2,
    }


@dataclass
class TaskRecord:
    task_id: int
    name: str
    description: str
    runner: Callable[..., Any]
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: str = "Queued"
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    started_at: str = ""
    completed_at: str = ""
    result: str = ""
    error: str = ""


class AppState:
    def __init__(self):
        self.data_dir = os.path.join(os.path.expanduser("~"), ".superapp")
        self.settings_path = os.path.join(self.data_dir, "settings.json")
        self.plugins_dir = os.path.join(os.getcwd(), "plugins")

        self.settings = _default_settings()
        self.log_entries: List[str] = []
        self.task_history: List[TaskRecord] = []
        self.listeners: Dict[str, List[Callable[..., None]]] = {
            "logs": [],
            "tasks": [],
            "settings": [],
            "notifications": [],
        }
        self._task_queue: "queue.Queue[TaskRecord]" = queue.Queue()
        self._task_counter = 0
        self._task_lock = threading.Lock()
        self._stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

        self._ensure_directories()
        self.load_settings()
        self.worker_thread.start()

    def _ensure_directories(self):
        os.makedirs(self.data_dir, exist_ok=True)
        for path in _default_settings().values():
            if isinstance(path, str) and os.path.isabs(path):
                try:
                    os.makedirs(path, exist_ok=True)
                except OSError:
                    pass
        os.makedirs(self.plugins_dir, exist_ok=True)

    def load_settings(self):
        if not os.path.exists(self.settings_path):
            self.save_settings()
            return

        try:
            with open(self.settings_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                merged = _default_settings()
                merged.update(data)
                self.settings = merged
        except Exception as exc:
            self.log(f"Failed to load settings: {exc}")

    def save_settings(self):
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=2)
        self.emit("settings", deepcopy(self.settings))

    def update_settings(self, updates: Dict[str, Any]):
        self.settings.update(updates)
        self.save_settings()
        self.notify("Settings saved.")

    def subscribe(self, event_name: str, callback: Callable[..., None]):
        self.listeners.setdefault(event_name, []).append(callback)

    def emit(self, event_name: str, *args, **kwargs):
        for callback in self.listeners.get(event_name, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                pass

    def log(self, message: str):
        timestamped = f"{datetime.now().strftime('%H:%M:%S')} {message}"
        self.log_entries.append(timestamped)
        self.log_entries = self.log_entries[-500:]
        self.emit("logs", timestamped, list(self.log_entries))

    def notify(self, message: str):
        self.log(message)
        self.emit("notifications", message)

    def submit_task(self, name: str, description: str, runner: Callable[..., Any], **kwargs) -> TaskRecord:
        with self._task_lock:
            self._task_counter += 1
            task = TaskRecord(
                task_id=self._task_counter,
                name=name,
                description=description,
                runner=runner,
                kwargs=kwargs,
            )
            self.task_history.insert(0, task)
        self._task_queue.put(task)
        self.emit("tasks", list(self.task_history))
        self.log(f"Queued task #{task.task_id}: {task.name}")
        return task

    def rerun_task(self, task_id: int):
        for task in self.task_history:
            if task.task_id == task_id:
                self.submit_task(task.name, task.description, task.runner, **task.kwargs)
                return True
        return False

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                task = self._task_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            task.status = "Running"
            task.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.emit("tasks", list(self.task_history))
            self.log(f"Started task #{task.task_id}: {task.name}")

            try:
                result = task.runner(**task.kwargs)
                task.status = "Completed"
                task.result = str(result) if result is not None else "Completed successfully."
                self.log(f"Completed task #{task.task_id}: {task.name}")
            except Exception as exc:
                task.status = "Failed"
                task.error = str(exc)
                self.log(f"Task #{task.task_id} failed: {exc}")
                self.log(traceback.format_exc())
            finally:
                task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.emit("tasks", list(self.task_history))
                self._task_queue.task_done()

    def load_plugins(self):
        plugins = []
        if not os.path.isdir(self.plugins_dir):
            return plugins

        for filename in sorted(os.listdir(self.plugins_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            path = os.path.join(self.plugins_dir, filename)
            module_name = f"superapp_plugin_{os.path.splitext(filename)[0]}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register_plugin"):
                    plugin = module.register_plugin(self)
                    if plugin:
                        plugins.append(plugin)
                        self.log(f"Loaded plugin: {getattr(plugin, 'button_text', filename)}")
            except Exception as exc:
                self.log(f"Plugin load failed for {filename}: {exc}")
        return plugins

    def shutdown(self):
        self._stop_event.set()
