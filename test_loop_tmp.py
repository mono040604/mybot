"""临时测试：验证 AgentLoop 完整闭环"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bus.events import InboundMessage
from bus.queue import MessageBus
from providers.openai_compat import OpenAICompatProvider
from agent.tools.registry import ToolRegistry
from agent.tools.filesystem import ReadFileTool
from agent.loop import AgentLoop


async def main():
    # 1. 读 config 建 provider
    config = json.loads(Path(__file__).parent.joinpath("config.json").read_text(encoding="utf-8"))
    p = config["providers"]["openai"]
    provider = OpenAICompatProvider(api_key=p["api_key"], api_base=p["api_base"], default_model=p["model"])

    # 2. 建 bus、tools、loop
    bus = MessageBus()
    tools = ToolRegistry()
    tools.register(ReadFileTool(workspace=Path(__file__).parent))
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        tools=tools,
        system_prompt="你是一个友好的中文助手，名字叫小M",
    )

    # 3. 启动 loop（后台运行）
    task = asyncio.create_task(loop.run())

    # 4. 发一条消息
    await bus.publish_inbound(InboundMessage(
        channel="cli", sender_id="user", chat_id="test",
        content="你好，介绍一下你自己",
    ))

    # 5. 等回复（最多等30秒）
    reply = await asyncio.wait_for(bus.consume_outbound(), timeout=30)
    print("机器人回复:", reply.content)

    # 6. 停止 loop
    loop.stop()
    task.cancel()
    await asyncio.sleep(0.1)  # 让 task 退出
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
