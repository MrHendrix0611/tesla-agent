class PermissionManager:

    def __init__(self):
        self.allowed_tools = {
            "read_file",
            "list_files",
            "search_files",
            "repository_map",
            "repository_search",
            "repository_symbols",
            "git_status",
            "git_diff",
            "git_log",
            "preview_patch",
            "diff_file",
        }

        self.confirmation_required = {
            "run_command",
            "write_file",
            "apply_patch",
            "rollback_file",
            "run_tests",
        }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools

    def requires_confirmation(self, tool_name: str) -> bool:
        return tool_name in self.confirmation_required

    def can_execute(self, tool_name: str) -> bool:
        return self.is_allowed(tool_name)

    def get_status(self, tool_name: str) -> str:
        if self.is_allowed(tool_name):
            return "allowed"

        if self.requires_confirmation(tool_name):
            return "confirmation_required"

        return "denied"