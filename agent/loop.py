import asyncio
from loguru import logger
from bus.events import InboundMessage, OutboundMessage
from bus.queue import MessageBus
from providers.base import LLMProvider
from agent.tools.registry import ToolRegistry
from agent.runner import AgentRunner, AgentRunSpec

class AgentLoop:
    def __init__(
            self,
            bus: MessageBus,
            context_builder,
            provider: LLMProvider,
            tools: ToolRegistry,
            system_prompt: str = "You are a helpful assistant.",
            sessions= None,
    ):
        self.bus = bus
        self.provider = provider
        self.tools = tools
        self.runner = AgentRunner()
        self.system_prompt = system_prompt
        self.sessions = sessions
        self.context_builder = context_builder
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("Agent loop started")
        while self._running:
            try:
                msg = await self.bus.consume_inbound()
            except asyncio.CancelledError:
                break
            asyncio.create_task(self._handle_message(msg))

    def stop(self) -> None:  # FIX: 去掉 async（stop 只改标志位，没有 await，不该是协程）
        self._running = False  # FIX: 双下划线→单下划线（要和 __init__ 里的 self._running 一致）

    async def _handle_message(self, msg: InboundMessage) -> None:
        try:
            await self._process(msg)
        except Exception as e:
            logger.exception("消息处理失败:{}", e)
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content=f"出错了:{e}",
            ))
        '''session = self.sessions.get_or_create(msg.session_key)
        history = session.get_history()

        initial_messages = [
            {"role": "system", "content": self.system_prompt},
            *history,
            {"role": "user", "content": msg.content},
        ]

        result = await self.runner.run(AgentRunSpec(
            initial_messages=initial_messages,
            tools=self.tools,
            provider=self.provider,
        ))
        '''

    async def _process(self, msg: InboundMessage) -> None:
        messages = await self.context_builder.build(msg.session_key, msg.content)
        result = await self.runner.run(AgentRunSpec(
            initial_messages=messages,
            tools=self.tools,
            provider=self.provider,
        ))
        session = self.context_builder.sessions.get_or_create(msg.session_key)
        session.add_messages("user", msg.content)
        session.add_messages("assistant", result.final_content or "")
        self.context_builder.sessions.save(session)

        outbound = OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=result.final_content or "",
        )
        await self.bus.publish_outbound(outbound)
        logger.info("回复 {}:{} -> {}", msg.channel, msg.chat_id,
                    (result.final_content or "")[:50])