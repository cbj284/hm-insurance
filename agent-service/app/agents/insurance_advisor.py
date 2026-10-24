from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from app.agents.schemas import InsuranceAgentContext
from app.agents.tools import (
    query_candidate_products,
    query_product_clause,
    save_insurance_plan,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """
你是“安心保”的智能保险顾问。你可以帮助用户推荐保险，回答用户保险条款问题。
- 当信息不足时，应先询问用户基本信息，形成用户画像。
- 然后查询候选产品，根据用户画像，推荐合适的保险组合，与用户确认后，调用工具保存方案。
- 用户用简称、别名或只说「达尔文」「达尔文12」等询问条款时：不要先向用户要产品ID。必须先调用 query_candidate_products（重疾险用 critical_illness）查出候选，把名称最接近的产品视为目标，再用其 id 调用 query_product_clause。
- 用户询问保险产品的条款问题时，调用query_product_clause查询对应产品的保险条款，再根据检索结果回答。
- 你的回答必须是基于检索到的保险条款，不要编造保险条款中没有的信息。如果没有相关条款，如实告知用户。
- 回答中的每个事实陈述必须紧跟[source_id]的引用标记。例如：这款产品的等待期为180天。[ref-001]
- 回答要简短、精确，不要长篇大论。
"""


def init_insurance_advisor():
    """初始化保险咨询与推荐子Agent"""

    model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="deepseek",
        api_key=settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}},
    )
    agent = create_agent(
        model=model,
        tools=[
            query_candidate_products,
            query_product_clause,
            save_insurance_plan,
        ],
        system_prompt=SYSTEM_PROMPT,
        context_schema=InsuranceAgentContext,
        checkpointer=True,
    )
    logger.info("保险顾问子Agent初始化完成")
    return agent
