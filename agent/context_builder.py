from loguru import logger
from agent.memory import MemoryStore
from agent.rag import RagStore
from agent.consolidator import Consolidator

class ContextBuilder:
    def __init__(self, provider, sessions, memory_store: MemoryStore, rag_store: RagStore, system_prompt: str = "You are a helpful assistant.", window_size: int=20, rag_top_k: int = 3, maintain_threshold: int = 40,):
        self.provider = provider
        self.sessions = sessions
        self.memory = memory_store
        self.rag = rag_store
        self.maintain_threshold = maintain_threshold
        self.consolidator = Consolidator(provider, memory_store)
        self.rag_top_k = rag_top_k
        self.window_size = window_size
        self.system_prompt = system_prompt

    async def build(self, session_key: str, user_content: str) -> list[dict]:
        session = self.sessions.get_or_create(session_key)
        await self._maybe_maintain(session)

        messages = [{"role": "system", "content": self.system_prompt}]

        memory_context = self.memory.get_memory_context()
        if memory_context:
            messages.append({"role": "system", "content": memory_context})

        related = await self.rag.search(user_content, top_k=self.rag_top_k)
        if related:
            text =  "更早对话中与本问题相关的记忆: \n" + "\n".join(f"- {t}" for _, t in related)
            messages.append({"role": "system", "content": text})  # FIX: 发的是 RAG 结果 text，不是 memory_context（否则 RAG 白检索、长期记忆重复发两次）

        for msg in session.get_history(self.window_size):
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_content})
        return messages

    async def _maybe_maintain(self, session) -> None:
        if len(session.messages) <= self.maintain_threshold:
            return

        old = session.messages[:-self.window_size]
        if not old:
            return

        await self.consolidator.consolidate(old)
        for chunk in self._chunk_messages(old, chunk_size=3):
            await self.rag.add(chunk)

        session.messages = session.messages[-self.window_size:]
        self.sessions.save(session)
        logger.info("整理:{}条旧对话内容已沉淀, session保留最近{}条", len(old), len(session.messages))

    @staticmethod
    def _chunk_messages(messages: list[dict], chunk_size: int = 3) -> list[str]:
        chunks = []
        for i in range(0, len(messages), chunk_size):
            group = messages[i:i + chunk_size]
            text = "\n".join(
                f"[{m.get('role')}] {m.get('content') or ''}" for m in group).strip()  # FIX: f-string 内层改用单引号，双引号会导致 SyntaxError
            if text:
                chunks.append(text)
        return chunks
            