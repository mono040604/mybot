from dataclasses import dataclass, field
from typing import Any
from loguru import logger

@dataclass
class AgentRunSpec:
    initial_messages: list[dict[str, Any]]
    tools: Any
    provider: Any
    max_iterations: int = 15
    max_tool_result_chars: int = 80000

@dataclass
class AgentRunResult:
    final_content: str | None = None
    messages: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    stop_reason: str = "completed"

class AgentRunner:
    async def run(self, spec: AgentRunSpec) -> AgentRunResult:
        messages = list(spec.initial_messages)
        tools_used: list[str] = []
        usage: dict[str, int] = {"prompt_tokens":0, 
                                 "completion_tokens":0, 
                                 "total_tokens":0}
        for iteration in range(spec.max_iterations):
            response = await spec.provider.chat(
                messages = messages,
                tools = spec.tools.get_definitions(),
                max_tokens = spec.provider.generation.max_tokens,
                temperature = spec.provider.generation.temperature,
            )
            self._accumulate_usage(usage, response.usage)
            logger.info(f"第 {iteration} 轮: finish_reason={response.finish_reason}")

            if response.has_tool_calls:
                # FIX: 一条 assistant 消息要包含【所有】tool_calls，不能每个 tool_call 单独一条
                # 否则多个工具调用时，OpenAI 会报 "tool_call_id 找不到对应的 assistant 消息"
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [self._to_openai_tool_call(tc) for tc in response.tool_calls],
                })
                for tool_call in response.tool_calls:
                    result = await spec.tools.execute(tool_call.name, tool_call.arguments)
                    result_text = self._truncate(result, spec.max_tool_result_chars)
                    tools_used.append(tool_call.name)

                    # 每个工具调用对应一条 tool 消息，必须紧跟在上面的 assistant 消息之后
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result_text,
                    })
                continue

            return AgentRunResult(
                final_content=response.content,
                messages=messages,
                tools_used=tools_used,
                usage=usage,
                stop_reason="completed",
            )
        return AgentRunResult(
            final_content= "已达到最大工具调用次数",
            messages=messages,
            tools_used=tools_used,
            usage=usage,
            stop_reason="max_iterations",
        )

    @staticmethod
    def _accumulate_usage(target: dict, addition: dict) -> None:
        for key, value in (addition or {}).items():
            target[key] = target.get(key, 0) + int(value or 0)

    @staticmethod
    def _truncate(result: Any, max_chars: int) -> str:  # FIX: _turncate → _truncate（调用处是 _truncate）
        text = str(result)
        if len(text) > max_chars:
            return text[:max_chars] + f"\n...[共截断{len(text)}字符]"
        return text

    @staticmethod
    def _to_openai_tool_call(tool_call) -> dict:
        import json
        return{
            "id": tool_call.id,
            "type": "function",
            "function":{
                "name": tool_call.name,
                "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
            },
        }
    