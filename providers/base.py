from dataclasses import dataclass, field
from abc import ABC, abstractmethod  # FIX: abstractclassmethod → abstractmethod


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class GenerationSettings:
    temperature: float = 0.7
    max_tokens: int = 4096


class LLMProvider(ABC):
    def __init__(self, api_key="", api_base="", default_model=""):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.generation = GenerationSettings()

    @abstractmethod  # FIX: abstractclassmethod → abstractmethod
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        """非流式请求。子类必须实现。"""
        ...

    @abstractmethod  # FIX: 去掉 async（get_default_model 是同步方法）
    def get_default_model(self) -> str:
        """返回默认模型名。"""
        ...

    # FIX: chat_stream 有默认实现，不该是 abstract
    async def chat_stream(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, on_content_delta=None) -> LLMResponse:
        """流式请求。默认实现：回退到非流式 chat()，拿到完整内容后一次性回调。"""
        response = await self.chat(messages=messages, tools=tools, model=model,
                                   max_tokens=max_tokens, temperature=temperature)
        if on_content_delta and response.content:
            await on_content_delta(response.content)
        return response