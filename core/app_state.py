"""Application-wide state, settings, and task queue for SuperApp."""

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
        "accent": "Blue",
        "default_output_folder": os.path.join(home, "Documents", "SuperApp"),
        "recordings_folder": os.path.join(home, "Documents", "SuperApp", "Recordings"),
        "exports_folder": os.path.join(home, "Documents", "SuperApp", "Exports"),
        "organized_folder": os.path.join(home, "Documents", "SuperApp", "Organized"),
        "snapshots_folder": os.path.join(home, "Documents", "SuperApp", "Snapshots"),
        "preferred_image_format": "png",
        "preferred_video_format": "mp4",
        "max_workers": 2,
        "confirm_destructive": True,
        "enable_toasts": True,
        "recent_folders": [],
        "favorites": [],
    }


@dataclass
class TaskRecord:
    task_id: int
    name: str
    description: str
    runner: Callable[..., Any]
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: str = "Queued"
    progress: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    started_at: str = ""
    completed_at: str = ""
    result: str = ""
    error: str = ""
    cancel_requested: bool = False

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.started_at or not self.completed_at:
            return None
        try:
            start = datetime.strptime(self.started_at, "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(self.completed_at, "%Y-%m-%d %H:%M:%S")
            return (end - start).total_seconds()
        except ValueError:
            return None


class AppState:
    """Singleton-style state container passed into every frame."""

    def __init__(self):
        self.data_dir = os.path.join(os.path.expanduser("~"), ".superapp")
        self.settings_path = os.path.join(self.data_dir, "settings.json")
        # Plugins live alongside the app code, not cwd.
        self.plugins_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins"
        )

        self.settings: Dict[str, Any] = _default_settings()
        self.log_entries: List[str] = []
        self.task_history: List[TaskRecord] = []
        self.listeners: Dict[str, List[Callable[..., None]]] = {
            "logs": [],
            "tasks": [],
            "settings": [],
            "notifications": [],
            "recent": [],
        }
        self._task_queue: "queue.Queue[TaskRecord]" = queue.Queue()
        self._task_counter = 0
        self._task_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._current_task: Optional[TaskRecord] = None
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

        self._ensure_directories()
        self.load_settings()
        self.worker_thread.start()

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------
    def _ensure_directories(self):
        os.makedirs(self.data_dir, exist_ok=True)
        for value in _default_settings().values():
            if isinstance(value, str) and os.path.isabs(value):
                try:
                    os.makedirs(value, exist_ok=True)
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
                # Preserve list-type defaults if user file has wrong types
                for key in ("recent_folders", "favorites"):
                    if not isinstance(merged.get(key), list):
                        merged[key] = []
                self.settings = merged
        except Exception as exc:  # noqa: BLE001
            self.log(f"Failed to load settings: {exc}")

    def save_settings(self):
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=2)
        self.emit("settings", deepcopy(self.settings))

    def update_settings(self, updates: Dict[str, Any]):
        self.settings.update(updates)
        self.save_settings()
        self.notify("Settings saved.", level="success")

    # ------------------------------------------------------------------
    # Pub/sub
    # ------------------------------------------------------------------
    def subscribe(self, event_name: str, callback: Callable[..., None]):
        self.listeners.setdefault(event_name, []).append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[..., None]):
        if callback in self.listeners.get(event_name, []):
            self.listeners[event_name].remove(callback)

    def emit(self, event_name: str, *args, **kwargs):
        for callback in list(self.listeners.get(event_name, [])):
            try:
                callback(*args, **kwargs)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Logging + notifications
    # ------------------------------------------------------------------
    def log(self, message: str):
        timestamped = f"{datetime.now().strftime('%H:%M:%S')} {message}"
        self.log_entries.append(timestamped)
        self.log_entries = self.log_entries[-1000:]
        self.emit("logs", timestamped, list(self.log_entries))

    def notify(self, message: str, level: str = "info"):
        self.log(message)
        self.emit("notifications", message, level)

    # ------------------------------------------------------------------
    # Recent folders / favorites
    # ------------------------------------------------------------------
    def remember_folder(self, path: str):
        if not path:
            return
        recents = self.settings.setdefault("recent_folders", [])
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self.settings["recent_folders"] = recents[:10]
        self.save_settings()
        self.emit("recent", list(self.settings["recent_folders"]))

    def toggle_favorite(self, frame_id: str):
        favorites = self.settings.setdefault("favorites", [])
        if frame_id in favorites:
            favorites.remove(frame_id)
        else:
            favorites.insert(0, frame_id)
        self.settings["favorites"] = favorites
        self.save_settings()

    # ------------------------------------------------------------------
    # Task queue
    # ------------------------------------------------------------------
    def submit_task(
        self,
        name: str,
        description: str,
        runner: Callable[..., Any],
        **kwargs,
    ) -> TaskRecord:
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

    def rerun_task(self, task_id: int) -> bool:
        for task in self.task_history:
            if task.task_id == task_id:
                self.submit_task(task.name, task.description, task.runner, **task.kwargs)
                return True
        return False

    def cancel_task(self, task_id: int) -> bool:
        for task in self.task_history:
            if task.task_id == task_id:
                task.cancel_requested = True
                if task.status == "Queued":
                    task.status = "Cancelled"
                    task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.log(f"Cancelled queued task #{task_id}")
                    self.emit("tasks", list(self.task_history))
                return True
        return False

    def report_progress(self, task_id: int, progress: float, status_text: str = ""):
        for task in self.task_history:
            if task.task_id == task_id:
                task.progress = max(0.0, min(1.0, progress))
                if status_text:
                    task.result = status_text
                self.emit("tasks", list(self.task_history))
                return

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                task = self._task_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if task.cancel_requested:
                task.status = "Cancelled"
                task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.emit("tasks", list(self.task_history))
                self._task_queue.task_done()
                continue

            self._current_task = task
            task.status = "Running"
            task.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.emit("tasks", list(self.task_history))
            self.log(f"Started task #{task.task_id}: {task.name}")

            try:
                result = task.runner(**task.kwargs)
                if task.cancel_requested:
                    task.status = "Cancelled"
                    self.log(f"Task #{task.task_id} cancelled")
                else:
                    task.status = "Completed"
                    task.progress = 1.0
                    task.result = str(result) if result is not None else "Completed successfully."
                    self.log(f"Completed task #{task.task_id}: {task.name}")
            except Exception as exc:  # noqa: BLE001
                task.status = "Failed"
                task.error = str(exc)
                self.log(f"Task #{task.task_id} failed: {exc}")
                self.log(traceback.format_exc())
            finally:
                task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.emit("tasks", list(self.task_history))
                self._current_task = None
                self._task_queue.task_done()

    # ------------------------------------------------------------------
    # Plugin loading
    # ------------------------------------------------------------------
    def load_plugins(self):
        plugins = []
        if not os.path.isdir(self.plugins_dir):
            return plugins
        for filename in sorted(os.listdir(self.plugins_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            if filename == "base.py":
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
            except Exception as exc:  # noqa: BLE001
                self.log(f"Plugin load failed for {filename}: {exc}")
        return plugins

    # ------------------------------------------------------------------
    # Stats helpers
    # ------------------------------------------------------------------
    def task_stats(self) -> Dict[str, int]:
        counts = {"Queued": 0, "Running": 0, "Completed": 0, "Failed": 0, "Cancelled": 0}
        for task in self.task_history:
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts

    def shutdown(self):
        self._stop_event.set()
