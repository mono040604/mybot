from agent.tools.base import Tool  # FIX: 统一相对导入
from typing import Any

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._cached_definitions: list[dict] | None = None

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        self._cached_definitions = None

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._cached_definitions = None

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)
    
    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
    
    def get_definitions(self) -> list[dict[str, Any]]:
        if self._cached_definitions is not None:
            return self._cached_definitions
        self._cached_definitions = [t.to_schema() for t in self._tools.values()]
        return self._cached_definitions

    async def execute(self, name: str, params: dict) -> Any:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {self.tool_names}"  # FIX: 引号位置
        try:
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {e}"