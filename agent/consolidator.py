from loguru import logger
from providers.base import LLMProvider
from agent.memory import MemoryStore

CONSOLIDATE_SYSTEM = "你是一个记忆整理助手。你的任务是把对话压缩成长期记忆。"

CONSOLIDATE_PROMPT = """请把【新的对话】合并进【旧的长期记忆】，输出更新后的长期记忆。

规则：
1. 保留所有仍然有效的事实（用户的名字、偏好、项目、重要决定、约束等）
2. 更新被推翻的旧事实（如果新对话里有信息否定了旧记忆）
3. 删除闲聊、问候、临时内容（"你好"、"谢谢"、一次性任务）
4. 每行一个事实，用 markdown 列表格式（"- "开头）
5. 只输出记忆内容本身，不要任何前言、解释或标题

【旧的长期记忆】
{existing}

【新的对话】
{conversation}

请输出更新后的长期记忆："""

class Consolidator:
    def __init__(self, provider: LLMProvider, memory_store: MemoryStore):
        self.provider = provider
        self.memory = memory_store

    async def consolidate(self, conversation: list[dict]) -> str:
        existing = self.memory.read_memory()
        conversation_text = self._format_conversation(conversation)
        prompt = CONSOLIDATE_PROMPT.format(
            existing = existing or "暂无",
            conversation=conversation_text,
        )

        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": CONSOLIDATE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        new_memory = (response.content or "").strip()

        if new_memory:
            self.memory.write_memory(new_memory)
        logger.info("记忆整理完成:{} 字符 -> {}字符", len(existing), len(new_memory))
        return new_memory

    @staticmethod
    def _format_conversation(conversation: list[dict]) -> str:
        lines = []
        for msg in conversation:
            role = msg.get("role", "unknown")
            content = msg.get("content", "") or ""
            lines.append(f"[{role}] {content}")
        return "\n".join(lines)