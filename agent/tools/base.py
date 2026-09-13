from abc import ABC, abstractmethod
from typing import Any

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        ...

    def to_schema(self) -> dict[str, Any]:
        return{
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
    