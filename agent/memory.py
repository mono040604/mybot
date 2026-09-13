from pathlib import Path

class MemoryStore:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_file = self.memory_dir / "MEMORY.md"

    def read_memory(self) -> str:
        try:
            return self.memory_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def write_memory(self, content: str) -> None:
        tmp = self.memory_file.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(self.memory_file)

    def get_memory_context(self) -> str:
        long_term = self.read_memory()
        if long_term:
            return f"##长期记忆\n{long_term}"
        return ""