"""临时脚本：用真实 API（智谱 GLM）端到端测试 对话 + 工具调用"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from providers.openai_compat import OpenAICompatProvider
from agent.tools.registry import ToolRegistry
from agent.tools.filesystem import ReadFileTool
from agent.runner import AgentRunner, AgentRunSpec


def build_provider() -> OpenAICompatProvider:
    """从 config.json 读取 provider 配置，创建真实 Provider"""
    config = json.loads(Path(__file__).parent.joinpath("config.json").read_text(encoding="utf-8"))
    p = config["providers"]["openai"]
    return OpenAICompatProvider(
        api_key=p["api_key"],
        api_base=p["api_base"],
        default_model=p["model"],
    )


async def test_chat(provider):
    """测试1：最简单的对话，验证 key 和地址对不对"""
    print("=== 测试1: 简单对话 ===")
    resp = await provider.chat(
        messages=[{"role": "user", "content": "用一句话介绍你自己"}],
    )
    print("回复:", resp.content)
    print("finish_reason:", resp.finish_reason)
    print("usage:", resp.usage)
    return resp.content


async def test_tool(provider):
    """测试2：工具调用，验证 function calling 通不通"""
    print("\n=== 测试2: 工具调用（读取 pyproject.toml） ===")
    registry = ToolRegistry()
    registry.register(ReadFileTool(workspace=Path(__file__).parent))

    spec = AgentRunSpec(
        initial_messages=[
            {"role": "user", "content": "请读取 pyproject.toml 文件，然后告诉我这个项目叫什么名字"}
        ],
        tools=registry,
        provider=provider,
    )
    result = await AgentRunner().run(spec)
    print("最终回复:", result.final_content)
    print("用了哪些工具:", result.tools_used)
    print("总 token:", result.usage)
    print("停止原因:", result.stop_reason)


async def main():
    provider = build_provider()
    await test_chat(provider)
    await test_tool(provider)
    print("\n=== 真实 API 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())