from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from app.agents.claim_tools import (
    query_claim_guide,
    query_claim_progress,
    query_user_policies,
)
from app.agents.schemas import InsuranceAgentContext
from app.agents.tools import query_product_clause
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
你是“安心保”的理赔顾问，只处理保单查询、理赔进度、理赔材料和理赔责任说明。
- 用户问“我的保单/保单号/保障期间”时，先调用 query_user_policies。
- 用户问理赔进度、案件号、审核结果时，先调用 query_claim_progress。
- 用户问怎么理赔、要什么材料、报案流程时，调用 query_claim_guide。
- 用户问某张保单的条款责任、免责、等待期是否影响理赔时，先从保单拿到 product_id，再调用 query_product_clause。
- 必须根据工具结果回答，不要编造保单号、金额或审核结论。没有记录就如实说明。
- 条款事实必须紧跟引用标记，例如：等待期内出险可能无法获赔。[ref-001]
- 回答简短、准确，引导用户补充保单号或案件号以便精确查询。
- 涉及复杂争议、投诉或无法判断的案件，建议用户转人工。
"""


def init_claim_advisor():
    """初始化理赔咨询子Agent"""

    model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="deepseek",
        api_key=settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}},
    )
    agent = create_agent(
        model=model,
        tools=[
            query_user_policies,
            query_claim_progress,
            query_claim_guide,
            query_product_clause,
        ],
        system_prompt=SYSTEM_PROMPT,
        context_schema=InsuranceAgentContext,
        checkpointer=True,
    )
    logger.info("理赔顾问子Agent初始化完成")
    return agent
