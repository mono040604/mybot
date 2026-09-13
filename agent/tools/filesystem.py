from pathlib import Path
from typing import Any
from agent.tools.base import Tool  # FIX: 统一相对导入


class ReadFileTool(Tool):  # FIX: 原来缺这行类声明，__init__ 飘在模块顶层
    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path"

    @property
    def parameters(self) -> dict[str, Any]:  # FIX: parmeters → parameters
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read (relative to workspace)"
                }
            },
            "required": ["path"],
        }

    async def execute(self, path: str) -> str:
        full_path = self.workspace / path
        try:
            full_path.resolve().relative_to(self.workspace.resolve())
        except ValueError:
            return f"Error: Path '{path}' is outside the workspace"
        if not full_path.exists():
            return f"Error: File '{path}' not found"

        try:
            return full_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"