import asyncio
import gateway
from agent.runner import AgentRunSpec

async def main():
    # 1. 组装消息（和 /chat 走的是同一条 context_builder）
    messages = await gateway.context_builder.build("test", "根据小明的学习情况给他一个学习建议")

    # 2. 直接跑 runner（AgentLoop 内部也是调这个 runner）
    result = await gateway.loop.runner.run(AgentRunSpec(
        initial_messages=messages,
        tools=gateway.tools,
        provider=gateway.provider,
    ))

    print("最终回复:", result.final_content)
    print("用到的工具:", result.tools_used)

asyncio.run(main())
