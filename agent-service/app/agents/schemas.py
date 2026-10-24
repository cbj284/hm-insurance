from dataclasses import dataclass
from typing import Annotated, Any, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class InsuranceAgentContext:
    """保险顾问Agent运行时上下文"""

    user_id: int


Intent = Literal[
    "chitchat",
    "recommendation_plan",
    "claim",
    "human_handoff",
    "fallback",
]


class RouteResult(BaseModel):
    """意图识别结果"""

    intent: Intent = Field(description="本轮消息应该进入的工作流")
    reason: str = Field(description="判断该意图的理由")


AdditionalInfo = dict[str, Any]


def merge_additional_info(
    left: dict[str, AdditionalInfo] | None,
    right: dict[str, AdditionalInfo] | None,
) -> dict[str, AdditionalInfo]:
    """按照AI消息id合并引用信息"""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class InsuranceAgentState(MessagesState):
    """保险顾问主Graph状态"""

    previous_workflow: Intent
    active_workflow: Intent
    additional_info: Annotated[
        dict[str, AdditionalInfo],
        merge_additional_info,
    ]
