"""临时测试脚本：验证 AgentRunner 的循环逻辑（用假 Provider，不调用真实 API）"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from providers.base import LLMProvider, LLMResponse, ToolCallRequest
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.runner import AgentRunner, AgentRunSpec


class MockProvider(LLMProvider):
    """假 Provider：不联网，按预设脚本返回响应，并记录每次收到的 messages"""

    def __init__(self):
        super().__init__(api_key="test", api_base="http://fake", default_model="mock")
        self.calls = []      # 记录每一轮收到的 messages（验证多轮上下文对不对）
        self.script = []     # 预设的响应队列

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        self.calls.append(messages)
        return self.script.pop(0)

    def get_default_model(self):
        return "mock"


class FakeTimeTool(Tool):
    @property
    def name(self):
        return "get_time"

    @property
    def description(self):
        return "get current time"

    @property
    def parameters(self):
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs):
        return "2026-08-15 12:00:00"


async def test_plain_loop():
    """测试1：单轮对话，无工具调用，直接返回文本"""
    provider = MockProvider()
    provider.script.append(LLMResponse(
        content="你好！",
        finish_reason="stop",
        usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    ))
    spec = AgentRunSpec(
        initial_messages=[{"role": "user", "content": "你好"}],
        tools=ToolRegistry(),
        provider=provider,
    )
    result = await AgentRunner().run(spec)
    assert result.final_content == "你好！", result.final_content
    assert result.tools_used == []
    assert len(provider.calls) == 1
    assert result.usage["total_tokens"] == 8
    print("[PASS] 1. 单轮无工具对话")


async def test_tool_loop():
    """测试2：第一轮要调工具，第二轮返回最终答案，验证消息拼接和 usage 累加"""
    provider = MockProvider()
    provider.script.append(LLMResponse(
        content=None,
        tool_calls=[ToolCallRequest(id="call_1", name="get_time", arguments={})],
        finish_reason="tool_calls",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    ))
    provider.script.append(LLMResponse(
        content="现在是 12 点",
        finish_reason="stop",
        usage={"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
    ))
    registry = ToolRegistry()
    registry.register(FakeTimeTool())
    spec = AgentRunSpec(
        initial_messages=[{"role": "user", "content": "现在几点了？"}],
        tools=registry,
        provider=provider,
    )
    result = await AgentRunner().run(spec)

    assert result.final_content == "现在是 12 点", result.final_content
    assert result.tools_used == ["get_time"], result.tools_used
    assert result.usage["total_tokens"] == 43, result.usage   # 15 + 28
    assert result.stop_reason == "completed"
    assert len(provider.calls) == 2, len(provider.calls)

    # 关键验证：第二轮发给 LLM 的消息里，必须包含 assistant 和 tool 消息
    second_call = provider.calls[1]
    roles = [m["role"] for m in second_call]
    assert "tool" in roles, f"第二轮缺少 tool 消息: {roles}"
    assert "assistant" in roles, f"第二轮缺少 assistant 消息: {roles}"

    # 验证 assistant 消息的 tool_calls 格式正确
    asst = [m for m in second_call if m["role"] == "assistant"][0]
    assert asst["tool_calls"][0]["function"]["name"] == "get_time"
    assert asst["tool_calls"][0]["id"] == "call_1"
    print("[PASS] 2. 工具调用循环 + 消息拼接 + usage 累加")


async def test_max_iterations():
    """测试3：模型一直要调工具，触发 max_iterations 上限"""
    provider = MockProvider()
    for _ in range(20):
        provider.script.append(LLMResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="c", name="get_time", arguments={})],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        ))
    registry = ToolRegistry()
    registry.register(FakeTimeTool())
    spec = AgentRunSpec(
        initial_messages=[{"role": "user", "content": "x"}],
        tools=registry,
        provider=provider,
        max_iterations=3,
    )
    result = await AgentRunner().run(spec)
    assert result.stop_reason == "max_iterations", result.stop_reason
    assert len(provider.calls) == 3
    print("[PASS] 3. max_iterations 上限")


async def test_truncate():
    """测试4：工具结果截断"""
    r = AgentRunner()
    long_text = "a" * 100
    out = r._truncate(long_text, 10)
    assert len(out) < 100
    assert "截断" in out
    print("[PASS] 4. 工具结果截断")


async def main():
    await test_plain_loop()
    await test_tool_loop()
    await test_max_iterations()
    await test_truncate()
    print("\n=== 全部 4 项测试通过 ===")


if __name__ == "__main__":
    asyncio.run(main())