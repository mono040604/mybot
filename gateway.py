import asyncio
import os
from contextlib import asynccontextmanager
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

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

cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
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
)
tools = ToolRegistry()
loop = AgentLoop(bus=bus, context_builder=context_builder, provider=provider, tools=tools)  # FIX: 用关键字参数，别用位置参数——否则 provider/tools 顺序一错就静默错位

class ChatRequest(BaseModel):
    session_key: str
    content: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop_task = asyncio.create_task(loop.run())
    yield
    loop.stop()
    loop_task.cancel()  # FIX: loop._task → loop_task（loop 没有 _task 属性，要取消的是上面 create_task 返回的 loop_task）
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "ok", "message": "mybot gateway 运行中，访问 /docs 查看接口文档"}


@app.post("/chat")
async def chat(req: ChatRequest):
    await bus.publish_inbound(InboundMessage(
        channel="wechat",
        sender_id=req.session_key,
        chat_id=req.session_key,
        content=req.content,
        session_key_override=req.session_key,
    ))
    outbound = await bus.consume_outbound()
    return {"content": outbound.content}

if __name__ == "__main__":
    # 云托管要求监听 0.0.0.0（所有网卡）而非 127.0.0.1：
    #   127.0.0.1 只接受本机回环连接，容器外的流量根本进不来；
    #   0.0.0.0 监听所有网卡，云托管的公网入口才能把请求转发进来。
    # 端口从环境变量 PORT 读：云托管会注入 PORT，并把你监听的端口映射到公网；
    #   写死 8000 会导致和它预期的端口对不上。
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)