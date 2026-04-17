import customtkinter as ctk


class TaskQueueFrame(ctk.CTkFrame):
    def __init__(self, master, app_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app_state = app_state
        self.task_map = {}
        self.selected_task_id = None

        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_widgets()
        if self.app_state:
            self.app_state.subscribe("tasks", self.refresh_tasks)
            self.app_state.subscribe("logs", self.refresh_logs)
            self._refresh_tasks_ui(self.app_state.task_history)
            for entry in self.app_state.log_entries[-100:]:
                self.log_box.insert("end", entry + "\n")

    def create_widgets(self):
        ctk.CTkLabel(self, text="Task Queue + History", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="n"
        )

        self.task_panel = ctk.CTkScrollableFrame(self)
        self.task_panel.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")

        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        self.detail_box = ctk.CTkTextbox(right, height=220)
        self.detail_box.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.log_box = ctk.CTkTextbox(right)
        self.log_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        ctk.CTkButton(footer, text="Re-run Selected", command=self.rerun_selected).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Clear Log View", fg_color="gray", command=self.clear_logs).pack(side="right", padx=5)

    def refresh_tasks(self, tasks):
        self.after(0, lambda: self._refresh_tasks_ui(tasks))

    def _refresh_tasks_ui(self, tasks):
        for child in self.task_panel.winfo_children():
            child.destroy()
        self.task_map = {}

        for row, task in enumerate(tasks):
            label = f"#{task.task_id} {task.name} [{task.status}]"
            btn = ctk.CTkButton(
                self.task_panel,
                text=label,
                anchor="w",
                fg_color="#1F6AA5" if task.task_id == self.selected_task_id else "#151515",
                command=lambda t=task: self.select_task(t),
            )
            btn.grid(row=row, column=0, padx=5, pady=4, sticky="ew")
            self.task_map[task.task_id] = task

        if self.selected_task_id and self.selected_task_id in self.task_map:
            self.select_task(self.task_map[self.selected_task_id])

    def select_task(self, task):
        self.selected_task_id = task.task_id
        self.detail_box.delete("1.0", "end")
        self.detail_box.insert(
            "end",
            "\n".join(
                [
                    f"Task #{task.task_id}",
                    f"Name: {task.name}",
                    f"Description: {task.description}",
                    f"Status: {task.status}",
                    f"Created: {task.created_at}",
                    f"Started: {task.started_at or '-'}",
                    f"Completed: {task.completed_at or '-'}",
                    f"Result: {task.result or '-'}",
                    f"Error: {task.error or '-'}",
                ]
            ),
        )

    def refresh_logs(self, latest_entry, _all_entries):
        self.after(0, lambda: self._refresh_logs_ui(latest_entry))

    def _refresh_logs_ui(self, latest_entry):
        self.log_box.insert("end", latest_entry + "\n")
        self.log_box.see("end")

    def rerun_selected(self):
        if self.app_state and self.selected_task_id:
            self.app_state.rerun_task(self.selected_task_id)

    def clear_logs(self):
        self.log_box.delete("1.0", "end")
