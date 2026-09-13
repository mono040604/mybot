"""临时测试：RagStore 持久化——重启后记忆还在"""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from providers.embedding import EmbeddingProvider
from agent.rag import RagStore


async def main():
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    oc = cfg["providers"]["openai"]
    path = Path("memory/rag_test.json")

    if path.exists():          # 清掉上次测试的残留，从零开始
        path.unlink()

    def make():
        return RagStore(
            EmbeddingProvider(api_key=oc["api_key"],
                              api_base=oc["api_base"], model="embedding-2"),
            store_path=path,
        )

    # 1. 第一次"运行"：存 3 条
    store = make()
    await store.add("用户叫小明，正在用 Python 写 mybot 微信机器人")
    await store.add("用户喜欢喝冷泡乌龙茶，不吃香菜")
    await store.add("用户养了一只叫豆豆的橘猫")
    print(f"第一次运行后 entries = {len(store.entries)} 条")
    print(f"磁盘文件大小 = {path.stat().st_size} 字节\n")

    # 2. 模拟重启：丢掉旧对象，new 一个新对象
    store2 = make()
    print(f"重启后自动加载 entries = {len(store2.entries)} 条\n")

    # 3. 检索验证：记忆真的回来了
    for q in ["用户养了什么宠物？", "用户喜欢喝什么？"]:
        print(f"=== 问：{q} ===")
        for score, text in await store2.search(q, top_k=2):
            print(f"  {score:.3f}  {text}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
