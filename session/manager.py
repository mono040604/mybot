import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

@dataclass
class Session:
    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_messages(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now().isoformat()

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        return self.messages[-max_messages:]

class SessionManager:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = workspace / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)
        self._cache: dict[str, Session] = {}

    def get_or_create(self, key: str) -> Session:
        if key in self._cache:
            return self._cache[key]
        session = self._load(key) or Session(key=key)
        self._cache[key] = session
        return session

    def save(self, session: Session) -> None:
        self._cache[session.key] = session
        path = self._path_for(session.key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._to_dict(session), ensure_ascii=False, indent=2), 
                       encoding="utf-8",
                       )
        tmp.replace(path)

    def _load(self, key: str) -> Session | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session(
            key = data["key"],
            messages=data.get("messages", []),
            created_at=data.get("create_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at")
        )

    def _path_for(self, key: str) -> Path:
        safe = key.replace(":", "_").replace("/", "_")
        return self.sessions_dir / f"{safe}.json"

    @staticmethod
    def _to_dict(session: Session) -> dict:
        return {
            "key": session.key,
            "messages": session.messages,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }