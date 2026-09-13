import httpx
import json
from typing import Any
from loguru import logger
from providers.base import LLMProvider, LLMResponse, ToolCallRequest

class OpenAICompatProvider(LLMProvider):
    async def chat(self,
                   messages: list[dict[str, Any]], 
                   tools: list[dict[str, Any]] | None = None, 
                   model: str | None = None, 
                   max_tokens: int = 4096, 
                   temperature: float = 0.7) -> LLMResponse:
        model = model or self.default_model
        url = f"{self.api_base}/chat/completions"

        body = {
            "model": model,
            "messages": self._clean_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = self._format_tools(tools)
            body["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body, headers=headers)

        if resp.status_code != 200:
            return LLMResponse(
                content=f"API_error {resp.status_code}:{resp.text[:500]}",
                finish_reason="error",
            )
        return self._parse_response(resp.json())  # FIX: _pares→_parse

    async def chat_stream(self, 
                          messages:list[dict[str, Any]], 
                          tools:list[dict[str, Any]] | None = None, 
                          model: str | None = None, 
                          max_tokens: int = 4096,
                          temperature: float = 0.7, 
                          on_content_delta=None) -> LLMResponse:
        model = model or self.default_model
        url = f"{self.api_base}/chat/completions"

        body = {
                    "model": model,
                    "messages": self._clean_messages(messages),
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
        if tools:
            body["tools"] = self._format_tools(tools)
            body["tool_choice"] = "auto"  # FIX: tools_choice→tool_choice

        headers = {
            "Authorization":f"Bearer {self.api_key}",
            "Content-Type":"application/json",
        }

        collected_content = ""
        collected_tool_calls: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    return LLMResponse(
                        content=f"API error {resp.status_code}: {error_text.decode()[:500]}",
                        finish_reason="error",
                    )
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str =line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}

                    text = delta.get("content") or ""
                    if text and on_content_delta:
                        await on_content_delta(text)
                    collected_content += text

                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc.get("id",""),
                                "name": "",
                                "arguments": "",
                            }
                        existing = collected_tool_calls[idx]
                        if tc.get("id"):
                            existing["id"] = tc["id"]
                        if tc.get("function"):
                            existing["name"] += tc["function"].get("name", "")
                            existing["arguments"] += tc["function"].get("arguments", "")
                    # FIX: usage收集移到for tc外面，仍在async for里面
                    if "usage" in chunk:
                        usage = {
                            "prompt_tokens": chunk["usage"].get("prompt_tokens", 0),
                            "completion_tokens": chunk["usage"].get("completion_tokens", 0),
                            "total_tokens": chunk["usage"].get("total_tokens", 0),
                        }

        # FIX: 移到async for外面，流式结束后组装结果
        tool_calls = []
        for idx in sorted(collected_tool_calls.keys()):
            tc_data = collected_tool_calls[idx]  # FIX: ( )→[ ]
            try:
                args = json.load(tc_data["arguments"])
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallRequest(
                id = tc_data["id"],
                name=tc_data["name"],
                arguments=args
            ))

        finish_reason = "tool_calls" if tool_calls else "stop"
        return LLMResponse(
            content=collected_content or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
    def get_default_model(self) -> str:
        return self.default_model  # FIX: 返回属性而非方法

    @staticmethod
    def _format_tools(tools:list[dict[str, Any]]) -> list[dict[str, Any]]:
        return[
            {"type": "function", "function": t}
            for t in tools
        ]

    @staticmethod
    def _clean_messages(message:list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned = []
        for msg in message:
            m = dict(msg)
            if m.get("role") == "assistant" and not m.get("content"):
                m["content"] = None if m.get("tool_calls") else ""
            cleaned.append(m)
        return cleaned

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> LLMResponse:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content")
        finish_reason = choice.get("finish_reason", "stop")
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})  # FIX: []→{}
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallRequest(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=args,
            ))
        # FIX: usage和return移到for循环外面
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason if not tool_calls else "tool_calls",
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )