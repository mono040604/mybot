"""临时测试：ContextBuilder 三层装配 + 溢出整理"""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from session.manager import SessionManager
from agent.memory import MemoryStore
from agent.rag import RagStore
from providers.openai_compat import OpenAICompatProvider
from providers.embedding import EmbeddingProvider
from agent.context_builder import ContextBuilder


def make(cfg):
    oc = cfg["providers"]["openai"]
    return OpenAICompatProvider(api_key=oc["api_key"], api_base=oc["api_base"],
                                default_model=oc["model"]), oc


async def scenario_recover():
    """情景1：事实被窗口挤掉后，靠 长期+RAG 找回来（不触发整理，省一次 LLM）"""
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    provider, oc = make(cfg)
    sessions = SessionManager(Path.cwd())
    memory = MemoryStore(Path.cwd())
    rag = RagStore(EmbeddingProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], model="embedding-2"),
        store_path=Path("memory/rag_recover.json"))  # FIX: 补上 store_path 持久化；情景1用独立文件避免与情景2互串

    # window=6, 阈值 999 = 本情景永不整理
    builder = ContextBuilder(provider, sessions, memory, rag,
                             system_prompt="你是乐于助人的中文助手。",
                             window_size=6, maintain_threshold=999)

    # 预置：长期记忆有"小明"；RAG 有一条更早的 mybot 片段
    memory.write_memory("- 用户叫小明，正在开发 mybot 微信机器人")
    await rag.add("用户之前在群里提过，mybot 要用 Python 写，目标跑在微信上")

    # 窗口内塞 8 条纯闲聊——没有"小明"、没有"mybot"
    s = sessions.get_or_create("recover_test")
    s.messages = []
    for i in range(8):
        s.messages.append({"role": "user" if i % 2 == 0 else "assistant",
                           "content": "今天天气不错" if i % 2 == 0 else "是啊，适合走走"})
    sessions.save(s)

    msgs = await builder.build("recover_test", "我叫什么名字？")
    print("=== 情景1：窗口内明明没有'小明'，看消息里它从哪出现 ===")
    for m in msgs:
        print(f"  [{m['role']}] {(m['content'].replace(chr(10),' '))[:55]}")


async def scenario_maintain():
    """情景2：会话超阈值 → 自动整理：consolidate→RAG→裁剪"""
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    provider, oc = make(cfg)
    sessions = SessionManager(Path.cwd())
    memory = MemoryStore(Path.cwd())
    rag = RagStore(EmbeddingProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], model="embedding-2"),
        store_path=Path("memory/rag_maintain.json"))  # FIX: 补上 store_path 持久化；情景2用独立文件避免与情景1互串

    builder = ContextBuilder(provider, sessions, memory, rag,
                             window_size=6, maintain_threshold=10)

    # 12 条 = 超过阈值。前 6 条带事实，后 6 条是最近闲聊
    key = "maintain_test"
    s = sessions.get_or_create(key)
    s.messages = []
    old = [
        ("user", "我叫小明，正在用 Python 写一个叫 mybot 的机器人，目标接入微信"),
        ("assistant", "听起来很酷，微信机器人要做的事情不少呢"),
        ("user", "是的，我打算先跑通一个简单的聊天回复，再慢慢加工具"),
        ("assistant", "循序渐进是对的"),
        ("user", "对了，我更喜欢喝茶，最近在喝冷泡乌龙茶"),
        ("assistant", "冷泡乌龙茶确实清爽"),
    ]
    recent = []
    for i in range(6):
        recent.append(("user" if i % 2 == 0 else "assistant",
                       "今天晚饭吃什么好" if i % 2 == 0 else "吃面吧，省事"))
    for role, content in old + recent:
        s.messages.append({"role": role, "content": content})
    sessions.save(s)

    msgs = await builder.build(key, "晚饭吃面怎么样？")
    print("\n=== 情景2：触发整理后 ===")
    print(f"session 剩余条数：{len(sessions.get_or_create(key).messages)}（应为 6）")
    print(f"RAG 归档条数：{len(rag.entries)}（应为 3 条 user 长发言）")
    print("MEMORY.md 现在的内容：")
    print(memory.read_memory())
    print("本次发给 LLM 的 messages 结构：")
    for m in msgs:
        print(f"  [{m['role']}] {(m['content'].replace(chr(10),' '))[:45]}")


async def main():
    await scenario_recover()
    await scenario_maintain()


if __name__ == "__main__":
    asyncio.run(main())
