"""临时测试：验证多轮记忆 + 重启不遗忘"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bus.events import InboundMessage
from bus.queue import MessageBus
from providers.openai_compat import OpenAICompatProvider
from agent.tools.registry import ToolRegistry
from agent.loop import AgentLoop
from session.manager import SessionManager


def build_provider():
    config = json.loads(Path(__file__).parent.joinpath("config.json").read_text(encoding="utf-8"))
    p = config["providers"]["openai"]
    return OpenAICompatProvider(api_key=p["api_key"], api_base=p["api_base"], default_model=p["model"])


async def ask(bus, content):
    """发一条消息，等回复"""
    await bus.publish_inbound(InboundMessage(channel="cli", sender_id="user", chat_id="test", content=content))
    reply = await asyncio.wait_for(bus.consume_outbound(), timeout=30)
    return reply.content


async def main():
    provider = build_provider()
    tools = ToolRegistry()

    # 第一次运行
    sessions = SessionManager(workspace=Path(__file__).parent)
    bus = MessageBus()
    loop = AgentLoop(bus, provider, tools, sessions=sessions, system_prompt="你是一个友好的中文助手")
    task = asyncio.create_task(loop.run())

    print("第一轮:", await ask(bus, "记住，我叫小明，我喜欢喝咖啡"))
    print("第二轮:", await ask(bus, "我叫什么名字？我喜欢喝什么？"))

    loop.stop()
    task.cancel()
    await asyncio.sleep(0.1)

    # 模拟重启：新建 SessionManager（从磁盘加载）+ 新 loop
    sessions2 = SessionManager(workspace=Path(__file__).parent)
    bus2 = MessageBus()
    loop2 = AgentLoop(bus2, provider, tools, sessions=sessions2, system_prompt="你是一个友好的中文助手")
    task2 = asyncio.create_task(loop2.run())

    print("重启后:", await ask(bus2, "我之前说我叫什么？"))

    loop2.stop()
    task2.cancel()
    await asyncio.sleep(0.1)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
