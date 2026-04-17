class ToolPlugin:
    plugin_id = "plugin"
    button_text = "Plugin"

    def build_frame(self, master, app_state):
        raise NotImplementedError
