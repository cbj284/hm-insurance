from collections.abc import AsyncIterator

from fastapi.sse import ServerSentEvent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.stream import CustomTransformer
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import AdditionalInfo, InsuranceAgentContext
from app.modules.chat.schemas import ChatRequest
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError
from app.modules.chat_thread.repository import ChatThreadRepository


class ChatService:
    def __init__(self, session: AsyncSession, agent: CompiledStateGraph):
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def chat_stream(
        self,
        user_id: int,
        request: ChatRequest,
    ) -> AsyncIterator[ServerSentEvent]:
        thread = await self.repository.find_owned(
            request.thread_id,
            user_id,
        )
        if thread is None:
            raise ChatThreadNotFoundError

        if request.decision:
            _input = Command(resume=request.decision)
        else:
            _input = {"messages": [HumanMessage(content=request.message)]}

        config = {"configurable": {"thread_id": str(request.thread_id)}}
        context = InsuranceAgentContext(user_id=user_id)

        stream = await self.agent.astream_events(
            _input,
            config,
            context=context,
            version="v3",
            transformers=[CustomTransformer],
        )

        final_message_id: str | None = None
        additional_info: AdditionalInfo = {}

        async for event in stream:
            method = event["method"]
            if method == "messages":
                data = event["params"]["data"][0]
                if isinstance(data, AIMessage):
                    yield ServerSentEvent(data=data.text, event="message")
                elif isinstance(data, dict) and data.get("delta") and data["delta"].get("text"):
                    yield ServerSentEvent(
                        data=data["delta"].get("text"),
                        event="message",
                    )
                elif isinstance(data, dict) and data.get("event") == "message-start" and data.get("id"):
                    final_message_id = data.get("id")

            if method == "custom":
                data = event["params"]["data"]
                if isinstance(data, dict) and data.get("type") == "additional_info":
                    additional_info = data.get("data", {})
                    yield ServerSentEvent(
                        data=additional_info,
                        event="additional_info",
                    )

        interrupts = await stream.interrupts()
        for item in interrupts:
            yield ServerSentEvent(data=item.value, event="interrupt")

        if final_message_id and additional_info:
            await self.agent.aupdate_state(
                config,
                {"additional_info": {final_message_id: additional_info}},
            )

        yield ServerSentEvent(data="[DONE]", event="done")
