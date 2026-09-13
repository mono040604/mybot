"""临时测试：验证 MemoryStore 读写 MEMORY.md"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent.memory import MemoryStore


def main():
    store = MemoryStore(workspace=Path(__file__).parent)

    # 1. 写入长期记忆
    store.write_memory("- 用户叫小明\n- 喜欢喝咖啡\n- 在做 mybot 项目")

    # 2. 读回
    print("=== 读回 MEMORY.md ===")
    print(store.read_memory())

    # 3. 注入 prompt 的格式
    print("=== 注入 prompt 的格式 ===")
    print(repr(store.get_memory_context()))

    # 4. 验证：删掉文件后 read 返回空串（容错）
    store.memory_file.unlink()          # 删除文件
    print("=== 删除后读回 ===")
    print(repr(store.read_memory()))     # 应该返回 ''，不报错


if __name__ == "__main__":
    main()
