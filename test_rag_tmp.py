"""临时测试 v2：记忆够多 + 打印分数 + 阈值过滤"""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from providers.embedding import EmbeddingProvider
from agent.rag import RagStore


async def main():
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    oc = config["providers"]["openai"]
    store = RagStore(EmbeddingProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], model="embedding-2",
    ))

    # 1. 存 15 条，覆盖 5 大主题，每条是"一句话事件"（比单句稍长）
    memories = [
        # 饮食
        "用户爱喝乌龙茶，最近迷上冷泡茶",
        "用户不吃香菜，点外卖备注永远是不要香菜",
        "用户对牛奶过敏，只能喝燕麦奶",
        # 宠物
        "用户养了一只三岁的橘猫叫豆豆，很粘人",
        "豆豆上周生病去了宠物医院，花了八百块",
        # 旅行
        "用户去年冬天去了日本，在京都待了一周",
        "用户护照今年十月过期，要记得提前换",
        # 工作
        "用户正在用 Python 写 mybot，一个要上微信的聊天机器人",
        "mybot 的语音部分还没做，用户计划用 Whisper 来接",
        # 喜好
        "用户最爱听 Coldplay，演唱会只去过一次",
        "用户跑步时会听播客，不听歌",
        "用户最近在看一本叫《置身事内》的书",
        # 其他
        "用户有个妹妹在读大学，学的是设计",
        "用户住在杭州，公司在滨江区",
        "用户周末喜欢去西湖边骑车",
    ]
    for m in memories:
        await store.add(m)
    print(f"已存入 {len(store.entries)} 条记忆\n")

    # 2. 三个 query，各取 top 3 + 分数（把 min_score 设成 0 先看分布）
    for q in ["用户平时喝什么？", "用户养了什么宠物？", "用户最近在看什么书？"]:
        print(f"=== 问：{q} ===")
        for score, text in await store.search(q, top_k=3):
            print(f"  {score:.3f}  {text}")
        print()

    # 3. 加上阈值再看：这次只打印分数达标的
    print("=== 加阈值 min_score=0.45 后再问：用户平时喝什么？ ===")
    for score, text in await store.search("用户平时喝什么？", top_k=3, min_score=0.45):
        print(f"  {score:.3f}  {text}")


if __name__ == "__main__":
    asyncio.run(main())
