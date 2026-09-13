"""临时测试：验证 Consolidator 把对话压缩成长期记忆"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from providers.openai_compat import OpenAICompatProvider
from agent.memory import MemoryStore
from agent.consolidator import Consolidator


async def main():
    # 1. 从 config.json 读配置（复用你的智谱 key）
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    oc = config["providers"]["openai"]
    provider = OpenAICompatProvider(
        api_key=oc["api_key"],
        api_base=oc["api_base"],
        default_model=oc["model"],
    )

    store = MemoryStore(workspace=Path.cwd())
    consolidator = Consolidator(provider, store)

    # 2. 模拟一段要被"驱逐"的旧对话（混了事实 + 闲聊）
    conversation = [
        {"role": "user", "content": "你好呀"},
        {"role": "assistant", "content": "你好！有什么可以帮你？"},
        {"role": "user", "content": "我叫小明，今年在做一个叫 mybot 的机器人项目"},
        {"role": "assistant", "content": "听起来不错，mybot 是做什么的？"},
        {"role": "user", "content": "它是个能上微信的聊天机器人，我打算用 Python 写"},
        {"role": "assistant", "content": "明白了，Python 很适合做这个。"},
        {"role": "user", "content": "对了，我不喜欢喝咖啡，更喜欢喝茶"},
    ]

    print("=== 第一次整理（验证：抽取事实 + 丢弃闲聊）===")
    new_memory = await consolidator.consolidate(conversation)
    print(new_memory)

    # 3. 再整理一段（验证"合并 + 更新"：旧记忆 + 新对话）
    conversation2 = [
        {"role": "user", "content": "我改主意了，现在开始喝咖啡了"},
        {"role": "user", "content": "还有，mybot 项目已经快完成了"},
    ]
    print("\n=== 第二次整理（验证：合并 + 更新旧事实）===")
    new_memory2 = await consolidator.consolidate(conversation2)
    print(new_memory2)


if __name__ == "__main__":
    asyncio.run(main())
