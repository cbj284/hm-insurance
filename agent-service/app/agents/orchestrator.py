from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.chitchat import init_chitchat_agent
from app.agents.claim_advisor import init_claim_advisor
from app.agents.insurance_advisor import init_insurance_advisor
from app.agents.intent_router import intent_router
from app.agents.schemas import InsuranceAgentContext, InsuranceAgentState, Intent


async def route_node(
    state: InsuranceAgentState,
) -> Command[Intent]:
    previous_workflow = state.get("active_workflow", "")
    previous_ai_message = find_previous_ai_message(state["messages"])
    context = f"上轮对话工作流:{previous_workflow}\n上轮对话AI回复:{previous_ai_message}"
    result = await intent_router.route(state["messages"][-1].content, context)

    if isinstance(result, str):
        return Command(
            update={
                "messages": [AIMessage(content=result)],
                "previous_workflow": previous_workflow,
                "active_workflow": "chitchat",
            },
            goto=END,
        )

    return Command(
        update={
            "previous_workflow": previous_workflow,
            "active_workflow": result.intent,
        },
        goto=result.intent,
    )


def find_previous_ai_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages[:-1]):
        if not isinstance(message, AIMessage):
            continue
        if message.tool_calls:
            continue
        if message.text:
            return message.text
    return ""


def human_handoff_node(state: InsuranceAgentState) -> dict:
    return {"messages": [AIMessage("已记录转人工请求，后续可接入人工客服系统。")]}


def fallback_node(state: InsuranceAgentState) -> dict:
    return {
        "messages": [
            AIMessage("我还不能确定你的需求，请说明是想咨询保险、推荐方案还是办理理赔。")
        ]
    }


def init_insurance_orchestrator(
    checkpointer: AsyncPostgresSaver,
):
    """初始化保险顾问主Graph"""

    builder = StateGraph(
        InsuranceAgentState,
        context_schema=InsuranceAgentContext,
    )
    builder.add_node("route", route_node)
    builder.add_node("chitchat", init_chitchat_agent())
    builder.add_node("recommendation_plan", init_insurance_advisor())
    builder.add_node("claim", init_claim_advisor())
    builder.add_node("human_handoff", human_handoff_node)
    builder.add_node("fallback", fallback_node)

    builder.add_edge(START, "route")
    builder.add_edge("chitchat", END)
    builder.add_edge("recommendation_plan", END)
    builder.add_edge("claim", END)
    builder.add_edge("human_handoff", END)
    builder.add_edge("fallback", END)

    return builder.compile(checkpointer=checkpointer)
