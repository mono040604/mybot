import asyncio
import json
from pathlib import Path

from bus.queue import MessageBus
from bus.events import InboundMessage
from providers.openai_compat import OpenAICompatProvider
from providers.embedding import EmbeddingProvider
from session.manager import SessionManager
from agent.memory import MemoryStore
from agent.rag import RagStore
from agent.context_builder import ContextBuilder
from agent.loop import AgentLoop
from agent.tools.registry import ToolRegistry

async def main():
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))  # FIX: json.loads（字符串），不是 json.load（文件对象）——read_text 返回的是 str
    oc = cfg["providers"]["openai"]

    bus = MessageBus()
    provider = OpenAICompatProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], default_model=oc["model"]
        )  # FIX: api_key=["api_key"] → oc["api_key"]。原来把字面量"api_key"装进列表了，认证会 401
    embedder = EmbeddingProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], model="embedding-2"
    )  # FIX: 同上
    sessions = SessionManager(Path.cwd())
    memory = MemoryStore(Path.cwd())
    rag = RagStore(embedder, store_path=Path("memory/rag.json"))
    context_builder = ContextBuilder(
        provider, sessions, memory, rag,
        system_prompt="You are a helpful assistant",
        window_size=20, maintain_threshold=40,
    )
    tools = ToolRegistry()
    loop = AgentLoop(bus=bus, context_builder=context_builder, provider=provider, tools=tools)  # FIX: 用关键字参数，别用位置参数——否则 provider/tools 顺序一错就静默错位
    loop_task = asyncio.create_task(loop.run())
    channel, chat_id = "cli", "me"  # FIX: "cil"→"cli"（拼写，影响 session_key 名）
    print('===mybot聊天(输入quit退出)===')  # FIX: quiet→quit
    while True:
        try:
            text = await asyncio.to_thread(input, "你：")
        except EOFError:
            break
        text = text.strip()                       # FIX: 去掉首尾空白，否则"   "会当内容发给 LLM
        if text.lower() in ("quit", "exit", "退出"):  # FIX: 补上退出判断，否则只能 Ctrl+C 强退
            break
        if not text:
            continue

        await bus.publish_inbound(InboundMessage(
            channel=channel, sender_id="me", chat_id=chat_id, content=text,
        ))
        outbound = await bus.consume_outbound()
        print(f"bot:{outbound.content}\n")

    loop.stop()
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())